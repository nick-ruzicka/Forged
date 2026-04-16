"""
Forge Flask API server.
Port 8090. JSON responses under /api/. Serves frontend/ as static files.
"""
import io
import json
import os
import re
import secrets
import threading
import time
import uuid
import zipfile
from collections import deque
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from api import db, executor
from api.models import AgentReview, Run, Skill, Tool, compute_trust_tier

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)

VERSION = "0.1.0"
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
    return s or f"tool-{int(time.time())}"


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
    t = Tool.from_row(row).to_dict()
    return t


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


# -------------------- Pipeline launch --------------------

def _launch_pipeline(tool_id: int):
    """Dispatch the agent pipeline to a Celery worker.

    Falls back to an in-process thread only if Celery dispatch fails — the
    production path is always the worker so Flask never blocks on Claude calls.
    """
    try:
        from celery_app import celery_app  # type: ignore
        celery_app.send_task("agents.tasks.run_pipeline_task", args=[tool_id])
        return
    except Exception as exc:
        print(f"[server] celery dispatch failed for tool {tool_id}: {exc}")

    def _run():
        try:
            from agents import pipeline  # type: ignore
        except Exception:
            return
        runner = getattr(pipeline, "run_pipeline", None) or getattr(pipeline, "run", None)
        if not runner:
            return
        try:
            runner(tool_id)
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# -------------------- Tools --------------------

@app.route("/api/tools", methods=["GET"])
def list_tools():
    category = request.args.get("category")
    output_type = request.args.get("output_type")
    trust_tier = request.args.get("trust_tier")
    app_type = request.args.get("app_type") or request.args.get("type")
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
        output_type=output_type,
        trust_tier=trust_tier,
        app_type=app_type,
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


@app.route("/api/tools/slug/<string:slug>/run", methods=["POST"])
def run_tool_by_slug(slug):
    row = db.get_tool_by_slug(slug)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return run_tool(row["id"])


@app.route("/api/tools/<int:tool_id>/versions", methods=["GET"])
def tool_versions(tool_id):
    rows = db.list_tool_versions(tool_id)
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify({"versions": rows})


@app.route("/api/tools/submit", methods=["POST"])
def submit_tool():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    tagline = (body.get("tagline") or "").strip()
    prompt = body.get("system_prompt") or body.get("prompt") or ""
    input_schema = body.get("input_schema") or []
    author_name = body.get("author_name") or ""
    author_email = body.get("author_email") or ""

    if not name:
        return jsonify({"error": "validation", "message": "name required"}), 400
    if not tagline:
        return jsonify({"error": "validation", "message": "tagline required"}), 400
    if not prompt.strip():
        return jsonify({"error": "validation", "message": "system_prompt required"}), 400
    if not author_email:
        return jsonify({"error": "validation", "message": "author_email required"}), 400

    if isinstance(input_schema, list):
        schema_str = json.dumps(input_schema)
    elif isinstance(input_schema, str):
        try:
            parsed = json.loads(input_schema)
            if not isinstance(parsed, list):
                return jsonify({"error": "validation", "message": "input_schema must be a list"}), 400
            schema_str = input_schema
        except json.JSONDecodeError:
            return jsonify({"error": "validation", "message": "input_schema is not valid JSON"}), 400
    else:
        return jsonify({"error": "validation", "message": "input_schema must be a list"}), 400

    injection_markers = ["ignore previous instructions", "ignore all previous"]
    low = prompt.lower()
    if any(m in low for m in injection_markers):
        return jsonify({
            "error": "preflight_failed",
            "message": "Prompt contains injection-like markers"
        }), 400

    slug_base = _slugify(body.get("slug") or name)
    slug = _unique_slug(slug_base)

    data = {
        "slug": slug,
        "name": name,
        "tagline": tagline,
        "description": body.get("description") or "",
        "category": body.get("category") or "Other",
        "tags": body.get("tags") or "",
        "output_type": body.get("output_type") or "probabilistic",
        "output_format": body.get("output_format") or "text",
        "system_prompt": prompt,
        "input_schema": schema_str,
        "model": body.get("model") or "claude-haiku-4-5-20251001",
        "max_tokens": int(body.get("max_tokens") or 1000),
        "temperature": float(body.get("temperature") or 0.3),
        "status": "pending_review",
        "version": 1,
        "author_name": author_name,
        "author_email": author_email,
        "data_sensitivity": body.get("data_sensitivity") or "internal",
        "submitted_at": datetime.utcnow(),
    }
    tool_id = db.insert_tool(data)
    _launch_pipeline(tool_id)

    return jsonify({"id": tool_id, "slug": slug, "status": "pending_review"}), 201


