# Multi-Dialect DDL Conversion Guide

This project now supports **multi-dialect SQL DDL conversion**, allowing you to convert between **6 major SQL databases**:

- **SQL Server** (`tsql`)
- **MySQL** (`mysql`)
- **Oracle** (`oracle`)
- **PostgreSQL** (`postgresql`)
- **IBM DB2** (`db2`)
- **SAP HANA** (`hana`)
- **Snowflake** (`snowflake`)

## Quick Start

### Using the Python API

```python
from converter_multi_dialect import convert

# Convert SQL Server to PostgreSQL
result = convert(
    sql_text="""
    CREATE TABLE dbo.Customers (
        CustomerID INT IDENTITY(1,1) NOT NULL,
        Name VARCHAR(100) NOT NULL,
        CONSTRAINT PK_Customers PRIMARY KEY (CustomerID)
    );
    """,
    source_dialect="tsql",
    target_dialect="postgresql"
)

print(result.converted_ddl)
print(f"Transformations: {result.transformations}")
print(f"Manual Review: {result.manual_review}")
```

### Using the CLI (with updated cli.py)

```bash
# Convert SQL Server file to PostgreSQL
python cli_multi_dialect.py input.sql --source tsql --target postgresql -o output.sql

# Convert MySQL file to Oracle
python cli_multi_dialect.py input.sql --source mysql --target oracle

# List supported dialects
python cli_multi_dialect.py --list-dialects
```

## Supported Conversions

All conversions are **bidirectional**. Examples:

| From | To | Example |
|------|----|---------| 
| SQL Server | PostgreSQL | `INT IDENTITY(1,1)` → `INTEGER SERIAL` |
| MySQL | Oracle | `AUTO_INCREMENT` → Sequence-based |
| Oracle | Snowflake | `NUMBER(10,2)` → `NUMBER(10,2)` |
| PostgreSQL | SQL Server | `SERIAL` → `INT IDENTITY(1,1)` |
| DB2 | MySQL | `GENERATED ALWAYS AS IDENTITY` → `AUTO_INCREMENT` |
| HANA | Oracle | Type mappings per `rules_multi_dialect.json` |

## Type Mappings

The `rules_multi_dialect.json` file defines type conversions for all dialect pairs. Examples:

### INT (Integer)
- SQL Server: `INT`
- MySQL: `INT`
- Oracle: `NUMBER(10,0)`
- PostgreSQL: `INTEGER`
- DB2: `INTEGER`
- HANA: `INTEGER`
- Snowflake: `INTEGER`

### VARCHAR (Text)
- SQL Server: `VARCHAR` (with `carry_args`)
- MySQL: `VARCHAR`
- Oracle: `VARCHAR2` (with `carry_args`)
- PostgreSQL: `VARCHAR`
- DB2: `VARCHAR`
- HANA: `VARCHAR`
- Snowflake: `VARCHAR`

### BIT (Boolean)
- SQL Server: `BIT`
- MySQL: `BIT`
- Oracle: `NUMBER(1,0)` (with review note)
- PostgreSQL: `BOOLEAN`
- DB2: `SMALLINT` (with review note)
- HANA: `BOOLEAN`
- Snowflake: `BOOLEAN`

### IDENTITY / AUTO_INCREMENT / SEQUENCE

Each database has different auto-increment syntax:

| Database | Syntax | Example |
|----------|--------|---------|
| SQL Server | `IDENTITY(seed,increment)` | `INT IDENTITY(1,1)` |
| MySQL | `AUTO_INCREMENT` | `INT AUTO_INCREMENT` |
| Oracle | `SEQUENCE` (separate object) | Requires `CREATE SEQUENCE` |
| PostgreSQL | `SERIAL` / `BIGSERIAL` | `SERIAL PRIMARY KEY` |
| DB2 | `GENERATED ALWAYS AS IDENTITY` | `INT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1)` |
| HANA | Configuration-based | Handled via table options |
| Snowflake | `AUTOINCREMENT` | `INT AUTOINCREMENT START 1 INCREMENT 1` |

**Converter behavior:** Automatically converts between these syntaxes based on source and target dialects.

### Functions

Common functions mapped across dialects:

