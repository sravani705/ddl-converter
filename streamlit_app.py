import os
import json
import requests
import streamlit as st

from converter_to_snowflake import convert_to_snowflake

# Optional imports
try:
    import sqlglot
    from sqlglot import transpile, parse_one
    SQLGLOT_AVAILABLE = True
except Exception:
    SQLGLOT_AVAILABLE = False


def call_claude(prompt: str, model: str = "claude-2") -> str:
    """Call the Claude HTTP API if `CLAUDE_API_KEY` is set.

    The function is intentionally simple and tolerant: it requires the
    `CLAUDE_API_KEY` environment variable. If not present or the call
    fails, it returns a helpful message.
    """
    key = os.environ.get("CLAUDE_API_KEY")
    if not key:
        return "CLAUDE_API_KEY not set. Set the env var to enable Claude calls."

    url = "https://api.anthropic.com/v1/complete"
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens_to_sample": 800,
        "temperature": 0.0,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        # Anthropic responses put the text in `completion` for /v1/complete
        return data.get("completion") or json.dumps(data, indent=2)
    except Exception as e:
        return f"Claude API call failed: {e}"


def validate_conversion(result) -> (bool, list):
    """Simple validation: pass if there are no manual-review items and
    the snowflake_ddl is non-empty. Returns (passed, issues).
    """
    issues = []
    if not result.snowflake_ddl or not result.snowflake_ddl.strip():
        issues.append("Converted DDL is empty.")
    if result.manual_review:
        issues.append(f"{len(result.manual_review)} manual-review item(s) present.")
    return (len(issues) == 0, issues)


def main():
    st.set_page_config(page_title="DDL Converter — Streamlit UI", layout="wide")
    st.title("Multi-Source SQL → Snowflake DDL Converter")

    left, right = st.columns([2, 3])

    with left:
        st.subheader("Source & Input")

        # Source dialect selector
        source_dialect = st.selectbox(
            "Source SQL Dialect",
            options=["tsql", "mysql", "oracle", "postgresql", "db2", "hana"],
            format_func=lambda x: {
                "tsql": "SQL Server (T-SQL)",
                "mysql": "MySQL",
                "oracle": "Oracle Database",
                "postgresql": "PostgreSQL",
                "db2": "IBM DB2",
                "hana": "SAP HANA"
            }.get(x, x),
            index=0,
            help="Select the source database dialect"
        )

        st.markdown(f"**Target:** Snowflake (fixed)")

        # Allow choosing a sample from test_cases if available
        sample_sql = ""
        try:
            from test_cases import TEST_CASES
            samples = {tc['id']: tc for tc in TEST_CASES}
            sample_choice = st.selectbox("Sample test case (optional)", ["(none)"] + [f"{c['id']}: {c['name']}" for c in TEST_CASES])
            if sample_choice and sample_choice != "(none)":
                key = int(sample_choice.split(":")[0])
                sample_sql = samples[key]["input"]
        except Exception:
            sample_sql = ""

        sql_text = st.text_area(f"Input DDL ({source_dialect.upper()})", value=sample_sql, height=300)
        run = st.button("Convert to Snowflake")

        st.markdown("---")
        st.subheader("Options")
        enable_sqlglot = st.checkbox("Enable SQLGlot normalization (optional)", value=False, help="Attempt to normalize / pretty-print SQL via sqlglot if installed.")
        enable_claude = st.checkbox("Enable Claude suggestions (requires CLAUDE_API_KEY)", value=False)

    with right:
        st.subheader("Result")
        result_area = st.empty()

    if run and sql_text.strip():
        with st.spinner("Converting…"):
            res = convert_to_snowflake(sql_text, source_dialect=source_dialect)

        # Show converted DDL
        with right:
            st.subheader("Converted Snowflake DDL")
            st.code(res.snowflake_ddl or "(no output)", language="sql")

            st.subheader("Validation")
            passed, issues = validate_conversion(res)
            if passed:
                st.success("Basic validation passed — no manual-review items and DDL present.")
            else:
                st.error("Validation issues found:")
                for it in issues:
                    st.write(f"- {it}")

            with st.expander("Transformations (what changed)"):
                if res.transformations:
                    for t in res.transformations:
                        st.write(f"- {t}")
                else:
                    st.write("(none)")

            with st.expander("Manual review items"):
                if res.manual_review:
                    for m in res.manual_review:
                        st.write(f"- {m}")
                else:
                    st.write("(none)")

            # SQLGlot normalization (optional)
            if enable_sqlglot:
                if SQLGLOT_AVAILABLE:
                    try:
                        st.subheader("SQLGlot Normalize")
                        try:
                            parsed = parse_one(res.snowflake_ddl)
                            normalized = parsed.to_sql(dialect="snowflake")
                        except Exception:
                            # fallback to transpile/format
                            normalized = "\n".join(transpile(res.snowflake_ddl, read=None, write="snowflake"))
                        st.code(normalized, language="sql")
                    except Exception as e:
                        st.warning(f"SQLGlot normalization failed: {e}")
                else:
                    st.warning("sqlglot not installed. See requirements.txt to add it.")

            if enable_claude:
                st.subheader("Claude suggestions (optional)")
                prompt = (
                    "You are an expert DBA converting SQL Server DDL to Snowflake. "
                    "Given the original SQL Server DDL and the converted Snowflake DDL and any manual-review items, "
                    "provide suggested edits to the Snowflake DDL to address review items, and short reasoning.\n\n"
                    "Original DDL:\n" + sql_text + "\n\n"
                    "Converted Snowflake DDL:\n" + (res.snowflake_ddl or "(none)") + "\n\n"
                    "Manual review items:\n" + ("\n".join(res.manual_review) if res.manual_review else "(none)") + "\n\n"
                    "Return only a suggested Snowflake DDL and brief bullet points of changes."
                )
                claude_resp = call_claude(prompt)
                st.text_area("Claude response", value=claude_resp, height=300)

            st.markdown("---")
            st.caption("Tip: to write only the DDL to a file, use the project's `cli.py -o` option or copy from the code block.")


if __name__ == "__main__":
    main()
