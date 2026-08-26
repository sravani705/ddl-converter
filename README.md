# Multi-Source SQL → Snowflake DDL Converter

Converts `CREATE TABLE` statements from **any SQL dialect** into equivalent
Snowflake DDL. Supports sources: SQL Server, MySQL, Oracle, PostgreSQL, DB2,
and SAP HANA. Built on a rules-driven conversion engine (not "ask the LLM and hope"),
with structured mappings, a 20-30 case regression test suite, and a hard rule 
that anything ambiguous or platform-divergent is flagged for **manual review**.

### Supported Source Dialects

- **SQL Server (T-SQL)** - `tsql`
- **MySQL** - `mysql`
- **Oracle Database** - `oracle`
- **PostgreSQL** - `postgresql`
- **IBM DB2** - `db2`
- **SAP HANA** - `hana`

**Target:** Always Snowflake

## Files

| File | Purpose |
|---|---|
| `rules.json` | **The source of truth.** Every type mapping, function mapping, identity syntax rule, reserved-word list, and "this has no equivalent" note lives here as data, not embedded in code. |
| `converter.py` | The parsing/conversion engine. Parses `CREATE TABLE` statements (balanced-paren aware, not naive regex-only), consults `rules.json` for every decision, and returns converted DDL + transformation log + manual-review list. |
| `cli.py` | Phase 1 "simple input interface" - run a `.sql` file (or stdin) through the converter from the command line. |
| `test_cases.py` | 30 SQL Server DDL inputs covering every category called out in Phase 3. |
| `golden_outputs.json` | Human-reviewed "expected" output for each test case (see "How the tests work" below). |
| `run_tests.py` | Runs all cases, diffs against the golden baseline, prints pass/fail, writes `test_report.md`. |
| `generate_golden.py` | One-time/deliberate script to (re)generate `golden_outputs.json` after a human has reviewed `dump_outputs.py` output. |
| `dump_outputs.py` | Prints full converter output (DDL + transformations + review items) for every test case, for human review. |
| `test_report.md` | Generated report: Input DDL -> Expected -> Agent Output -> Pass/Fail -> Comments, per Phase 3. |

## Quick start

```bash
# Convert a file
python3 cli.py my_table.sql

# Convert a file and save just the DDL
python3 cli.py my_table.sql -o my_table_snowflake.sql

# Pipe DDL in
cat my_table.sql | python3 cli.py

# Run the full regression suite
python3 run_tests.py
```

## Phase 1 - How the agent works

`convert(sql_text)` in `converter.py`:

1. Finds every `CREATE TABLE ... (...)` statement in the input (handles
   multiple tables per batch, `GO` separators, trailing `;`).
2. Splits the column/constraint list on **top-level** commas only (a
   custom paren/quote-aware splitter - not a plain `.split(",")`, so
   `DECIMAL(10,2)`, `IDENTITY(1,1)`, `CHECK(...)`, and quoted string
   defaults containing commas/parens all parse correctly).
3. For each item, decides column vs. table-level constraint
   (`CONSTRAINT`, `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`, `CHECK`,
   `INDEX`).
4. For columns: extracts name, base type, type arguments, `IDENTITY`,
   nullability, `DEFAULT` expression, inline constraints, and known
   SQL-Server-only attributes (`ROWGUIDCOL`, `PERSISTED`, `SPARSE`,
   `FILESTREAM`, `MASKED WITH (...)`, `COLLATE ...`) - each looked up
   in `rules.json`, never guessed.
5. For table-level constraints: carries `PRIMARY KEY` / `UNIQUE` /
   `FOREIGN KEY` / `CHECK` through with schema-qualified reference names
   rewritten, strips `CLUSTERED`/`NONCLUSTERED` hints and unsupported
   `ON DELETE`/`ON UPDATE` actions (each with a review note), and drops
   inline `INDEX` definitions (not valid Snowflake `CREATE TABLE` syntax).
6. Returns a `ConversionResult`: `snowflake_ddl`, `transformations`
   (what changed and why), `manual_review` (what needs a human).

