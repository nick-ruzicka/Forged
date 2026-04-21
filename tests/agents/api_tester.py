"""API testing agent. Hits every Forge endpoint once and exits non-zero on failure."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = os.environ.get("FORGE_URL", "http://localhost:8090")
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "api_report.json"
FAILURE_LOG = REPORT_DIR / "api_failures.log"
ALERT_LOG = REPORT_DIR / "alerts.log"

CONSECUTIVE_FAIL_THRESHOLD = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hit(method: str, path: str, **kwargs) -> dict:
    url = f"{BASE_URL}{path}"
    start = time.time()
    result = {
        "endpoint": path,
        "method": method,
        "status_code": None,
        "response_time_ms": None,
        "passed": False,
        "error_message": None,
        "response_preview": None,
    }
    try:
        resp = requests.request(method, url, timeout=40, **kwargs)
        result["status_code"] = resp.status_code
        result["response_time_ms"] = int((time.time() - start) * 1000)
        try:
            result["response_preview"] = resp.json()
        except Exception:
            result["response_preview"] = resp.text[:500]
    except requests.exceptions.RequestException as exc:
        result["error_message"] = f"request failed: {exc}"
        result["response_time_ms"] = int((time.time() - start) * 1000)
    return result


def check_health() -> dict:
    r = hit("GET", "/api/health")
    if r["status_code"] == 200 and isinstance(r["response_preview"], dict):
        body = r["response_preview"]
        if all(k in body for k in ("status", "version", "timestamp")):
            r["passed"] = True
        else:
            r["error_message"] = "missing keys in health response"
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_list_tools() -> dict:
    r = hit("GET", "/api/tools")
    if r["status_code"] == 200 and isinstance(r["response_preview"], dict):
        if "tools" in r["response_preview"]:
            r["passed"] = True
        else:
            r["error_message"] = "'tools' key missing from list response"
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_tool_by_slug() -> dict:
    r = hit("GET", "/api/tools/slug/account-research-brief")
    if r["status_code"] == 200 and isinstance(r["response_preview"], dict):
        if "input_schema" in r["response_preview"] or (
            "tool" in r["response_preview"] and "input_schema" in r["response_preview"]["tool"]
        ):
            r["passed"] = True
        else:
            r["error_message"] = "no input_schema in tool response"
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_list_skills() -> dict:
    r = hit("GET", "/api/skills")
    if r["status_code"] == 200:
        r["passed"] = True
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_run_tool() -> tuple[dict, int | None]:
    body = {
        "inputs": {
            "company_name": "Acme Corp",
            "company_website": "acme.example.com",
            "segment": "Mid-Market",
        },
        "user_name": "test_agent",
        "user_email": "test@forge.internal",
    }
    r = hit("POST", "/api/tools/slug/account-research-brief/run", json=body)
    run_id = None
    if r["status_code"] == 200 and isinstance(r["response_preview"], dict):
        preview = r["response_preview"]
        if "output" in preview or "output_data" in preview or "result" in preview:
            r["passed"] = True
            run_id = preview.get("run_id") or preview.get("id")
        else:
            r["error_message"] = "no output field in run response"
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r, run_id


def check_rate_run(run_id: int | None) -> dict:
    if run_id is None:
        return {
            "endpoint": "/api/runs/<id>/rate",
            "method": "POST",
            "status_code": None,
            "response_time_ms": 0,
            "passed": False,
            "error_message": "skipped: no run_id from previous step",
        }
    r = hit("POST", f"/api/runs/{run_id}/rate", json={"rating": 4})
    if r["status_code"] == 200:
        r["passed"] = True
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_agent_status() -> dict:
    r = hit("GET", "/api/agent/status/1")
    if r["status_code"] == 200:
        r["passed"] = True
    elif not r["error_message"]:
        r["error_message"] = f"expected 200, got {r['status_code']}"
    return r


def check_app_html() -> dict:
    """GET /apps/<slug> should return HTML with the injected ForgeAPI SDK.

    Fetches the full body directly (hit()'s preview truncates at 500 chars).
    """
    path = "/apps/job-search-pipeline"
    url = f"{BASE_URL}{path}"
    start = time.time()
    result = {
        "endpoint": path,
        "method": "GET",
        "status_code": None,
        "response_time_ms": None,
        "passed": False,
        "error_message": None,
        "response_preview": None,
    }
    try:
        resp = requests.get(url, timeout=15)
        result["status_code"] = resp.status_code
        result["response_time_ms"] = int((time.time() - start) * 1000)
        if resp.status_code != 200:
            result["error_message"] = f"expected 200, got {resp.status_code}"
            return result
        body = resp.text
        result["response_preview"] = body[:500]
        if "ForgeAPI" in body or "FORGE_APP" in body:
            result["passed"] = True
        else:
            result["error_message"] = "HTML body missing ForgeAPI / FORGE_APP injection"
    except requests.exceptions.RequestException as exc:
        result["error_message"] = f"request failed: {exc}"
        result["response_time_ms"] = int((time.time() - start) * 1000)
    return result


def check_apps_analyze() -> dict:
    """POST /api/apps/analyze should classify a tiny HTML snippet."""
    sample = "<html><body><h1>Hello</h1><input name='name'></body></html>"
    r = hit("POST", "/api/apps/analyze", json={"html": sample})
    if r["status_code"] != 200:
        if not r["error_message"]:
            r["error_message"] = f"expected 200, got {r['status_code']}"
        return r
    body = r.get("response_preview")
    if isinstance(body, dict) and body.get("suggested_name"):
        r["passed"] = True
    else:
        r["error_message"] = "response missing suggested_name"
    return r


def check_app_data_roundtrip() -> dict:
    """POST then GET /api/apps/<id>/data/<key> — the value must round-trip."""
    key = "test-key"
    payload = {"value": {"hello": "world", "stamp": int(time.time())}}
    post_r = hit("POST", f"/api/apps/1/data/{key}", json=payload)
    if post_r["status_code"] != 200:
        r = post_r
        if not r["error_message"]:
            r["error_message"] = f"POST expected 200, got {r['status_code']}"
        r["endpoint"] = f"/api/apps/1/data/{key} (roundtrip)"
        return r

    get_r = hit("GET", f"/api/apps/1/data/{key}")
    get_r["endpoint"] = f"/api/apps/1/data/{key} (roundtrip)"
    if get_r["status_code"] != 200:
        if not get_r["error_message"]:
            get_r["error_message"] = f"GET expected 200, got {get_r['status_code']}"
        return get_r
    body = get_r.get("response_preview") or {}
    if isinstance(body, dict) and body.get("found"):
        get_r["passed"] = True
    else:
        get_r["error_message"] = "GET after POST: expected found=true, got " + str(body)[:200]
    return get_r


def run_cycle(consecutive_failures: dict) -> dict:
    results = []
    results.append(check_health())
    results.append(check_list_tools())
    results.append(check_tool_by_slug())
    results.append(check_list_skills())
    run_result, run_id = check_run_tool()
    results.append(run_result)
    results.append(check_rate_run(run_id))
    results.append(check_agent_status())
    results.append(check_app_html())
    results.append(check_apps_analyze())
    results.append(check_app_data_roundtrip())

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    for r in results:
        key = f"{r['method']} {r['endpoint']}"
        if r["passed"]:
            consecutive_failures[key] = 0
        else:
            consecutive_failures[key] += 1
            _log_failure(r)
            if consecutive_failures[key] >= CONSECUTIVE_FAIL_THRESHOLD:
                _log_alert(key, consecutive_failures[key], r)

    report = {
        "timestamp": now(),
        "base_url": BASE_URL,
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "results": results,
        "consecutive_failures": dict(consecutive_failures),
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    return report


def _log_failure(r: dict) -> None:
    entry = {
        "timestamp": now(),
        "endpoint": r["endpoint"],
        "method": r["method"],
        "status_code": r["status_code"],
        "error_message": r["error_message"],
        "response_preview": r["response_preview"],
    }
    with FAILURE_LOG.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _log_alert(key: str, count: int, r: dict) -> None:
    line = (
        f"{now()} CRITICAL {key} failed {count} consecutive cycles. "
        f"status={r['status_code']} error={r['error_message']}\n"
    )
    with ALERT_LOG.open("a") as fh:
        fh.write(line)
    print(line.rstrip())


def main() -> int:
    consecutive_failures: dict = defaultdict(int)
    print(f"[api_tester] Base URL: {BASE_URL}. Report: {REPORT_FILE}")
    try:
        report = run_cycle(consecutive_failures)
    except Exception as exc:
        print(f"[api_tester] error: {exc}")
        return 1
    print(
        f"[api_tester] {report['timestamp']} "
        f"passed={report['passed']} failed={report['failed']}"
    )
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
