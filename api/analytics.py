"""
Forge analytics API — Blueprint owned by T-DASH.

Complements (does NOT duplicate) /api/admin/analytics owned by T4.
Register in server.py with:
    from api.analytics import analytics_bp
    app.register_blueprint(analytics_bp)

Auth: every route checks X-Admin-Key header against ADMIN_KEY env var.
"""
from __future__ import annotations

import logging
import os
from functools import wraps
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from psycopg2 import errors as pg_errors

from api import db

log = logging.getLogger("forge.analytics")

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _admin_key() -> str:
    return os.environ.get("ADMIN_KEY", "")


def check_admin_key(fn):
    """Decorator: require a matching X-Admin-Key header. Copied pattern from api/admin.py."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = _admin_key()
        provided = request.headers.get("X-Admin-Key", "")
        if not expected or provided != expected:
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


def _eval_runs_missing(exc: Exception) -> bool:
    """True if the exception indicates eval_runs table does not exist."""
    msg = str(exc).lower()
    if isinstance(exc, pg_errors.UndefinedTable):
        return True
    return "relation" in msg and "eval_runs" in msg and "does not exist" in msg


# -------- /funnel: single query building submission lifecycle counts --------

@analytics_bp.route("/funnel", methods=["GET"])
@check_admin_key
def funnel():
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE t.submitted_at IS NOT NULL)                       AS submitted,
            COUNT(*) FILTER (WHERE ar.completed_at IS NOT NULL)                      AS reviewed,
            COUNT(*) FILTER (WHERE t.status = 'approved')                            AS approved,
            COUNT(*) FILTER (WHERE t.run_count >= 1)                                 AS run_once,
            COUNT(*) FILTER (WHERE t.run_count >= 10)                                AS run_10x,
            COUNT(*) FILTER (WHERE t.last_run_at >= NOW() - INTERVAL '30 days')      AS active_30d
        FROM tools t
        LEFT JOIN LATERAL (
            SELECT completed_at FROM agent_reviews
            WHERE tool_id = t.id
            ORDER BY id DESC LIMIT 1
        ) ar ON TRUE
    """
    with db.get_db() as cur:
        cur.execute(sql)
        row = cur.fetchone() or {}

    return jsonify({
        "submitted":  int(row.get("submitted")  or 0),
        "reviewed":   int(row.get("reviewed")   or 0),
        "approved":   int(row.get("approved")   or 0),
        "run_once":   int(row.get("run_once")   or 0),
        "run_10x":    int(row.get("run_10x")    or 0),
        "active_30d": int(row.get("active_30d") or 0),
    })


# -------- /builders: author leaderboard --------

@analytics_bp.route("/builders", methods=["GET"])
@check_admin_key
def builders():
    sql = """
        SELECT
            COALESCE(NULLIF(t.author_email, ''), '(unknown)')  AS author_email,
            COALESCE(MAX(t.author_name), '')                   AS author_name,
            COUNT(*)                                           AS submissions,
            COALESCE(
                SUM(CASE WHEN t.status = 'approved' THEN 1 ELSE 0 END)::float
                / NULLIF(COUNT(*), 0),
                0
            )                                                  AS approval_rate,
            COALESCE(AVG(t.reliability_score)::real, 0)        AS avg_reliability,
            COALESCE(SUM(t.run_count), 0)                      AS total_runs
        FROM tools t
        WHERE COALESCE(t.author_email, '') <> ''
        GROUP BY COALESCE(NULLIF(t.author_email, ''), '(unknown)')
        ORDER BY total_runs DESC, submissions DESC
        LIMIT 20
    """
    with db.get_db() as cur:
        cur.execute(sql)
        rows = cur.fetchall() or []

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "author_email":    r["author_email"],
            "author_name":     r["author_name"] or r["author_email"],
            "submissions":     int(r["submissions"] or 0),
            "approval_rate":   round(float(r["approval_rate"] or 0), 3),
            "avg_reliability": round(float(r["avg_reliability"] or 0), 1),
            "total_runs":      int(r["total_runs"] or 0),
        })
    return jsonify({"builders": out})


# -------- /quality: eval_runs precision/recall --------