## Phase 2 - Rules library (`rules.json`)

Everything the spec's mapping table asks for, plus more, expressed as
structured JSON so the mappings can be audited, edited, or extended
without touching Python:

- `type_mappings` - SQL Server type -> Snowflake type, with `carry_args`
  (keep `(n)` / `(p,s)`), `fixed_args` (force specific args, e.g.
  `MONEY` -> `NUMBER(19,4)`), and an optional `review` note that's
  surfaced even when a mapping *does* exist but the two platforms behave
  differently (e.g. `TINYINT`, `UNIQUEIDENTIFIER`, `MONEY`). Types with
  **no** Snowflake equivalent (`HIERARCHYID`, `ROWVERSION`, ...) have
  `target: null` and are left unconverted with an explanation, never
  guessed at.
- `function_mappings` - `GETDATE()` -> `CURRENT_TIMESTAMP()`,
  `ISNULL(` -> `COALESCE(`, `NEWID()` -> `UUID_STRING()`,
  `GETUTCDATE()` -> `CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())`
  (flagged for review since it depends on the session `TIMEZONE`
  parameter), etc.
- `identity_syntax` - `IDENTITY(seed,increment)` -> Snowflake
  `AUTOINCREMENT START seed INCREMENT increment`.
- `bit_literal_defaults` - `BIT` default literals (`0`/`1`/`(0)`/`(1)`/
  `((0))`/`((1))`) -> `FALSE`/`TRUE` once the column itself has been
  retyped to `BOOLEAN`.
- `schema_handling` - which SQL Server schemas (default: `dbo`) are
  dropped vs. carried through as a Snowflake schema prefix.
- `reserved_words` - Snowflake reserved words; any identifier that
  collides (or needs quoting for another reason) is emitted
  double-quoted.
- `unsupported_table_options` / `unsupported_column_attributes` -
  regex-detected SQL-Server-only clauses (`ON [PRIMARY]`, `WITH (...)`
  table options, `ROWGUIDCOL`, `PERSISTED`, `SPARSE`, `FILESTREAM`,
  `MASKED WITH (...)`, `COLLATE ...`) each paired with a plain-English
  reason for why it was removed and what to do about it.
- `constraint_notes` - the (extremely relevant) fact that Snowflake
  accepts `PRIMARY KEY` / `FOREIGN KEY` / `UNIQUE` / `CHECK` syntax but
  does **not enforce** any of it - always surfaced once per table so a
  migration doesn't silently lose data-integrity guarantees.

**To add a new mapping**, edit `rules.json` - no code changes needed for
a straightforward type or function mapping. The engine will pick it up
automatically.

## Phase 3 - Testing

`test_cases.py` has 30 cases spanning: simple tables, multiple data
types, identity columns, primary keys, foreign keys (incl. `ON DELETE
CASCADE` / `ON UPDATE`), composite keys, default values (literals,
double-wrapped `((0))` style, function calls), nullable vs. `NOT NULL`
vs. omitted, `UNIQUE`/`CHECK` constraints, custom schema names, reserved
words as identifiers, `MAX`-length `VARCHAR`/`NVARCHAR`, decimal
precision/scale combinations, every SQL Server date/time type, and a
cluster of genuinely unsupported features: `UNIQUEIDENTIFIER`+`NEWID()`,
`ROWVERSION`, computed columns, `XML`, filegroup/`WITH(...)` table
options, `CLUSTERED`/`NONCLUSTERED` hints, inline `INDEX`, `MONEY`/
`SMALLMONEY`, `BINARY`/`VARBINARY`/`IMAGE`, `TINYINT`, multi-table `GO`
batches, `MASKED WITH`/`COLLATE`, `GEOGRAPHY`/`HIERARCHYID`, and
`SQL_VARIANT`/`ROWGUIDCOL`.

### How the tests work

1. `dump_outputs.py` runs every case and prints the full output (DDL +
   transformation log + manual-review log) for **human review**.
