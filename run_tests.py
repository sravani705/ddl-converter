"""
Phase 3 test harness.

Runs every case in test_cases.py through the converter and compares the
result against golden_outputs.json (a human-reviewed baseline - see
generate_golden.py / README.md). Produces:
  - a console summary (pass/fail counts)
  - test_report.md: the "Input DDL -> Expected Snowflake DDL -> Agent Output
    -> Pass/Fail -> Comments" table requested in Phase 3, one section per case.

Exit code is non-zero if any case fails, so this can be wired into CI.
"""
import json
import sys
from test_cases import TEST_CASES
from converter import convert

with open("golden_outputs.json") as f:
    GOLDEN = json.load(f)


def run() -> int:
    results = []
    n_pass = 0
    for tc in TEST_CASES:
        res = convert(tc["input"])
        expected = GOLDEN.get(tc["id"])
        actual_ddl = res.snowflake_ddl
        expected_ddl = expected["snowflake_ddl"] if expected else None
        passed = expected is not None and actual_ddl == expected_ddl

        comments = []
        if expected is None:
            comments.append("No golden baseline recorded for this case.")
        if passed:
            n_pass += 1
            if res.manual_review:
                comments.append(
                    f"{len(res.manual_review)} manual-review item(s) flagged as expected "
                    f"(see below) - this is correct behavior, not a defect."
                )
            else:
                comments.append("Clean conversion, no manual-review items.")
        else:
            comments.append("Output DDL does not match the reviewed baseline - regression.")

        results.append({
            "id": tc["id"],
            "category": tc["category"],
            "name": tc["name"],
            "input": tc["input"].strip(),
            "expected_ddl": expected_ddl or "(no baseline)",
            "actual_ddl": actual_ddl,
            "passed": passed,
            "comments": " ".join(comments),
            "transformations": res.transformations,
            "manual_review": res.manual_review,
        })

    write_report(results, n_pass, len(TEST_CASES))
    print(f"{n_pass}/{len(TEST_CASES)} passed.")
    return 0 if n_pass == len(TEST_CASES) else 1


def write_report(results, n_pass, n_total):
    lines = []
    lines.append("# SQL Server -> Snowflake DDL Conversion Agent - Test Report\n")
    lines.append(f"**Result: {n_pass}/{n_total} test cases passed.**\n")
    lines.append("| ID | Category | Name | Pass/Fail |")
    lines.append("|----|----------|------|-----------|")
    for r in results:
        status = "PASS" if r["passed"] else "**FAIL**"
        lines.append(f"| {r['id']} | {r['category']} | {r['name']} | {status} |")
    lines.append("")

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"## {r['id']}: {r['name']} - {status}\n")
        lines.append(f"**Category:** {r['category']}\n")
        lines.append("**Input DDL (SQL Server):**")
        lines.append("```sql")
        lines.append(r["input"])
        lines.append("```\n")
        lines.append("**Expected Snowflake DDL:**")
        lines.append("```sql")
        lines.append(r["expected_ddl"])
        lines.append("```\n")
        lines.append("**Agent Output:**")
        lines.append("```sql")
        lines.append(r["actual_ddl"])
        lines.append("```\n")
        lines.append(f"**Pass/Fail:** {status}\n")
        lines.append(f"**Comments:** {r['comments']}\n")
        if r["transformations"]:
            lines.append("**Transformations applied:**")
            for t in r["transformations"]:
                lines.append(f"- {t}")
            lines.append("")
        if r["manual_review"]:
            lines.append("**Manual review required:**")
            for m in r["manual_review"]:
                lines.append(f"- {m}")
            lines.append("")
        lines.append("---\n")

    with open("test_report.md", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(run())
