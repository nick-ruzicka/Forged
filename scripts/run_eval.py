"""
T-EVAL — pipeline evaluation harness.

Iterates tests/eval/corpus/*.json, submits each to POST /api/tools/submit,
polls GET /api/tools/<id> until the tool reaches a terminal status
(approved | rejected | needs_changes) or the 5-minute timeout fires.
For each item, records one row in `eval_runs` with load_test_run = FALSE:

    corpus_item_id         — the corpus file's `id` field
    tool_id                — the Forge tool id (NULL if pre-flight 400'd)
    expected_outcome       — derived from corpus `label`
    actual_outcome         — 'should_pass' | 'should_reject' | NULL
    expected_security_tier — from corpus
    actual_security_tier   — from the Forge tool row after review
    agent_verdicts         — full agent_reviews row via /api/agent/review/<id>
                             (or NULL if unavailable)
    latency_ms             — submit -> terminal status
    error                  — human-readable failure note (if any)

Run:
    venv/bin/python3 scripts/run_eval.py \\
        [--corpus tests/eval/corpus] \\
        [--base-url http://localhost:8090] \\
        [--timeout 300] \\
        [--only gtm_sdr_cold_email_draft,adv_pii_bomb]

The harness is idempotent: re-running appends fresh eval_runs rows;
it never mutates existing rows. A preflight rejection (HTTP 400 with
error=preflight_failed) is treated as a valid terminal `should_reject`
outcome — catching bad submissions at preflight is a feature of the
pipeline, not a harness failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import psycopg2
import psycopg2.extras
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "tests" / "eval" / "corpus"
DEFAULT_BASE_URL = os.environ.get("FORGE_API_URL", "http://localhost:8090")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://forge:forge@localhost:5432/forge"
)

TERMINAL_STATUSES = {"approved", "rejected", "needs_changes"}
POLL_INTERVAL_SEC = 2.0


def _load_corpus(corpus_dir: Path) -> list[dict]:
    if not corpus_dir.exists():
        raise SystemExit(f"corpus dir not found: {corpus_dir}")
    items = []
    for p in sorted(corpus_dir.iterdir()):
        if p.suffix != ".json":
            continue
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise SystemExit(f"bad JSON in {p.name}: {e}")
    return items


def _submit(base_url: str, submission: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/tools/submit. Return (status_code, body_json_or_error_dict)."""
    url = f"{base_url.rstrip('/')}/api/tools/submit"
    try:
        r = requests.post(url, json=submission, timeout=30)
    except requests.RequestException as e:
        return 0, {"error": "transport", "message": str(e)}
    try:
        body = r.json()
    except ValueError:
        body = {"error": "non_json", "message": r.text[:300]}
    return r.status_code, body


def _poll_tool(base_url: str, tool_id: int, timeout_sec: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Poll until tool.status is terminal. Return (tool_dict, error_or_none)."""
    deadline = time.time() + timeout_sec
    url = f"{base_url.rstrip('/')}/api/tools/{tool_id}"
    last_status = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=15)
        except requests.RequestException as e:
            time.sleep(POLL_INTERVAL_SEC)
            continue
        if r.status_code != 200:
            time.sleep(POLL_INTERVAL_SEC)
            continue
        body = r.json()
        last_status = body.get("status")
        if last_status in TERMINAL_STATUSES:
            return body, None
        time.sleep(POLL_INTERVAL_SEC)
    return None, f"timeout after {timeout_sec}s (last status={last_status})"


def _fetch_agent_review(base_url: str, tool_id: int) -> Optional[Dict[str, Any]]:
    """GET /api/agent/review/<tool_id> — may 404 for rejected-at-preflight tools."""
    url = f"{base_url.rstrip('/')}/api/agent/review/{tool_id}"
    try:
        r = requests.get(url, timeout=10)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _map_status_to_outcome(status: str) -> str:
    # approved -> should_pass; rejected or needs_changes -> should_reject
    if status == "approved":
        return "should_pass"
    return "should_reject"


def _insert_eval_run(conn, row: Dict[str, Any]) -> int:
    sql = """
    INSERT INTO eval_runs (
        corpus_item_id, tool_id, expected_outcome, actual_outcome,
        expected_security_tier, actual_security_tier, agent_verdicts,
        latency_ms, error, load_test_run, completed_at
    ) VALUES (
        %(corpus_item_id)s, %(tool_id)s, %(expected_outcome)s, %(actual_outcome)s,
        %(expected_security_tier)s, %(actual_security_tier)s,
        %(agent_verdicts)s::jsonb, %(latency_ms)s, %(error)s,
        FALSE, %(completed_at)s
    ) RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)
        eval_id = cur.fetchone()[0]
    conn.commit()
    return eval_id


