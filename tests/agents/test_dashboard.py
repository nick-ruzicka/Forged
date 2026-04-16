"""Live status dashboard for the Forge testing agents. Reads JSON reports and renders HTML."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from flask import Flask

PORT = 8091
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"

app = Flask(__name__)


def _load_json(name: str) -> dict | None:
    path = REPORT_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _count_class(passed: int, failed: int) -> str:
    if failed == 0 and passed > 0:
        return "ok"
    if failed > 0:
        return "fail"
    return "pending"


def _render_api(report: dict | None) -> str:
    if not report:
        return "<section class='card pending'><h2>API Tester</h2><p>No report yet.</p></section>"
    cls = _count_class(report["passed"], report["failed"])
    failures = [r for r in report.get("results", []) if not r.get("passed")]
    rows = []
    for r in failures:
        rows.append(
            f"<tr><td>{escape(r['method'])}</td>"
            f"<td>{escape(r['endpoint'])}</td>"
            f"<td>{escape(str(r.get('status_code')))}</td>"
            f"<td class='err'>{escape(str(r.get('error_message') or ''))}</td></tr>"
        )
    table = ""
    if rows:
        table = (
            "<table><thead><tr><th>Method</th><th>Endpoint</th>"
            "<th>Status</th><th>Error</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    return f"""
    <section class='card {cls}'>
      <h2>API Tester</h2>
      <p class='meta'>Last run: {escape(report.get('timestamp', '—'))}</p>
      <p class='stat'>
        <span class='ok-num'>{report['passed']}</span> passed &nbsp;
        <span class='fail-num'>{report['failed']}</span> failed &nbsp;
        <span class='total-num'>{report['total']}</span> total
      </p>
      {table or "<p class='ok-text'>All endpoints healthy.</p>"}
    </section>
    """


def _render_ui(report: dict | None) -> str:
    if not report:
        return "<section class='card pending'><h2>UI Tester</h2><p>No report yet.</p></section>"
    cls = _count_class(report["passed"], report["failed"])
    failures = [r for r in report.get("results", []) if not r.get("passed")]
    rows = []
    for r in failures:
        shot = ""
        if r.get("screenshot_path"):
            shot = (f"<a href='/screenshot/{escape(Path(r['screenshot_path']).name)}' "
                    f"target='_blank'>screenshot</a>")
        rows.append(
            f"<tr><td>{escape(r['page'])}</td>"
            f"<td>{escape(r['test_name'])}</td>"
            f"<td class='err'>{escape(str(r.get('error_message') or ''))}</td>"
            f"<td>{shot}</td></tr>"
        )
    table = ""
    if rows:
        table = (
            "<table><thead><tr><th>Page</th><th>Test</th>"
            "<th>Error</th><th>Evidence</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    return f"""
    <section class='card {cls}'>
      <h2>UI Tester</h2>
      <p class='meta'>Last run: {escape(report.get('timestamp', '—'))}</p>
      <p class='stat'>
        <span class='ok-num'>{report['passed']}</span> passed &nbsp;
        <span class='fail-num'>{report['failed']}</span> failed &nbsp;
        <span class='total-num'>{report['total']}</span> total
      </p>
      {table or "<p class='ok-text'>All UI checks passing.</p>"}
    </section>
    """


def _render_ux(report: dict | None) -> str:
    if not report:
        return "<section class='card pending'><h2>UX Auditor</h2><p>No report yet.</p></section>"
    counts = report.get("counts", {})
    high = counts.get("high", 0)
    medium = counts.get("medium", 0)
    low = counts.get("low", 0)
    cls = "fail" if high else ("warn" if medium else "ok")

    # Top findings by severity
    all_findings: list = []
    for page_rep in report.get("pages", []):
        for f in page_rep.get("findings", []):
            all_findings.append({**f, "page": page_rep.get("page", "?")})
    order = {"high": 0, "medium": 1, "low": 2}
    top = sorted(all_findings, key=lambda f: order.get(f.get("severity"), 9))[:10]
    rows = []
    for f in top:
        rows.append(
            f"<tr><td class='sev-{escape(f.get('severity','low'))}'>"
            f"{escape(f.get('severity',''))}</td>"
            f"<td>{escape(f.get('page',''))}</td>"
            f"<td>{escape(f.get('category',''))}</td>"
            f"<td>{escape((f.get('observation') or '')[:150])}</td>"
            f"<td>{escape((f.get('fix') or '')[:120])}</td></tr>"
        )
    table = ""
    if rows:
        table = (
            "<table><thead><tr><th>Sev</th><th>Page</th><th>Category</th>"
            "<th>Observation</th><th>Fix</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    return f"""
    <section class='card {cls}'>
      <h2>UX Auditor</h2>
      <p class='meta'>Last run: {escape(report.get('timestamp', '—'))}
         &nbsp; pages: {len(report.get('pages', []))}</p>
      <p class='stat'>
        <span class='fail-num'>{high}</span> high &nbsp;
        <span class='warn-num'>{medium}</span> medium &nbsp;
        <span class='total-num'>{low}</span> low
      </p>
      {table or "<p class='ok-text'>No findings this cycle.</p>"}
    </section>
    """


def _render_audit(report: dict | None) -> str:
    if not report:
        return "<section class='card pending'><h2>Code Auditor</h2><p>No report yet.</p></section>"
    counts = report.get("counts", {})
    critical = counts.get("critical", 0)
    warning = counts.get("warning", 0)
    info = counts.get("info", 0)
    cls = "fail" if critical else ("warn" if warning else "ok")

    findings = report.get("findings", [])
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    top = sorted(findings, key=lambda f: severity_order.get(f["severity"], 99))[:10]
    rows = []
    for f in top:
        rows.append(
            f"<tr><td class='sev-{escape(f['severity'])}'>{escape(f['severity'])}</td>"
            f"<td>{escape(f['file'])}:{f['line_number']}</td>"
            f"<td>{escape(f['issue_type'])}</td>"
            f"<td>{escape(f['description'])}</td></tr>"
        )
    table = ""
    if rows:
        table = (
            "<table><thead><tr><th>Severity</th><th>Location</th>"
            "<th>Type</th><th>Description</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    return f"""
    <section class='card {cls}'>
      <h2>Code Auditor</h2>
      <p class='meta'>Last run: {escape(report.get('timestamp', '—'))}
         &nbsp; files: {report.get('files_scanned', 0)}</p>
      <p class='stat'>
        <span class='fail-num'>{critical}</span> critical &nbsp;
        <span class='warn-num'>{warning}</span> warnings &nbsp;
        <span class='total-num'>{info}</span> info
      </p>
      {table or "<p class='ok-text'>No findings.</p>"}
    </section>
    """


STYLES = """
body { background:#0a0a0a; color:#e0e0e0; font-family:-apple-system,Segoe UI,sans-serif;
       margin:0; padding:24px; }
