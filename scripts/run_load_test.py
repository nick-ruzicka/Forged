"""
T-EVAL load test — 'does it scale?' demo data.

Picks 5 known-good (should_pass) realistic GTM corpus items and submits each
20 times concurrently, for 100 submissions total. Each submission is a POST
to /api/tools/submit followed by a poll of /api/tools/<id> until a terminal
status or until the per-item timeout fires. Results are written to
`eval_runs` with load_test_run = TRUE so the reporter can split corpus vs.
load numbers.

Submission-time latency is what we measure here (submit -> terminal status).
We deliberately do NOT de-dupe by name; instead, each copy's name is
suffixed with a worker/replica tag so unique-slug enforcement on the
server doesn't 400 us.

Usage:
    venv/bin/python3 scripts/run_load_test.py \\
        [--base-url http://localhost:8090] \\
        [--replicas 20] [--concurrency 20] \\
        [--timeout 540] \\
        [--only gtm_sdr_cold_email_draft,gtm_marops_utm_builder,...]

Design notes:
- 20 workers on 100 jobs should clear in well under 10 min even if
  per-item latency is ~5s average. If the pipeline is saturated and
  items stretch past `--timeout`, they are recorded with an error set.
- We authenticate as a new `author_email` per replica so Forge doesn't
  bucket them as one noisy user.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "tests" / "eval" / "corpus"
DEFAULT_BASE_URL = os.environ.get("FORGE_API_URL", "http://localhost:8090")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://forge:forge@localhost:5432/forge"
)

TERMINAL_STATUSES = {"approved", "rejected", "needs_changes"}
POLL_INTERVAL_SEC = 3.0

# Defaults — 5 realistic GTM items that should all pass preflight cleanly.
DEFAULT_LOAD_ITEMS = [
    "gtm_sdr_cold_email_draft",
    "gtm_sdr_call_opener",
    "gtm_marops_utm_builder",
    "gtm_marops_subject_line_ab",
    "gtm_csm_health_score_explainer",
]

_db_lock = threading.Lock()


def _load_corpus(corpus_dir: Path) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for p in sorted(corpus_dir.iterdir()):
        if p.suffix != ".json":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["id"]] = d
    return out


def _clone_submission(item: Dict[str, Any], replica: int) -> Dict[str, Any]:
    sub = json.loads(json.dumps(item["submission"]))
    tag = f"{replica:02d}-{uuid.uuid4().hex[:6]}"
    sub["name"] = f"{sub['name']} LOAD {tag}"
    sub["author_email"] = f"loadtest+{item['id']}+{tag}@forge.local"
    # force a unique slug suggestion
    sub["slug"] = f"eval-load-{item['id'].replace('_','-')}-{tag}"
    return sub


def _submit_and_wait(
    base_url: str, submission: Dict[str, Any], timeout_sec: int
) -> Tuple[int, Dict[str, Any], int]:
    """Returns (http_status_submit, final_body_or_error, latency_ms)."""
    t0 = time.time()
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/api/tools/submit",
            json=submission,
            timeout=30,
        )
    except requests.RequestException as e:
        return 0, {"error": "transport", "message": str(e)}, int((time.time() - t0) * 1000)

    try:
        body = r.json()
    except ValueError:
        body = {"error": "non_json", "message": r.text[:300]}

    if r.status_code != 201 or "id" not in body:
        return r.status_code, body, int((time.time() - t0) * 1000)

    tool_id = int(body["id"])
    deadline = time.time() + timeout_sec
    last_status = None
    while time.time() < deadline:
        try:
            g = requests.get(f"{base_url.rstrip('/')}/api/tools/{tool_id}", timeout=15)
        except requests.RequestException:
            time.sleep(POLL_INTERVAL_SEC)
            continue
        if g.status_code == 200:
            tj = g.json()
            last_status = tj.get("status")
            if last_status in TERMINAL_STATUSES:
                tj["_tool_id"] = tool_id
                return 201, tj, int((time.time() - t0) * 1000)
        time.sleep(POLL_INTERVAL_SEC)
    return 201, {
        "error": "poll_timeout",
        "tool_id": tool_id,
        "last_status": last_status,
    }, int((time.time() - t0) * 1000)


def _insert_load_row(conn, row: Dict[str, Any]) -> int:
    sql = """
    INSERT INTO eval_runs (
        corpus_item_id, tool_id, expected_outcome, actual_outcome,
        expected_security_tier, actual_security_tier, agent_verdicts,
        latency_ms, error, load_test_run, completed_at
    ) VALUES (
        %(corpus_item_id)s, %(tool_id)s, %(expected_outcome)s, %(actual_outcome)s,
        %(expected_security_tier)s, %(actual_security_tier)s,
        %(agent_verdicts)s::jsonb, %(latency_ms)s, %(error)s,
        TRUE, %(completed_at)s
    ) RETURNING id
    """
    with _db_lock:
        with conn.cursor() as cur:
            cur.execute(sql, row)
            eval_id = cur.fetchone()[0]
        conn.commit()
    return eval_id


def _worker(args_tuple):
    conn, base_url, item, replica, timeout_sec = args_tuple
    submission = _clone_submission(item, replica)
    http_status, body, latency_ms = _submit_and_wait(base_url, submission, timeout_sec)

    tool_id = body.get("_tool_id") or body.get("id") or body.get("tool_id")
    status = body.get("status")
    actual_outcome: Optional[str] = None
    error: Optional[str] = None
    if http_status == 201 and status in TERMINAL_STATUSES:
        actual_outcome = "should_pass" if status == "approved" else "should_reject"
    elif http_status == 201 and body.get("error") == "poll_timeout":
        error = f"poll_timeout (last={body.get('last_status')})"
    elif http_status == 400:
        actual_outcome = "should_reject"
        error = f"preflight: {body.get('message','')[:200]}"
    else:
        error = f"submit_failed http={http_status} body={json.dumps(body)[:250]}"

    row = {
        "corpus_item_id": item["id"],
        "tool_id": int(tool_id) if isinstance(tool_id, int) or (isinstance(tool_id, str) and str(tool_id).isdigit()) else None,
        "expected_outcome": item["label"],
        "actual_outcome": actual_outcome,
        "expected_security_tier": item.get("expected_security_tier"),
        "actual_security_tier": body.get("security_tier"),
        "agent_verdicts": None,  # agent-review payload dropped for load rows to keep the table light
        "latency_ms": latency_ms,
        "error": error,
        "completed_at": datetime.utcnow(),
    }
    eval_id = _insert_load_row(conn, row)
    row["eval_run_id"] = eval_id
    row["replica"] = replica
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="T-EVAL load test (100 concurrent submissions)")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--replicas", type=int, default=20, help="submissions per corpus item")
    ap.add_argument("--concurrency", type=int, default=20, help="thread pool size")
    ap.add_argument("--timeout", type=int, default=540, help="per-submission poll timeout (seconds)")
    ap.add_argument(
        "--only",
        default=",".join(DEFAULT_LOAD_ITEMS),
        help="comma-sep corpus ids to load (should all be should_pass items)",
    )
    args = ap.parse_args()

    corpus = _load_corpus(Path(args.corpus))
    wanted = [cid.strip() for cid in args.only.split(",") if cid.strip()]
    items = []
    for cid in wanted:
        if cid not in corpus:
            raise SystemExit(f"corpus item '{cid}' not found in {args.corpus}")
        if corpus[cid]["label"] != "should_pass":
            print(f"[warn] {cid} is label={corpus[cid]['label']} — including anyway", file=sys.stderr)
        items.append(corpus[cid])

    total = len(items) * args.replicas
    print(
        f"[load] base_url={args.base_url} items={len(items)} replicas/item={args.replicas} "
        f"total={total} concurrency={args.concurrency} timeout={args.timeout}s"
    )

    conn = psycopg2.connect(DATABASE_URL)
    t0 = time.time()
    try:
        jobs = [(conn, args.base_url, item, r, args.timeout) for item in items for r in range(args.replicas)]
        done = 0
        match = 0
        mismatch = 0
        errored = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(_worker, j) for j in jobs]
            for fut in as_completed(futures):
                done += 1
                try:
                    row = fut.result()
                except Exception as e:
                    errored += 1
                    print(f"[{done:03d}/{total}] WORKER CRASH: {e}", file=sys.stderr)
                    continue
                actual = row["actual_outcome"]
                if actual is None:
                    errored += 1
                    tag = f"ERROR ({row['error']})"
                elif actual == row["expected_outcome"]:
                    match += 1
                    tag = "match"
                else:
                    mismatch += 1
                    tag = f"MISMATCH ({actual})"
                print(
                    f"[{done:03d}/{total}] {row['corpus_item_id']:<40s} "
                    f"rep={row['replica']:02d} tool={row['tool_id']} {row['latency_ms']:>6d}ms {tag}",
                    flush=True,
                )
        elapsed = time.time() - t0
        print(f"[load] done in {elapsed:.1f}s  match={match} mismatch={mismatch} error={errored}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
