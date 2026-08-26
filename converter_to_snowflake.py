"""
Specialized converter: Any SQL dialect → Snowflake DDL

Supports source dialects:
- SQL Server (tsql)
- MySQL (mysql)
- Oracle (oracle)
- PostgreSQL (postgresql)
- IBM DB2 (db2)
- SAP HANA (hana)

Target: Always Snowflake

Wraps converter_multi_dialect.py with Snowflake as fixed target.
"""

from converter_multi_dialect import convert as multi_dialect_convert, ConversionResult, SUPPORTED_DIALECTS
import re

TARGET_DIALECT = "snowflake"
VALID_SOURCE_DIALECTS = ["tsql", "mysql", "oracle", "postgresql", "db2", "hana"]


def convert_to_snowflake(sql_text: str, source_dialect: str = "tsql") -> ConversionResult:
    """
    Convert DDL from any supported SQL dialect to Snowflake.

    Args:
        sql_text: Source SQL DDL
        source_dialect: Source dialect code
                       - "tsql" for SQL Server
                       - "mysql" for MySQL
                       - "oracle" for Oracle
                       - "postgresql" for PostgreSQL
                       - "db2" for IBM DB2
                       - "hana" for SAP HANA

    Returns:
        ConversionResult with Snowflake DDL, transformations, and manual-review items
    """
    if source_dialect not in VALID_SOURCE_DIALECTS:
        result = ConversionResult(source_dialect=source_dialect, target_dialect=TARGET_DIALECT)
        result.add_review(
            f"Source dialect '{source_dialect}' not supported. "
            f"Valid options: {', '.join(VALID_SOURCE_DIALECTS)}"
        )
        result.converted_ddl = sql_text
        result.snowflake_ddl = sql_text
        return result

    # Use multi-dialect converter with Snowflake as target
    return multi_dialect_convert(
        sql_text,
        source_dialect=source_dialect,
        target_dialect=TARGET_DIALECT
    )


# Alias for backward compatibility
convert = convert_to_snowflake


if __name__ == "__main__":
    import sys

    # Example: test all source dialects
    test_sqls = {
        "tsql": """
        CREATE TABLE dbo.Customers (
            CustomerID INT IDENTITY(1,1) NOT NULL,
            Name VARCHAR(100) NOT NULL,
            Email VARCHAR(255),
            RegisteredDate DATETIME DEFAULT GETDATE(),
            CONSTRAINT PK_Customers PRIMARY KEY (CustomerID)
        );
        """,
        "mysql": """
        CREATE TABLE customers (
            customer_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            registered_date DATETIME DEFAULT NOW()
        );
        """,
        "oracle": """
        CREATE TABLE customers (
            customer_id NUMBER(10,0) NOT NULL,
            name VARCHAR2(100) NOT NULL,
            email VARCHAR2(255),
            registered_date DATE DEFAULT SYSDATE,
            PRIMARY KEY (customer_id)
        );
        """,
        "postgresql": """
        CREATE TABLE customers (
            customer_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "db2": """
        CREATE TABLE customers (
            customer_id INT GENERATED ALWAYS AS IDENTITY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255),
            registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (customer_id)
        );
        """,
        "hana": """
        CREATE TABLE customers (
            customer_id INTEGER NOT NULL PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            email NVARCHAR(255),
            registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    }

    print("=" * 80)
    print("MULTI-SOURCE TO SNOWFLAKE CONVERSION EXAMPLES")
    print("=" * 80)

    for source, sql in test_sqls.items():
        print(f"\n{'=' * 80}")
        print(f"SOURCE: {source.upper()}")
        print(f"{'=' * 80}")
        print(f"\nInput DDL:\n{sql.strip()}\n")

        result = convert_to_snowflake(sql, source_dialect=source)

        print(f"Output Snowflake DDL:\n{result.snowflake_ddl}\n")

        if result.transformations:
            print("Transformations:")
            for t in result.transformations:
                print(f"  - {t}")
        else:
            print("Transformations: (none)")

        # Only print manual-review items when converted DDL differs from input
        src = sql or ""
        tgt = result.snowflake_ddl or ""

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "")).strip()

        if _norm(tgt) != _norm(src):
            if result.manual_review:
                print("\nManual Review Items:")
                for m in result.manual_review:
                    print(f"  ! {m}")
            else:
                print("Manual Review Items: (none)")