@app.route("/api/tools/test", methods=["POST"])
def test_prompt():
    """Run a prompt + sample inputs ad-hoc WITHOUT persisting a tool.

    Used by the single-page submit flow so authors can try their prompt before
    filling in any metadata. Body:
        {"system_prompt": str, "inputs": {name: value}, "model": optional str,
         "max_tokens": optional int, "temperature": optional float}
    Returns {output: str, duration_ms: int}.
    """
    body = request.get_json(silent=True) or {}
    prompt = (body.get("system_prompt") or body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "validation", "message": "system_prompt required"}), 400
    inputs = body.get("inputs") or {}
    if not isinstance(inputs, dict):
        return jsonify({"error": "validation", "message": "inputs must be an object"}), 400

    model = body.get("model") or "claude-haiku-4-5-20251001"
    max_tokens = int(body.get("max_tokens") or 800)
    temperature = float(body.get("temperature") or 0.3)

    # Interpolate {{variables}} in the prompt
    def interpolate(template: str, values: dict) -> str:
        def repl(m):
            key = m.group(1).strip()
            v = values.get(key, "")
            return str(v) if v is not None else ""
        return re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, template)

    rendered = interpolate(prompt, inputs)

    start = time.time()
    try:
        from anthropic import Anthropic
        client = Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": rendered}],
        )
        output = resp.content[0].text if resp.content else ""
    except Exception as e:
        return jsonify({"error": "llm_failure", "message": str(e)}), 500
    duration_ms = int((time.time() - start) * 1000)
    return jsonify({
        "output": output,
        "duration_ms": duration_ms,
        "rendered_prompt": rendered,
        "model": model,
    })


