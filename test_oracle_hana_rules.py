"""
Verification test suite for Oracle -> Snowflake and SAP HANA -> Snowflake DDL conversion rules.
"""

from converter_multi_dialect import convert

def run_tests():
    oracle_cases = [
        ("NUMBER", "c1 NUMBER", "NUMBER"),
        ("NUMBER(p,s)", "c1 NUMBER(10,2)", "NUMBER(10,2)"),
        ("INTEGER", "c1 INTEGER", "INTEGER"),
        ("SMALLINT", "c1 SMALLINT", "SMALLINT"),
        ("FLOAT", "c1 FLOAT", "FLOAT"),
        ("BINARY_FLOAT", "c1 BINARY_FLOAT", "FLOAT"),
        ("BINARY_DOUBLE", "c1 BINARY_DOUBLE", "DOUBLE"),
        ("VARCHAR2(n)", "c1 VARCHAR2(100)", "VARCHAR(100)"),
        ("VARCHAR(n)", "c1 VARCHAR(50)", "VARCHAR(50)"),
        ("CHAR(n)", "c1 CHAR(10)", "CHAR(10)"),
        ("NCHAR(n)", "c1 NCHAR(20)", "CHAR(20)"),
        ("NVARCHAR2(n)", "c1 NVARCHAR2(150)", "VARCHAR(150)"),
        ("CLOB", "c1 CLOB", "VARCHAR"),
        ("NCLOB", "c1 NCLOB", "VARCHAR"),
        ("BLOB", "c1 BLOB", "BINARY"),
        ("RAW(n)", "c1 RAW(16)", "BINARY(16)"),
        ("DATE", "c1 DATE", "TIMESTAMP_NTZ"),
        ("TIMESTAMP", "c1 TIMESTAMP", "TIMESTAMP_NTZ"),
        ("TIMESTAMP WITH TIME ZONE", "c1 TIMESTAMP WITH TIME ZONE", "TIMESTAMP_TZ"),
        ("TIMESTAMP WITH LOCAL TIME ZONE", "c1 TIMESTAMP WITH LOCAL TIME ZONE", "TIMESTAMP_TZ"),
        ("INTERVAL", "c1 INTERVAL", "INTERVAL"),
        ("XMLTYPE", "c1 XMLTYPE", "VARIANT"),
        ("ROWID", "c1 ROWID", "VARCHAR"),
        ("UROWID", "c1 UROWID", "VARCHAR"),
        ("JSON", "c1 JSON", "VARIANT")
    ]

    hana_cases = [
        ("TINYINT", "c1 TINYINT", "NUMBER(3,0)"),
        ("SMALLINT", "c1 SMALLINT", "SMALLINT"),
        ("INTEGER", "c1 INTEGER", "INTEGER"),
        ("INT", "c1 INT", "INTEGER"),
        ("BIGINT", "c1 BIGINT", "BIGINT"),
        ("DECIMAL(p,s)", "c1 DECIMAL(12,4)", "NUMBER(12,4)"),
        ("SMALLDECIMAL", "c1 SMALLDECIMAL", "NUMBER"),
        ("REAL", "c1 REAL", "FLOAT"),
        ("DOUBLE", "c1 DOUBLE", "DOUBLE"),
        ("BOOLEAN", "c1 BOOLEAN", "BOOLEAN"),
        ("CHAR(n)", "c1 CHAR(10)", "CHAR(10)"),
        ("VARCHAR(n)", "c1 VARCHAR(100)", "VARCHAR(100)"),
        ("NVARCHAR(n)", "c1 NVARCHAR(100)", "VARCHAR(100)"),
        ("ALPHANUM(n)", "c1 ALPHANUM(10)", "VARCHAR(10)"),
        ("SHORTTEXT", "c1 SHORTTEXT(50)", "VARCHAR(50)"),
        ("CLOB", "c1 CLOB", "VARCHAR"),
        ("NCLOB", "c1 NCLOB", "VARCHAR"),
        ("BLOB", "c1 BLOB", "BINARY"),
        ("DATE", "c1 DATE", "DATE"),
        ("TIME", "c1 TIME", "TIME"),
        ("SECONDDATE", "c1 SECONDDATE", "TIMESTAMP_NTZ"),
        ("TIMESTAMP", "c1 TIMESTAMP", "TIMESTAMP_NTZ"),
        ("LONGDATE", "c1 LONGDATE", "TIMESTAMP_NTZ"),
        ("ST_POINT", "c1 ST_POINT", "GEOGRAPHY"),
        ("ST_GEOMETRY", "c1 ST_GEOMETRY", "GEOMETRY")
    ]

    print("=" * 70)
    print("TESTING ORACLE -> SNOWFLAKE CONVERSION RULES")
    print("=" * 70)
    oracle_passes = 0
    for name, col_sql, expected_type in oracle_cases:
        ddl = f"CREATE TABLE test_table (\n    {col_sql}\n);"
        res = convert(ddl, source_dialect="oracle", target_dialect="snowflake")
        out_line = res.converted_ddl.strip().split("\n")[1].strip()
        expected_line = f"c1 {expected_type}"
        passed = out_line == expected_line
        status = "PASS" if passed else "FAIL"
        if passed:
            oracle_passes += 1
        print(f"[{status}] {name:30} -> {out_line:25} (expected: {expected_line})")

    print("\n" + "=" * 70)
    print("TESTING SAP HANA -> SNOWFLAKE CONVERSION RULES")
    print("=" * 70)
    hana_passes = 0
    for name, col_sql, expected_type in hana_cases:
        ddl = f"CREATE TABLE test_table (\n    {col_sql}\n);"
        res = convert(ddl, source_dialect="hana", target_dialect="snowflake")
        out_line = res.converted_ddl.strip().split("\n")[1].strip()
        expected_line = f"c1 {expected_type}"
        passed = out_line == expected_line
        status = "PASS" if passed else "FAIL"
        if passed:
            hana_passes += 1
        print(f"[{status}] {name:30} -> {out_line:25} (expected: {expected_line})")

    print("\n" + "=" * 70)
    print(f"RESULTS: Oracle: {oracle_passes}/{len(oracle_cases)} passed | HANA: {hana_passes}/{len(hana_cases)} passed")
    print("=" * 70)

    # Full table conversions
    print("\n" + "=" * 70)
    print("TESTING FULL ORACLE DDL CONVERSION WITH CONSTRAINTS & DEFAULTS")
    print("=" * 70)
    oracle_table_ddl = """
    CREATE TABLE SYS.employees (
        emp_id NUMBER(10,0) NOT NULL,
        first_name VARCHAR2(50),
        last_name VARCHAR2(50) NOT NULL,
        hire_date DATE DEFAULT SYSDATE,
        salary NUMBER(10,2),
        resume CLOB,
        avatar BLOB,
        guid RAW(16),
        metadata JSON,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP,
        CONSTRAINT pk_employees PRIMARY KEY (emp_id)
    );
    """
    res_ora = convert(oracle_table_ddl, source_dialect="oracle", target_dialect="snowflake")
    print(res_ora.converted_ddl)
    print("Transformations:", res_ora.transformations)
    print("Manual Review:", res_ora.manual_review)

    print("\n" + "=" * 70)
    print("TESTING FULL SAP HANA DDL CONVERSION WITH CONSTRAINTS & DEFAULTS")
    print("=" * 70)
    hana_table_ddl = """
    CREATE TABLE SYS.products (
        product_id BIGINT NOT NULL,
        product_code ALPHANUM(20) NOT NULL,
        title NVARCHAR(200) NOT NULL,
        summary SHORTTEXT(500),
        price DECIMAL(10,2),
        in_stock BOOLEAN,
        item_flag TINYINT,
        release_date DATE,
        created_at SECONDDATE DEFAULT CURRENT_TIMESTAMP,
        updated_at LONGDATE,
        location ST_POINT,
        geometry_shape ST_GEOMETRY,
        PRIMARY KEY (product_id)
    );
    """
    res_hana = convert(hana_table_ddl, source_dialect="hana", target_dialect="snowflake")
    print(res_hana.converted_ddl)
    print("Transformations:", res_hana.transformations)
    print("Manual Review:", res_hana.manual_review)

    return oracle_passes == len(oracle_cases) and hana_passes == len(hana_cases)

if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
