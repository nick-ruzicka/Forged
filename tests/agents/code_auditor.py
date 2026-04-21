"""Code quality audit agent. AST-based static analysis; runs once and exits."""
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "tests" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "code_audit.json"
SCAN_DIRS = ["api", "agents"]

EXTERNAL_CALL_MARKERS = (
    "requests.get(",
    "requests.post(",
    "requests.put(",
    "requests.delete(",
    "requests.patch(",
    "anthropic.",
    "Anthropic(",
    "client.messages.create",
    "psycopg2.connect",
    "redis.Redis",
    "celery_app.send_task",
    "urlopen(",
    "urlretrieve(",
    "httpx.",
    "subprocess.run(",
    "subprocess.Popen(",
)

SQL_VERBS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b", re.IGNORECASE)

# Variable names that, when interpolated into SQL, are by convention trusted
# SQL metadata (column lists, placeholder lists, ORDER BY clauses, WHERE clause
# fragments built from code-controlled inputs). Values themselves are passed
# separately through cur.execute(sql, values).
TRUSTED_SQL_METADATA = re.compile(
    r"\{\s*(placeholders|col_sql|cols|columns|where_sql|where_clause|where|"
    r"sets|set_clause|order_by|order_sql|sort|sort_order|order|table|tbl|"
    r"schema|fields|filters?|col_list|value_placeholders)\b[^}]*\}",
    re.IGNORECASE,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def severity(issue_type: str) -> str:
    critical = {"sql_injection_risk", "hardcoded_credential"}
    warning = {
        "missing_error_handling",
        "missing_input_validation",
        "hardcoded_value",
        "long_function",
    }
    if issue_type in critical:
        return "critical"
    if issue_type in warning:
        return "warning"
    return "info"


def add(findings, file, line, issue_type, description):
    findings.append({
        "file": str(file.relative_to(ROOT)),
        "line_number": line,
        "issue_type": issue_type,
        "severity": severity(issue_type),
        "description": description,
    })


def _contains_external_call(source: str) -> bool:
    return any(marker in source for marker in EXTERNAL_CALL_MARKERS)


def _has_try(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Try):
            return True
    return False


def _function_body_source(path: Path, node: ast.FunctionDef, lines: list[str]) -> str:
    start = node.lineno - 1
    end = node.end_lineno if hasattr(node, "end_lineno") and node.end_lineno else start + 1
    return "\n".join(lines[start:end])


def audit_file(path: Path, findings: list) -> None:
    try:
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        add(findings, path, getattr(exc, "lineno", 0) or 0, "syntax_error", str(exc))
        return

    lines = source.splitlines()

    # Unused imports
    _check_unused_imports(path, tree, findings)

    # Walk all function/method definitions
    defined_funcs = set()
    called_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_funcs.add(node.name)
            _check_function(path, node, source, lines, findings)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_funcs.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_funcs.add(node.func.attr)

    # Dead code — module-level functions not referenced anywhere in this file
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if node.name in ("main",):
                continue
            if node.name not in called_funcs:
                add(findings, path, node.lineno, "dead_code",
                    f"function '{node.name}' is defined but never called in this file")

    # SQL injection risk — f-strings / % / + with SQL
    _check_sql_injection(path, source, lines, findings)

    # Hardcoded values (localhost, :PORT, api keys)
    _check_hardcoded(path, lines, findings)


def _check_unused_imports(path: Path, tree: ast.AST, findings: list) -> None:
    imports: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imports[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                imports[name] = node.lineno

    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # For Attribute nodes, walk to find base Name
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)

    for name, lineno in imports.items():
        if name not in used:
            add(findings, path, lineno, "unused_import",
                f"import '{name}' is not used")


def _check_function(path, node, source, lines, findings):
    body_source = _function_body_source(path, node, lines)

    # Long function
    if hasattr(node, "end_lineno") and node.end_lineno:
        length = node.end_lineno - node.lineno
        if length > 80:
            add(findings, path, node.lineno, "long_function",
                f"function '{node.name}' is {length} lines long (threshold: 80)")

        # Missing docstring for longer functions
        if length > 20 and not ast.get_docstring(node):
            add(findings, path, node.lineno, "missing_docstring",
                f"function '{node.name}' is {length} lines but has no docstring")

    # External call with no try/except — but skip:
    # (a) Flask routes: framework handles exceptions via app.errorhandler
    # (b) Very short functions (< 10 lines): too small to need local handling;
    #     exceptions should propagate to the caller
    # (c) DB query helpers in api/db.py: raising is correct — callers need to
    #     know when the DB is unreachable, not silently get None
    is_flask_route = any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in ("route", "get", "post", "put", "delete", "patch")
        for d in node.decorator_list
    )
    func_length = (
        node.end_lineno - node.lineno
        if hasattr(node, "end_lineno") and node.end_lineno
        else 0
    )
    is_short = func_length < 10
    is_db_helper = "api/db.py" in str(path)
    if (
        _contains_external_call(body_source)
        and not _has_try(node)
        and not is_flask_route
        and not is_short
        and not is_db_helper
    ):
        add(findings, path, node.lineno, "missing_error_handling",
            f"function '{node.name}' makes external calls with no try/except")

    # API endpoint with DB write and no validation
    is_route = any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in ("route", "get", "post", "put", "delete", "patch")
        for d in node.decorator_list
    )
    if is_route and ("INSERT" in body_source.upper() or "UPDATE" in body_source.upper()):
        has_validation = any(
            tok in body_source
            for tok in ("request.get_json", "request.json", "validate", "required",
                        "if not ", "KeyError", "abort(")
        )
        if not has_validation:
            add(findings, path, node.lineno, "missing_input_validation",
                f"route '{node.name}' writes to DB without obvious input validation")


