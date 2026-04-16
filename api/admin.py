"""
Forge admin API — Blueprint owned by T4.

Register in server.py with:
    from api.admin import admin_bp, agent_admin_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(agent_admin_bp)

Auth: every route checks X-Admin-Key header against ADMIN_KEY env var.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from api import db
from api.models import compute_trust_tier

log = logging.getLogger("forge.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")
agent_admin_bp = Blueprint("agent_admin", __name__, url_prefix="/api/agent")

PENDING_STATUSES = ("pending_review", "agent_reviewing", "submitted")


def _admin_key() -> str:
    return os.environ.get("ADMIN_KEY", "")


def check_admin_key(fn):
    """Decorator: require a matching X-Admin-Key header."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = _admin_key()
        provided = request.headers.get("X-Admin-Key", "")
        if not expected or provided != expected:
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


def _maybe_json(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return value


def _serialize_dt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_json(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {k: _serialize_dt(v) for k, v in row.items()}


def _fetch_review(tool_id: int) -> Optional[Dict[str, Any]]:
    review = db.get_agent_review_by_tool(tool_id)
    if not review:
        return None
    for k in (
        "classifier_output",
        "security_scan_output",
        "security_flags",
        "red_team_output",
        "vulnerabilities",
        "hardening_suggestions",
        "hardener_output",
        "changes_made",
        "qa_output",
        "test_cases",
        "qa_issues",
        "human_overrides",
    ):
        if k in review:
            review[k] = _maybe_json(review[k])
    return _row_json(review)


# -------- Queue --------

@admin_bp.route("/queue", methods=["GET"])
@check_admin_key
def get_queue():
    placeholders = ", ".join(["%s"] * len(PENDING_STATUSES))
    sql = (
        "SELECT * FROM tools WHERE status IN (" + placeholders + ") "
        "ORDER BY submitted_at DESC NULLS LAST, created_at DESC"
    )
    with db.get_db() as cur:
        cur.execute(sql, list(PENDING_STATUSES))
        rows = [dict(r) for r in cur.fetchall()]

    tools: List[Dict[str, Any]] = []
    for row in rows:
        tool = _row_json(row) or {}
        tool["input_schema"] = _maybe_json(tool.get("input_schema"))
        tool["agent_review"] = _fetch_review(row["id"])
        tools.append(tool)

    return jsonify({"tools": tools, "count": len(tools)})


@admin_bp.route("/queue/count", methods=["GET"])
@check_admin_key
def get_queue_count():
    placeholders = ", ".join(["%s"] * len(PENDING_STATUSES))
    with db.get_db() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS c FROM tools WHERE status IN ({placeholders})",
            list(PENDING_STATUSES),
        )
        row = cur.fetchone()
    return jsonify({"count": int(row["c"]) if row else 0})


# -------- Decisions --------

def _apply_score_overrides(tool: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply admin overrides to governance scores + recompute trust tier."""
    allowed_ints = {
        "reliability_score",
        "safety_score",
        "complexity_score",
        "verified_score",
        "security_tier",
    }
    allowed_strs = {"data_sensitivity", "trust_tier"}

    updates: Dict[str, Any] = {}
    for k, v in (overrides or {}).items():
        if k in allowed_ints and v is not None:
            try:
                updates[k] = int(v)
            except (TypeError, ValueError):
                continue
        elif k in allowed_strs and v is not None:
            updates[k] = str(v)

    reliability = updates.get("reliability_score", tool.get("reliability_score") or 0)
    safety = updates.get("safety_score", tool.get("safety_score") or 0)
    verified = updates.get("verified_score", tool.get("verified_score") or 0)
    security_tier = updates.get("security_tier", tool.get("security_tier") or 1)
    data_sensitivity = updates.get("data_sensitivity", tool.get("data_sensitivity") or "internal")
    run_count = tool.get("run_count") or 0

    if "trust_tier" not in updates:
        updates["trust_tier"] = compute_trust_tier(
            int(reliability), int(safety), int(verified),
            int(security_tier), str(data_sensitivity), int(run_count),
        )
    return updates


def _launch_deploy(tool_id: int) -> None:
    try:
        from api.deploy import deploy_tool
    except Exception as exc:
        log.warning("deploy_tool import failed: %s", exc)
        return

    def _run():
        try:
            deploy_tool(tool_id)
        except Exception as exc:
            log.error("deploy_tool(%s) failed: %s", tool_id, exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


@admin_bp.route("/tools/<int:tool_id>/approve", methods=["POST"])
@check_admin_key
def approve_tool(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404

    body = request.get_json(silent=True) or {}
    reviewer = body.get("reviewer") or body.get("human_reviewer") or "admin"
    notes = body.get("notes") or body.get("human_notes") or ""
    overrides = body.get("score_overrides") or body.get("overrides") or {}

    score_updates = _apply_score_overrides(tool, overrides)

    now = datetime.now(timezone.utc)
    updates: Dict[str, Any] = dict(score_updates)
    updates.update({
        "status": "approved",
        "approved_at": now,
        "approved_by": reviewer,
    })

    hardened = tool.get("hardened_prompt") or tool.get("system_prompt")
    if hardened:
        updates["system_prompt"] = hardened

    new_version = int(tool.get("version") or 1)
    if tool.get("status") != "approved":
        new_version = max(new_version, 1)
    updates["version"] = new_version

    db.update_tool(tool_id, **updates)

    review = db.get_agent_review_by_tool(tool_id)
    if review:
        db.update_agent_review(
            review["id"],
            human_decision="approved",
            human_reviewer=reviewer,
            human_notes=notes,
            human_overrides=overrides or {},
            completed_at=now,
        )

    try:
        db.insert_tool_version(
            tool_id=tool_id,
            version=new_version,
            system_prompt=tool.get("system_prompt") or "",
            hardened_prompt=hardened or "",
            input_schema=tool.get("input_schema") or "[]",
            change_summary=f"Approved by {reviewer}",
            created_by=reviewer,
        )
    except Exception as exc:
        log.warning("tool_version insert failed for %s: %s", tool_id, exc)

    _launch_deploy(tool_id)

    updated = db.get_tool(tool_id) or {}
    return jsonify({
        "success": True,
        "trust_tier": updated.get("trust_tier"),
        "endpoint_url": updated.get("endpoint_url"),
        "status": updated.get("status"),
    })


@admin_bp.route("/tools/<int:tool_id>/reject", methods=["POST"])
@check_admin_key
def reject_tool(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404

    body = request.get_json(silent=True) or {}
    reviewer = body.get("reviewer") or "admin"
    feedback = body.get("feedback") or body.get("reason") or ""
    notes = body.get("notes") or ""

    db.update_tool(tool_id, status="rejected")

    review = db.get_agent_review_by_tool(tool_id)
    if review:
        db.update_agent_review(
            review["id"],
            human_decision="rejected",
            human_reviewer=reviewer,
            human_notes=notes or feedback,
            completed_at=datetime.now(timezone.utc),
        )

    return jsonify({"success": True, "status": "rejected", "feedback": feedback})


@admin_bp.route("/tools/<int:tool_id>/needs-changes", methods=["POST"])
@check_admin_key
def needs_changes(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404

    body = request.get_json(silent=True) or {}
    reviewer = body.get("reviewer") or "admin"
    feedback = body.get("feedback") or ""
    notes = body.get("notes") or ""

    db.update_tool(tool_id, status="needs_changes")

    review = db.get_agent_review_by_tool(tool_id)
    if review:
        db.update_agent_review(
            review["id"],
            human_decision="needs_changes",
            human_reviewer=reviewer,
            human_notes=notes or feedback,
            completed_at=datetime.now(timezone.utc),
        )

    return jsonify({"success": True, "status": "needs_changes", "feedback": feedback})


@admin_bp.route("/tools/<int:tool_id>/override-scores", methods=["POST"])
@check_admin_key
def override_scores(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404

    body = request.get_json(silent=True) or {}
    overrides = body.get("overrides") or body
    updates = _apply_score_overrides(tool, overrides)
    if not updates:
        return jsonify({"error": "no valid score fields provided"}), 400

    db.update_tool(tool_id, **updates)

    review = db.get_agent_review_by_tool(tool_id)
    if review:
        db.update_agent_review(
            review["id"],
            human_overrides=overrides,
        )

    updated = db.get_tool(tool_id) or {}
    return jsonify({
        "success": True,
        "trust_tier": updated.get("trust_tier"),
        "reliability_score": updated.get("reliability_score"),
        "safety_score": updated.get("safety_score"),
        "complexity_score": updated.get("complexity_score"),
        "verified_score": updated.get("verified_score"),
        "data_sensitivity": updated.get("data_sensitivity"),
    })


@admin_bp.route("/tools/<int:tool_id>/archive", methods=["POST"])
@check_admin_key
def archive_tool(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404
    db.update_tool(tool_id, status="archived")
    return jsonify({"success": True, "status": "archived"})


# -------- Runs --------

def _parse_bool(val: Any) -> Optional[bool]:
    if val is None:
        return None
    s = str(val).lower()
    if s in ("1", "true", "yes", "t"):
        return True
    if s in ("0", "false", "no", "f"):
        return False
    return None


@admin_bp.route("/runs", methods=["GET"])
@check_admin_key
def list_runs():
    tool_id = request.args.get("tool_id", type=int)
    user_email = request.args.get("user_email")
    flagged = _parse_bool(request.args.get("flagged"))
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        page, limit = 1, 50

    where: List[str] = []
    params: List[Any] = []
    if tool_id is not None:
        where.append("r.tool_id = %s")
        params.append(tool_id)
    if user_email:
        where.append("r.user_email = %s")
        params.append(user_email)
    if flagged is not None:
        where.append("r.output_flagged = %s")
        params.append(flagged)
    if date_from:
        where.append("r.created_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("r.created_at <= %s")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * limit

    sql = (
        "SELECT r.*, t.name AS tool_name, t.slug AS tool_slug, "
        "       t.trust_tier AS tool_trust_tier "
        "FROM runs r LEFT JOIN tools t ON t.id = r.tool_id "
        f"{where_sql} ORDER BY r.created_at DESC LIMIT %s OFFSET %s"
    )
    count_sql = (
        "SELECT COUNT(*) AS c FROM runs r LEFT JOIN tools t ON t.id = r.tool_id "
        f"{where_sql}"
    )

    with db.get_db() as cur:
        cur.execute(count_sql, params)
        total = int(cur.fetchone()["c"])
        cur.execute(sql, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]

    runs: List[Dict[str, Any]] = []
    for r in rows:
        item = _row_json(r) or {}
        item["input_data"] = _maybe_json(item.get("input_data"))
        runs.append(item)

    return jsonify({
        "runs": runs,
        "total": total,
        "page": page,
        "limit": limit,
    })


@admin_bp.route("/runs/<int:run_id>/flag", methods=["POST"])
@check_admin_key
def flag_run(run_id: int):
    run = db.get_run(run_id)
    if not run:
        return jsonify({"error": "run not found"}), 404

    body = request.get_json(silent=True) or {}
    reason = body.get("reason") or body.get("flag_reason") or "admin_flag"

    db.update_run(run_id, output_flagged=True, flag_reason=reason)

    new_count = 0
    if run.get("tool_id"):
        try:
            new_count = db.increment_flag_count(int(run["tool_id"]))
        except Exception as exc:
            log.warning("flag_count increment failed for tool %s: %s",
                        run.get("tool_id"), exc)

    return jsonify({
        "success": True,
        "run_id": run_id,
        "tool_id": run.get("tool_id"),
        "tool_flag_count": new_count,
    })


# -------- Analytics --------

@admin_bp.route("/analytics", methods=["GET"])
@check_admin_key
def analytics():
    out: Dict[str, Any] = {}

    with db.get_db() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM tools WHERE status = 'approved'")
        out["total_tools"] = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT COUNT(*) AS c FROM runs "
            "WHERE created_at >= NOW() - INTERVAL '30 days'"
        )
        out["total_runs_month"] = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT COALESCE(AVG(rating)::real, 0) AS avg FROM runs "
            "WHERE rating IS NOT NULL"
        )
        out["avg_rating"] = round(float(cur.fetchone()["avg"] or 0), 2)

        placeholders = ", ".join(["%s"] * len(PENDING_STATUSES))
        cur.execute(
            f"SELECT COUNT(*) AS c FROM tools WHERE status IN ({placeholders})",
            list(PENDING_STATUSES),
        )
        out["pending_count"] = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT trust_tier, COUNT(*) AS c FROM tools "
            "WHERE status = 'approved' GROUP BY trust_tier"
        )
        out["tools_by_trust_tier"] = {
            (r["trust_tier"] or "unverified"): int(r["c"]) for r in cur.fetchall()
        }

        cur.execute(
            "SELECT DATE(created_at) AS d, COUNT(*) AS c FROM runs "
            "WHERE created_at >= NOW() - INTERVAL '30 days' "
            "GROUP BY DATE(created_at) ORDER BY d ASC"
        )
        out["runs_per_day"] = [
            {"date": r["d"].isoformat() if hasattr(r["d"], "isoformat") else str(r["d"]),
             "count": int(r["c"])}
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT t.id, t.name, t.slug, t.trust_tier, "
            "       COUNT(r.id) AS runs, COALESCE(AVG(r.rating)::real, 0) AS avg_rating "
            "FROM tools t LEFT JOIN runs r ON r.tool_id = t.id "
            "WHERE t.status = 'approved' "
            "GROUP BY t.id, t.name, t.slug, t.trust_tier "
            "ORDER BY runs DESC LIMIT 10"
        )
        out["top_tools"] = [
            {
                "id": r["id"],
                "name": r["name"],
                "slug": r["slug"],
                "trust_tier": r["trust_tier"],
                "runs": int(r["runs"] or 0),
                "avg_rating": round(float(r["avg_rating"] or 0), 2),
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT COALESCE(category, 'Uncategorized') AS c, COUNT(*) AS n "
            "FROM tools WHERE status = 'approved' GROUP BY category "
            "ORDER BY n DESC"
        )
        out["category_distribution"] = {
            r["c"]: int(r["n"]) for r in cur.fetchall()
        }

        cur.execute(
            "SELECT status, COUNT(*) AS c FROM tools "
            "WHERE status IN ('approved', 'rejected') GROUP BY status"
        )
        counts = {r["status"]: int(r["c"]) for r in cur.fetchall()}
        total_decided = counts.get("approved", 0) + counts.get("rejected", 0)
        pass_rate = (counts.get("approved", 0) / total_decided) if total_decided else 0.0
        out["agent_pass_rate"] = round(pass_rate, 3)

        cur.execute(
            "SELECT COUNT(*) AS c FROM tools WHERE flag_count >= 3"
        )
        out["flagged_tools_count"] = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT COALESCE(SUM(dlp_tokens_found), 0) AS total "
            "FROM runs WHERE dlp_tokens_found > 0"
        )
        out["total_pii_masked"] = int(cur.fetchone()["total"] or 0)

    return jsonify(out)


# -------- Agent pipeline re-run --------

@agent_admin_bp.route("/rerun/<int:tool_id>", methods=["POST"])
@check_admin_key
def rerun_pipeline(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "tool not found"}), 404

    with db.get_db(dict_cursor=False) as cur:
        cur.execute("DELETE FROM agent_reviews WHERE tool_id = %s", (tool_id,))

    db.update_tool(tool_id, status="agent_reviewing")
    db.create_agent_review(tool_id)

    dispatched = False
    try:
        from agents import pipeline  # type: ignore

        def _run():
            try:
                runner = getattr(pipeline, "run", None) or getattr(pipeline, "run_pipeline", None)
                if callable(runner):
                    runner(tool_id)
            except Exception as exc:
                log.error("pipeline rerun for %s failed: %s", tool_id, exc)

        threading.Thread(target=_run, daemon=True).start()
        dispatched = True
    except Exception as exc:
        log.warning("pipeline import failed, could not relaunch for %s: %s",
                    tool_id, exc)

    return jsonify({
        "success": True,
        "tool_id": tool_id,
        "status": "agent_reviewing",
        "pipeline_dispatched": dispatched,
    })