2. Once a human has read through and confirmed each case is converting
   correctly (this was done for the 30 cases shipped here), running
   `generate_golden.py` snapshots that reviewed output into
   `golden_outputs.json` - the regression baseline.
3. `run_tests.py` re-runs every case and does an exact-match diff against
   `golden_outputs.json`. A mismatch is a **FAIL** (a regression from a
   later code/rule change), not silently accepted as the new expected
   value - `golden_outputs.json` only changes when a human deliberately
   re-runs `generate_golden.py` after reviewing the new output.
4. `run_tests.py` writes `test_report.md`: for every case, Input DDL ->
   Expected Snowflake DDL -> Agent Output -> Pass/Fail -> Comments, plus
   the full transformation and manual-review logs. Current status:
   **30/30 passing.**

Add a new case by appending to `TEST_CASES` in `test_cases.py`, running
`dump_outputs.py` to review its output, then `generate_golden.py` to
lock it in.

## Phase 4 - "Never silently guess"

Three concrete mechanisms enforce this, not just a prompt instruction:

1. **Unknown type** (not in `rules.json` at all): the type name is left
   completely unchanged in the output DDL (so the statement is easy to
   grep for and obviously not production-ready) and a manual-review
   entry says exactly that: *"SQL Server type 'X' has no rule defined in
   the conversion library. Left unchanged - map manually and add a
   rule."*
2. **Known type with no Snowflake equivalent** (`target: null` in
   `rules.json`, e.g. `HIERARCHYID`, `ROWVERSION`, `CURSOR`): same
   treatment, plus a specific explanation of *why* there's no equivalent
   and what the usual redesign pattern is.
3. **Behavior that differs even though a mapping exists** (e.g.
   `TINYINT` -> `SMALLINT` loses the unsigned 0-255 constraint,
   `NEWID()` -> `UUID_STRING()` uses a different algorithm, `GETUTCDATE()`
   depends on session timezone in Snowflake but not in SQL Server): the
   conversion still happens (so the DDL is runnable), but a manual-review
   note is *always* attached - it is never silently treated as a clean
   1:1 mapping.

Anything the parser can't recognize at all (an unfamiliar column clause,
an unfamiliar table-level constraint) is left in place as a trailing
`-- MANUAL REVIEW REQUIRED: ...` comment rather than dropped or guessed
at.

## Sharing & Deployment

**Want to share this with your team?** See [DEPLOYMENT.md](DEPLOYMENT.md) for a comprehensive guide covering:

- **Streamlit Cloud** (easiest—free hosting, instant public URL)
- **Docker** (local/private hosting, cloud deployments)
- **GitHub** (share source code for technical teams to run locally)
- **AWS Lambda / Google Cloud Run / Azure** (serverless options)
- **Email / USB / Cloud Storage** (one-off file sharing)

Quick public demo (Streamlit Cloud):
```bash
git push YOUR_REPO_URL
# Then deploy via https://share.streamlit.io
```

Quick local setup:
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Quick Docker:
```bash
docker build -t ddl-converter .
docker run -p 8502:8502 ddl-converter
# Open http://localhost:8502
```

## Known limitations / good next extensions

- Parses `CREATE TABLE` only. `ALTER TABLE ADD CONSTRAINT` (a common way
  to add FKs after the fact), `CREATE INDEX`, views, and stored
  procedures are out of scope for this phase.
- Column-level `CHECK` constraints (as opposed to table-level) aren't
  special-cased separately from the "unrecognized clause" fallback -
  they're uncommon in generated SQL Server DDL (`CHECK` is usually
  table-level) but would be a quick addition to `parse_column`.
  addition to `parse_column`.
- Multiple SQL dialect quirks (temporal tables, partitioned tables,
  `PERIOD FOR SYSTEM_TIME`) aren't covered - they'd need new
  `unsupported_table_options`/`unsupported_column_attributes` entries at
  minimum, and likely a manual-redesign note like `HIERARCHYID`'s.
