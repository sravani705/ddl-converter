from test_cases import TEST_CASES
from converter import convert

for tc in TEST_CASES:
    print("=" * 90)
    print(f"{tc['id']} [{tc['category']}] {tc['name']}")
    print("-" * 90)
    res = convert(tc["input"])
    print(res.snowflake_ddl)
    print("\n-- transformations:")
    for t in res.transformations:
        print(f"  * {t}")
    print("-- manual review:")
    for r in res.manual_review:
        print(f"  * {r}")
    print()