@app.route("/api/tools/suggest-metadata", methods=["POST"])
def suggest_metadata():
    """Given a prompt (and optionally detected variables), suggest tool metadata.

    Returns {name, tagline, description, category, output_type, output_format}.
    Used to auto-fill the collapsed details drawer on the submit page.
    """
    body = request.get_json(silent=True) or {}
    prompt = (body.get("system_prompt") or body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "validation", "message": "system_prompt required"}), 400
    variables = body.get("variables") or []

    try:
        from anthropic import Anthropic
        client = Anthropic()
        sys_msg = (
            "You are a product designer for an internal AI tool marketplace at a B2B SaaS "
            "company. Given a prompt template, return STRICT JSON suggesting "
            "metadata. No markdown, no preamble."
        )
        user_msg = (
            f"Prompt template:\n\"\"\"\n{prompt}\n\"\"\"\n\n"
            f"Detected variables: {json.dumps(variables)}\n\n"
            "Return JSON with exactly these keys:\n"
            "{\n"
            '  "name": "Title Case Tool Name (3-40 chars)",\n'
            '  "tagline": "One sentence describing what it does (<=80 chars)",\n'
            '  "description": "2-3 sentences of plain text detail.",\n'
            '  "category": "one of: Account Research | Email Generation | Contact Scoring | Data Lookup | Reporting | Onboarding | Forecasting | Other",\n'
            '  "output_type": "deterministic | probabilistic | mixed",\n'
            '  "output_format": "text | markdown | email_draft | table | json"\n'
            "}"
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=sys_msg,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return jsonify({"error": "invalid_json_from_model", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "llm_failure", "message": str(e)}), 500

    return jsonify(data)


@app.route("/api/submit/app", methods=["POST"])
def submit_app():
    """Submit a full HTML app (single file or zip). Used by the forge CLI.

    Pipeline dispatch goes through Celery via _launch_pipeline — never inline.
    """
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    category = (request.form.get("category") or "Other").strip() or "Other"
    author_name = (request.form.get("author_name") or "").strip()
    author_email = (request.form.get("author_email") or "").strip()

    if not name:
        return jsonify({"error": "validation", "message": "name required"}), 400
    if not author_email:
        return jsonify({"error": "validation", "message": "author_email required"}), 400

    app_html = request.form.get("html") or ""
    upload = request.files.get("file")

    if not app_html and upload is not None:
        try:
            blob = upload.read()
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                index_name = None
                for member in zf.namelist():
                    base = os.path.basename(member)
                    if base == "index.html":
                        index_name = member
                        break
                if not index_name:
                    return jsonify({
                        "error": "validation",
                        "message": "zip does not contain index.html",
                    }), 400
                with zf.open(index_name) as fh:
                    app_html = fh.read().decode("utf-8", errors="replace")
        except zipfile.BadZipFile:
            return jsonify({"error": "validation", "message": "uploaded file is not a valid zip"}), 400

    if not app_html.strip():
        return jsonify({
            "error": "validation",
            "message": "html or zip with index.html required",
        }), 400

    slug = _unique_slug(_slugify(name))

    data = {
        "slug": slug,
        "name": name,
        "tagline": (description[:80] if description else name)[:80],
        "description": description or f"App: {name}",
        "category": category,
        "tags": "",
        "output_type": "deterministic",
        "output_format": "html",
        "system_prompt": "",
        "input_schema": "[]",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "temperature": 0.3,
        "status": "pending_review",
        "version": 1,
        "author_name": author_name or "cli",
        "author_email": author_email,
        "data_sensitivity": "internal",
        "submitted_at": datetime.utcnow(),
        "app_html": app_html,
        "app_type": "app",
    }
    tool_id = db.insert_tool(data)
    _launch_pipeline(tool_id)

    return jsonify({
        "id": tool_id,
        "slug": slug,
        "url": f"/apps/{slug}",
        "status": "pending_review",
    }), 201


@app.route("/api/tools/<int:tool_id>", methods=["PUT"])
def update_tool_draft(tool_id):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    if tool.get("status") not in ("draft", "needs_changes"):
        return jsonify({"error": "forbidden", "message": "Tool is not editable"}), 403

    body = request.get_json(silent=True) or {}
    author_email = request.headers.get("X-Author-Email") or body.get("author_email")
    if author_email != tool.get("author_email") and request.headers.get("X-Admin-Key") != ADMIN_KEY:
        return jsonify({"error": "forbidden"}), 403

    allowed = {
        "name", "tagline", "description", "category", "tags",
        "system_prompt", "input_schema", "model", "max_tokens", "temperature",
        "output_type", "output_format", "data_sensitivity",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if "input_schema" in updates and isinstance(updates["input_schema"], list):
        updates["input_schema"] = json.dumps(updates["input_schema"])
    if updates:
        db.update_tool(tool_id, **updates)
    return jsonify({"id": tool_id, "updated": list(updates.keys())})


@app.route("/api/tools/<int:tool_id>/fork", methods=["POST"])
def fork_tool(tool_id):
    parent = db.get_tool(tool_id)
    if not parent:
        return jsonify({"error": "not_found"}), 404

    body = request.get_json(silent=True) or {}
    new_name = body.get("name") or f"{parent['name']} (fork)"
    author_name = body.get("author_name") or parent.get("author_name") or ""
    author_email = body.get("author_email") or parent.get("author_email") or ""
    slug = _unique_slug(_slugify(new_name))

    data = {
        "slug": slug,
        "name": new_name,
        "tagline": parent.get("tagline") or "",
        "description": parent.get("description") or "",
        "category": parent.get("category") or "Other",
        "tags": parent.get("tags") or "",
        "output_type": parent.get("output_type") or "probabilistic",
        "output_format": parent.get("output_format") or "text",
        "system_prompt": parent.get("system_prompt") or "",
        "input_schema": parent.get("input_schema") or "[]",
        "model": parent.get("model") or "claude-haiku-4-5-20251001",
        "max_tokens": parent.get("max_tokens") or 1000,
        "temperature": parent.get("temperature") or 0.3,
        "status": "draft",
        "version": 1,
        "author_name": author_name,
        "author_email": author_email,
        "fork_of": tool_id,
        "data_sensitivity": parent.get("data_sensitivity") or "internal",
    }
    new_id = db.insert_tool(data)
    return jsonify({"id": new_id, "slug": slug}), 201


@app.route("/api/tools/<int:tool_id>/run", methods=["POST"])
def run_tool(tool_id):
    retry_after = _rate_limit_check(_client_ip())
    if retry_after:
        resp = jsonify({"error": "rate_limited", "retry_after": retry_after})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404

    body = request.get_json(silent=True) or {}
    inputs = body.get("inputs") or body.get("input_data") or {}
    user_name = body.get("user_name")
    user_email = body.get("user_email")
    source = body.get("source") or "web"

    # Detect first-run for this user before executor inserts the new run.
    first_run = False
    if user_email:
        try:
            with db.get_db() as cur:
                cur.execute(
                    "SELECT 1 FROM runs WHERE user_email = %s LIMIT 1",
                    (user_email,),
                )
                first_run = cur.fetchone() is None
        except Exception:
            first_run = False

    try:
        result = executor.run_tool(
            tool_id=tool_id,
            inputs=inputs,
            user_name=user_name,
            user_email=user_email,
            source=source,
        )
    except ValueError as e:
        return jsonify({"error": "validation", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "execution_error", "message": str(e)}), 500

    if isinstance(result, dict):
        result.setdefault("first_run", first_run)
    return jsonify(result)


@app.route("/api/tools/<int:tool_id>/runs", methods=["GET"])
def tool_runs(tool_id):
    rows = db.list_recent_runs(tool_id, limit=20)
    out = []
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        out.append({
            "id": r.get("id"),
            "rating": r.get("rating"),
            "user_name": r.get("user_name"),
            "source": r.get("source"),
            "run_duration_ms": r.get("run_duration_ms"),
            "output_flagged": r.get("output_flagged"),
            "created_at": r.get("created_at"),
        })
    return jsonify({"runs": out})


# -------------------- Runs --------------------

@app.route("/api/runs/<int:run_id>", methods=["GET"])
def get_run(run_id):
    row = db.get_run(run_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    is_admin = request.headers.get("X-Admin-Key") == ADMIN_KEY
    requestor_email = request.headers.get("X-User-Email") or request.args.get("user_email")
    if not is_admin and requestor_email and row.get("user_email") and requestor_email != row.get("user_email"):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(Run.from_row(row).to_dict())


@app.route("/api/runs/<int:run_id>/rate", methods=["POST"])
def rate_run(run_id):
    row = db.get_run(run_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    rating = body.get("rating")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "validation", "message": "rating must be 1-5"}), 400
    if not (1 <= rating <= 5):
        return jsonify({"error": "validation", "message": "rating must be 1-5"}), 400

    note = body.get("note") or body.get("rating_note")
    db.update_run(run_id, rating=rating, rating_note=note)
    db.recompute_avg_rating(row["tool_id"])
    return jsonify({"ok": True, "run_id": run_id, "rating": rating})


@app.route("/api/runs/<int:run_id>/flag", methods=["POST"])
def flag_run(run_id):
    row = db.get_run(run_id)
    if not row:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    reason = body.get("reason") or body.get("flag_reason") or ""
    db.update_run(run_id, output_flagged=True, flag_reason=reason)
    new_count = db.increment_flag_count(row["tool_id"])
    if new_count >= 3:
        db.update_tool(row["tool_id"], requires_review=True)
    return jsonify({"ok": True, "run_id": run_id, "flag_count": new_count})


# -------------------- Shareable tokens --------------------

@app.route("/api/t/<string:access_token>", methods=["GET"])
def resolve_access_token(access_token):
    row = db.get_tool_by_access_token(access_token)
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "tagline": row.get("tagline"),
    })