@analytics_bp.route("/quality", methods=["GET"])
@check_admin_key
def quality():
    sql = """
        SELECT
            COUNT(*)                                                                                  AS total,
            COUNT(*) FILTER (WHERE expected_outcome='should_reject' AND actual_outcome='should_reject') AS tp,
            COUNT(*) FILTER (WHERE expected_outcome='should_pass'   AND actual_outcome='should_reject') AS fp,
            COUNT(*) FILTER (WHERE expected_outcome='should_pass'   AND actual_outcome='should_pass')   AS tn,
            COUNT(*) FILTER (WHERE expected_outcome='should_reject' AND actual_outcome='should_pass')   AS fn
        FROM eval_runs
        WHERE actual_outcome IS NOT NULL
          AND completed_at IS NOT NULL
          AND load_test_run = FALSE
    """
    try:
        with db.get_db() as cur:
            cur.execute(sql)
            row = cur.fetchone() or {}
    except Exception as exc:
        if _eval_runs_missing(exc):
            return jsonify({"empty": True})
        log.warning("quality query failed: %s", exc)
        return jsonify({"empty": True})

    total = int(row.get("total") or 0)
    if total == 0:
        return jsonify({"empty": True})

    tp = int(row.get("tp") or 0)
    fp = int(row.get("fp") or 0)
    tn = int(row.get("tn") or 0)
    fn = int(row.get("fn") or 0)
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall    = (tp / (tp + fn)) if (tp + fn) else 0.0

    return jsonify({
        "empty": False,
        "total": total,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": round(precision, 3),
        "recall":    round(recall, 3),
    })


# -------- /latency: load test latency histogram --------

@analytics_bp.route("/latency", methods=["GET"])
@check_admin_key
def latency():
    sql = """
        SELECT
            width_bucket(latency_ms, 0, 600000, 30) AS bucket,
            COUNT(*)                               AS n,
            MIN(latency_ms)                        AS bucket_min,
            MAX(latency_ms)                        AS bucket_max
        FROM eval_runs
        WHERE load_test_run = TRUE AND latency_ms IS NOT NULL
        GROUP BY bucket
        ORDER BY bucket
    """
    try:
        with db.get_db() as cur:
            cur.execute(sql)
            rows = cur.fetchall() or []
    except Exception as exc:
        if _eval_runs_missing(exc):
            return jsonify({"empty": True})
        log.warning("latency query failed: %s", exc)
        return jsonify({"empty": True})

    if not rows:
        return jsonify({"empty": True})

    buckets = [
        {
            "bucket":     int(r["bucket"] or 0),
            "count":      int(r["n"] or 0),
            "min_ms":     int(r["bucket_min"] or 0),
            "max_ms":     int(r["bucket_max"] or 0),
        }
        for r in rows
    ]
    return jsonify({"empty": False, "buckets": buckets})


# -------- /cost-breakdown: cost_usd grouped by tool category and week --------

@analytics_bp.route("/cost-breakdown", methods=["GET"])
@check_admin_key
def cost_breakdown():
    sql = """
        SELECT
            DATE_TRUNC('week', r.created_at)::date        AS week,
            COALESCE(NULLIF(t.category, ''), 'Uncategorized') AS category,
            COALESCE(SUM(r.cost_usd)::float, 0)           AS cost_usd,
            COUNT(*)                                      AS runs
        FROM runs r
        LEFT JOIN tools t ON t.id = r.tool_id
        WHERE r.created_at >= NOW() - INTERVAL '90 days'
        GROUP BY DATE_TRUNC('week', r.created_at)::date,
                 COALESCE(NULLIF(t.category, ''), 'Uncategorized')
        ORDER BY week ASC, category ASC
    """
    with db.get_db() as cur:
        cur.execute(sql)
        rows = cur.fetchall() or []

    entries = []
    categories: List[str] = []
    seen = set()
    for r in rows:
        week = r["week"]
        week_s = week.isoformat() if hasattr(week, "isoformat") else str(week)
        cat = r["category"] or "Uncategorized"
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)
        entries.append({
            "week":     week_s,
            "category": cat,
            "cost_usd": round(float(r["cost_usd"] or 0), 4),
            "runs":     int(r["runs"] or 0),
        })
    return jsonify({"entries": entries, "categories": categories})