h1 { font-weight:600; letter-spacing:-0.02em; margin:0 0 8px 0; }
.sub { color:#888; margin:0 0 24px 0; font-size:13px; }
.grid { display:grid; grid-template-columns:1fr; gap:16px; max-width:1100px; }
.card { background:#141414; border:1px solid #2a2a2a; border-radius:8px; padding:20px; }
.card.ok { border-left:4px solid #4CAF50; }
.card.fail { border-left:4px solid #f44336; }
.card.warn { border-left:4px solid #FF9800; }
.card.pending { border-left:4px solid #555; }
.card h2 { margin:0 0 6px 0; font-size:16px; }
.meta { color:#888; font-size:12px; margin:0 0 12px 0; }
.stat { margin:0 0 14px 0; font-size:14px; }
.ok-num { color:#4CAF50; font-weight:600; }
.fail-num { color:#f44336; font-weight:600; }
.warn-num { color:#FF9800; font-weight:600; }
.total-num { color:#888; }
.ok-text { color:#4CAF50; font-size:13px; }
.err { color:#f88; font-family:ui-monospace,monospace; font-size:12px; }
table { width:100%; border-collapse:collapse; margin-top:8px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid #222;
         font-size:12px; vertical-align:top; }
th { color:#888; font-weight:500; }
.sev-critical { color:#f44336; font-weight:600; }
.sev-warning  { color:#FF9800; }
.sev-info     { color:#888; }
a { color:#0066FF; text-decoration:none; }
a:hover { text-decoration:underline; }
"""


@app.route("/")
def dashboard():
    api = _load_json("api_report.json")
    ui = _load_json("ui_report.json")
    audit = _load_json("code_audit.json")
    ux = _load_json("ux_report.json")

    return (
        "<!doctype html><html><head>"
        "<meta charset='utf-8'>"
        "<meta http-equiv='refresh' content='30'>"
        "<title>Forge — Test Dashboard</title>"
        f"<style>{STYLES}</style></head><body>"
        "<h1>Forge Test Dashboard</h1>"
        "<p class='sub'>Auto-refreshes every 30 seconds. "
        "API + UI + code audit + UX audit agents running continuously.</p>"
        "<div class='grid'>"
        f"{_render_api(api)}"
        f"{_render_ui(ui)}"
        f"{_render_ux(ux)}"
        f"{_render_audit(audit)}"
        "</div>"
        "</body></html>"
    )


@app.route("/screenshot/<name>")
def screenshot(name: str):
    from flask import send_from_directory, abort
    shots = REPORT_DIR / "screenshots"
    if not (shots / name).exists():
        abort(404)
    return send_from_directory(str(shots), name)


if __name__ == "__main__":
    print(f"[test_dashboard] starting on http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
