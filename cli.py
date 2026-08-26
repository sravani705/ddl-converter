"""
Phase 1 "simple input interface".

Usage:
    python3 cli.py input.sql                 # write result to stdout
    python3 cli.py input.sql -o output.sql    # write Snowflake DDL to a file,
                                               # print the report to stdout
    cat input.sql | python3 cli.py            # read from stdin

Output always has three clearly separated parts:
    1. Converted Snowflake DDL
    2. List of transformations made
    3. Any unsupported / ambiguous elements ("Manual review required")
"""
import argparse
import sys

from converter import convert


def main():
    ap = argparse.ArgumentParser(description="Convert SQL Server DDL to Snowflake DDL.")
    ap.add_argument("input", nargs="?", help="Path to a .sql file. Omit to read from stdin.")
    ap.add_argument("-o", "--output", help="Write just the converted DDL to this file.")
    args = ap.parse_args()

    if args.input:
        with open(args.input) as f:
            sql_text = f.read()
    else:
        sql_text = sys.stdin.read()

    result = convert(sql_text)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result.snowflake_ddl + "\n")

    print("=" * 80)
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
