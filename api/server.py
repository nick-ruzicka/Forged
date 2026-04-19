"""
Forge Flask API server.
Port 8090. JSON responses under /api/. Serves frontend/ as static files.

After the prompt-stack demolition: Forge serves apps (HTML bundles) and skills
(SKILL.md files). No prompt tools, no agent review pipeline, no creator/learning/
workflow modules. Pre-demolition state is tagged `pre-prompt-demolition`.
"""
import json
import os
import re
import threading
import time
import urllib.parse
from collections import deque
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from api import db
from api.models import Skill, Tool

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)

VERSION = "0.2.0"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "forge-admin-2026")

app = Flask(__name__, static_folder=None)
CORS(app)


@app.before_request
def _block_traversal():
    """Block path traversal attempts before any routing.

    Flask/Werkzeug resolves .. before routing, so route handlers never see
    traversal chars. This middleware checks the raw path from the WSGI environ
    before resolution happens.
    """
    raw = request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or request.path
    if ".." in raw or "%2e" in raw.lower():
        return jsonify({"error": "not_found"}), 404


# -------------------- Error handlers --------------------

@app.errorhandler(400)
def _400(e):
    return jsonify({"error": "bad_request", "message": str(e)}), 400


@app.errorhandler(404)
def _404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "path": request.path}), 404
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"error": "not_found"}), 404


@app.errorhandler(500)
def _500(e):
    return jsonify({"error": "internal_server_error", "message": str(e)}), 500


@app.errorhandler(Exception)
def _generic(e):
    code = getattr(e, "code", 500)
    if isinstance(code, int) and 400 <= code < 600:
        return jsonify({"error": type(e).__name__, "message": str(e)}), code
    return jsonify({"error": "internal_server_error", "message": str(e)}), 500


# -------------------- Static frontend --------------------

@app.route("/")
def _index():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"forge": "api", "version": VERSION}), 200


@app.route("/<path:path>")
def _static(path):
    if path.startswith("api/") or ".." in path:
        return jsonify({"error": "not_found"}), 404
    full = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(FRONTEND_DIR, path)
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"error": "not_found"}), 404


# -------------------- Health --------------------

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


# -------------------- Helpers --------------------

def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", (name or "").lower())
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or f"app-{int(time.time())}"


def _unique_slug(base: str) -> str:
    slug = base
    i = 2
    while db.slug_exists(slug):
        slug = f"{base}-{i}"
        i += 1
    return slug


def _require_admin():
    key = request.headers.get("X-Admin-Key")
    if key != ADMIN_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


def _jsonify_tool(row: dict) -> dict:
    if not row:
        return {}
    return Tool.from_row(row).to_dict()


# -------------------- Rate limiting (in-memory) --------------------

_RATE_WINDOW_SEC = 3600
_RATE_LIMIT = 30
_rate_store: dict = {}
_rate_lock = threading.Lock()


def _rate_limit_check(ip: str):
    now = time.time()
    with _rate_lock:
        q = _rate_store.get(ip)
        if q is None:
            q = deque()
            _rate_store[ip] = q
        cutoff = now - _RATE_WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            retry_after = int(_RATE_WINDOW_SEC - (now - q[0])) + 1
            return retry_after
        q.append(now)
        return 0


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


# -------------------- Catalog (apps only) --------------------

@app.route("/api/tools", methods=["GET"])
def list_tools():
    category = request.args.get("category")
    search = request.args.get("search") or request.args.get("q")
    sort = request.args.get("sort", "popular")
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 12))
    except ValueError:
        page, limit = 1, 12
    limit = max(1, min(limit, 100))

    rows, total = db.list_tools(
        status="approved",
        category=category,
        app_type="app",
        search=search,
        sort=sort,
        page=page,
        limit=limit,
    )
    return jsonify({
        "tools": [_jsonify_tool(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
    })


@app.route("/api/tools/<int:tool_id>", methods=["GET"])
def get_tool(tool_id):
    row = db.get_tool(tool_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_jsonify_tool(row))


@app.route("/api/tools/slug/<string:slug>", methods=["GET"])
def get_tool_by_slug(slug):
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        return jsonify({"error": "not_found"}), 404
    row = db.get_tool_by_slug(slug)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_jsonify_tool(row))


@app.route("/api/tools/<int:tool_id>/fork", methods=["POST"])
def fork_tool(tool_id):
    parent = db.get_tool(tool_id)
    if not parent:
        return jsonify({"error": "not_found"}), 404
    if (parent.get("app_type") or "prompt") != "app":
        return jsonify({"error": "not_an_app"}), 400

    body = request.get_json(silent=True) or {}
    new_name = body.get("name") or f"{parent['name']} (fork)"
    author_name = body.get("author_name") or parent.get("author_name") or ""
    author_email = body.get("author_email")
    if not author_email:
        return jsonify({"error": "validation", "message": "author_email required"}), 400

    slug = _unique_slug(_slugify(new_name))
    data = {
        "slug": slug,
        "name": new_name,
        "tagline": parent.get("tagline") or "",
        "description": parent.get("description") or "",
        "category": parent.get("category") or "Other",
        "tags": parent.get("tags") or "",
        "app_type": "app",
        "app_html": parent.get("app_html") or "",
        "status": "draft",
        "version": 1,
        "author_name": author_name,
        "author_email": author_email,
        "fork_of": tool_id,
        "submitted_at": datetime.utcnow(),
    }
    new_id = db.insert_tool(data)
    return jsonify({"id": new_id, "slug": slug, "status": "draft"}), 201


# -------------------- Identity (anonymous-by-default) --------------------

def _get_identity():
    """Return (user_id, email) from request. Either header or query param.

    `X-Forge-User-Id` is the anonymous UUID generated client-side on first visit.
    Email is optional and only set when the user explicitly provides one.
    """
    uid = request.headers.get("X-Forge-User-Id") or request.args.get("user_id")
    email = request.headers.get("X-Forge-User-Email") or request.args.get("email")
    body = request.get_json(silent=True) if request.method in ("POST", "PUT", "PATCH") else None
    if isinstance(body, dict):
        uid = uid or body.get("user_id")
        email = email or body.get("email")
    return (uid or "").strip() or None, (email or "").strip() or None


@app.route("/api/me", methods=["GET"])
def me_get():
    uid, email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
    if not row:
        return jsonify({"user_id": uid, "email": None, "name": None, "team": None, "anonymous": True})
    return jsonify({**dict(row), "anonymous": not row.get("email")})


@app.route("/api/me", methods=["POST"])
def me_upsert():
    """Lazy identity. User provides email/name when needed (publishing, etc.)."""
    uid, email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip() or None
    email = (body.get("email") or email or "").strip() or None
    team = email.split("@")[-1] if email and "@" in email else None
    with db.get_db() as cur:
        cur.execute(
            """
            INSERT INTO users (user_id, email, name, team)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
              email = COALESCE(EXCLUDED.email, users.email),
              name = COALESCE(EXCLUDED.name, users.name),
              team = COALESCE(EXCLUDED.team, users.team),
              updated_at = NOW()
            RETURNING *
            """,
            (uid, email, name, team),
        )
        row = cur.fetchone()
    return jsonify({**dict(row), "anonymous": not row.get("email")})


# -------------------- Context layer --------------------

@app.route("/api/me/context", methods=["GET"])
def get_context():
    """The context object every app can read via ForgeAPI.context().

    Returns a pre-digested summary of the user's work context: role, team,
    recent activity, connected services, upcoming meetings (when available).
    Apps call this to be contextually aware without asking the user to re-enter info.
    """
    uid, email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400

    # Build context from what we know
    user_info = {}
    with db.get_db() as cur:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        if row:
            user_info = dict(row)

    # Recent activity: last 10 app opens
    recent_apps = []
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT t.slug, t.name, t.icon, ui.last_opened_at, ui.open_count
            FROM user_items ui JOIN tools t ON t.id = ui.tool_id
            WHERE ui.user_id = %s AND ui.last_opened_at IS NOT NULL
            ORDER BY ui.last_opened_at DESC LIMIT 10
            """,
            (uid,),
        )
        for r in cur.fetchall():
            recent_apps.append({
                "slug": r["slug"], "name": r["name"], "icon": r["icon"],
                "last_opened": r["last_opened_at"].isoformat() if r.get("last_opened_at") else None,
                "open_count": r["open_count"],
            })

    # Team context: what others on the same team use most
    team = user_info.get("team")
    team_popular = []
    if team:
        with db.get_db() as cur:
            cur.execute(
                """
                SELECT t.slug, t.name, t.icon, COUNT(*) as team_installs
                FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                JOIN tools t ON t.id = ui.tool_id
                WHERE u.team = %s AND t.status = 'approved'
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY team_installs DESC LIMIT 5
                """,
                (team,),
            )
            team_popular = [dict(r) for r in cur.fetchall()]

    # Connected services status
    services = {}
    try:
        from api.connectors.salesforce import SalesforceConnector
        services["salesforce"] = {"configured": SalesforceConnector().is_configured()}
    except Exception:
        services["salesforce"] = {"configured": False}

    context = {
        "user": {
            "user_id": uid,
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "role": user_info.get("role"),
            "team": team,
            "onboarded": user_info.get("onboarded", False),
        },
        "recent_apps": recent_apps,
        "team_popular": team_popular,
        "services": services,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return jsonify(context)


@app.route("/api/me/role", methods=["POST"])
def set_role():
    """Set the user's role during onboarding. Used for role-aware catalog filtering.

    Rate-limited: max 10 role changes per hour per IP. This prevents
    enumeration/filling attacks on the users table. Until SSO is added,
    this is the primary defense against unauthenticated user creation spam.
    """
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    # Rate limit by IP to prevent spam user creation
    ip = _client_ip()
    retry_after = _rate_limit_check(ip)
    if retry_after:
        return jsonify({"error": "rate_limited", "retry_after": retry_after}), 429
    body = request.get_json(silent=True) or {}
    role = (body.get("role") or "").strip()
    valid_roles = {"AE", "SDR", "RevOps", "CS", "Product", "Eng", "Recruiter", "Other"}
    if role not in valid_roles:
        return jsonify({"error": f"Invalid role. Choose from: {', '.join(sorted(valid_roles))}"}), 400
    # Validate user_id format (must look like a UUID, not arbitrary strings)
    if not re.match(r"^[a-f0-9\-]{8,}", uid):
        return jsonify({"error": "invalid user_id format"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            INSERT INTO users (user_id, role, onboarded) VALUES (%s, %s, TRUE)
            ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role, onboarded = TRUE, updated_at = NOW()
            """,
            (uid, role),
        )
    return jsonify({"role": role, "onboarded": True})


