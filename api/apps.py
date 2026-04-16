"""
Forge App Platform.

Serves single-file HTML apps (tools with app_type='app') and backs them with a
per-user key/value store (app_data) plus a ForgeAPI bridge injected at the top
of <body>. Apps can then call window.ForgeAPI.{getData,setData,deleteData,
runTool,listTools} without knowing anything about the platform internals.

Routes:
    GET    /apps/<slug>                   — serve injected app HTML page
    GET    /api/apps/<id>/data/<key>      — {value, found}
    POST   /api/apps/<id>/data/<key>      — upsert, body {value}
    DELETE /api/apps/<id>/data/<key>      — delete
    GET    /api/apps/<id>/data            — list keys
    POST   /api/apps/analyze              — Claude-powered HTML analysis
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from api import db


_CONTAINER_PROXY_LOG = logging.getLogger("forge.sandbox.proxy")


apps_bp = Blueprint("apps", __name__)

ANALYZE_MODEL = os.environ.get("FORGE_APP_ANALYZE_MODEL", "claude-sonnet-4-6")
ANALYZE_MAX_TOKENS = int(os.environ.get("FORGE_APP_ANALYZE_MAX_TOKENS", "1500"))


# -------------------- ForgeAPI bridge --------------------

_EXIT_STRIP = (
    "<div style=\""
    "position:fixed;top:0;left:0;right:0;height:30px;z-index:2147483647;"
    "background:rgba(13,13,13,0.92);backdrop-filter:blur(6px);"
    "border-bottom:1px solid #2a2a2a;color:#e8e8e8;"
    "font:500 12px/30px 'DM Sans',system-ui,-apple-system,sans-serif;"
    "padding:0 14px;display:flex;align-items:center;gap:10px;\">"
    "<a href=\"/\" target=\"_top\" style=\"color:#3aa3ff;text-decoration:none;\">← Forge catalog</a>"
    "<span style=\"color:#555;\">·</span>"
    "<span style=\"color:#888;\">Running inside Forge</span>"
    "</div>"
    "<style>"
    "body{padding-top:30px!important;}"
    "</style>"
)


def _forge_api_script(tool_id: int, slug: str, user_name: str) -> str:
    """
    Return the <script> block that exposes window.FORGE_APP + window.ForgeAPI
    to the app. Keep it self-contained so apps can rely on a fixed contract.
    """
    cfg = {
        "toolId": tool_id,
        "slug": slug,
        "userName": user_name or "",
        "apiBase": "/api",
    }
    cfg_json = json.dumps(cfg)
    return (
        _EXIT_STRIP
        + "<script>\n"
        f"window.FORGE_APP = {cfg_json};\n"
        "(function(){\n"
        "  var cfg = window.FORGE_APP;\n"
        "  function req(path, opts){\n"
        "    opts = opts || {};\n"
        "    var init = {method: opts.method || 'GET', headers: {'Accept':'application/json'}};\n"
        "    if (opts.body !== undefined){\n"
        "      init.headers['Content-Type'] = 'application/json';\n"
        "      init.body = JSON.stringify(opts.body);\n"
        "    }\n"
        "    return fetch(cfg.apiBase + path, init).then(function(r){\n"
        "      if (!r.ok) return r.text().then(function(t){ throw new Error(t || ('HTTP '+r.status)); });\n"
        "      return r.json();\n"
        "    });\n"
        "  }\n"
        "  window.ForgeAPI = {\n"
        "    getData: function(key){\n"
        "      return req('/apps/' + cfg.toolId + '/data/' + encodeURIComponent(key)).then(function(r){\n"
        "        return r && r.found ? r.value : null;\n"
        "      });\n"
        "    },\n"
        "    setData: function(key, value){\n"
        "      return req('/apps/' + cfg.toolId + '/data/' + encodeURIComponent(key), {method:'POST', body:{value:value}});\n"
        "    },\n"
        "    deleteData: function(key){\n"
        "      return req('/apps/' + cfg.toolId + '/data/' + encodeURIComponent(key), {method:'DELETE'});\n"
        "    },\n"
        "    listKeys: function(){\n"
        "      return req('/apps/' + cfg.toolId + '/data');\n"
        "    },\n"
        "    runTool: function(slug, inputs){\n"
        "      return req('/tools/slug/' + encodeURIComponent(slug)).then(function(tool){\n"
        "        if (!tool || !tool.id) throw new Error('tool not found: ' + slug);\n"
        "        return req('/tools/' + tool.id + '/run', {method:'POST', body:{inputs: inputs || {}, user_name: cfg.userName, source:'app'}});\n"
        "      });\n"
        "    },\n"
        "    listTools: function(){\n"
        "      return req('/tools');\n"
        "    }\n"
        "  };\n"
        "  window.ForgeAPI.data = {\n"
        "    salesforce: {\n"
        "      accounts: function(params){ params = params || {}; return fetch('/api/forgedata/salesforce/accounts?' + new URLSearchParams(params), {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(function(r){return r.json();}); },\n"
        "      opportunities: function(params){ params = params || {}; return fetch('/api/forgedata/salesforce/opportunities?' + new URLSearchParams(params), {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(function(r){return r.json();}); },\n"
        "      contacts: function(params){ params = params || {}; return fetch('/api/forgedata/salesforce/contacts?' + new URLSearchParams(params), {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(function(r){return r.json();}); },\n"
        "      activities: function(account_id){ return fetch('/api/forgedata/salesforce/activities?account_id=' + encodeURIComponent(account_id), {headers:{'X-Tool-Id': String(window.FORGE_APP.toolId)}}).then(function(r){return r.json();}); },\n"
        "      status: function(){ return fetch('/api/forgedata/status').then(function(r){return r.json();}); }\n"
        "    }\n"
        "  };\n"
        "})();\n"
        "</script>\n"
    )


_BODY_OPEN_RE = re.compile(r"(<body\b[^>]*>)", re.IGNORECASE)


def _inject_bridge(html: str, tool_id: int, slug: str, user_name: str) -> str:
    script = _forge_api_script(tool_id, slug, user_name)
    if not html:
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{slug}</title></head><body>{script}"
            "<p>No app HTML defined.</p></body></html>"
        )
    match = _BODY_OPEN_RE.search(html)
    if match:
        idx = match.end()
        return html[:idx] + "\n" + script + html[idx:]
    # No <body> tag — wrap minimally so the injection still executes.
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{slug}</title></head><body>{script}{html}</body></html>"
    )


# -------------------- App HTML --------------------

@apps_bp.route("/apps/<string:slug>", methods=["GET"])
def serve_app(slug):
    tool = db.get_tool_by_slug(slug)
    if not tool:
        return jsonify({"error": "not_found", "slug": slug}), 404
    if (tool.get("app_type") or "prompt") != "app":
        return jsonify({"error": "not_an_app", "slug": slug}), 404

    user_name = request.args.get("user") or ""
    tool_id = tool["id"]

    # Every /apps/<slug> hit stamps last_request_at so the hibernator's idle
    # sweep leaves this tool alone. Cheap — one UPDATE per page load.
    try:
        db.update_tool(tool_id, last_request_at=datetime.utcnow())
    except Exception:
        _CONTAINER_PROXY_LOG.exception("last_request_at update failed tool_id=%s", tool_id)

    if tool.get("container_mode"):
        try:
            from forge_sandbox.manager import SandboxManager
            import requests

            port = SandboxManager().ensure_running(tool_id)
            upstream = requests.get(f"http://127.0.0.1:{port}/", timeout=10)
            body = upstream.text or ""
            script = _forge_api_script(tool_id, slug, user_name)
            lower = body.lower()
            close_idx = lower.rfind("</body>")
            if close_idx >= 0:
                rendered = body[:close_idx] + "\n" + script + body[close_idx:]
            else:
                rendered = body + script
            return Response(rendered, mimetype="text/html; charset=utf-8", status=upstream.status_code)
        except Exception as exc:
            _CONTAINER_PROXY_LOG.exception("container proxy failed tool_id=%s slug=%s", tool_id, slug)
            return jsonify({
                "error": "sandbox_unavailable",
                "slug": slug,
                "message": str(exc),
            }), 502

    html = tool.get("app_html") or ""
    rendered = _inject_bridge(html, tool_id, slug, user_name)
    return Response(rendered, mimetype="text/html; charset=utf-8")


# -------------------- App data KV store --------------------

def _get_app_data_row(tool_id: int, key: str):
    with db.get_db() as cur:
        cur.execute(
            "SELECT id, data, updated_at FROM app_data WHERE tool_id = %s AND user_key = %s",
            (tool_id, key),
        )
        row = cur.fetchone()
        return dict(row) if row else None


@apps_bp.route("/api/apps/<int:tool_id>/data/<path:key>", methods=["GET"])
def get_app_data(tool_id, key):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    row = _get_app_data_row(tool_id, key)
    if not row:
        return jsonify({"value": None, "found": False})
    raw = row.get("data")
    value = None
    if raw is not None:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            value = raw
    return jsonify({"value": value, "found": True})


@apps_bp.route("/api/apps/<int:tool_id>/data/<path:key>", methods=["POST"])
def set_app_data(tool_id, key):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(silent=True) or {}
    if "value" not in body:
        return jsonify({"error": "validation", "message": "body.value required"}), 400
    payload = json.dumps(body["value"])
    with db.get_db(dict_cursor=False) as cur:
        cur.execute(
            """INSERT INTO app_data (tool_id, user_key, data, created_at, updated_at)
               VALUES (%s, %s, %s, NOW(), NOW())
               ON CONFLICT (tool_id, user_key)
               DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()""",
            (tool_id, key, payload),
        )
    return jsonify({"success": True, "tool_id": tool_id, "key": key})


@apps_bp.route("/api/apps/<int:tool_id>/data/<path:key>", methods=["DELETE"])
def delete_app_data(tool_id, key):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    with db.get_db(dict_cursor=False) as cur:
        cur.execute(
            "DELETE FROM app_data WHERE tool_id = %s AND user_key = %s",
            (tool_id, key),
        )
    return jsonify({"success": True, "tool_id": tool_id, "key": key})


@apps_bp.route("/api/apps/<int:tool_id>/data", methods=["GET"])
def list_app_data(tool_id):
    tool = db.get_tool(tool_id)
    if not tool:
        return jsonify({"error": "not_found"}), 404
    with db.get_db() as cur:
        cur.execute(
            "SELECT user_key, updated_at FROM app_data WHERE tool_id = %s ORDER BY updated_at DESC",
            (tool_id,),
        )
        rows = cur.fetchall()
    keys = []
    for r in rows:
        ts = r["updated_at"]
        keys.append({
            "key": r["user_key"],
            "updated_at": ts.isoformat() if hasattr(ts, "isoformat") else ts,
        })
    return jsonify({"keys": keys})


# -------------------- HTML analysis --------------------

_ANALYZE_SYSTEM_PROMPT = (
    "You analyze a single-file HTML app that a user wants to publish to an internal "
    "AI tool marketplace called Forge. Return ONLY a single valid JSON object with these fields:\n"
    "{\n"
    "  \"suggested_name\": \"Title Case, 3-60 chars\",\n"
    "  \"suggested_tagline\": \"one sentence, <=80 chars\",\n"
    "  \"suggested_category\": \"one of: Account Research | Email Generation | Contact Scoring | Data Lookup | Reporting | Onboarding | Forecasting | Other\",\n"
    "  \"detected_inputs\": [ {\"name\": \"snake_case\", \"label\": \"Label\", \"type\": \"text|textarea|select|number|email|checkbox\"} ],\n"
    "  \"uses_forge_api\": true|false,\n"
    "  \"safety_notes\": [\"short string\", ...]\n"
    "}\n"
    "Detect uses_forge_api as true when the HTML references window.ForgeAPI, window.FORGE_APP, "
    "ForgeAPI.getData, ForgeAPI.setData, ForgeAPI.runTool, or ForgeAPI.listTools. "
    "detected_inputs should list the visible form fields the user is expected to fill in. "
    "safety_notes should flag inline external script sources, credential prompts, or data-exfil shapes. "
    "Never wrap the JSON in prose or code fences."
)


def _call_claude(system: str, user_message: str) -> str:
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError(f"anthropic package not installed: {e}")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=ANALYZE_MODEL,
        max_tokens=ANALYZE_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    parts = []
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> dict:
    if not text:
        raise ValueError("empty model response")
    s = text.strip()
    m = _JSON_FENCE_RE.search(s)
    if m:
        s = m.group(1)
    # Fallback: take substring between the first '{' and the last '}'.
    if not s.startswith("{"):
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            s = s[first:last + 1]
    return json.loads(s)


def _heuristic_analysis(html: str) -> dict:
    """Cheap, offline fallback when Claude is unavailable or fails."""
    low = (html or "").lower()
    uses = any(m in low for m in (
        "window.forgeapi", "forgeapi.getdata", "forgeapi.setdata",
        "forgeapi.deletedata", "forgeapi.runtool", "forgeapi.listtools",
        "window.forge_app",
    ))
    detected = []
    for m in re.finditer(r"<input\b[^>]*>", html or "", re.IGNORECASE):
        tag = m.group(0)
        name_match = re.search(r'name=["\']([^"\']+)', tag, re.IGNORECASE)
        type_match = re.search(r'type=["\']([^"\']+)', tag, re.IGNORECASE)
        if name_match:
            detected.append({
                "name": name_match.group(1),
                "label": name_match.group(1).replace("_", " ").title(),
                "type": (type_match.group(1).lower() if type_match else "text"),
            })
    if re.search(r"<textarea\b", html or "", re.IGNORECASE):
        detected.append({"name": "notes", "label": "Notes", "type": "textarea"})
    safety = []
    if re.search(r"<script\b[^>]*src=", html or "", re.IGNORECASE):
        safety.append("Loads an external <script src=...> — review the source before approving.")
    return {
        "suggested_name": "Custom App",
        "suggested_tagline": "Single-file HTML tool published to Forge.",
        "suggested_category": "Other",
        "detected_inputs": detected,
        "uses_forge_api": uses,
        "safety_notes": safety,
    }


@apps_bp.route("/api/apps/analyze", methods=["POST"])
def analyze_app():
    body = request.get_json(silent=True) or {}
    html = body.get("html") or ""
    if not isinstance(html, str) or not html.strip():
        return jsonify({"error": "validation", "message": "html required"}), 400

    try:
        raw = _call_claude(_ANALYZE_SYSTEM_PROMPT, html[:20000])
        result = _extract_json(raw)
    except Exception as exc:
        # Fall back to a quick heuristic so the submit form always has something to render.
        fallback = _heuristic_analysis(html)
        fallback["error"] = f"analyzer_fallback: {exc}"
        return jsonify(fallback)

    # Normalize fields so the submit form can rely on the shape.
    result.setdefault("suggested_name", "Custom App")
    result.setdefault("suggested_tagline", "")
    result.setdefault("suggested_category", "Other")
    result.setdefault("detected_inputs", [])
    result.setdefault("uses_forge_api", False)
    result.setdefault("safety_notes", [])
    return jsonify(result)
