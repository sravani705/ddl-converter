"""
SQLGlot integration helpers for DDL conversion.

Provides utilities for:
- Validating SQL syntax
- Parsing and inspecting SQL structure
- Formatting and normalizing SQL
- Transpiling between dialects
"""

from typing import Optional, List, Dict, Any
import sqlglot
from sqlglot import parse_one, transpile
from sqlglot.expressions import Table, Column, DataType


def validate_sql(sql_text: str, dialect: str = "tsql") -> tuple[bool, Optional[str]]:
    """
    Validate SQL syntax using sqlglot.
    
    Args:
        sql_text: SQL code to validate
        dialect: SQL dialect ("tsql" for SQL Server, "snowflake" for Snowflake)
    
    Returns:
        (is_valid, error_message)
    """
    try:
        parse_one(sql_text, dialect=dialect)
        return (True, None)
    except Exception as e:
        return (False, str(e))


def format_sql(sql_text: str, dialect: str = "snowflake", pretty: bool = True) -> str:
    """
    Format/pretty-print SQL using sqlglot.
    
    Args:
        sql_text: SQL to format
        dialect: Target SQL dialect
        pretty: Whether to use pretty-printing (line breaks, indentation)
    
    Returns:
        Formatted SQL string
    """
    try:
        parsed = parse_one(sql_text, dialect="tsql")
        formatted = parsed.sql(dialect=dialect, pretty=pretty)
        return formatted
    except Exception as e:
        return f"-- Format error: {e}\n{sql_text}"


def extract_table_info(sql_text: str) -> List[Dict[str, Any]]:
    """
    Extract table name, columns, and data types from CREATE TABLE statement.
    
    Returns a list of dicts with:
    - table_name: str
    - columns: List[Dict] with 'name', 'data_type', 'nullable'
    """
    try:
        parsed = parse_one(sql_text, dialect="tsql")
        
        if not isinstance(parsed, sqlglot.exp.Create):
            return []
        
        results = []
        table = parsed.this
        
        if isinstance(table, (sqlglot.exp.Table, sqlglot.exp.Schema)):
            table_name = table.name if hasattr(table, 'name') else str(table)
            
            columns = []
            # Extract column definitions from table schema
            if hasattr(table, 'expressions'):
                for expr in table.expressions:
                    if isinstance(expr, sqlglot.exp.ColumnDef):
                        col_info = {
                            'name': expr.name,
                            'data_type': str(expr.kind),
                            'nullable': not expr.constraints or any(
                                c.kind != 'NOT NULL' for c in expr.constraints
                            ) if expr.constraints else True,
                        }
                        columns.append(col_info)
            
            results.append({
                'table_name': table_name,
                'columns': columns,
            })
        
        return results
    except Exception as e:
        return []


def transpile_tsql_to_snowflake(sql_text: str) -> str:
    """
    Transpile SQL Server DDL to Snowflake using sqlglot.
    
    Note: This is a basic transpilation. For production use, combine with converter.py
    for rule-based conversions and manual-review flagging.
    
    Returns:
        Transpiled SQL string
    """
    try:
        result = transpile(sql_text, read="tsql", write="snowflake")
        return result[0] if result else sql_text
    except Exception as e:
        return f"-- Transpilation error: {e}\n{sql_text}"


def normalize_identifiers(sql_text: str, quote_all: bool = False) -> str:
    """
    Normalize identifiers (table/column names) in SQL.
    
    Args:
        sql_text: SQL to normalize
        quote_all: If True, quote all identifiers; if False, only quote reserved words
    
    Returns:
        SQL with normalized identifiers
    """
    try:
        parsed = parse_one(sql_text, dialect="tsql")
        
        if quote_all:
            # Quote all identifiers
            for identifier in parsed.find_all(sqlglot.exp.Identifier):
                identifier.quoted = True
        
        normalized = parsed.sql(dialect="snowflake")
        return normalized
    except Exception as e:
        return f"-- Normalization error: {e}\n{sql_text}"


def get_sql_type_info(sql_text: str) -> Dict[str, List[str]]:
    """
    Extract data types used in a SQL statement.
    
    Returns:
        Dict with keys: 'types' (list of unique types found)
    """
    try:
        parsed = parse_one(sql_text, dialect="tsql")
        types = set()
        
        for dtype in parsed.find_all(sqlglot.exp.DataType):
            types.add(str(dtype))
        
        return {'types': sorted(list(types))}
    except Exception as e:
        return {'types': [], 'error': str(e)}


# Example usage
if __name__ == "__main__":
    sample_sql = """
    CREATE TABLE dbo.Customer (
        CustomerID INT IDENTITY(1,1) NOT NULL,
        CustomerName VARCHAR(100) NOT NULL,
        Email VARCHAR(255),
        CONSTRAINT PK_Customer PRIMARY KEY (CustomerID)
    );
    """
    
    print("=== Validation ===")
    is_valid, error = validate_sql(sample_sql)
    print(f"Valid: {is_valid}")
    if error:
        print(f"Error: {error}")
    
    print("\n=== Formatted SQL ===")
    formatted = format_sql(sample_sql)
    print(formatted)
    
    print("\n=== Type Info ===")
    types = get_sql_type_info(sample_sql)
    print(f"Types found: {types['types']}")
    
    print("\n=== Transpile (sqlglot only) ===")
    transpiled = transpile_tsql_to_snowflake(sample_sql)
    print(transpiled)