| Function | SQL Server | MySQL | Oracle | PostgreSQL | DB2 | HANA | Snowflake |
|----------|-----------|-------|--------|------------|-----|------|-----------|
| Current Date/Time | `GETDATE()` | `NOW()` | `SYSDATE` | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP()` |
| UTC Time | `GETUTCDATE()` | `UTC_TIMESTAMP()` | `SYS_EXTRACT_UTC(SYSTIMESTAMP)` | `CURRENT_TIMESTAMP AT TIME ZONE 'UTC'` | `CURRENT_TIMESTAMP` | `CURRENT_TIMESTAMP` | `CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())` |
| Coalesce NULL | `ISNULL(a, b)` | `IFNULL(a, b)` | `NVL(a, b)` | `COALESCE(a, b)` | `COALESCE(a, b)` | `COALESCE(a, b)` | `COALESCE(a, b)` |
| UUID/GUID | `NEWID()` | `UUID()` | `DBMS_RANDOM.VALUE()` | `gen_random_uuid()` | `GENERATE_UNIQUE()` | `SYSUUID` | `UUID_STRING()` |

## Default Values

BIT literal defaults vary by target dialect:

| Value | SQL Server | MySQL | Oracle | PostgreSQL | DB2 | HANA | Snowflake |
|-------|-----------|-------|--------|------------|-----|------|-----------|
| False | `0` | `FALSE` | `0` | `false` | `0` | `false` | `FALSE` |
| True | `1` | `TRUE` | `1` | `true` | `1` | `true` | `TRUE` |

## Schema Handling

Each database has default schemas that may be stripped:

| Database | Default/System Schemas Stripped |
|----------|----------------------------------|
| SQL Server | `dbo`, `sys` |
| MySQL | `mysql`, `information_schema`, `performance_schema` |
| Oracle | `SYS`, `SYSTEM` |
| PostgreSQL | `pg_catalog`, `information_schema`, `public` |
| DB2 | `SYSCAT`, `SYSFUN`, `SYSIBM` |
| HANA | `SYS`, `CATALOG` |
| Snowflake | (none) |

**Behavior:** If a table is in one of these default schemas, the schema prefix is dropped.

## Reserved Words

Each database has a reserved word list. Identifiers colliding with reserved words in the target dialect are automatically double-quoted.

**Example:**
- SQL Server: `[Order]` (quoted with brackets)
- Snowflake: `"Order"` (quoted with double-quotes; also a reserved word in Snowflake)

## Constraints

The converter handles:

- **PRIMARY KEY** — Syntax varies; enforcement varies by database
- **FOREIGN KEY** — Syntax converted; enforcement not guaranteed
- **UNIQUE** — Syntax converted; enforcement varies
- **CHECK** — Syntax converted; Snowflake does not enforce

**Manual Review Notes:** Each constraint is flagged with database-specific enforcement caveats.

## Unsupported Types

Some types have **no equivalent** in certain target databases:

| Type | Status | Recommendation |
|------|--------|-----------------|
| `HIERARCHYID` | Unsupported (all) | Re-model as materialized path or adjacency-list |
| `ROWVERSION` / `TIMESTAMP` | Unsupported (all) | Use manual timestamps, CDC, or database-specific tracking |
| `UNIQUEIDENTIFIER` (SQL Server) | Mapped to VARCHAR(36) | Loses native UUID generation; implement manually |
| `XML` | Varies | Oracle: XMLTYPE; MySQL: LONGTEXT; Snowflake: VARIANT |
| `GEOGRAPHY` / `GEOMETRY` | Varies | Each database has different spatial semantics |

## Example Conversions

### SQL Server → PostgreSQL

```sql
-- Input (SQL Server)
CREATE TABLE dbo.Employees (
    EmployeeID INT IDENTITY(1,1) NOT NULL,
    FirstName VARCHAR(50) NOT NULL,
    HireDate DATETIME DEFAULT GETDATE(),
    CONSTRAINT PK_Employees PRIMARY KEY (EmployeeID)
);

-- Output (PostgreSQL)
CREATE TABLE Employees (
    EmployeeID INTEGER SERIAL NOT NULL,
    FirstName VARCHAR(50) NOT NULL,
    HireDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT PK_Employees PRIMARY KEY (EmployeeID)
);

-- Transformations:
-- - Dropped schema prefix 'dbo.'
-- - Converted IDENTITY to SERIAL
-- - Converted DATETIME to TIMESTAMP
-- - Converted GETDATE() to CURRENT_TIMESTAMP
```

### MySQL → Oracle

```sql
-- Input (MySQL)
CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    balance DECIMAL(10,2) DEFAULT 0.00
);

-- Output (Oracle)
CREATE TABLE customers (
    customer_id NUMBER(10,0),
    email VARCHAR2(255) NOT NULL,
    balance NUMBER(10,2) DEFAULT 0.00,
    PRIMARY KEY (customer_id)
);
-- Note: AUTO_INCREMENT not directly supported; requires SEQUENCE + trigger
```

### Oracle → Snowflake

```sql
-- Input (Oracle)
CREATE TABLE employees (
    emp_id NUMBER(10,0) NOT NULL,
    name VARCHAR2(100),
    salary NUMBER(10,2),
    PRIMARY KEY (emp_id)
);

