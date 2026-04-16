"""
T-EVAL — read eval_runs, compute metrics, emit markdown.

Metrics:
  * Precision / Recall / F1 for the should_reject class, plus a
    security-weighted F1 where false negatives (the pipeline let
    through a tool we expected it to block) count 3x. False negatives
    are the real risk here — a missed adversarial submission is the
    incident; a false positive is a ticket.
  * Accuracy per adversarial subcategory (one row per category).
  * Latency p50 / p95 / p99 reported separately for:
       - corpus runs (load_test_run = FALSE)
       - load-test runs (load_test_run = TRUE)

Only the most recent eval run per corpus item is scored for precision/
recall (so re-running the harness doesn't double-count). Load latency
uses every row.

Usage:
    venv/bin/python3 scripts/generate_eval_report.py \\
        [--db postgresql://forge:forge@localhost:5432/forge] \\
        [--out tests/eval/REPORT.md]

The script prints the markdown to stdout AND writes it to `--out`
(default tests/eval/REPORT.md). Exit code is 0 even when metrics are
bad — this is a reporter, not a gate.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "tests" / "eval" / "REPORT.md"
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://forge:forge@localhost:5432/forge"
)

FN_WEIGHT = 3  # security-weighted F1: FN costs 3x a FP


def _percentile(values: List[int], pct: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (pct / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _fetch_latest_corpus_rows(conn) -> List[Dict[str, Any]]:
    """One row per corpus_item_id — the most recent corpus (non-load) eval_run."""
    sql = """
    SELECT DISTINCT ON (corpus_item_id)
        id, corpus_item_id, tool_id, expected_outcome, actual_outcome,
        expected_security_tier, actual_security_tier,
        latency_ms, error, created_at
    FROM eval_runs
    WHERE load_test_run = FALSE
    ORDER BY corpus_item_id, created_at DESC, id DESC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def _fetch_corpus_latencies(conn) -> List[int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT latency_ms FROM eval_runs "
            "WHERE load_test_run=FALSE AND latency_ms IS NOT NULL"
        )
        return [r[0] for r in cur.fetchall()]


def _fetch_load_latencies(conn) -> List[int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT latency_ms FROM eval_runs "
            "WHERE load_test_run=TRUE AND latency_ms IS NOT NULL"
        )
        return [r[0] for r in cur.fetchall()]


def _load_corpus_catalog() -> Dict[str, Dict[str, Any]]:
    """Read corpus dir to recover category labels (adversarial subcategories)."""
    out: Dict[str, Dict[str, Any]] = {}
    corpus_dir = REPO_ROOT / "tests" / "eval" / "corpus"
    if not corpus_dir.exists():
        return out
    for p in sorted(corpus_dir.iterdir()):
        if p.suffix != ".json":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out[d["id"]] = {
            "category": d.get("category", ""),
            "label": d.get("label", ""),
            "expected_security_tier": d.get("expected_security_tier"),
        }
    return out


