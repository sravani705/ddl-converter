"""
CLI for multi-source to Snowflake DDL conversion.

Usage:
    python cli.py input.sql                                    # Default: SQL Server → Snowflake
    python cli.py input.sql --source mysql                     # MySQL → Snowflake
    python cli.py input.sql --source oracle -o output.sql      # Oracle → Snowflake
    python cli.py --source postgresql input.sql                # PostgreSQL → Snowflake
    python cli.py --list-sources                               # Show all supported source dialects
    cat input.sql | python cli.py --source hana                # Pipe input with source dialect

Output always has three sections:
    1. Converted Snowflake DDL
    2. List of transformations made
    3. Any unsupported / ambiguous elements ("Manual review required")
"""
import argparse
import sys

from converter_to_snowflake import convert_to_snowflake


def main():
    ap = argparse.ArgumentParser(
        description="Convert SQL DDL from multiple sources (SQL Server, MySQL, Oracle, PostgreSQL, DB2, HANA) to Snowflake DDL."
    )
    ap.add_argument(
        "input",
        nargs="?",
        help="Path to a .sql file. Omit to read from stdin."
    )
    ap.add_argument(
        "-o", "--output",
        help="Write just the converted Snowflake DDL to this file."
    )
    ap.add_argument(
        "--source",
        default="tsql",
        choices=["tsql", "mysql", "oracle", "postgresql", "db2", "hana"],
        help="Source SQL dialect (default: tsql for SQL Server)."
    )
    ap.add_argument(
        "--list-sources",
        action="store_true",
        help="List all supported source dialects and exit."
    )
    args = ap.parse_args()

    # Handle --list-sources
    if args.list_sources:
        print("Supported Source Dialects:")
        print("-" * 40)
        sources = {
            "tsql": "SQL Server / T-SQL",
            "mysql": "MySQL",
            "oracle": "Oracle Database",
            "postgresql": "PostgreSQL",
            "db2": "IBM DB2",
            "hana": "SAP HANA"
        }
        for code, name in sources.items():
            print(f"  {code:15} {name}")
        print("-" * 40)
        print("Target: Always Snowflake")
        return

    if args.input:
        with open(args.input) as f:
            sql_text = f.read()
    else:
        sql_text = sys.stdin.read()

    result = convert_to_snowflake(sql_text, source_dialect=args.source)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result.snowflake_ddl + "\n")

    print("=" * 80)
    print(f"CONVERSION: {args.source.upper()} → SNOWFLAKE")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("CONVERTED SNOWFLAKE DDL")
    print("=" * 80)
    print(result.snowflake_ddl)

    print("\n" + "=" * 80)
    print(f"TRANSFORMATIONS MADE ({len(result.transformations)})")
    print("=" * 80)
    if result.transformations:
        for t in result.transformations:
            print(f"  - {t}")
    else:
        print("  (none)")

    print("\n" + "=" * 80)
    print(f"MANUAL REVIEW REQUIRED ({len(result.manual_review)})")
    print("=" * 80)
    if result.manual_review:
        for r in result.manual_review:
            print(f"  ! {r}")
    else:
        print("  (none)")


if __name__ == "__main__":
    main()