-- Output (Snowflake)
CREATE TABLE employees (
    emp_id NUMBER(10,0) NOT NULL,
    name VARCHAR(100),
    salary NUMBER(10,2),
    PRIMARY KEY (emp_id)
);

-- Transformations:
-- - Converted VARCHAR2 to VARCHAR
```

## Manual Review Items

The converter flags items requiring manual review, such as:

1. **Type equivalence warnings** — When a mapping exists but behavior differs
   - Example: SQL Server `TINYINT` (unsigned 0-255) → Snowflake `SMALLINT` (signed)
2. **Missing implementations** — When no equivalent exists
   - Example: `ROWVERSION` → "Use manual timestamps or CDC"
3. **Database-specific constraints** — When enforcement varies
   - Example: PostgreSQL `FOREIGN KEY` → "Not enforced by default; implement application-level or via trigger"
4. **Timezone/locale considerations** — When behavior depends on session settings
   - Example: `GETUTCDATE()` on Snowflake depends on session `TIMEZONE` parameter

Always review these items before deploying to production.

## Configuration

### Creating Custom Dialect Rules

Edit `rules_multi_dialect.json` to add or modify mappings:

```json
{
  "type_mappings": {
    "MY_CUSTOM_TYPE": {
      "tsql": {"target": "TYPE_A"},
      "postgresql": {"target": "TYPE_B"},
      ...
    }
  },
  "function_mappings": {
    "MY_FUNCTION": {
      "tsql": {"replacement": "FUNC_A()"},
      "postgresql": {"replacement": "func_b()"},
      ...
    }
  }
}
```

### Adding a New SQL Dialect

1. Add dialect code to `metadata.supported_dialects` in `rules_multi_dialect.json`
2. Add type mappings for all types to the new dialect
3. Add function mappings for all functions
4. Add identity syntax rules
5. Add schema stripping rules
6. Update CLI to recognize the new dialect

## Files

| File | Purpose |
|------|---------|
| `rules_multi_dialect.json` | Centralized rules for all dialect conversions |
| `converter_multi_dialect.py` | Multi-dialect conversion engine |
| `cli_multi_dialect.py` | Command-line interface for multi-dialect conversion |
| `streamlit_multi_dialect.py` | Streamlit UI with dialect selectors (planned) |

## API Reference

### `convert(sql_text, source_dialect="tsql", target_dialect="snowflake")`

```python
from converter_multi_dialect import convert, SUPPORTED_DIALECTS

result = convert(
    sql_text="CREATE TABLE ...",
    source_dialect="tsql",
    target_dialect="postgresql"
)

print(result.converted_ddl)
print(result.transformations)
print(result.manual_review)
print(result.source_dialect)
print(result.target_dialect)
```

**Returns:** `ConversionResult` with:
- `converted_ddl` — Converted DDL
- `transformations` — List of changes made
- `manual_review` — List of items requiring human review
- `source_dialect` — Source dialect used
- `target_dialect` — Target dialect used

## Limitations & Future Work

1. **Parsed columns/indexes** — `CREATE INDEX`, `ALTER TABLE` not yet supported
2. **Dialect-specific DDL** — Window functions, CTEs, etc. not yet converted
3. **Views/Procedures** — Only `CREATE TABLE` currently supported
4. **Data type edge cases** — Some precise type behaviors may vary
5. **Performance optimization syntax** — `WITH`, `HINT`, etc. stripped but not re-emitted

## Troubleshooting

**"Unsupported dialect"** error:
- Check spelling: `tsql`, `mysql`, `oracle`, `postgresql`, `db2`, `hana`, `snowflake`
- Run `python cli_multi_dialect.py --list-dialects`

**"Type has no equivalent"** warning:
- Type is truly unsupported in target dialect
- Choose an alternative type and add custom rule to `rules_multi_dialect.json`

**Conversion looks wrong:**
- Review the `manual_review` items
- Check `rules_multi_dialect.json` for the specific type/function mapping
- Test with a small sample before running on production data

## Resources

- **rules_multi_dialect.json** — Source of truth for all mappings
- **Supported Dialects:** `tsql`, `mysql`, `oracle`, `postgresql`, `db2`, `hana`, `snowflake`
- **GitHub:** https://github.com/sravani705/ddl-converter
