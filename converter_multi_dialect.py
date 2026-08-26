"""
Multi-dialect SQL DDL conversion engine.

Supports conversion FROM: SQL Server, MySQL, Oracle, PostgreSQL, DB2, SAP HANA
Supports conversion TO: Any of the above + Snowflake

Uses rules_multi_dialect.json for all mappings.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

# Optional SQLGlot import
try:
    from sqlglot_helpers import validate_sql as sqlglot_validate
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules_multi_dialect.json")
with open(RULES_PATH, "r") as f:
    RULES = json.load(f)

SUPPORTED_DIALECTS = RULES.get("metadata", {}).get("supported_dialects", [])


@dataclass
class ConversionResult:
    """Result of DDL conversion."""
    snowflake_ddl: str = ""
    converted_ddl: str = ""  # For multi-dialect, use this instead of snowflake_ddl
    transformations: List[str] = field(default_factory=list)
    manual_review: List[str] = field(default_factory=list)
    source_dialect: str = ""
    target_dialect: str = ""

    def add_transform(self, msg: str):
        self.transformations.append(msg)

    def add_review(self, msg: str):
        self.manual_review.append(msg)


def convert(
    sql_text: str,
    source_dialect: str = "tsql",
    target_dialect: str = "snowflake"
) -> ConversionResult:
    """
    Convert DDL from one SQL dialect to another.

    Args:
        sql_text: Source SQL DDL
        source_dialect: Source dialect (tsql, mysql, oracle, postgresql, db2, hana, snowflake)
        target_dialect: Target dialect (same options)

    Returns:
        ConversionResult with converted DDL, transformations, and manual-review items
    """
    result = ConversionResult(
        source_dialect=source_dialect,
        target_dialect=target_dialect
    )

    if source_dialect not in SUPPORTED_DIALECTS:
        result.add_review(f"Source dialect '{source_dialect}' not supported. Supported: {', '.join(SUPPORTED_DIALECTS)}")
        result.converted_ddl = sql_text
        return result

    if target_dialect not in SUPPORTED_DIALECTS:
        result.add_review(f"Target dialect '{target_dialect}' not supported. Supported: {', '.join(SUPPORTED_DIALECTS)}")
        result.converted_ddl = sql_text
        return result

    # Optional pre-validation with SQLGlot
    if SQLGLOT_AVAILABLE:
        is_valid, error = sqlglot_validate(sql_text, dialect=source_dialect)
        if not is_valid:
            result.add_review(f"SQLGlot validation warning for {source_dialect}: {error}")

    # If source == target, no conversion needed
    if source_dialect == target_dialect:
        result.converted_ddl = sql_text
        result.add_transform(f"No conversion: source and target dialects are both {source_dialect}")
        return result

    # Parse and convert CREATE TABLE statements
    result.converted_ddl = _convert_create_table(
        sql_text,
        source_dialect,
        target_dialect,
        result
    )

    # Set snowflake_ddl for backward compatibility
    if target_dialect == "snowflake":
        result.snowflake_ddl = result.converted_ddl

    return result


def _convert_create_table(
    sql_text: str,
    source_dialect: str,
    target_dialect: str,
    result: ConversionResult
) -> str:
    """Convert CREATE TABLE statements from source to target dialect."""
    
    # Find all CREATE TABLE ... (...); statements
    pattern = r"CREATE\s+TABLE\s+(\w+(?:\.\w+)?)\s*\((.*?)\)\s*(?:;|GO|$)"
    matches = re.finditer(pattern, sql_text, re.IGNORECASE | re.DOTALL)

    converted_statements = []
    for match in matches:
        table_name = match.group(1)
        columns_text = match.group(2)

        # Strip schema prefix if needed
        schema_strip_list = RULES.get("schema_handling", {}).get(source_dialect, {}).get("strip_schemas", [])
        if "." in table_name:
            schema, tbl = table_name.rsplit(".", 1)
            if schema.upper() in [s.upper() for s in schema_strip_list]:
                table_name = tbl
                result.add_transform(f"Dropped schema prefix '{schema}.' from table '{tbl}'")

        # Parse columns and constraints
        columns_parts = _split_columns(columns_text)
        converted_columns = []

        for part in columns_parts:
            part = part.strip()
            if not part:
                continue

            if part.upper().startswith("CONSTRAINT "):
                # Table-level constraint
                converted_constraint = _convert_constraint(part, source_dialect, target_dialect, result)
                if converted_constraint:
                    converted_columns.append(converted_constraint)
            elif part.upper().startswith(("PRIMARY KEY", "UNIQUE", "CHECK", "FOREIGN KEY", "INDEX")):
                # Table-level constraint
                converted_constraint = _convert_constraint(part, source_dialect, target_dialect, result)
                if converted_constraint:
                    converted_columns.append(converted_constraint)
            else:
                # Column definition
                converted_col = _convert_column(part, source_dialect, target_dialect, result)
                if converted_col:
                    converted_columns.append(converted_col)

        # Build converted CREATE TABLE
        converted_stmt = f"CREATE TABLE {table_name} (\n"
        converted_stmt += ",\n".join(converted_columns)
        converted_stmt += "\n);"

        converted_statements.append(converted_stmt)

    # If no CREATE TABLE found, return original
    if not converted_statements:
        return sql_text

    return "\n\nGO\n\n".join(converted_statements) if len(converted_statements) > 1 else converted_statements[0]


def _convert_column(
    col_def: str,
    source_dialect: str,
    target_dialect: str,
    result: ConversionResult
) -> str:
    """Convert a single column definition."""
    col_def = col_def.strip()
    
    # Extract column name and type
    match = re.match(r"(\[?\w+\]?)\s+(.+)", col_def, re.IGNORECASE)
    if not match:
        return col_def

    col_name = match.group(1)
    type_and_rest = match.group(2)

    # Extract data type — support multi-word base types (e.g. "DOUBLE PRECISION", "TIMESTAMP WITH TIME ZONE")
    s = type_and_rest.strip()
    base_type = None
    type_args = None
    rest = ""

    # Try to match the longest type name present in RULES.type_mappings
    type_keys = list(RULES.get("type_mappings", {}).keys())
    # sort by length (characters) to match multi-word keys first
    type_keys_sorted = sorted(type_keys, key=lambda k: len(k), reverse=True)
    s_upper = s.upper()
    for key in type_keys_sorted:
        if s_upper.startswith(key):
            # found a matching base type; extract optional args and remainder
            m = re.match(r"(?i)" + re.escape(key) + r"(?:\s*\(([^)]+)\))?(.*)", s)
            if m:
                base_type = key
                type_args = m.group(1)
                rest = m.group(2) or ""
                break

    # Fallback: single-word type extraction
    if not base_type:
        type_match = re.match(r"(\w+)(?:\s*\(([^)]+)\))?(.*)", s, re.IGNORECASE)
        if not type_match:
            return col_def
        base_type = type_match.group(1).upper()
        type_args = type_match.group(2)
        rest = type_match.group(3)

    # Special-case: MySQL uses TINYINT(1) as boolean in many schemas
    if source_dialect == "mysql" and base_type == "TINYINT" and type_args:
        # normalize args like '1' or '1 unsigned' -> treat as boolean when width==1
        arg_norm = re.sub(r"\s+", "", type_args)
        if arg_norm.split(',')[0] == '1':
            base_type = "BOOLEAN"
            type_args = None

    # Look up type mapping
    type_mapping = RULES.get("type_mappings", {}).get(base_type, {})
    if not type_mapping:
        result.add_review(f"No type mapping found for '{base_type}'; left unchanged")
        converted_type = base_type
    else:
        target_info = type_mapping.get(target_dialect, {})
        if target_info.get("target") is None:
            result.add_review(f"Type '{base_type}' has no equivalent in {target_dialect}; left unchanged. Reason: {target_info.get('review', 'Unknown')}")
            converted_type = base_type
            if type_args:
                converted_type += f"({type_args})"
        else:
            converted_type = target_info.get("target", base_type)
            if target_info.get("fixed_args"):
                converted_type += f"({target_info['fixed_args']})"
            elif target_info.get("carry_args") and type_args:
                converted_type += f"({type_args})"
            if target_info.get("review"):
                result.add_review(f"Column '{col_name}' type '{base_type}': {target_info['review']}")

    # Convert identity syntax
    rest = _convert_identity_syntax(rest, source_dialect, target_dialect, result)

    # Convert DEFAULT expressions
    rest = _convert_default_expressions(rest, source_dialect, target_dialect, result)

    return f"    {col_name} {converted_type}{rest}"


def _convert_constraint(
    constraint_def: str,
    source_dialect: str,
    target_dialect: str,
    result: ConversionResult
) -> str:
    """Convert a table-level constraint."""
    # For now, pass through with minimal changes
    constraint_def = constraint_def.strip()

    # Remove CLUSTERED/NONCLUSTERED hints
    if "CLUSTERED" in constraint_def.upper():
        constraint_def = re.sub(r"\bCLUSTERED\b|\bNONCLUSTERED\b", "", constraint_def, flags=re.IGNORECASE)
        result.add_transform(f"Removed CLUSTERED/NONCLUSTERED hint from constraint")

    # Remove unsupported constraint options (e.g., ON DELETE CASCADE for Snowflake)
    if target_dialect == "snowflake" and ("ON DELETE" in constraint_def.upper() or "ON UPDATE" in constraint_def.upper()):
        constraint_def = re.sub(r"\s+ON\s+(DELETE|UPDATE)\s+\S+", "", constraint_def, flags=re.IGNORECASE)
        result.add_transform(f"Removed ON DELETE/UPDATE clause (not supported in {target_dialect})")

    # Flag manual review for certain constraints
    if "PRIMARY KEY" in constraint_def.upper():
        result.add_review(f"PRIMARY KEY constraint in {target_dialect}: enforcement varies by database")
    elif "FOREIGN KEY" in constraint_def.upper():
        result.add_review(f"FOREIGN KEY constraint in {target_dialect}: enforcement varies by database")

    return constraint_def


def _convert_identity_syntax(
    rest: str,
    source_dialect: str,
    target_dialect: str,
    result: ConversionResult
) -> str:
    """Convert IDENTITY/AUTO_INCREMENT/SEQUENCE syntax."""
    identity_rules = RULES.get("identity_syntax", {})
    
    source_rules = identity_rules.get(source_dialect, {})
    target_rules = identity_rules.get(target_dialect, {})

    if not source_rules or not target_rules:
        return rest

    # Find and replace identity syntax
    pattern = source_rules.get("pattern", "")
    if pattern and re.search(pattern, rest, re.IGNORECASE):
        match = re.search(pattern, rest, re.IGNORECASE)
        if match:
            seed, increment = 1, 1
            if match.groups():
                try:
                    seed = int(match.group(1))
                    increment = int(match.group(2))
                except:
                    pass
            
            template = target_rules.get("template", "")
            if template and "{seed}" in template:
                replacement = template.format(seed=seed, increment=increment)
            elif template:
                replacement = template
            else:
                replacement = ""

            rest = re.sub(pattern, replacement, rest, flags=re.IGNORECASE)
            result.add_transform(f"Converted IDENTITY/AUTO_INCREMENT syntax from {source_dialect} to {target_dialect}")

    return rest


def _convert_default_expressions(
    rest: str,
    source_dialect: str,
    target_dialect: str,
    result: ConversionResult
) -> str:
    """Convert DEFAULT expressions and functions."""
    function_mappings = RULES.get("function_mappings", {})
    
    for func_name, func_defs in function_mappings.items():
        # Skip non-dict entries (like "_comment")
        if not isinstance(func_defs, dict):
            continue
            
        source_func = func_defs.get(source_dialect)
        target_func = func_defs.get(target_dialect)
        
        if source_func and target_func and isinstance(source_func, dict) and isinstance(target_func, dict):
            pattern = func_name + r"\s*\("
            if re.search(pattern, rest, re.IGNORECASE):
                replacement_text = target_func.get("replacement", "")
                if replacement_text:
                    rest = re.sub(pattern, replacement_text, rest, flags=re.IGNORECASE)
                    result.add_transform(f"Converted function '{func_name}()' to '{replacement_text}'")
                if target_func.get("review"):
                    result.add_review(target_func["review"])

    return rest


def _split_columns(columns_text: str) -> List[str]:
    """Split column/constraint definitions on top-level commas only."""
    parts = []
    current = []
    depth = 0
    in_string = False
    string_char = None

    for char in columns_text:
        if in_string:
            if char == string_char and (len(current) == 0 or current[-1] != "\\"):
                in_string = False
            current.append(char)
        elif char in ("'", '"'):
            in_string = True
            string_char = char
            current.append(char)
        elif char in ("(", "["):
            depth += 1
            current.append(char)
        elif char in (")", "]"):
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current))

    return parts


if __name__ == "__main__":
    # Example usage
    sample_tsql = """
    CREATE TABLE dbo.Customers (
        CustomerID INT IDENTITY(1,1) NOT NULL,
        Name VARCHAR(100) NOT NULL,
        Email VARCHAR(255),
        CONSTRAINT PK_Customers PRIMARY KEY (CustomerID)
    );
    """

    print("=== SQL Server → PostgreSQL ===")
    result = convert(sample_tsql, source_dialect="tsql", target_dialect="postgresql")
    print(result.converted_ddl)
    print(f"\nTransformations: {result.transformations}")
    print(f"Manual Review: {result.manual_review}\n")

    print("=== SQL Server → MySQL ===")
    result = convert(sample_tsql, source_dialect="tsql", target_dialect="mysql")
    print(result.converted_ddl)
    print(f"\nTransformations: {result.transformations}")
    print(f"Manual Review: {result.manual_review}\n")

    print("=== SQL Server → Snowflake ===")
    result = convert(sample_tsql, source_dialect="tsql", target_dialect="snowflake")
    print(result.converted_ddl)
    print(f"\nTransformations: {result.transformations}")
    print(f"Manual Review: {result.manual_review}")
