"""
Forge Flask API server.
Port 8090. JSON responses under /api/. Serves frontend/ as static files.

After the prompt-stack demolition: Forge serves apps (HTML bundles) and skills
(SKILL.md files). No prompt tools, no agent review pipeline, no creator/learning/
workflow modules. Pre-demolition state is tagged `pre-prompt-demolition`.
"""
import os
import re
import threading
import time
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
    if path.startswith("api/"):
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
    rows = db.list_skills(category=category, search=search)
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
    }
    skill_id = db.insert_skill(data)
    return jsonify({"id": skill_id, "status": "ok"}), 201


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
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "validation", "message": "name required"}), 400
    tagline = (data.get("tagline") or "").strip()
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
    return jsonify({
        "id": tool_id,
        "slug": slug,
        "url": f"/apps/{slug}",
        "status": "pending_review",
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
