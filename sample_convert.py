import json
from test_cases import TEST_CASES
from converter import convert

tc = TEST_CASES[0]
res = convert(tc['input'])

out = {
    'id': tc['id'],
    'name': tc['name'],
    'snowflake_ddl': res.snowflake_ddl,
    'transformations': res.transformations,
    'manual_review': res.manual_review,
}

with open('sample_output.json', 'w') as f:
    json.dump(out, f, indent=2)

print('Wrote sample_output.json')