# -------------------- Agents --------------------

@app.route("/api/agent/status/<int:tool_id>", methods=["GET"])
def agent_status(tool_id):
    review = db.get_agent_review_by_tool(tool_id)
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404

    stages = [
        ("preflight", "Pre-flight check"),
        ("classifier", "Classifier"),
        ("security", "Security scanner"),
        ("red_team", "Red Team"),
        ("hardener", "Prompt hardener"),
        ("qa", "QA tester"),
        ("synthesizer", "Review synthesizer"),
    ]

    def _is_done(review_row, stage_key):
        if not review_row:
            return stage_key == "preflight" and tool.get("status") == "pending_review"
        mapping = {
            "preflight": True,
            "classifier": bool(review_row.get("classifier_output")),
            "security": bool(review_row.get("security_scan_output")),
            "red_team": bool(review_row.get("red_team_output")),
            "hardener": bool(review_row.get("hardener_output")),
            "qa": bool(review_row.get("qa_output")),
            "synthesizer": bool(review_row.get("review_summary")),
        }
        return mapping.get(stage_key, False)

    stage_states = []
    done_flag = True
    for key, label in stages:
        is_done = _is_done(review, key) if done_flag else False
        stage_states.append({
            "key": key,
            "label": label,
            "status": "done" if is_done else ("running" if done_flag else "waiting"),
        })
        if not is_done:
            done_flag = False

    completed = sum(1 for s in stage_states if s["status"] == "done")
    progress = int(100 * completed / len(stages))

    return jsonify({
        "tool_id": tool_id,
        "status": tool.get("status"),
        "progress_pct": progress,
        "stages": stage_states,
        "review_id": review.get("id") if review else None,
        "recommendation": (review or {}).get("agent_recommendation"),
        "confidence": (review or {}).get("agent_confidence"),
    })


