# SQLGlot Integration Guide

This project uses **SQLGlot** for optional SQL validation, formatting, and transpilation. SQLGlot is already in `requirements.txt`.

## What is SQLGlot?

SQLGlot is a Python SQL parser and transpiler that:
- Parses SQL into an AST (Abstract Syntax Tree)
- Validates SQL syntax across multiple dialects
- Transpiles SQL between dialects (e.g., `tsql` → `snowflake`)
- Formats and pretty-prints SQL
- Extracts metadata (tables, columns, types, etc.)

**Installation:**
```bash
pip install sqlglot
```

## Using SQLGlot in This Project

### 1. Helper Module (`sqlglot_helpers.py`)

A new module providing utilities:

```python
from sqlglot_helpers import (
    validate_sql,           # Check if SQL is syntactically valid
    format_sql,             # Pretty-print SQL
    extract_table_info,     # Get table/column metadata
    transpile_tsql_to_snowflake,  # Direct SQL Server → Snowflake
    normalize_identifiers,  # Quote reserved words
    get_sql_type_info,      # Extract data types
)
```

### 2. Examples

#### Validate SQL
```python
from sqlglot_helpers import validate_sql

sql = "CREATE TABLE Customers (ID INT, Name VARCHAR(100));"
is_valid, error = validate_sql(sql, dialect="tsql")
if is_valid:
    print("✓ SQL is valid")
else:
    print(f"✗ Error: {error}")
```

#### Format SQL
```python
from sqlglot_helpers import format_sql

sql = "CREATE TABLE Customers (ID INT, Name VARCHAR(100));"
formatted = format_sql(sql, dialect="snowflake", pretty=True)
print(formatted)
# Output:
# CREATE TABLE Customers (
#   ID INT,
#   Name VARCHAR(100)
# )
```

#### Extract Table Info
```python
from sqlglot_helpers import extract_table_info

sql = """
CREATE TABLE dbo.Customers (
    CustomerID INT IDENTITY(1,1) NOT NULL,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(255)
);
"""
info = extract_table_info(sql)
# Output:
# [
#   {
#     'table_name': 'Customers',
#     'columns': [
#       {'name': 'CustomerID', 'data_type': 'INT', 'nullable': False},
#       {'name': 'Name', 'data_type': 'VARCHAR(100)', 'nullable': False},
#       {'name': 'Email', 'data_type': 'VARCHAR(255)', 'nullable': True}
#     ]
#   }
# ]
```

#### Get Data Types Used
```python
from sqlglot_helpers import get_sql_type_info

sql = "CREATE TABLE Orders (ID INT, Amount DECIMAL(10,2), Name VARCHAR(100));"
types = get_sql_type_info(sql)
print(types['types'])
# Output: ['DECIMAL(10,2)', 'INT', 'VARCHAR(100)']
```

### 3. Integration in Streamlit UI

The `streamlit_app.py` already includes optional SQLGlot formatting:

```python
if enable_sqlglot:
    if SQLGLOT_AVAILABLE:
        st.subheader("SQLGlot Normalize")
        normalized = normalize_identifiers(res.snowflake_ddl)
        st.code(normalized, language="sql")
```

Users can enable the "SQLGlot normalization" checkbox to see pretty-printed output.

### 4. Integration in Core Converter

`converter.py` now optionally imports SQLGlot helpers. You can enhance the conversion with pre-validation:

```python
# In converter.py's convert() function
if SQLGLOT_AVAILABLE:
    is_valid, error = sqlglot_validate(sql_text, dialect="tsql")
    if not is_valid:
        result.add_review(f"SQLGlot validation warning: {error}")
```

## Use Cases

| Use Case | Function | Example |
|----------|----------|---------|
| **Validate input** | `validate_sql()` | Check user SQL before conversion |
| **Pre-conversion formatting** | `format_sql()` | Normalize input DDL |
| **Type audit** | `get_sql_type_info()` | Find all data types used |
| **Metadata extraction** | `extract_table_info()` | Build a schema catalog |
| **Direct transpile** | `transpile_tsql_to_snowflake()` | Quick (but basic) SQL Server → Snowflake |
| **Identifier normalization** | `normalize_identifiers()` | Quote reserved words automatically |

## Comparison: SQLGlot vs. This Project's Converter

| Feature | SQLGlot | DDL Converter |
|---------|---------|---------------|
| **Scope** | Generic SQL transpilation | Rules-driven, manual-review-aware |
| **Accuracy** | Good for simple cases | Handles complex edge cases + rule overrides |
| **Manual review** | No | ✓ Flags ambiguous conversions |
| **Type mappings** | Generic defaults | Configurable via `rules.json` |
| **Function mappings** | Built-in | Extensible via `rules.json` |
| **Unknown types** | Passes through silently | Flags for review + explains why |
| **Constraint handling** | Basic | Rules-based, respects platform differences |

**Recommendation:**
- Use **SQLGlot** for quick, simple conversions & formatting
- Use **DDL Converter** for production migrations that need explicit manual-review flagging

## Advanced: Extending SQLGlot Helpers

Add custom logic to `sqlglot_helpers.py` for your use case. Examples:

```python
def find_unsupported_functions(sql_text: str) -> List[str]:
    """Find SQL Server-specific functions in DDL."""
    parsed = parse_one(sql_text, dialect="tsql")
    functions = []
    for func in parsed.find_all(sqlglot.exp.Func):
        functions.append(func.name)
    return list(set(functions))

def add_column_comments(sql_text: str, comments: Dict[str, str]) -> str:
    """Add inline comments to column definitions."""
    # Parse, find columns, add comments
    pass
```

## Troubleshooting

**SQLGlot not working?**
- Check installation: `pip install sqlglot`
- Verify import: `python -c "import sqlglot; print(sqlglot.__version__)"`

**Transpilation seems wrong?**
- Remember: SQLGlot's transpile is generic. For production, use the full `converter.py` with `rules.json`.
- SQLGlot may not handle SQL Server-specific constructs perfectly (e.g., `IDENTITY(1,1)` syntax).

## Resources

- **SQLGlot GitHub:** https://github.com/tobymao/sqlglot
- **SQLGlot Docs:** https://sqlglot.com/
- **Dialects:** SQLGlot supports 20+ SQL dialects (tsql, snowflake, postgres, mysql, etc.)

## Next Steps

1. Use `sqlglot_helpers.py` for validation in the Streamlit app
2. Extend `rules.json` with more type mappings (SQLGlot can help audit what types are used)
3. Build a schema discovery tool using `extract_table_info()`
4. Add pre-conversion normalization step to the CLI