# -------------------- Actions API --------------------

@app.route("/api/actions/slack", methods=["POST"])
def action_slack_post():
    """Post a message to Slack via the configured webhook.

    Body: {channel (optional), message, user_id}
    Logged to action_log for audit. Rate limited.
    """
    uid, _ = _get_identity()
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message required"}), 400

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return jsonify({"error": "Slack not configured", "configured": False}), 503

    import urllib.request
    payload = json.dumps({"text": message}).encode()
    try:
        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        status = "completed"
    except Exception as exc:
        status = "failed"

    # Log the action
    tool_id = body.get("tool_id")
    with db.get_db() as cur:
        cur.execute(
            "INSERT INTO action_log (user_id, tool_id, action_type, action_data, status) VALUES (%s, %s, %s, %s, %s)",
            (uid, tool_id, "slack_post", json.dumps({"message": message[:500]}), status),
        )

    return jsonify({"success": status == "completed", "action": "slack_post"})


@app.route("/api/actions/email-draft", methods=["POST"])
def action_email_draft():
    """Generate an email draft. Doesn't send — returns the draft for the user to review.

    Body: {to, subject, body, tool_id}
    In the future this could integrate with Gmail API to pre-fill a compose window.
    """
    uid, _ = _get_identity()
    body = request.get_json(silent=True) or {}
    to = (body.get("to") or "").strip()
    subject = (body.get("subject") or "").strip()
    email_body = (body.get("body") or "").strip()
    if not to or not subject or not email_body:
        return jsonify({"error": "to, subject, and body required"}), 400

    # Log
    with db.get_db() as cur:
        cur.execute(
            "INSERT INTO action_log (user_id, tool_id, action_type, action_data, status) VALUES (%s, %s, %s, %s, %s)",
            (uid, body.get("tool_id"), "email_draft",
             json.dumps({"to": to, "subject": subject, "body_length": len(email_body)}),
             "completed"),
        )

    # Return a mailto: link that opens the user's email client
    import urllib.parse
    mailto = f"mailto:{urllib.parse.quote(to)}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(email_body)}"

    return jsonify({
        "success": True, "action": "email_draft",
        "mailto": mailto,
        "to": to, "subject": subject, "body": email_body,
    })


@app.route("/api/actions/log", methods=["GET"])
def action_log_list():
    """View recent actions for audit. Admin or self only."""
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT al.*, t.name AS tool_name, t.icon AS tool_icon
            FROM action_log al
            LEFT JOIN tools t ON t.id = al.tool_id
            WHERE al.user_id = %s
            ORDER BY al.created_at DESC LIMIT 50
            """,
            (uid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify({"actions": rows, "count": len(rows)})


# -------------------- Recommendations (Sensei-equivalent) --------------------

@app.route("/api/me/recommended", methods=["GET"])
def recommended_for_you():
    """Return the top 5 apps most relevant to this user today.

    Ranking factors:
    1. Role match (apps tagged for the user's role)
    2. Team popularity (what others on the same team use)
    3. Not already installed (no point recommending what you have)

    This is the "Today for you" panel data.
    """
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"items": [], "reason": "no_user"})

    # Get user's role + team
    role = None
    team = None
    with db.get_db() as cur:
        cur.execute("SELECT role, team FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        if row:
            role = row.get("role")
            team = row.get("team")

    # Get already installed
    installed_ids = set()
    with db.get_db() as cur:
        cur.execute("SELECT tool_id FROM user_items WHERE user_id = %s", (uid,))
        installed_ids = {r["tool_id"] for r in cur.fetchall()}

    # Score each approved tool
    with db.get_db() as cur:
        cur.execute("SELECT * FROM tools WHERE status = 'approved' AND app_type = 'app'")
        all_tools = [dict(r) for r in cur.fetchall()]

    scored = []
    for t in all_tools:
        if t["id"] in installed_ids:
            continue  # skip already installed
        score = 0
        reason = ""
        # Role match
        try:
            tags = json.loads(t.get("role_tags") or "[]")
            if role and role in tags:
                score += 10
                reason = f"Popular with {role}" if role.endswith("s") else f"Popular with {role}s"
        except Exception:
            pass
        # Install count as popularity signal
        score += min((t.get("install_count") or 0), 20)
        if (t.get("install_count") or 0) >= 3:
            reason = reason or f"{t['install_count']} installs"
        scored.append({**_jsonify_tool(t), "score": score, "reason": reason or "New to Forge"})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:5]
    return jsonify({"items": top, "role": role, "count": len(top)})


# -------------------- Claude exec proxy (admin only) --------------------

@app.route("/api/claude-runs", methods=["GET"])
def list_claude_runs():
    """Proxy to forge-agent's /claude-exec/runs. Admin only."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        req = ur.Request("http://localhost:4242/claude-exec/runs",
                         headers={"X-Forge-Token": token})
        with ur.urlopen(req, timeout=5) as r:
            return jsonify(json.loads(r.read()))
    except Exception as exc:
        return jsonify({"error": "agent_unavailable", "message": str(exc)[:200]}), 502


