"""
SQL Server -> Snowflake DDL conversion engine.

Design principle: every mapping decision is driven by rules.json (a structured
config layer), not by asking an LLM to "just know" the answer. Anything the
rules file doesn't cover, or that behaves differently between the two
platforms, is surfaced as an explicit manual-review item instead of being
silently guessed.

Public entry point: convert(sql_text: str) -> ConversionResult
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Optional SQLGlot import for enhanced validation
try:
    from sqlglot_helpers import validate_sql as sqlglot_validate, format_sql as sqlglot_format
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")
with open(RULES_PATH, "r") as f:
    RULES = json.load(f)

RESERVED_WORDS = set(w.upper() for w in RULES["reserved_words"])
STRIP_SCHEMAS = set(s.upper() for s in RULES["schema_handling"]["strip_schemas"])


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #

@dataclass
class ConversionResult:
    snowflake_ddl: str = ""
    transformations: List[str] = field(default_factory=list)
    manual_review: List[str] = field(default_factory=list)

    def add_transform(self, msg: str):
        self.transformations.append(msg)

    def add_review(self, msg: str):
        self.manual_review.append(msg)


# --------------------------------------------------------------------------- #
# Low level text helpers (paren/quote aware)
# --------------------------------------------------------------------------- #

def find_matching_paren(text: str, open_idx: int) -> int:
    """text[open_idx] must be '('. Returns index of the matching ')' respecting
    nested parens and single/double quoted string literals."""
    assert text[open_idx] == "("
    depth = 0
    i = open_idx
    n = len(text)
    in_str = None
    while i < n:
        c = text[i]
        if in_str:
            if c == in_str:
                # handle doubled quote escape ('' inside a string)
                if in_str == "'" and i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_str = None
        elif c in ("'", '"'):
            in_str = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"Unbalanced parentheses starting at index {open_idx}")


def split_top_level(text: str, sep: str = ",") -> List[str]:
    """Split text on sep, ignoring seps that are nested inside parens or quotes."""
    parts = []
    depth = 0
    in_str = None
    start = 0
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if in_str:
            if c == in_str:
                if in_str == "'" and i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_str = None
        elif c in ("'", '"'):
            in_str = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return [p for p in (p.strip() for p in parts) if p != ""]


def strip_ident_delims(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return raw[1:-1]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw


def quote_if_needed(identifier: str) -> str:
    """Snowflake-quote an identifier if it collides with a reserved word or
    contains characters that require quoting."""
    bare = strip_ident_delims(identifier)
    needs_quote = (
        bare.upper() in RESERVED_WORDS
        or not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", bare)
    )
    if needs_quote:
        return f'"{bare}"'
    return bare


def unwrap_redundant_parens(expr: str) -> str:
    expr = expr.strip()
    while len(expr) >= 2 and expr[0] == "(" and expr[-1] == ")":
        try:
            match_idx = find_matching_paren(expr, 0)
        except ValueError:
            break
        if match_idx == len(expr) - 1:
            expr = expr[1:-1].strip()
        else:
            break
    return expr


def extract_expression_after(rest: str, start: int) -> Tuple[str, int]:
    """Given `rest` and the index right after a keyword like DEFAULT, extract
    the following expression (balanced-paren / quote aware) and return
    (expression_text, index_after_expression)."""
    i = start
    n = len(rest)
    while i < n and rest[i].isspace():
        i += 1
    if i < n and rest[i] == "(":
        end = find_matching_paren(rest, i)
        return rest[i:end + 1], end + 1
    # bare token / function-call / literal: consume until a top-level
    # whitespace-delimited stop keyword, respecting quotes and parens.
    stop_words = {"NULL", "NOT", "CONSTRAINT", "IDENTITY", "COLLATE"}
    j = i
    depth = 0
    in_str = None
    tok_start = i
    while j < n:
        c = rest[j]
        if in_str:
            if c == in_str:
                in_str = None
            j += 1
            continue
        if c in ("'", '"'):
            in_str = c
            j += 1
            continue
        if c == "(":
            depth += 1
            j += 1
            continue
        if c == ")":
            if depth == 0:
                break
            depth -= 1
            j += 1
            continue
        if depth == 0 and c.isspace():
            word_match = re.match(r"\s+([A-Za-z_]+)", rest[j:])
            if word_match and word_match.group(1).upper() in stop_words:
                break
        j += 1
    return rest[tok_start:j].strip(), j


# --------------------------------------------------------------------------- #
# Type conversion
# --------------------------------------------------------------------------- #

def convert_type(type_name: str, args_raw: Optional[str], col_label: str,
                  result: ConversionResult) -> str:
    key = type_name.upper()
    mapping = RULES["type_mappings"].get(key)

    if mapping is None:
        result.add_review(
            f"{col_label}: SQL Server type '{type_name}' has no rule defined in the "
            f"conversion library. Left unchanged - map manually and add a rule."
        )
        return type_name.upper() + (f"({args_raw})" if args_raw else "")

    target = mapping.get("target")
    if target is None:
        result.add_review(f"{col_label}: {mapping.get('review', f'No Snowflake equivalent for {type_name}.')}")
        return type_name.upper() + (f"({args_raw})" if args_raw else "")

    out_type = target
    max_case = bool(args_raw and args_raw.strip().upper() == "MAX" and mapping.get("max_alias"))
    if max_case:
        pass  # out_type stays as bare target; Snowflake VARCHAR/BINARY with no size = max size
    elif mapping.get("fixed_args"):
        out_type = f"{target}({mapping['fixed_args']})"
    elif mapping.get("carry_args") and args_raw:
        out_type = f"{target}({args_raw})"

    original_str = type_name.upper() + (f"({args_raw})" if args_raw else "")
    if original_str != out_type:
        if max_case:
            result.add_transform(
                f"{col_label}: {type_name}(MAX) -> {target} (Snowflake VARCHAR/BINARY have no "
                f"explicit max-length variant; omitting the size defaults to the max size)."
            )
        else:
            result.add_transform(f"{col_label}: {type_name}{f'({args_raw})' if args_raw else ''} -> {out_type}")

    if "review" in mapping:
        result.add_review(f"{col_label}: {mapping['review']}")

    return out_type


# --------------------------------------------------------------------------- #
# Default expression conversion
# --------------------------------------------------------------------------- #

def convert_default_expr(raw_default: str, sqlserver_type: str, col_label: str,
                          result: ConversionResult) -> str:
    expr = raw_default

    for pattern, spec in RULES["function_mappings"].items():
        rx = re.compile(pattern, re.IGNORECASE)
        if rx.search(expr):
            if spec["replacement"] is None:
                result.add_review(
                    f"{col_label}: DEFAULT uses an expression matching '{pattern}' with no "
                    f"Snowflake equivalent. {spec.get('review', '')} Left unchanged - "
                    f"'{raw_default}' is NOT valid Snowflake syntax as-is."
                )
                continue
            new_expr = rx.sub(spec["replacement"], expr)
            if new_expr != expr:
                result.add_transform(f"{col_label}: DEFAULT {expr} -> {new_expr}")
                expr = new_expr
            if "review" in spec:
                result.add_review(f"{col_label}: {spec['review']}")

    unwrapped = unwrap_redundant_parens(expr)
    if unwrapped != expr.strip():
        expr = unwrapped

    if sqlserver_type.upper() == "BIT":
        norm = re.sub(r"\s+", "", unwrap_redundant_parens(raw_default))
        bit_map = RULES["bit_literal_defaults"]
        if norm in bit_map:
            new_val = bit_map[norm]
            if new_val != expr:
                result.add_transform(f"{col_label}: DEFAULT {raw_default.strip()} -> {new_val} (BIT -> BOOLEAN literal)")
            expr = new_val

    return expr


# --------------------------------------------------------------------------- #
# Column parsing
# --------------------------------------------------------------------------- #

COMPUTED_COL_RE = re.compile(r"^\s*(\[[^\]]+\]|\"[^\"]+\"|\w+)\s+AS\s*\(", re.IGNORECASE)
INLINE_CONSTRAINT_RE = re.compile(
    r"CONSTRAINT\s+(\[[^\]]+\]|\"[^\"]+\"|\w+)\s+(PRIMARY\s+KEY|UNIQUE)\b", re.IGNORECASE
)


def parse_column(segment: str, table_label: str, result: ConversionResult) -> str:
    seg = segment.strip()

    computed = COMPUTED_COL_RE.match(seg)
    if computed:
        col_name = quote_if_needed(computed.group(1))
        result.add_review(
            f"{table_label}.{col_name}: computed column ('{seg}') skipped. Snowflake supports "
            f"computed/virtual columns with different syntax (<name> <type> AS (<expr>)) and a "
            f"data type must be supplied explicitly - port the expression manually."
        )
        return f"    -- MANUAL REVIEW REQUIRED: computed column not converted: {seg}"

    m = re.match(r'^(\[[^\]]+\]|"[^"]+"|\S+)\s+(.*)$', seg, re.DOTALL)
    if not m:
        result.add_review(f"{table_label}: could not parse column definition '{seg}'. Left unchanged.")
        return f"    -- MANUAL REVIEW REQUIRED: unparsed column definition: {seg}"

    raw_name, rest = m.group(1), m.group(2)
    col_name = quote_if_needed(raw_name)
    col_label = f"{table_label}.{strip_ident_delims(raw_name)}"

    type_m = re.match(r'^(\[?\w+\]?)\s*(\(\s*([^()]*)\s*\))?\s*(.*)$', rest, re.DOTALL)
    raw_type = strip_ident_delims(type_m.group(1))
    args_raw = type_m.group(3).strip() if type_m.group(3) else None
    rest = type_m.group(4)

    sqlserver_type = raw_type
    out_type = convert_type(raw_type, args_raw, col_label, result)

    autoincrement = None
    default_expr = None
    nullability = None
    trailing_constraint = None
    leftover_notes = []

    changed = True
    while changed:
        changed = False
        rest_stripped = rest.strip()
        if not rest_stripped:
            break

        id_pattern = re.compile(RULES["identity_syntax"]["pattern"], re.IGNORECASE)
        id_default_pattern = re.compile(RULES["identity_syntax"]["default_pattern"], re.IGNORECASE)
        m2 = id_pattern.search(rest)
        if m2:
            seed, incr = m2.group(1), m2.group(2)
            autoincrement = RULES["identity_syntax"]["template_with_args"].format(seed=seed, increment=incr)
            result.add_transform(f"{col_label}: IDENTITY({seed},{incr}) -> {autoincrement}")
            rest = rest[:m2.start()] + rest[m2.end():]
            changed = True
            continue
        m2 = id_default_pattern.search(rest)
        if m2:
            autoincrement = RULES["identity_syntax"]["template_default"]
            result.add_transform(f"{col_label}: IDENTITY -> {autoincrement}")
            rest = rest[:m2.start()] + rest[m2.end():]
            changed = True
            continue

        m2 = re.search(r"\bDEFAULT\b", rest, re.IGNORECASE)
        if m2:
            expr_text, end_idx = extract_expression_after(rest, m2.end())
            default_expr = convert_default_expr(expr_text, sqlserver_type, col_label, result)
            rest = rest[:m2.start()] + rest[end_idx:]
            changed = True
            continue

        m2 = re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE)
        if m2:
            nullability = "NOT NULL"
            rest = rest[:m2.start()] + rest[m2.end():]
            changed = True
            continue
        m2 = re.search(r"\bNULL\b", rest, re.IGNORECASE)
        if m2:
            nullability = "NULL"
            rest = rest[:m2.start()] + rest[m2.end():]
            changed = True
            continue

        m2 = INLINE_CONSTRAINT_RE.search(rest)
        if m2:
            cname = quote_if_needed(m2.group(1))
            ckind = re.sub(r"\s+", " ", m2.group(2).upper())
            trailing_constraint = f"CONSTRAINT {cname} {ckind}"
            rest = rest[:m2.start()] + rest[m2.end():]
            changed = True
            continue

        m2 = re.search(r"\bMASKED\s+WITH\s*\(", rest, re.IGNORECASE)
        if m2:
            open_idx = m2.end() - 1
            close_idx = find_matching_paren(rest, open_idx)
            masked_pat = next(
                p for p in RULES["unsupported_column_attributes"]["patterns"]
                if "MASKED" in p["regex"]
            )
            result.add_review(f"{col_label}: {masked_pat['reason']}")
            rest = rest[:m2.start()] + rest[close_idx + 1:]
            changed = True
            continue

        matched_unsupported = False
        for pat in RULES["unsupported_column_attributes"]["patterns"]:
            if "MASKED" in pat["regex"]:
                continue  # handled above with balanced-paren extraction
            m2 = re.search(pat["regex"], rest, re.IGNORECASE)
            if m2:
                result.add_review(f"{col_label}: {pat['reason']}")
                rest = rest[:m2.start()] + rest[m2.end():]
                changed = True
                matched_unsupported = True
                break
        if matched_unsupported:
            continue

        remaining = rest.strip().strip(",").strip()
        if remaining:
            leftover_notes.append(remaining)
            result.add_review(
                f"{col_label}: unrecognized clause '{remaining}' was not automatically "
                f"converted - verify manually."
            )
        break

    pieces = [col_name, out_type]
    if autoincrement:
        pieces.append(autoincrement)
    if default_expr is not None:
        pieces.append(f"DEFAULT {default_expr}")
    if nullability:
        pieces.append(nullability)
    if trailing_constraint:
        pieces.append(trailing_constraint)

    line = "    " + " ".join(pieces)
    if leftover_notes:
        line += "  -- MANUAL REVIEW: unrecognized clause(s): " + "; ".join(leftover_notes)
    return line


# --------------------------------------------------------------------------- #
# Table-level constraint parsing
# --------------------------------------------------------------------------- #

def strip_clustered(text: str, table_label: str, result: ConversionResult) -> str:
    def _sub(m):
        return ""
    new_text, n = re.subn(r"\b(NON)?CLUSTERED\b", "", text, flags=re.IGNORECASE)
    if n:
        result.add_review(
            f"{table_label}: CLUSTERED/NONCLUSTERED index hint removed - Snowflake has no "
            f"user-defined clustered/nonclustered indexes (automatic micro-partitioning is "
            f"used instead; consider a CLUSTER BY clause if explicit clustering is needed)."
        )
    return re.sub(r"\s{2,}", " ", new_text).strip()


def convert_qualified_name(raw: str) -> str:
    parts = [strip_ident_delims(p) for p in raw.strip().split(".")]
    if len(parts) > 1 and parts[0].upper() in STRIP_SCHEMAS:
        parts = parts[1:]
    return ".".join(quote_if_needed(p) for p in parts)


def parse_table_constraint(segment: str, table_label: str, result: ConversionResult,
                            flags: dict) -> Optional[str]:
    if re.match(r"^INDEX\b", segment.strip(), re.IGNORECASE):
        result.add_review(
            f"{table_label}: inline INDEX definition removed ('{segment.strip()}'). Snowflake "
            f"does not support user-defined secondary indexes / inline INDEX clauses in "
            f"CREATE TABLE. Consider a CLUSTER BY clause or the search optimization service."
        )
        return None

    seg = strip_clustered(segment.strip(), table_label, result)

    m = re.match(r"^CONSTRAINT\s+(\[[^\]]+\]|\"[^\"]+\"|\w+)\s+(.*)$", seg, re.IGNORECASE | re.DOTALL)
    prefix = ""
    body = seg
    if m:
        cname = quote_if_needed(m.group(1))
        prefix = f"CONSTRAINT {cname} "
        body = m.group(2)

    body_upper = body.strip().upper()

    if body_upper.startswith("PRIMARY KEY") or body_upper.startswith("UNIQUE"):
        flags["pk_fk_unique"] = True
        return "    " + prefix + re.sub(r"\s{2,}", " ", body.strip())

    if body_upper.startswith("FOREIGN KEY"):
        flags["pk_fk_unique"] = True
        body_clean, n1 = re.subn(r"\bON\s+DELETE\s+(CASCADE|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT)",
                                  "", body, flags=re.IGNORECASE)
        body_clean, n2 = re.subn(r"\bON\s+UPDATE\s+(CASCADE|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT)",
                                  "", body_clean, flags=re.IGNORECASE)
        if n1 or n2:
            cname_disp = m.group(1) if m else "(unnamed)"
            result.add_review(
                f"{table_label}, constraint {cname_disp}: ON DELETE/ON UPDATE referential action "
                f"removed from FOREIGN KEY - Snowflake does not support cascading referential "
                f"actions. Re-implement the cascade/null/default behavior in ETL or application logic."
            )
        ref_m = re.search(r"REFERENCES\s+(\[[^\]]+\]|\"[^\"]+\"|[\w\.\[\]\"]+)", body_clean, re.IGNORECASE)
        if ref_m:
            converted_ref = convert_qualified_name(ref_m.group(1))
            body_clean = body_clean[:ref_m.start(1)] + converted_ref + body_clean[ref_m.end(1):]
        return "    " + prefix + re.sub(r"\s{2,}", " ", body_clean.strip())

    if body_upper.startswith("CHECK"):
        flags["check"] = True
        chk_expr = body.strip()
        for pattern, spec in RULES["function_mappings"].items():
            rx = re.compile(pattern, re.IGNORECASE)
            if rx.search(chk_expr) and spec["replacement"]:
                chk_expr = rx.sub(spec["replacement"], chk_expr)
        return "    " + prefix + re.sub(r"\s{2,}", " ", chk_expr)

    result.add_review(
        f"{table_label}: unrecognized table-level constraint '{segment.strip()}' was not "
        f"automatically converted - verify manually."
    )
    return f"    -- MANUAL REVIEW REQUIRED: unrecognized constraint: {segment.strip()}"


# --------------------------------------------------------------------------- #
# Table-level statement parsing
# --------------------------------------------------------------------------- #

CONSTRAINT_START_RE = re.compile(
    r"^(CONSTRAINT\b|PRIMARY\s+KEY\b|FOREIGN\s+KEY\b|UNIQUE\b|CHECK\b|INDEX\b)", re.IGNORECASE
)


def convert_create_table(stmt: str, result: ConversionResult) -> None:
    header_m = re.search(r"CREATE\s+TABLE\s+([^\(]+?)\s*\(", stmt, re.IGNORECASE)
    if not header_m:
        result.add_review("Could not locate a CREATE TABLE ... ( header in a statement; skipped.")
        return

    raw_table_name = header_m.group(1).strip()
    open_paren_idx = header_m.end() - 1
    close_paren_idx = find_matching_paren(stmt, open_paren_idx)
    body = stmt[open_paren_idx + 1:close_paren_idx]
    trailing = stmt[close_paren_idx + 1:]

    name_parts = [strip_ident_delims(p) for p in raw_table_name.split(".")]
    dropped_schema = None
    if len(name_parts) > 1 and name_parts[0].upper() in STRIP_SCHEMAS:
        dropped_schema = name_parts[0]
        name_parts = name_parts[1:]
    table_name_out = ".".join(quote_if_needed(p) for p in name_parts)
    table_label = f"Table {name_parts[-1]}"

    for opt in RULES["unsupported_table_options"]["patterns"]:
        if re.search(opt["regex"], trailing, re.IGNORECASE):
            result.add_review(f"{table_label}: {opt['reason']}")

    if dropped_schema:
        result.add_transform(
            f"{table_label}: dropped default schema prefix '{dropped_schema}.' "
            f"(SQL Server's default schema has no meaningful Snowflake equivalent by default)."
        )

    items = split_top_level(body, ",")
    column_lines = []
    constraint_lines = []
    flags = {"pk_fk_unique": False, "check": False}
    for item in items:
        if CONSTRAINT_START_RE.match(item.strip()):
            line = parse_table_constraint(item, table_label, result, flags)
            if line:
                constraint_lines.append(line)
        else:
            column_lines.append(parse_column(item, table_label, result))

    if flags["pk_fk_unique"]:
        result.add_review(f"{table_label}: {RULES['constraint_notes']['foreign_key']}")
    if flags["check"]:
        result.add_review(f"{table_label}: {RULES['constraint_notes']['check']}")

    all_lines = column_lines + constraint_lines
    ddl = f"CREATE TABLE {table_name_out} (\n" + ",\n".join(all_lines) + "\n);"
    if result.snowflake_ddl:
        result.snowflake_ddl += "\n\n"
    result.snowflake_ddl += ddl


# --------------------------------------------------------------------------- #
# Top level entry point
# --------------------------------------------------------------------------- #

def find_create_table_statements(sql_text: str) -> List[str]:
    text = re.sub(r"(?im)^\s*GO\s*$", "\n", sql_text)
    statements = []
    for m in re.finditer(r"CREATE\s+TABLE\s+[^\(]+?\(", text, re.IGNORECASE):
        start = m.start()
        open_idx = m.end() - 1
        try:
            close_idx = find_matching_paren(text, open_idx)
        except ValueError:
            continue
        semi = text.find(";", close_idx)
        end = semi + 1 if semi != -1 else close_idx + 1
        statements.append(text[start:end])
    return statements


def convert(sql_text: str) -> ConversionResult:
    result = ConversionResult()
    statements = find_create_table_statements(sql_text)
    if not statements:
        result.add_review("No CREATE TABLE statement found in the input.")
        return result
    for stmt in statements:
        convert_create_table(stmt, result)
    return result


if __name__ == "__main__":
    import sys
    src = sys.stdin.read()
    res = convert(src)
    print(res.snowflake_ddl)
    print("\n-- Transformations:")
    for t in res.transformations:
        print(f"--  * {t}")
    print("\n-- Manual review required:")
    for r in res.manual_review:
        print(f"--  * {r}")