@app.route("/api/agent/review/<int:tool_id>", methods=["GET"])
def agent_review(tool_id):
    review = db.get_agent_review_by_tool(tool_id)
    if not review:
        return jsonify({"error": "not_found"}), 404
    return jsonify(AgentReview.from_row(review).to_dict())


@app.route("/api/agent/rerun/<int:tool_id>", methods=["POST"])
def agent_rerun(tool_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    _launch_pipeline(tool_id)
    return jsonify({"ok": True, "tool_id": tool_id, "pipeline": "launched"})


# -------------------- Skills --------------------

@app.route("/api/skills", methods=["GET"])
def list_skills():
    category = request.args.get("category")
    search = request.args.get("search") or request.args.get("q")
    sort = request.args.get("sort", "upvotes")
    rows = db.list_skills(category=category, search=search, sort=sort)
    out = [Skill.from_row(r).to_dict() for r in rows]
    return jsonify({"skills": out})


@app.route("/api/skills", methods=["POST"])
def create_skill():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    prompt_text = (body.get("prompt_text") or "").strip()
    if not title or not prompt_text:
        return jsonify({"error": "validation", "message": "title and prompt_text required"}), 400
    data = {
        "title": title,
        "description": body.get("description") or "",
        "prompt_text": prompt_text,
        "category": body.get("category") or "Other",
        "use_case": body.get("use_case") or "",
        "author_name": body.get("author_name") or "",
        "source_url": body.get("source_url") or "",
    }
    skill_id = db.insert_skill(data)
    return jsonify({"id": skill_id, "title": title}), 201


@app.route("/api/skills/<int:skill_id>/upvote", methods=["POST"])
def upvote_skill(skill_id):
    db.increment_skill_upvotes(skill_id)
    return jsonify({"ok": True, "skill_id": skill_id})


@app.route("/api/skills/<int:skill_id>/copy", methods=["POST"])
def copy_skill(skill_id):
    db.increment_skill_copy_count(skill_id)
    return jsonify({"ok": True, "skill_id": skill_id})


_SKILL_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _skill_slug(title: str) -> str:
    slug = _SKILL_SLUG_RE.sub("-", (title or "skill").lower()).strip("-")
    return slug or "skill"


@app.route("/api/skills/<int:skill_id>/download", methods=["GET"])
def download_skill(skill_id):
    row = db.get_skill(skill_id)
    if not row:
        return jsonify({"error": "not_found", "message": "Skill not found"}), 404
    md = row.get("prompt_text") or ""
    slug = _skill_slug(row.get("title") or "")
    db.increment_skill_copy_count(skill_id)
    return Response(
        md,
        mimetype="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.md"',
            "X-Skill-Slug": slug,
        },
    )