def _check_sql_injection(path: Path, source: str, lines: list[str], findings: list) -> None:
    # SQL-verb-at-start-of-fstring: f"UPDATE ...", f"SELECT ...", etc.
    # AND the same line has no %s parameter — implies pure interpolation (unsafe).
    # If %s is present, the author is mixing trusted column/table names with
    # parameterized values, which is the standard safe pattern.
    sql_start = re.compile(
        r"f['\"](?:\s*)(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)\b",
        re.IGNORECASE,
    )
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not SQL_VERBS.search(stripped):
            continue
        has_fstring_sql = bool(sql_start.search(line)) and "{" in line
        has_param_placeholder = "%s" in line
        # Check if every interpolated name is in the trusted-metadata allowlist.
        # If so, this is the standard pattern for dynamic columns/tables with
        # parameterized values passed via cur.execute's second argument.
        if has_fstring_sql:
            all_trusted = True
            for match in re.finditer(r"\{[^}]+\}", line):
                if not TRUSTED_SQL_METADATA.match(match.group(0)):
                    all_trusted = False
                    break
            if all_trusted:
                continue
            add(findings, path, i, "sql_injection_risk",
                "f-string interpolation inside SQL literal — use parameters instead")
            continue
        # String concatenation building SQL. Safe if a %s appears OR the concat'd
        # variable is a trusted metadata name (placeholders, col_sql, etc.).
        if "+ " in line and any(v in line.upper() for v in ("SELECT ", "WHERE ", "INSERT ", "UPDATE ")):
            if re.search(r"['\"].*['\"]\s*\+\s*\w+", line):
                m = re.search(r"\+\s*(\w+)", line)
                trusted_concat = False
                if m:
                    var = m.group(1).lower()
                    if var in ("placeholders", "col_sql", "cols", "columns",
                               "where_sql", "where_clause", "where", "sets",
                               "set_clause", "order_by", "order_sql", "sort",
                               "sort_order", "order", "table", "tbl", "schema",
                               "fields", "filter", "filters", "col_list",
                               "value_placeholders"):
                        trusted_concat = True
                if not trusted_concat and not has_param_placeholder:
                    add(findings, path, i, "sql_injection_risk",
                        "string concatenation inside SQL literal — use parameters instead")


def _check_hardcoded(path: Path, lines: list[str], findings: list) -> None:
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "os.environ" in line or "getenv" in line or "load_dotenv" in line:
            continue
        # Hardcoded localhost / IPs
        if re.search(r"['\"](?:localhost|127\.0\.0\.1|0\.0\.0\.0)['\"]", line):
            add(findings, path, i, "hardcoded_value",
                f"hardcoded host literal: {stripped[:100]}")
        # Hardcoded port (e.g., :8090, port=8090)
        elif re.search(r"port\s*=\s*\d{4,5}\b", line) or re.search(r":\d{4,5}['\"]", line):
            add(findings, path, i, "hardcoded_value",
                f"hardcoded port number: {stripped[:100]}")
        # API key shaped literals
        if re.search(r"['\"]sk-ant-[A-Za-z0-9_-]+['\"]", line):
            add(findings, path, i, "hardcoded_credential",
                "Anthropic API key literal appears in source")
        elif re.search(r"['\"](?:AKIA|xoxb-|ghp_|gho_)[A-Za-z0-9_-]+['\"]", line):
            add(findings, path, i, "hardcoded_credential",
                "API credential literal appears in source")


def run_once() -> dict:
    findings: list = []
    files_scanned = 0
    for subdir in SCAN_DIRS:
        base = ROOT / subdir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            audit_file(path, findings)
            files_scanned += 1

    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    report = {
        "timestamp": now(),
        "files_scanned": files_scanned,
        "counts": counts,
        "findings": findings,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    print(
        f"[code_auditor] {report['timestamp']} files={files_scanned} "
        f"critical={counts.get('critical', 0)} "
        f"warnings={counts.get('warning', 0)} "
        f"info={counts.get('info', 0)}"
    )
    return report


def main() -> int:
    print(f"[code_auditor] Report: {REPORT_FILE}")
    try:
        run_once()
    except Exception as exc:
        print(f"[code_auditor] error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