def _confusion(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Confusion on the should_reject class (positive = should_reject)."""
    tp = fp = tn = fn = skipped = 0
    for r in rows:
        exp = r["expected_outcome"]
        act = r["actual_outcome"]
        if act is None:
            skipped += 1
            continue
        exp_pos = exp == "should_reject"
        act_pos = act == "should_reject"
        if exp_pos and act_pos:
            tp += 1
        elif exp_pos and not act_pos:
            fn += 1
        elif (not exp_pos) and act_pos:
            fp += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "skipped": skipped}


def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def _weighted_f1(tp: int, fp: int, fn: int, fn_weight: int = FN_WEIGHT) -> float:
    """F-beta where FN weight is higher. Equivalent to F_beta with beta^2 = fn_weight."""
    if tp == 0 and fp == 0 and fn == 0:
        return 0.0
    beta_sq = float(fn_weight)
    denom = (1 + beta_sq) * tp + beta_sq * fn + fp
    if denom == 0:
        return 0.0
    return (1 + beta_sq) * tp / denom


def _accuracy_by_category(
    rows: List[Dict[str, Any]], catalog: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, int]] = {}
    for r in rows:
        meta = catalog.get(r["corpus_item_id"], {})
        cat = meta.get("category", "unknown")
        b = buckets.setdefault(cat, {"total": 0, "correct": 0, "errored": 0})
        b["total"] += 1
        if r["actual_outcome"] is None:
            b["errored"] += 1
            continue
        if r["actual_outcome"] == r["expected_outcome"]:
            b["correct"] += 1
    out = []
    for cat, b in sorted(buckets.items()):
        acc = (b["correct"] / b["total"]) if b["total"] else 0.0
        out.append({
            "category": cat,
            "total": b["total"],
            "correct": b["correct"],
            "errored": b["errored"],
            "accuracy": acc,
        })
    return out


def _tier_mismatches(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        exp = r["expected_security_tier"]
        act = r["actual_security_tier"]
        if exp is None or act is None:
            continue
        if exp != act:
            out.append({
                "corpus_item_id": r["corpus_item_id"],
                "expected": exp,
                "actual": act,
            })
    return out


def _false_negatives(rows: List[Dict[str, Any]]) -> List[str]:
    """Corpus IDs where we expected should_reject and got should_pass."""
    return [
        r["corpus_item_id"] for r in rows
        if r["expected_outcome"] == "should_reject"
           and r["actual_outcome"] == "should_pass"
    ]


def _false_positives(rows: List[Dict[str, Any]]) -> List[str]:
    return [
        r["corpus_item_id"] for r in rows
        if r["expected_outcome"] == "should_pass"
           and r["actual_outcome"] == "should_reject"
    ]


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x*100:.1f}%"


def _fmt_ms(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x:.0f}ms"


def build_report(conn) -> str:
    catalog = _load_corpus_catalog()
    rows = _fetch_latest_corpus_rows(conn)
    conf = _confusion(rows)
    prec, rec, f1 = _prf(conf["tp"], conf["fp"], conf["fn"])
    wf1 = _weighted_f1(conf["tp"], conf["fp"], conf["fn"])

    corpus_latencies = _fetch_corpus_latencies(conn)
    load_latencies = _fetch_load_latencies(conn)

    cats = _accuracy_by_category(rows, catalog)
    tier_bad = _tier_mismatches(rows)
    fns = _false_negatives(rows)
    fps = _false_positives(rows)

    total = len(rows)
    scored = total - conf["skipped"]
    overall_accuracy = (
        (conf["tp"] + conf["tn"]) / scored if scored else 0.0
    )

    lines: List[str] = []
    lines.append("# Forge Pipeline Evaluation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Corpus items evaluated (latest run each): **{total}**")
    lines.append(f"- Scored (actual_outcome present): **{scored}**   Errored/skipped: **{conf['skipped']}**")
    lines.append(f"- Overall accuracy: **{_fmt_pct(overall_accuracy)}**")
    lines.append("")
    lines.append("### Reject-class metrics (positive = should_reject)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| TP (caught adversarial) | {conf['tp']} |")
    lines.append(f"| FP (false alarm on benign) | {conf['fp']} |")
    lines.append(f"| FN (missed adversarial — SECURITY RISK) | **{conf['fn']}** |")
    lines.append(f"| TN (correctly passed benign) | {conf['tn']} |")
    lines.append(f"| Precision | {_fmt_pct(prec)} |")
    lines.append(f"| Recall | {_fmt_pct(rec)} |")
    lines.append(f"| F1 | {_fmt_pct(f1)} |")
    lines.append(f"| Security-weighted F1 (FN weight = {FN_WEIGHT}x FP) | {_fmt_pct(wf1)} |")
    lines.append("")

    if fns:
        lines.append("### False negatives (MISSED ADVERSARIAL — top priority)")
        lines.append("")
        for cid in fns:
            meta = catalog.get(cid, {})
            lines.append(f"- `{cid}`  (category: {meta.get('category','?')})")
        lines.append("")
    else:
        lines.append("### False negatives")
        lines.append("")
        lines.append("None. Every should_reject item was caught.")
        lines.append("")

    if fps:
        lines.append("### False positives (benign items blocked)")
        lines.append("")
        for cid in fps:
            meta = catalog.get(cid, {})
            lines.append(f"- `{cid}`  (category: {meta.get('category','?')})")
        lines.append("")

    lines.append("## Accuracy by subcategory")
    lines.append("")
    lines.append("| Category | Total | Correct | Errored | Accuracy |")
    lines.append("|---|---:|---:|---:|---:|")
    for c in cats:
        lines.append(
            f"| {c['category']} | {c['total']} | {c['correct']} | {c['errored']} | "
            f"{_fmt_pct(c['accuracy'])} |"
        )
    lines.append("")

    lines.append("## Security-tier mismatches")
    lines.append("")
    if tier_bad:
        lines.append("| Corpus ID | Expected | Actual |")
        lines.append("|---|---:|---:|")
        for t in tier_bad:
            lines.append(f"| `{t['corpus_item_id']}` | {t['expected']} | {t['actual']} |")
    else:
        lines.append("No tier mismatches where both expected and actual are present.")
    lines.append("")

    lines.append("## Latency")
    lines.append("")
    lines.append("| Source | N | p50 | p95 | p99 |")
    lines.append("|---|---:|---:|---:|---:|")
    lines.append(
        f"| Corpus | {len(corpus_latencies)} | "
        f"{_fmt_ms(_percentile(corpus_latencies,50))} | "
        f"{_fmt_ms(_percentile(corpus_latencies,95))} | "
        f"{_fmt_ms(_percentile(corpus_latencies,99))} |"
    )
    lines.append(
        f"| Load | {len(load_latencies)} | "
        f"{_fmt_ms(_percentile(load_latencies,50))} | "
        f"{_fmt_ms(_percentile(load_latencies,95))} | "
        f"{_fmt_ms(_percentile(load_latencies,99))} |"
    )
    lines.append("")

    lines.append("## Per-item detail (latest corpus run)")
    lines.append("")
    lines.append("| Corpus ID | Category | Expected | Actual | Tier exp/act | Latency | Error |")
    lines.append("|---|---|---|---|---|---:|---|")
    for r in rows:
        meta = catalog.get(r["corpus_item_id"], {})
        err = (r.get("error") or "").replace("|", "/").replace("\n", " ")
        if len(err) > 60:
            err = err[:57] + "..."
        tier = f"{r.get('expected_security_tier')}/{r.get('actual_security_tier')}"
        lines.append(
            f"| `{r['corpus_item_id']}` | {meta.get('category','')} | "
            f"{r['expected_outcome']} | {r['actual_outcome']} | {tier} | "
            f"{_fmt_ms(r.get('latency_ms'))} | {err} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("Notes: FN = pipeline accepted an adversarial submission. These are the "
                 "items to triage first. Corpus latency is the submit→terminal round-trip, "
                 "not the model call. Load latency is only meaningful when the system is "
                 "concurrently saturated; spread across 20 threads it is a ceiling estimate.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="T-EVAL report generator")
    ap.add_argument("--db", default=DATABASE_URL)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    conn = psycopg2.connect(args.db)
    try:
        md = build_report(conn)
    finally:
        conn.close()

    sys.stdout.write(md)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    sys.stderr.write(f"\n[report] wrote {out_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