# -------------------- Admin Blueprint hook --------------------

try:
    from api.admin import admin_bp  # type: ignore
    app.register_blueprint(admin_bp)
except Exception:
    pass


# -------------------- GitHub auto-deploy: in-place HTML update --------------------

@app.route("/api/admin/tools/<int:tool_id>/update-html", methods=["POST"])
def admin_update_app_html(tool_id):
    """Trusted auto-redeploy path for approved app-type tools.

    Called by forge_bot/deployer.py when a push arrives for a slug that is
    already live — we skip the full review pipeline and just swap `app_html`
    in place. Admin-only via X-Admin-Key.
    """
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    if (tool.get("app_type") or "prompt") != "app":
        return jsonify({"error": "not_an_app", "tool_id": tool_id}), 400
    if tool.get("status") != "approved":
        return jsonify({
            "error": "not_approved",
            "message": "update-html only applies to approved apps",
            "status": tool.get("status"),
        }), 400

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


# -------------------- Sandbox admin routes (T1-WAVE3) --------------------

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
        return jsonify({
            "success": port is not None,
            "tool_id": tool_id,
            "port": port,
        })
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
        return jsonify({"error": "not_an_app", "tool_id": tool_id}), 400
    slug = tool.get("slug") or f"tool-{tool_id}"
    try:
        from forge_sandbox import builder
        result = builder.build_image(tool_id, tool.get("app_html") or "", slug)
    except Exception as exc:
        return jsonify({"error": "build_error", "message": str(exc)}), 500
    if not result.get("success"):
        return jsonify({
            "success": False,
            "image_tag": None,
            "build_output": result.get("build_output", ""),
        }), 500
    db.update_tool(tool_id, container_mode=True)
    return jsonify({
        "success": True,
        "tool_id": tool_id,
        "image_tag": result.get("image_tag"),
    })


# -------------------- Creator Blueprint hook --------------------

try:
    from api.creator import creator_bp  # type: ignore
    app.register_blueprint(creator_bp)
except Exception:
    pass


# -------------------- Workflow Blueprint hook --------------------

try:
    from api.workflow import workflow_bp  # type: ignore
    app.register_blueprint(workflow_bp)
except Exception:
    pass


# -------------------- Apps Blueprint hook --------------------

try:
    from api.apps import apps_bp  # type: ignore
    app.register_blueprint(apps_bp)
except Exception:
    pass


# -------------------- Learning Blueprint hook --------------------

try:
    from api.learning import learning_bp  # type: ignore
    app.register_blueprint(learning_bp)
except Exception:
    pass


# -------------------- ForgeData Blueprint hook --------------------

try:
    from api.forgedata import forgedata_bp  # type: ignore
    app.register_blueprint(forgedata_bp)
except ImportError:
    pass


# -------------------- Analytics Blueprint hook (T-DASH) --------------------

try:
    from api.analytics import analytics_bp  # type: ignore
    app.register_blueprint(analytics_bp)
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
