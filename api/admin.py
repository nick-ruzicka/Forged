"""
Forge admin blueprint — simplified after prompt-stack demolition.

Scope: app submissions only. An app is either pending_review, approved, rejected,
needs_changes, or archived. No agent pipeline, no prompt runs, no score overrides.
"""
import logging
import os
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, after_this_request

from api import db


def _restrict_cors(response):
    """Override the global CORS * with a pinned origin for admin routes."""
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:8090"
    return response

log = logging.getLogger("forge.admin")

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "forge-admin-2026")


def check_admin_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        key = request.headers.get("X-Admin-Key")
        if key != ADMIN_KEY:
            return jsonify({"error": "unauthorized"}), 401
        after_this_request(_restrict_cors)
        return view(*args, **kwargs)
    return wrapped


def _serialize_tool_row(row: dict) -> dict:
    """Trim a tool row for the admin queue. Don't return giant app_html over the wire."""
    app_html = row.get("app_html") or ""
    return {
        "id": row.get("id"),
        "slug": row.get("slug"),
        "name": row.get("name"),
        "tagline": row.get("tagline"),
        "description": row.get("description"),
        "category": row.get("category"),
        "app_type": row.get("app_type"),
        "status": row.get("status"),
        "author_name": row.get("author_name"),
        "author_email": row.get("author_email"),
        "created_at": _iso(row.get("created_at")),
        "submitted_at": _iso(row.get("submitted_at")),
        "html_length": len(app_html),
        "has_html": bool(app_html),
    }


def _iso(val):
    if isinstance(val, datetime):
        return val.isoformat()
    return val


# -------------------- Review queue --------------------

@admin_bp.route("/queue", methods=["GET"])
@check_admin_key
def get_queue():
    """Return all apps awaiting admin review."""
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT * FROM tools
            WHERE status = 'pending_review' AND app_type = 'app'
            ORDER BY submitted_at DESC NULLS LAST, created_at DESC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({
        "tools": [_serialize_tool_row(r) for r in rows],
        "count": len(rows),
    })


@admin_bp.route("/queue/count", methods=["GET"])
@check_admin_key
def queue_count():
    with db.get_db() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM tools WHERE status = 'pending_review' AND app_type = 'app'"
        )
        n = cur.fetchone()["c"]
    return jsonify({"count": n})


@admin_bp.route("/tools/<int:tool_id>/approve", methods=["POST"])
@check_admin_key
def approve(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404

    body = request.get_json(silent=True) or {}
    reviewer = body.get("reviewer") or body.get("reviewer_email") or ""

    db.update_tool(
        tool_id,
        status="approved",
        approved_at=datetime.utcnow(),
        approved_by=reviewer,
        deployed=True,
        deployed_at=datetime.utcnow(),
        endpoint_url=f"/apps/{tool.get('slug')}",
    )
    return jsonify({
        "success": True,
        "tool_id": tool_id,
        "slug": tool.get("slug"),
        "status": "approved",
        "url": f"/apps/{tool.get('slug')}",
    })


@admin_bp.route("/tools/<int:tool_id>/reject", methods=["POST"])
@check_admin_key
def reject(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    db.update_tool(tool_id, status="rejected")
    log.info("tool %s rejected: %s", tool_id, reason)
    return jsonify({"success": True, "tool_id": tool_id, "status": "rejected"})


@admin_bp.route("/tools/<int:tool_id>/needs-changes", methods=["POST"])
@check_admin_key
def needs_changes(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    feedback = (body.get("feedback") or "").strip()
    db.update_tool(tool_id, status="needs_changes")
    log.info("tool %s needs changes: %s", tool_id, feedback)
    return jsonify({"success": True, "tool_id": tool_id, "status": "needs_changes"})


@admin_bp.route("/tools/<int:tool_id>/archive", methods=["POST"])
@check_admin_key
def archive(tool_id: int):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    db.update_tool(tool_id, status="archived")
    return jsonify({"success": True, "tool_id": tool_id, "status": "archived"})


# -------------------- Analytics (minimal) --------------------

@admin_bp.route("/analytics", methods=["GET"])
@check_admin_key
def analytics():
    """Roll-up metrics for the admin dashboard. Apps + skills only."""
    with db.get_db() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM tools WHERE app_type = 'app' AND status = 'approved'")
        apps_live = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM tools WHERE app_type = 'app' AND status = 'pending_review'")
        apps_pending = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM skills")
        skills_total = cur.fetchone()["c"]
        cur.execute(
            """
            SELECT slug, name, run_count, avg_rating
            FROM tools
            WHERE app_type = 'app' AND status = 'approved'
            ORDER BY run_count DESC NULLS LAST
            LIMIT 10
            """
        )
        top_apps = [dict(r) for r in cur.fetchall()]

    return jsonify({
        "apps_live": apps_live,
        "apps_pending": apps_pending,
        "skills_total": skills_total,
        "top_apps": top_apps,
    })
