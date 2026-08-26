"""
Run every case in test_cases.py through the converter and save the result as
golden_outputs.json. This is a ONE-TIME step, run only after a human has
reviewed dump_outputs.py output and confirmed each case converts correctly
(see README.md). From then on, run_tests.py compares against this file as a
regression baseline - it does NOT regenerate it automatically, so a future
code change that silently alters output will show up as a FAIL, not be
silently accepted as the new "expected" value.
"""
import json
from test_cases import TEST_CASES
from converter import convert

golden = {}
for tc in TEST_CASES:
    res = convert(tc["input"])
    golden[tc["id"]] = {
        "snowflake_ddl": res.snowflake_ddl,
        "transformations": res.transformations,
        "manual_review": res.manual_review,
    }

with open("golden_outputs.json", "w") as f:
    json.dump(golden, f, indent=2)

print(f"Wrote golden_outputs.json with {len(golden)} entries.")