def _run_one(conn, base_url: str, item: Dict[str, Any], timeout_sec: int) -> Dict[str, Any]:
    corpus_id = item["id"]
    expected_outcome = item["label"]
    expected_tier = item.get("expected_security_tier")
    submission = item["submission"]

    t0 = time.time()
    status_code, body = _submit(base_url, submission)
    tool_id: Optional[int] = None
    actual_outcome: Optional[str] = None
    actual_tier: Optional[int] = None
    agent_verdicts: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    if status_code == 201 and isinstance(body, dict) and "id" in body:
        tool_id = int(body["id"])
        tool_row, poll_err = _poll_tool(base_url, tool_id, timeout_sec)
        if tool_row is None:
            error = poll_err or "poll_failed"
        else:
            actual_outcome = _map_status_to_outcome(tool_row.get("status") or "")
            actual_tier = tool_row.get("security_tier")
            agent_verdicts = _fetch_agent_review(base_url, tool_id)
    elif status_code == 400 and isinstance(body, dict) and body.get("error") in (
        "preflight_failed", "validation"
    ):
        # Preflight rejection is a valid terminal "should_reject" — the
        # pipeline caught it before agents ran.
        actual_outcome = "should_reject"
        error = f"preflight: {body.get('message', '')[:200]}"
    else:
        error = f"submit_failed http={status_code} body={json.dumps(body)[:300]}"

    latency_ms = int((time.time() - t0) * 1000)

    row = {
        "corpus_item_id": corpus_id,
        "tool_id": tool_id,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "expected_security_tier": expected_tier,
        "actual_security_tier": actual_tier,
        "agent_verdicts": json.dumps(agent_verdicts) if agent_verdicts is not None else None,
        "latency_ms": latency_ms,
        "error": error,
        "completed_at": datetime.utcnow(),
    }
    eval_id = _insert_eval_run(conn, row)
    row["eval_run_id"] = eval_id
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="T-EVAL corpus harness")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--timeout", type=int, default=300, help="per-item poll timeout (seconds)")
    ap.add_argument("--only", default="", help="comma-sep corpus ids to run (subset)")
    args = ap.parse_args()

    corpus = _load_corpus(Path(args.corpus))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        corpus = [c for c in corpus if c["id"] in wanted]
        if not corpus:
            print(f"no corpus items matched --only={args.only}", file=sys.stderr)
            return 2

    print(f"[eval] base_url={args.base_url}  items={len(corpus)}  timeout={args.timeout}s")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        ok_match = 0
        ok_mismatch = 0
        errored = 0
        for i, item in enumerate(corpus, 1):
            cid = item["id"]
            print(f"[{i:02d}/{len(corpus)}] {cid} (expect={item['label']}) ...", flush=True)
            try:
                row = _run_one(conn, args.base_url, item, args.timeout)
            except Exception as e:
                print(f"    FATAL running {cid}: {e}", file=sys.stderr)
                errored += 1
                continue
            actual = row["actual_outcome"]
            if actual is None:
                errored += 1
                status = f"ERROR ({row['error']})"
            elif actual == row["expected_outcome"]:
                ok_match += 1
                status = "match"
            else:
                ok_mismatch += 1
                status = f"MISMATCH (got {actual})"
            print(
                f"    -> {status}  tool_id={row['tool_id']}  "
                f"tier={row['actual_security_tier']}  "
                f"latency={row['latency_ms']}ms  eval_run_id={row['eval_run_id']}"
            )
        print(
            f"[eval] done. match={ok_match} mismatch={ok_mismatch} error={errored}"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