@app.route("/api/claude-runs/<string:run_id>/log", methods=["GET"])
def get_claude_run_log(run_id):
    """Proxy to forge-agent's /claude-exec/log/{run_id}. Admin only."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    if not re.match(r"^[a-f0-9]{16}$", run_id):
        return jsonify({"error": "invalid run_id"}), 400
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        req = ur.Request(f"http://localhost:4242/claude-exec/log/{run_id}",
                         headers={"X-Forge-Token": token})
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception as exc:
        return jsonify({"error": "agent_unavailable", "message": str(exc)[:200]}), 502


@app.route("/api/claude-exec", methods=["POST"])
def trigger_claude_exec():
    """Proxy to forge-agent's /claude-exec. Admin only."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    body = request.get_json(silent=True) or {}
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        payload = json.dumps(body).encode()
        req = ur.Request(
            "http://localhost:4242/claude-exec",
            data=payload,
            headers={"X-Forge-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception as exc:
        return jsonify({"error": "agent_unavailable", "message": str(exc)[:200]}), 502


# -------------------- Forge Agent token --------------------

@app.route("/api/agent/token")
def agent_token():
    """Serve the forge-agent auth token to the frontend.

    The token lives in ~/.forge/agent-token and is generated by forge-agent
    on first run. Only serves to same-origin requests (the browser enforces
    this via the cookie/referer policy). External sites can't read this.
    """
    token_path = os.path.expanduser("~/.forge/agent-token")
    if os.path.exists(token_path):
        try:
            token = open(token_path).read().strip()
            return jsonify({"token": token, "available": True})
        except Exception:
            return jsonify({"token": None, "available": False})
    return jsonify({"token": None, "available": False})


@app.route("/api/forge-agent/launch", methods=["POST"])
def proxy_launch():
    """Proxy launch request to forge-agent."""
    body = request.get_json(silent=True) or {}
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        data = json.dumps(body).encode()
        req = ur.Request(
            "http://localhost:4242/launch",
            data=data,
            headers={"X-Forge-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 502


@app.route("/api/forge-agent/install", methods=["POST", "OPTIONS"])
def proxy_install():
    """Proxy install request to forge-agent, streaming SSE response."""
    from flask import Response
    import http.client
    # Handle CORS preflight
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin", "")
        cors_origin = origin if origin in ("http://localhost:3000", "http://localhost:3002", "http://localhost:8090") else "http://localhost:8090"
        return Response("", headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    body = request.get_json(silent=True) or {}
    try:
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        data = json.dumps(body).encode()

        def generate():
            try:
                conn = http.client.HTTPConnection("localhost", 4242, timeout=300)
                conn.request("POST", "/install", body=data, headers={
                    "X-Forge-Token": token,
                    "Content-Type": "application/json",
                })
                resp = conn.getresponse()
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    yield line
                conn.close()
            except Exception as e:
                yield f'event: error\ndata: {json.dumps({"type": "error", "message": str(e)})}\n\n'.encode()

        origin = request.headers.get("Origin", "")
        cors_origin = origin if origin in ("http://localhost:3000", "http://localhost:3002", "http://localhost:8090") else "http://localhost:8090"
        return Response(generate(), mimetype="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Access-Control-Allow-Origin": cors_origin,
                            "Access-Control-Allow-Headers": "Content-Type",
                        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 502


@app.route("/api/forge-agent/running", methods=["GET"])
def proxy_running():
    """Proxy running status request to forge-agent."""
    try:
        import urllib.request as ur
        req = ur.Request("http://localhost:4242/running")
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"apps": []}), 200


@app.route("/api/forge-agent/usage", methods=["GET"])
def proxy_usage():
    """Proxy usage stats request to forge-agent."""
    slug = request.args.get("slug", "")
    try:
        import urllib.request as ur
        req = ur.Request(f"http://localhost:4242/usage?slug={slug}")
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception:
        return jsonify({"slug": slug, "sessions_7d": [], "total_sec_7d": 0,
                        "session_count_7d": 0, "last_opened": None}), 200


@app.route("/api/forge-agent/privacy", methods=["GET"])
def proxy_privacy():
    """Proxy privacy request to forge-agent."""
    try:
        import urllib.request as ur
        req = ur.Request("http://localhost:4242/privacy")
        with ur.urlopen(req, timeout=5) as r:
            return jsonify(json.loads(r.read()))
    except Exception:
        return jsonify({"error": "forge-agent unavailable"}), 200


@app.route("/api/forge-agent/updates", methods=["GET"])
def proxy_updates():
    """Proxy updates request to forge-agent."""
    try:
        import urllib.request as ur
        slug = request.args.get("slug", "")
        req = ur.Request(f"http://localhost:4242/updates")
        with ur.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            if slug:
                data["updates"] = [u for u in data.get("updates", []) if u.get("slug") == slug]
            return jsonify(data)
    except Exception:
        return jsonify({"updates": []}), 200


@app.route("/api/forge-agent/uninstall", methods=["POST"])
def proxy_uninstall():
    """Proxy uninstall request to forge-agent."""
    body = request.get_json(silent=True) or {}
    try:
        import urllib.request as ur
        token = open(os.path.expanduser("~/.forge/agent-token")).read().strip()
        data = json.dumps(body).encode()
        req = ur.Request(
            "http://localhost:4242/uninstall",
            data=data,
            headers={"X-Forge-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with ur.urlopen(req, timeout=10) as r:
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 502


# -------------------- Stars / Wishlist --------------------

@app.route("/api/me/stars", methods=["GET"])
def list_stars():
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT t.*, s.starred_at
            FROM starred_items s JOIN tools t ON t.id = s.tool_id
            WHERE s.user_id = %s AND t.status = 'approved'
            ORDER BY s.starred_at DESC
            """,
            (uid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    items = []
    for r in rows:
        d = _jsonify_tool(r)
        d["starred_at"] = r.get("starred_at").isoformat() if r.get("starred_at") else None
        items.append(d)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/me/stars/<int:tool_id>", methods=["POST"])
def star_item(tool_id: int):
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            "INSERT INTO starred_items (user_id, tool_id) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (uid, tool_id),
        )
        added = cur.fetchone() is not None
    return jsonify({"starred": added, "tool_id": tool_id})


@app.route("/api/me/stars/<int:tool_id>", methods=["DELETE"])
def unstar_item(tool_id: int):
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            "DELETE FROM starred_items WHERE user_id = %s AND tool_id = %s RETURNING id",
            (uid, tool_id),
        )
        removed = cur.fetchone() is not None
    return jsonify({"unstarred": removed, "tool_id": tool_id})


# -------------------- Shelf (per-user library) --------------------

@app.route("/api/me/items", methods=["GET"])
def shelf_list():
    """Return everything on a user's shelf, joined with the tool row.

    Accepts user_id (preferred) or email (back-compat).
    """
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT t.*, ui.added_at, ui.installed_locally, ui.installed_at,
                   ui.installed_version, ui.last_opened_at, ui.open_count
            FROM user_items ui
            JOIN tools t ON t.id = ui.tool_id
            WHERE (ui.user_id = %s OR (%s IS NOT NULL AND ui.user_email = %s))
              AND t.status = 'approved'
            ORDER BY ui.last_opened_at DESC NULLS LAST, ui.added_at DESC
            """,
            (uid, email, email),
        )
        rows = [dict(r) for r in cur.fetchall()]
    items = []
    for r in rows:
        d = _jsonify_tool(r)
        d["added_at"] = r.get("added_at").isoformat() if r.get("added_at") else None
        d["installed_locally"] = r.get("installed_locally") or False
        d["installed_at"] = r.get("installed_at").isoformat() if r.get("installed_at") else None
        d["installed_version"] = r.get("installed_version")
        d["last_opened_at"] = r.get("last_opened_at").isoformat() if r.get("last_opened_at") else None
        d["open_count"] = r.get("open_count") or 0
        items.append(d)
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/me/items/<int:tool_id>", methods=["POST"])
def shelf_add(tool_id: int):
    """Add to shelf (idempotent). user_id required, email optional.

    Body may include {installed: true} to mark the item as locally installed
    (set by the frontend after a successful forge-agent install).
    """
    uid, email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    mark_installed = body.get("installed", False)
    with db.get_db() as cur:
        if email:
            cur.execute(
                """
                INSERT INTO user_items (user_id, user_email, tool_id, installed_locally, installed_at)
                VALUES (%s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
                ON CONFLICT (user_email, tool_id) DO UPDATE
                  SET user_id = COALESCE(EXCLUDED.user_id, user_items.user_id),
                      installed_locally = user_items.installed_locally OR EXCLUDED.installed_locally,
                      installed_at = COALESCE(user_items.installed_at, EXCLUDED.installed_at)
                RETURNING id
                """,
                (uid, email, tool_id, mark_installed, mark_installed),
            )
        else:
            # Anonymous user (no email) — use the partial unique index on (user_id, tool_id)
            cur.execute(
                """
                INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at)
                VALUES (%s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
                ON CONFLICT (user_id, tool_id) WHERE user_id IS NOT NULL DO UPDATE
                  SET installed_locally = user_items.installed_locally OR EXCLUDED.installed_locally,
                      installed_at = COALESCE(user_items.installed_at, EXCLUDED.installed_at)
                RETURNING id
                """,
                (uid, tool_id, mark_installed, mark_installed),
            )
        row = cur.fetchone()
        added = row is not None
        # Bump install_count denormalized counter (only on true insert, not update)
        if added:
            cur.execute(
                "UPDATE tools SET install_count = COALESCE(install_count,0)+1 WHERE id = %s",
                (tool_id,),
            )
    return jsonify({
        "added": added,
        "tool_id": tool_id,
        "slug": tool.get("slug"),
        "delivery": tool.get("delivery") or "embedded",
        "installed_locally": mark_installed,
    })


@app.route("/api/me/items/<int:tool_id>", methods=["DELETE"])
def shelf_remove(tool_id: int):
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            DELETE FROM user_items
            WHERE (user_id = %s OR (%s IS NOT NULL AND user_email = %s))
              AND tool_id = %s
            RETURNING id
            """,
            (uid, email, email, tool_id),
        )
        removed = cur.fetchone() is not None
        if removed:
            cur.execute(
                "UPDATE tools SET install_count = GREATEST(0, COALESCE(install_count,0)-1) WHERE id = %s",
                (tool_id,),
            )
    return jsonify({"removed": removed, "tool_id": tool_id})


@app.route("/api/me/items/<int:tool_id>/launch", methods=["POST"])
def shelf_open(tool_id: int):
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            UPDATE user_items
            SET open_count = open_count + 1, last_opened_at = NOW()
            WHERE (user_id = %s OR (%s IS NOT NULL AND user_email = %s))
              AND tool_id = %s
            RETURNING open_count
            """,
            (uid, email, email, tool_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not_in_shelf"}), 404
    return jsonify({"open_count": row["open_count"]})


@app.route("/api/me/items/<int:tool_id>/install", methods=["POST"])
def shelf_mark_installed(tool_id: int):
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    body = request.get_json(silent=True) or {}
    version = body.get("version") or "manual"
    with db.get_db() as cur:
        cur.execute(
            """
            UPDATE user_items
            SET installed_locally = TRUE, installed_at = NOW(), installed_version = %s
            WHERE (user_id = %s OR (%s IS NOT NULL AND user_email = %s))
              AND tool_id = %s
            RETURNING id
            """,
            (version, uid, email, email, tool_id),
        )
        row = cur.fetchone()
    return jsonify({"installed": row is not None, "version": version})


# -------------------- Install discovery (agent scan) --------------------

def _reconcile_matches(user_id: str, payload: dict, cur) -> set:
    """Three-pass match: bundle ID, brew formula, brew cask.

    Upserts user_items rows with source='detected'. Manual-source rows that
    are already installed_locally=TRUE keep source='manual'. Manual rows with
    installed_locally=FALSE are upgraded to TRUE on detection (source stays
    'manual'). Returns the set of matched tool ids for the caller's bookkeeping.
    """
    bundle_ids = [a["bundle_id"] for a in payload.get("apps", []) if a.get("bundle_id")]
    formulas = list(payload.get("brew", []))
    casks = list(payload.get("brew_casks", []))

    matched = set()

    if bundle_ids:
        cur.execute(
            "SELECT id FROM tools WHERE app_bundle_id = ANY(%s) AND status = 'approved'",
            (bundle_ids,),
        )
        matched.update(r[0] for r in cur.fetchall())

    if formulas:
        cur.execute(
            """
            SELECT id FROM tools
            WHERE status = 'approved'
              AND install_meta IS NOT NULL
              AND (install_meta::jsonb)->>'type' = 'brew'
              AND (install_meta::jsonb)->>'formula' = ANY(%s)
            """,
            (formulas,),
        )
        matched.update(r[0] for r in cur.fetchall())

    if casks:
        cur.execute(
            """
            SELECT id FROM tools
            WHERE status = 'approved'
              AND install_meta IS NOT NULL
              AND (install_meta::jsonb)->>'type' = 'brew'
              AND (install_meta::jsonb)->>'cask' = ANY(%s)
            """,
            (casks,),
        )
        matched.update(r[0] for r in cur.fetchall())

    for tool_id in matched:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
            VALUES (%s, %s, TRUE, NOW(), 'detected')
            ON CONFLICT (user_id, tool_id) WHERE user_id IS NOT NULL DO UPDATE
              SET installed_locally = TRUE,
                  installed_at = COALESCE(user_items.installed_at, NOW()),
                  source = CASE WHEN user_items.source = 'manual'
                                THEN 'manual' ELSE 'detected' END
            """,
            (user_id, tool_id),
        )

    return matched


def _reconcile_unknowns(user_id: str, apps: list, matched_tool_ids: set, cur) -> int:
    """Upsert user_items rows for apps that didn't match any catalog tool.

    Identifies unknowns by bundle_id; preserves hidden=TRUE when re-detecting.
    Returns the count of unknown rows touched.
    """
    # Build the set of bundle_ids that matched a catalog tool — those don't become unknowns.
    if matched_tool_ids:
        cur.execute(
            "SELECT app_bundle_id FROM tools WHERE id = ANY(%s) AND app_bundle_id IS NOT NULL",
            (list(matched_tool_ids),),
        )
        matched_bundle_ids = {r[0] for r in cur.fetchall()}
    else:
        matched_bundle_ids = set()

    touched = 0
    for app in apps:
        bundle_id = app.get("bundle_id")
        if not bundle_id or bundle_id in matched_bundle_ids:
            continue
        name = app.get("name") or bundle_id
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name,
                                    source, installed_locally, installed_at, hidden)
            VALUES (%s, NULL, %s, %s, 'detected', TRUE, NOW(), FALSE)
            ON CONFLICT (user_id, detected_bundle_id) WHERE tool_id IS NULL AND detected_bundle_id IS NOT NULL
            DO UPDATE SET
                detected_name     = EXCLUDED.detected_name,
                installed_locally = TRUE,
                installed_at      = COALESCE(user_items.installed_at, NOW())
                -- hidden is intentionally NOT touched here
            """,
            (user_id, bundle_id, name),
        )
        touched += 1
    return touched


def _reconcile_uninstalls(user_id: str, payload: dict, matched_tool_ids: set, cur) -> int:
    """Set installed_locally=FALSE for source='detected' rows missing from this scan.

    - Matched rows (tool_id NOT NULL): keyed by app_bundle_id / install_meta lookup.
    - Unknown rows (tool_id NULL): keyed by detected_bundle_id.
    Manual-source rows are never touched.
    """
    seen_bundle_ids = {a["bundle_id"] for a in payload.get("apps", []) if a.get("bundle_id")}
    seen_formulas = set(payload.get("brew", []))
    seen_casks = set(payload.get("brew_casks", []))

    # Pre-load currently-detected, currently-installed shelf rows for this user.
    cur.execute(
        """
        SELECT ui.id, ui.tool_id, ui.detected_bundle_id,
               t.app_bundle_id,
               (t.install_meta::jsonb)->>'formula' AS formula,
               (t.install_meta::jsonb)->>'cask' AS cask
        FROM user_items ui
        LEFT JOIN tools t ON t.id = ui.tool_id
        WHERE ui.user_id = %s
          AND ui.source = 'detected'
          AND ui.installed_locally = TRUE
        """,
        (user_id,),
    )
    candidates = cur.fetchall()

    to_unmark = []
    for row in candidates:
        ui_id, tool_id, det_bundle_id, app_bundle_id, formula, cask = row
        if tool_id is None:
            # Unknown row — key on detected_bundle_id.
            if det_bundle_id and det_bundle_id not in seen_bundle_ids:
                to_unmark.append(ui_id)
        else:
            # Matched row — present in scan if any of its match keys match.
            present = (
                (app_bundle_id and app_bundle_id in seen_bundle_ids)
                or (formula and formula in seen_formulas)
                or (cask and cask in seen_casks)
            )
            if not present:
                to_unmark.append(ui_id)

    if to_unmark:
        cur.execute(
            "UPDATE user_items SET installed_locally = FALSE, installed_at = NULL WHERE id = ANY(%s)",
            (to_unmark,),
        )
    return len(to_unmark)


@app.route("/api/agent/scan", methods=["POST"])
def agent_scan():
    """Receive a scan payload from forge_agent and reconcile against this user's shelf.

    Body shape:
        {"apps": [{"bundle_id": str, "name": str, "path": str}, ...],
         "brew": [str, ...],
         "brew_casks": [str, ...]}
    """
    uid, _email = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("apps"), list):
        return jsonify({"error": "apps_must_be_list"}), 400

    with db.get_db(dict_cursor=False) as cur:
        matched = _reconcile_matches(uid, payload, cur)
        _reconcile_unknowns(uid, payload["apps"], matched, cur)
        unmarked = _reconcile_uninstalls(uid, payload, matched, cur)

        cur.execute(
            """SELECT COUNT(*) FROM user_items
               WHERE user_id = %s AND tool_id IS NULL
                 AND installed_locally = TRUE AND hidden = FALSE""",
            (uid,),
        )
        detected_count = cur.fetchone()[0]

    return jsonify({
        "matched":  len(matched),
        "detected": detected_count,
        "unmarked": unmarked,
    })


# -------------------- Reviews --------------------

@app.route("/api/tools/<int:tool_id>/reviews", methods=["GET"])
def list_reviews(tool_id: int):
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT r.id, r.user_id, r.rating, r.note, r.created_at,
                   u.name AS author_name, u.email AS author_email
            FROM tool_reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            WHERE r.tool_id = %s
            ORDER BY r.created_at DESC
            """,
            (tool_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT AVG(rating)::float AS avg, COUNT(*) AS n FROM tool_reviews WHERE tool_id = %s",
            (tool_id,),
        )
        agg = dict(cur.fetchone())
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify({
        "tool_id": tool_id,
        "reviews": rows,
        "avg_rating": agg.get("avg"),
        "review_count": agg.get("n") or 0,
    })


@app.route("/api/tools/<int:tool_id>/reviews", methods=["POST"])
def post_review(tool_id: int):
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    body = request.get_json(silent=True) or {}
    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        return jsonify({"error": "rating_must_be_1_to_5"}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error": "rating_must_be_1_to_5"}), 400
    note = (body.get("note") or "").strip() or None
    with db.get_db() as cur:
        cur.execute(
            """
            INSERT INTO tool_reviews (tool_id, user_id, rating, note)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tool_id, user_id) DO UPDATE SET
              rating = EXCLUDED.rating,
              note = EXCLUDED.note,
              updated_at = NOW()
            RETURNING id, rating, note
            """,
            (tool_id, uid, rating, note),
        )
        row = cur.fetchone()
        # Update denormalized aggregates on the tool
        cur.execute(
            """
            UPDATE tools
            SET avg_rating = COALESCE((SELECT AVG(rating) FROM tool_reviews WHERE tool_id = %s), 0),
                review_count = COALESCE((SELECT COUNT(*) FROM tool_reviews WHERE tool_id = %s), 0)
            WHERE id = %s
            """,
            (tool_id, tool_id, tool_id),
        )
    return jsonify({"id": row["id"], "rating": row["rating"], "note": row["note"]})


# -------------------- Inspection / Trust card --------------------

@app.route("/api/tools/<int:tool_id>/inspection", methods=["GET"])
def get_tool_inspection(tool_id: int):
    from api.inspector import get_inspection, render_badges
    insp = get_inspection(tool_id)
    if not insp:
        return jsonify({"tool_id": tool_id, "badges": [], "ready": False})
    return jsonify({
        "tool_id": tool_id,
        "ready": True,
        "badges": render_badges(insp),
        "raw": insp,
    })


@app.route("/api/tools/<int:tool_id>/inspect", methods=["POST"])
def reinspect_tool(tool_id: int):
    """Re-run inspection on demand. Useful after `update-html`."""
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    from api.inspector import store_inspection, render_badges
    insp = store_inspection(tool_id, tool.get("app_html") or "")
    return jsonify({"tool_id": tool_id, "badges": render_badges(insp), "raw": insp})


# -------------------- Skill subscriptions --------------------

@app.route("/api/me/skills", methods=["GET"])
def list_skill_subs():
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT s.*, ss.subscribed_at, ss.last_synced_at, ss.installed_version
            FROM skill_subscriptions ss
            JOIN skills s ON s.id = ss.skill_id
            WHERE ss.user_id = %s
            ORDER BY ss.subscribed_at DESC
            """,
            (uid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"skills": rows, "count": len(rows)})


@app.route("/api/me/skills/<int:skill_id>", methods=["POST"])
def subscribe_skill(skill_id: int):
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            INSERT INTO skill_subscriptions (user_id, skill_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, skill_id) DO NOTHING
            RETURNING id
            """,
            (uid, skill_id),
        )
        added = cur.fetchone() is not None
    return jsonify({"subscribed": added, "skill_id": skill_id})


@app.route("/api/me/skills/<int:skill_id>", methods=["DELETE"])
def unsubscribe_skill(skill_id: int):
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            "DELETE FROM skill_subscriptions WHERE user_id = %s AND skill_id = %s RETURNING id",
            (uid, skill_id),
        )
        removed = cur.fetchone() is not None
    return jsonify({"unsubscribed": removed, "skill_id": skill_id})


@app.route("/api/me/skills/sync", methods=["GET"])
def skills_sync_payload():
    """Used by `forge sync`. Returns every subscribed skill's full content."""
    uid, _ = _get_identity()
    if not uid:
        return jsonify({"error": "user_id_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT s.id, s.title, s.prompt_text, s.category, s.author_name,
                   ss.installed_version
            FROM skill_subscriptions ss
            JOIN skills s ON s.id = ss.skill_id
            WHERE ss.user_id = %s
            """,
            (uid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"skills": rows, "count": len(rows)})


# -------------------- Social aggregations --------------------

@app.route("/api/tools/<int:tool_id>/social", methods=["GET"])
def social_stats(tool_id: int):
    """Per-tool social aggregates: installs, team installs, role concentration, weekly."""
    uid, _ = _get_identity()
    user_team = None
    if uid:
        with db.get_db() as cur:
            cur.execute("SELECT team FROM users WHERE user_id = %s", (uid,))
            row = cur.fetchone()
            if row:
                user_team = row.get("team")
    with db.get_db() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM user_items WHERE tool_id = %s",
            (tool_id,),
        )
        total = cur.fetchone()["n"]
        team_n = 0
        role_concentration = None
        installs_this_week = 0
        if user_team:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                WHERE ui.tool_id = %s AND u.team = %s
                """,
                (tool_id, user_team),
            )
            team_n = cur.fetchone()["n"]
            # Role concentration: which role dominates installs for this tool on this team?
            if team_n >= 2:
                cur.execute(
                    """
                    SELECT u.role, COUNT(*) AS n FROM user_items ui
                    JOIN users u ON u.user_id = ui.user_id
                    WHERE ui.tool_id = %s AND u.team = %s AND u.role IS NOT NULL
                    GROUP BY u.role ORDER BY n DESC LIMIT 1
                    """,
                    (tool_id, user_team),
                )
                top_role = cur.fetchone()
                if top_role and top_role["n"] / team_n > 0.6:
                    role_concentration = {
                        "role": top_role["role"],
                        "count": top_role["n"],
                        "total": team_n,
                    }
            # Installs this week on team
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                WHERE ui.tool_id = %s AND u.team = %s
                  AND ui.added_at >= NOW() - INTERVAL '7 days'
                """,
                (tool_id, user_team),
            )
            installs_this_week = cur.fetchone()["n"]
        cur.execute(
            "SELECT AVG(rating)::float AS avg, COUNT(*) AS n FROM tool_reviews WHERE tool_id = %s",
            (tool_id,),
        )
        ratings = dict(cur.fetchone())
    return jsonify({
        "tool_id": tool_id,
        "install_count": total,
        "team_install_count": team_n,
        "team": user_team,
        "avg_rating": ratings.get("avg"),
        "review_count": ratings.get("n") or 0,
        "role_concentration": role_concentration,
        "installs_this_week": installs_this_week,
    })


@app.route("/api/tools/<int:tool_id>/coinstalls", methods=["GET"])
def tool_coinstalls(tool_id: int):
    """Top 3 tools most frequently co-installed with this tool."""
    uid, _ = _get_identity()
    with db.get_db() as cur:
        user_count = 0
        if uid:
            cur.execute("SELECT COUNT(*) AS n FROM user_items WHERE user_id = %s", (uid,))
            user_count = cur.fetchone()["n"]

        if user_count >= 5 and uid:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon, COUNT(*) as overlap
                FROM user_items ui2
                JOIN tools t ON t.id = ui2.tool_id
                WHERE ui2.user_id IN (
                    SELECT ui3.user_id FROM user_items ui3
                    WHERE ui3.tool_id IN (
                        SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                    )
                    AND ui3.user_id != %(uid)s
                    GROUP BY ui3.user_id
                    HAVING COUNT(*) >= 2
                )
                AND ui2.tool_id != %(tool_id)s
                AND t.status = 'approved'
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY overlap DESC
                LIMIT 3
            """, {"uid": uid, "tool_id": tool_id})
        else:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon, COUNT(*) as overlap
                FROM user_items ui2
                JOIN tools t ON t.id = ui2.tool_id
                WHERE ui2.user_id IN (
                    SELECT user_id FROM user_items WHERE tool_id = %(tool_id)s
                )
                AND ui2.tool_id != %(tool_id)s
                AND t.status = 'approved'
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY overlap DESC
                LIMIT 3
            """, {"tool_id": tool_id})

        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"tool_id": tool_id, "coinstalls": rows})


@app.route("/api/team/trending", methods=["GET"])
def team_trending():
    """Role-aware trending + team popular tools for catalog discovery strip."""
    uid, email = _get_identity()
    if not uid:
        return jsonify({"role_trending": [], "team_popular": [], "role": None, "team": None})

    user_role = None
    user_team = None
    with db.get_db() as cur:
        cur.execute("SELECT role, team FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        if row:
            user_role = row.get("role")
            user_team = row.get("team")

    role_trending = []
    team_popular = []

    with db.get_db() as cur:
        if user_role:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon,
                       COUNT(*) as installs_this_week
                FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                JOIN tools t ON t.id = ui.tool_id
                WHERE u.role = %(role)s
                  AND ui.added_at >= NOW() - INTERVAL '7 days'
                  AND t.status = 'approved'
                  AND ui.tool_id NOT IN (
                      SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                  )
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY installs_this_week DESC
                LIMIT 3
            """, {"role": user_role, "uid": uid})
            role_trending = [
                {**dict(r), "reason": f"{r['installs_this_week']} {user_role}s installed this week"}
                for r in cur.fetchall()
            ]

        if user_team:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.icon,
                       COUNT(*) as team_installs
                FROM user_items ui
                JOIN users u ON u.user_id = ui.user_id
                JOIN tools t ON t.id = ui.tool_id
                WHERE u.team = %(team)s
                  AND t.status = 'approved'
                  AND ui.tool_id NOT IN (
                      SELECT tool_id FROM user_items WHERE user_id = %(uid)s
                  )
                GROUP BY t.id, t.slug, t.name, t.icon
                ORDER BY team_installs DESC
                LIMIT 3
            """, {"team": user_team, "uid": uid})
            team_popular = [
                {**dict(r), "reason": "popular on your team"}
                for r in cur.fetchall()
            ]

    return jsonify({
        "role_trending": role_trending,
        "team_popular": team_popular,
        "role": user_role,
        "team": user_team,
    })


# -------------------- App versions --------------------

@app.route("/api/tools/<int:tool_id>/versions", methods=["GET"])
def list_app_versions(tool_id: int):
    with db.get_db() as cur:
        cur.execute(
            "SELECT * FROM app_versions WHERE tool_id = %s ORDER BY version_number DESC",
            (tool_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        # don't ship app_html in list view (heavy)
        r.pop("app_html", None)
    return jsonify({"tool_id": tool_id, "versions": rows, "count": len(rows)})


@app.route("/api/me/updates", methods=["GET"])
def updates_for_user():
    """Items on the user's shelf that have a newer version than what they have."""
    uid, email = _get_identity()
    if not uid and not email:
        return jsonify({"error": "user_id_or_email_required"}), 400
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT t.id, t.slug, t.name, t.icon, t.version AS current_version,
                   ui.installed_version, ui.installed_locally,
                   (SELECT changelog FROM app_versions
                    WHERE tool_id = t.id ORDER BY version_number DESC LIMIT 1) AS latest_changelog,
                   (SELECT is_security FROM app_versions
                    WHERE tool_id = t.id ORDER BY version_number DESC LIMIT 1) AS is_security
            FROM user_items ui
            JOIN tools t ON t.id = ui.tool_id
            WHERE (ui.user_id = %s OR (%s IS NOT NULL AND ui.user_email = %s))
            """,
            (uid, email, email),
        )
        rows = [dict(r) for r in cur.fetchall()]
    pending = [r for r in rows
               if r.get("installed_version") and str(r["installed_version"]) != str(r.get("current_version"))]
    return jsonify({"updates": pending, "count": len(pending)})


# -------------------- Shareable tokens --------------------

@app.route("/api/t/<string:access_token>", methods=["GET"])
def resolve_token(access_token):
    row = db.get_tool_by_access_token(access_token)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "slug": row.get("slug"),
        "name": row.get("name"),
        "url": f"/apps/{row.get('slug')}",
    })


# -------------------- Skills --------------------

@app.route("/api/skills", methods=["GET"])
def list_skills():
    category = request.args.get("category")
    search = request.args.get("search")
    # Admin can see all statuses; default is approved-only
    include = request.args.get("include")
    if include == "pending":
        admin_check = _require_admin()
        if admin_check:
            return admin_check
        review_status = None  # no filter — show all
    else:
        review_status = "approved"
    rows = db.list_skills(category=category, search=search, review_status=review_status)
    return jsonify({
        "skills": [Skill.from_row(r).to_dict() for r in rows],
        "count": len(rows),
    })


@app.route("/api/skills", methods=["POST"])
def submit_skill():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    prompt_text = (body.get("prompt_text") or "").strip()
    if not title:
        return jsonify({"error": "validation", "message": "title required"}), 400
    if not prompt_text:
        return jsonify({"error": "validation", "message": "prompt_text required"}), 400

    data = {
        "title": title,
        "description": body.get("description") or "",
        "prompt_text": prompt_text,
        "category": body.get("category") or "other",
        "use_case": body.get("use_case") or "",
        "author_name": body.get("author_name") or "",
        "source_url": body.get("source_url") or "",
        "review_status": "pending",
    }

    # Handle data_sensitivity if provided
    sensitivity = body.get("data_sensitivity")
    if sensitivity and sensitivity in ("public", "internal", "confidential"):
        data["data_sensitivity"] = sensitivity

    skill_id = db.insert_skill(data)

    # Store author-supplied test cases if provided
    test_cases_raw = body.get("test_cases")
    if test_cases_raw and isinstance(test_cases_raw, dict):
        cases = []
        for prompt in (test_cases_raw.get("positive") or []):
            cases.append({"kind": "positive", "prompt": prompt})
        for prompt in (test_cases_raw.get("negative") or []):
            cases.append({"kind": "negative", "prompt": prompt})
        if cases:
            db.insert_skill_test_cases(skill_id, cases)

    # Enqueue the review pipeline
    try:
        from forge_sandbox.tasks import skill_review_pipeline
        skill_review_pipeline.delay(skill_id)
    except Exception as exc:
        # Pipeline enqueue failed — skill stays pending, log the error.
        # Fail-closed: skill remains in 'pending' until pipeline runs.
        print(f"[server] skill_review_pipeline enqueue failed for skill {skill_id}: {exc}")

    return jsonify({"skill_id": skill_id, "status": "pending"}), 201


@app.route("/api/skills/<int:skill_id>/review", methods=["GET"])
def get_skill_review(skill_id):
    """Return review status and feedback for a skill."""
    skill = db.get_skill(skill_id)
    if not skill:
        return jsonify({"error": "not_found"}), 404

    result = {
        "skill_id": skill_id,
        "review_status": skill.get("review_status", "pending"),
        "review_id": skill.get("review_id"),
        "blocked_reason": skill.get("blocked_reason"),
        "approved_at": skill["approved_at"].isoformat() if skill.get("approved_at") else None,
        "blocked_at": skill["blocked_at"].isoformat() if skill.get("blocked_at") else None,
    }

    # Include review details if a review exists
    if skill.get("review_id"):
        review = db.get_review_by_skill(skill_id)
        if review:
            result["review"] = {
                "recommendation": review.get("agent_recommendation"),
                "confidence": review.get("agent_confidence"),
                "summary": review.get("review_summary"),
            }

    # Include test cases
    result["test_cases"] = db.get_skill_test_cases(skill_id)

    return jsonify(result)


@app.route("/api/skills/<int:skill_id>/upvote", methods=["POST"])
def upvote_skill(skill_id):
    count = db.increment_skill_upvotes(skill_id)
    if count is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"id": skill_id, "upvotes": count})


@app.route("/api/skills/<int:skill_id>/copy", methods=["POST"])
def copy_skill(skill_id):
    count = db.increment_skill_copy_count(skill_id)
    if count is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"id": skill_id, "copy_count": count})


@app.route("/api/skills/<int:skill_id>/download", methods=["GET"])
def download_skill(skill_id):
    row = db.get_skill(skill_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    db.increment_skill_copy_count(skill_id)
    from flask import Response
    content = row.get("prompt_text") or ""
    return Response(
        content,
        mimetype="text/markdown",
        headers={
            "Content-Disposition":
                f'attachment; filename="{row.get("title", "skill").replace(" ", "-")}.md"'
        },
    )


# -------------------- Admin --------------------

@app.route("/api/admin/tools/<int:tool_id>/update-html", methods=["POST"])
def admin_update_app_html(tool_id):
    """Trusted auto-redeploy path for approved app-type tools (GitHub webhook)."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    if (tool.get("app_type") or "prompt") != "app":
        return jsonify({"error": "not_an_app"}), 400

    body = request.get_json(silent=True) or {}
    html = body.get("html")
    if not isinstance(html, str) or not html.strip():
        return jsonify({"error": "validation", "message": "html required"}), 400

    db.update_tool(tool_id, app_html=html, deployed_at=datetime.utcnow())
    slug = tool.get("slug") or ""
    return jsonify({
        "success": True,
        "tool_id": tool_id,
        "slug": slug,
        "url": f"/apps/{slug}" if slug else None,
    })


# -------------------- Sandbox admin (T1-WAVE3) --------------------

@app.route("/api/admin/sandbox/status", methods=["GET"])
def admin_sandbox_status():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    try:
        from forge_sandbox.manager import SandboxManager
        return jsonify(SandboxManager().get_status())
    except Exception as exc:
        return jsonify({"error": "sandbox_error", "message": str(exc)}), 500


@app.route("/api/admin/sandbox/hibernate/<int:tool_id>", methods=["POST"])
def admin_sandbox_hibernate(tool_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    try:
        from forge_sandbox.manager import SandboxManager
        SandboxManager().hibernate(tool_id)
        return jsonify({"success": True, "tool_id": tool_id, "status": "stopped"})
    except Exception as exc:
        return jsonify({"error": "sandbox_error", "message": str(exc)}), 500


@app.route("/api/admin/sandbox/prewarm/<int:tool_id>", methods=["POST"])
def admin_sandbox_prewarm(tool_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    try:
        from forge_sandbox.manager import SandboxManager
        port = SandboxManager().pre_warm(tool_id)
        return jsonify({"success": port is not None, "tool_id": tool_id, "port": port})
    except Exception as exc:
        return jsonify({"error": "sandbox_error", "message": str(exc)}), 500


@app.route("/api/admin/tools/<int:tool_id>/enable-container", methods=["POST"])
def admin_enable_container(tool_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    if (tool.get("app_type") or "prompt") != "app":
        return jsonify({"error": "not_an_app"}), 400
    slug = tool.get("slug") or f"tool-{tool_id}"
    try:
        from forge_sandbox import builder
        result = builder.build_image(tool_id, tool.get("app_html") or "", slug)
    except Exception as exc:
        return jsonify({"error": "build_error", "message": str(exc)}), 500
    if not result.get("success"):
        return jsonify({"success": False, "image_tag": None,
                        "build_output": result.get("build_output", "")}), 500
    db.update_tool(tool_id, container_mode=True)
    return jsonify({"success": True, "tool_id": tool_id,
                    "image_tag": result.get("image_tag")})


@app.route("/api/admin/skills/<int:skill_id>/override", methods=["POST"])
def admin_override_skill(skill_id):
    """Admin override: approve, block, retroactively block, or unblock a skill."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    skill = db.get_skill(skill_id)
    if not skill:
        return jsonify({"error": "not_found"}), 404

    body = request.get_json(silent=True) or {}
    action = body.get("action")
    reason = (body.get("reason") or "").strip()

    valid_actions = {"override_approve", "override_block", "retroactive_block", "unblock", "manual_rereview"}
    if action not in valid_actions:
        return jsonify({"error": "validation", "message": f"action must be one of {sorted(valid_actions)}"}), 400
    if len(reason) < 20:
        return jsonify({"error": "validation", "message": "reason must be at least 20 characters"}), 400

    from_status = skill.get("review_status")

    # Determine new status
    status_map = {
        "override_approve": "approved",
        "override_block": "blocked",
        "retroactive_block": "blocked",
        "unblock": "approved",
        "manual_rereview": "pending",
    }
    to_status = status_map[action]

    # Update skill
    update_fields = {"review_status": to_status}
    if to_status == "approved":
        from datetime import datetime as dt
        update_fields["approved_at"] = dt.utcnow()
        update_fields["blocked_reason"] = None
        update_fields["blocked_at"] = None
    elif to_status == "blocked":
        from datetime import datetime as dt
        update_fields["blocked_reason"] = f"{action}:{reason}"
        update_fields["blocked_at"] = dt.utcnow()

    db.update_skill(skill_id, **update_fields)

    # Log the admin action
    reviewer = request.headers.get("X-Admin-User", "admin")
    db.insert_skill_admin_action(
        skill_id=skill_id,
        action=action,
        reason=reason,
        reviewer=reviewer,
        from_status=from_status,
        to_status=to_status,
    )

    # If manual_rereview, enqueue pipeline again
    if action == "manual_rereview":
        try:
            from forge_sandbox.tasks import skill_review_pipeline
            skill_review_pipeline.delay(skill_id)
        except Exception as exc:
            print(f"[server] re-review enqueue failed for skill {skill_id}: {exc}")

    return jsonify({
        "skill_id": skill_id,
        "review_status": to_status,
        "action": action,
    })


# -------------------- App upload (keep — used by forge CLI + GitHub bot) --------------------

@app.route("/api/submit/app", methods=["POST"])
def submit_app():
    """Submit a full HTML app. Accepts either multipart (html/file) or JSON.

    Body (JSON):  {html, name, tagline, description, category, author_name, author_email}
    Multipart:    same fields + optional `file` (zip containing index.html)

    No pipeline dispatch — apps go straight to `pending_review` for admin approval.
    """
    import io
    import json
    import zipfile

    content_type = (request.content_type or "").lower()
    if "multipart/form-data" in content_type:
        form = request.form
        html = form.get("html")
        upload = request.files.get("file")
        if upload and not html:
            try:
                if upload.filename and upload.filename.lower().endswith(".zip"):
                    z = zipfile.ZipFile(io.BytesIO(upload.read()))
                    candidates = [n for n in z.namelist() if n.endswith("index.html")]
                    if not candidates:
                        return jsonify({"error": "validation",
                                        "message": "zip missing index.html"}), 400
                    html = z.read(candidates[0]).decode("utf-8", errors="replace")
                else:
                    html = upload.read().decode("utf-8", errors="replace")
            except Exception as exc:
                return jsonify({"error": "upload_error", "message": str(exc)}), 400
        data = {k: form.get(k) for k in
                ("name", "tagline", "description", "category", "author_name", "author_email")}
    else:
        body = request.get_json(silent=True) or {}
        html = body.get("html")
        data = {k: body.get(k) for k in
                ("name", "tagline", "description", "category", "author_name", "author_email")}

    if not html or not html.strip():
        return jsonify({"error": "validation", "message": "html required"}), 400
    name = re.sub(r"<[^>]+>", "", (data.get("name") or "")).strip()
    if not name:
        return jsonify({"error": "validation", "message": "name required"}), 400
    tagline = re.sub(r"<[^>]+>", "", (data.get("tagline") or "")).strip()
    if not tagline:
        return jsonify({"error": "validation", "message": "tagline required"}), 400
    author_email = (data.get("author_email") or "").strip()
    if not author_email:
        return jsonify({"error": "validation", "message": "author_email required"}), 400

    slug = _unique_slug(_slugify(name))
    row = {
        "slug": slug,
        "name": name,
        "tagline": tagline,
        "description": data.get("description") or "",
        "category": data.get("category") or "Other",
        "app_type": "app",
        "app_html": html,
        "status": "pending_review",
        "version": 1,
        "author_name": data.get("author_name") or "",
        "author_email": author_email,
        "submitted_at": datetime.utcnow(),
    }
    tool_id = db.insert_tool(row)

    # Auto-inspect at submit time so the trust card is ready immediately.
    try:
        from api.inspector import store_inspection
        store_inspection(tool_id, html)
    except Exception as exc:
        print(f"[server] inspection failed for tool {tool_id}: {exc}")
    # Auto-approve seeded path with no review (admin can later require review per-org).
    db.update_tool(tool_id, status="approved", approved_at=datetime.utcnow(),
                   approved_by="auto", deployed=True, deployed_at=datetime.utcnow())

    # Record initial version
    try:
        with db.get_db() as cur:
            cur.execute(
                """
                INSERT INTO app_versions (tool_id, version_number, app_html, changelog, is_user_facing, created_by)
                VALUES (%s, 1, %s, %s, FALSE, %s)
                """,
                (tool_id, html, "Initial version.", row["author_email"]),
            )
    except Exception as exc:
        print(f"[server] versioning failed for tool {tool_id}: {exc}")

    return jsonify({
        "id": tool_id,
        "slug": slug,
        "url": f"/apps/{slug}",
        "status": "pending_review",
    }), 201


# -------------------- Publish from GitHub --------------------

@app.route("/api/submit/from-github", methods=["POST"])
def submit_from_github():
    """Clone a public GitHub repo, find index.html, publish it.

    Accepts {github_url, name, tagline, description, category, author_name, author_email, icon}.
    Returns {id, slug, url, status}.
    """
    import shutil
    import subprocess
    import tempfile

    body = request.get_json(silent=True) or {}
    github_url = (body.get("github_url") or "").strip()
    if not github_url or "github.com" not in github_url:
        return jsonify({"error": "validation", "message": "github_url required"}), 400
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "validation", "message": "name required"}), 400
    tagline = (body.get("tagline") or "").strip()
    if not tagline:
        return jsonify({"error": "validation", "message": "tagline required"}), 400
    author_email = (body.get("author_email") or "").strip()
    if not author_email:
        return jsonify({"error": "validation", "message": "author_email required"}), 400

    tmp = tempfile.mkdtemp(prefix="forge-gh-")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", github_url, tmp],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return jsonify({"error": "clone_failed", "message": result.stderr.strip()[:300]}), 400
        # find index.html
        index_path = None
        for root, _, files in os.walk(tmp):
            if ".git" in root:
                continue
            if "index.html" in files:
                index_path = os.path.join(root, "index.html")
                break
        if not index_path:
            return jsonify({"error": "no_index_html",
                            "message": "Repo does not contain an index.html"}), 400
        with open(index_path, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass

    slug = _unique_slug(_slugify(name))
    row = {
        "slug": slug,
        "name": name,
        "tagline": tagline,
        "description": body.get("description") or "",
        "category": body.get("category") or "Other",
        "app_type": "app",
        "app_html": html,
        "delivery": "embedded",
        "icon": body.get("icon") or "⊞",
        "source_url": github_url,
        "status": "approved",
        "version": 1,
        "author_name": body.get("author_name") or "",
        "author_email": author_email,
        "deployed": True,
        "deployed_at": datetime.utcnow(),
        "approved_at": datetime.utcnow(),
        "approved_by": "auto",
        "endpoint_url": f"/apps/{slug}",
        "submitted_at": datetime.utcnow(),
    }
    tool_id = db.insert_tool(row)

    try:
        from api.inspector import store_inspection
        store_inspection(tool_id, html)
    except Exception:
        pass
    try:
        with db.get_db() as cur:
            cur.execute(
                "INSERT INTO app_versions (tool_id, version_number, app_html, changelog, is_user_facing, created_by) VALUES (%s, 1, %s, %s, FALSE, %s)",
                (tool_id, html, "Cloned from " + github_url, author_email),
            )
    except Exception:
        pass

    return jsonify({
        "id": tool_id, "slug": slug,
        "url": f"/apps/{slug}",
        "status": "approved", "source": "github",
    }), 201


# -------------------- Blueprint registrations --------------------

try:
    from api.apps import apps_bp  # type: ignore
    app.register_blueprint(apps_bp)
except Exception as e:
    print(f"[server] apps blueprint failed: {e}")

try:
    from api.admin import admin_bp  # type: ignore
    app.register_blueprint(admin_bp)
except Exception as e:
    print(f"[server] admin blueprint failed: {e}")

try:
    from api.deploy import deploy_bp  # type: ignore
    app.register_blueprint(deploy_bp)
except Exception:
    pass

try:
    from api.forgedata import forgedata_bp  # type: ignore
    app.register_blueprint(forgedata_bp)
except Exception:
    pass


# -------------------- Main --------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    host = os.environ.get("HOST", "0.0.0.0")
    try:
        db.init_db()
    except Exception as e:
        print(f"[warn] init_db failed: {e}")
    app.run(host=host, port=port, debug=False)
