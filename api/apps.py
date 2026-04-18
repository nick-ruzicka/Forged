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

def _exit_strip(tool_id: int, slug: str) -> str:
    """The thin header bar injected at the top of every served app.

    Includes: back link, status label, and an "+ Add" button so users can
    add an app to their shelf without leaving the app view.
    """
    return (
        f'<div id="forge-app-bar" style="'
        f'position:fixed;top:0;left:0;right:0;height:34px;z-index:2147483647;'
        f'background:rgba(13,13,13,0.94);backdrop-filter:blur(6px);'
        f'border-bottom:1px solid #2a2a2a;color:#e8e8e8;'
        f"font:500 12px/34px 'DM Sans',system-ui,-apple-system,sans-serif;"
        f'padding:0 14px;display:flex;align-items:center;gap:10px;">'
        f'<a href="/" target="_top" style="color:#3aa3ff;text-decoration:none;">← Forge</a>'
        f'<span style="color:#555;">·</span>'
        f'<span style="color:#888;flex:1;">Running inside Forge</span>'
        f'<button id="forge-add-btn" style="background:#0066FF;color:white;border:none;'
        f'padding:4px 12px;border-radius:4px;font-size:11px;font-weight:600;cursor:pointer;"'
        f' onclick="(async function(){{var b=document.getElementById(\'forge-add-btn\');'
        f'b.disabled=true;b.textContent=\'…\';'
        f'var uid;try{{uid=localStorage.getItem(\'forge_user_id\')}}catch(e){{}}uid=uid||\'anon-\'+Date.now();'
        f'localStorage.setItem(\'forge_user_id\',uid);'
        f'try{{await fetch(\'/api/me/items/{tool_id}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\','
        f'\'X-Forge-User-Id\':uid}},body:JSON.stringify({{}})}});'
        f'b.textContent=\'✓ Added\';b.style.background=\'#1a7f4b\';'
        f'}}catch(e){{b.textContent=\'+ Add\';b.disabled=false;}}}})();">'
        f'+ Add</button>'
        f'</div>'
        f'<style>body{{padding-top:34px!important;}}</style>'
    )


# Keep a backward-compat reference for any code that imported _EXIT_STRIP
_EXIT_STRIP = _exit_strip(0, "")


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
        _exit_strip(tool_id, slug)
        + "<script>\n"
        f"window.FORGE_APP = {cfg_json};\n"
        "(function(){\n"
        "  var cfg = window.FORGE_APP;\n"
        "  var _isPreview = new URLSearchParams(window.location.search).get('preview') === 'true';\n"
        "  var _previewStore = {}; // in-memory store for preview mode writes\n"
        "  var _demoData = null;\n"
        "  // Load demo data if in preview mode\n"
        "  if (_isPreview) {\n"
        "    try {\n"
        "      fetch(cfg.apiBase + '/apps/' + cfg.toolId + '/demo-data').then(function(r){\n"
        "        return r.json();\n"
        "      }).then(function(d){\n"
        "        _demoData = d.demo_data || {};\n"
        "      }).catch(function(){});\n"
        "    } catch(e) {}\n"
        "  }\n"
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
        "    isPreview: _isPreview,\n"
        "    getData: function(key){\n"
        "      if (_isPreview) {\n"
        "        // Return from in-memory preview store first, then demo data\n"
        "        return Promise.resolve(\n"
        "          _previewStore[key] !== undefined ? _previewStore[key]\n"
        "          : (_demoData && _demoData[key] !== undefined ? _demoData[key] : null)\n"
        "        );\n"
        "      }\n"
        "      return req('/apps/' + cfg.toolId + '/data/' + encodeURIComponent(key)).then(function(r){\n"
        "        return r && r.found ? r.value : null;\n"
        "      });\n"
        "    },\n"
        "    setData: function(key, value){\n"
        "      if (_isPreview) {\n"
        "        // Preview mode: store in memory only (visually works, doesn't persist)\n"
        "        _previewStore[key] = value;\n"
        "        return Promise.resolve({success: true, preview: true});\n"
        "      }\n"
        "      return req('/apps/' + cfg.toolId + '/data/' + encodeURIComponent(key), {method:'POST', body:{value:value}});\n"
        "    },\n"
        "    deleteData: function(key){\n"
        "      if (_isPreview) { delete _previewStore[key]; return Promise.resolve({success:true}); }\n"
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
        "\n"
        "  // Context layer: pre-digested user + work context.\n"
        "  // Every app can call ForgeAPI.context() to know who the user is,\n"
        "  // what they've been working on, and what their team uses.\n"
        "  // NOTE: We use cfg.userName (from ?user= query param) instead of\n"
        "  // localStorage because iframes without allow-same-origin can't\n"
        "  // access localStorage. This is the security-safe path.\n"
        "  var _userId = cfg.userName || '';\n"
        "  try { _userId = _userId || localStorage.getItem('forge_user_id') || ''; } catch(e) {}\n"
        "  window.ForgeAPI.context = function() {\n"
        "    return fetch(cfg.apiBase + '/me/context', {\n"
        "      headers: {'X-Forge-User-Id': _userId}\n"
        "    }).then(function(r){ return r.json(); });\n"
        "  };\n"
        "\n"
        "  // App composability: call another app by slug.\n"
        "  // Returns the app's output. This is how apps become functions.\n"
        "  window.ForgeAPI.runApp = window.ForgeAPI.runTool; // alias for clarity\n"
        "\n"
        "  // Actions API: apps that DO things, not just advise.\n"
        "  window.ForgeAPI.actions = {\n"
        "    slackPost: function(message, toolId) {\n"
        "      return fetch(cfg.apiBase + '/actions/slack', {\n"
        "        method: 'POST',\n"
        "        headers: {'Content-Type':'application/json', 'X-Forge-User-Id': _userId},\n"
        "        body: JSON.stringify({message: message, tool_id: toolId || cfg.toolId})\n"
        "      }).then(function(r){ return r.json(); });\n"
        "    },\n"
        "    emailDraft: function(to, subject, body, toolId) {\n"
        "      return fetch(cfg.apiBase + '/actions/email-draft', {\n"
        "        method: 'POST',\n"
        "        headers: {'Content-Type':'application/json', 'X-Forge-User-Id': _userId},\n"
        "        body: JSON.stringify({to:to, subject:subject, body:body, tool_id: toolId || cfg.toolId})\n"
        "      }).then(function(r){ return r.json(); });\n"
        "    },\n"
        "    log: function() {\n"
        "      return fetch(cfg.apiBase + '/actions/log', {\n"
        "        headers: {'X-Forge-User-Id': _userId}\n"
        "      }).then(function(r){ return r.json(); });\n"
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
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        return jsonify({"error": "not_found"}), 404
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

    # Backend-aware apps: inject health-check overlay that gates the frontend
    # on the local backend being reachable.
    if tool.get("has_local_backend"):
        rendered = _inject_backend_overlay(
            rendered,
            port=tool.get("backend_port") or 5001,
            health_path=tool.get("backend_health_path") or "/health",
            docker_image=tool.get("backend_docker_image") or "",
            start_script=tool.get("backend_start_script") or "",
            app_name=tool.get("name") or slug,
            slug=slug,
        )

    return Response(rendered, mimetype="text/html; charset=utf-8")


# -------------------- Backend health-check overlay --------------------


def _inject_backend_overlay(
    html: str,
    port: int,
    health_path: str,
    docker_image: str,
    start_script: str,
    app_name: str,
    slug: str = "",
) -> str:
    """Inject an overlay that checks whether a local backend is reachable.

    If the backend responds to `http://localhost:{port}{health_path}`, the overlay
    hides and the app renders normally. If it doesn't, the overlay shows friendly
    install instructions (Docker preferred, shell script as fallback).

    This is the "frontend in Forge, backend runs locally" pattern.
    """
    docker_image_esc = (docker_image or "").replace("'", "\\'").replace('"', "&quot;")
    start_script_esc = (start_script or "").replace("'", "\\'").replace("\n", "\\n").replace('"', "&quot;")
    app_name_esc = (app_name or "").replace("'", "\\'").replace('"', "&quot;")
    slug_esc = (slug or "").replace("'", "\\'").replace('"', "&quot;")

    # Manual command block (always shown as fallback)
    if docker_image:
        manual_cmd = f"docker run -p {port}:{port} {docker_image}"
    elif start_script:
        manual_cmd = start_script
    else:
        manual_cmd = "# See the app README for backend setup"
    manual_cmd_esc = manual_cmd.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    overlay = (
        f'\n<div id="forge-backend-overlay" style="display:none;position:fixed;inset:0;'
        f'background:#0d0d0d;z-index:99999;flex-direction:column;align-items:center;'
        f'justify-content:center;gap:12px;font-family:DM Sans,system-ui,sans-serif;color:#f0f0f0;'
        f'text-align:center;padding:24px;">'
        f'<div style="font-size:48px;">⚙️</div>'
        f'<h2 style="color:#f0f0f0;margin:0;font-size:22px;">Backend not running</h2>'
        f'<p style="color:#888;margin:0 0 16px;font-size:14px;max-width:440px;">'
        f'{app_name_esc} needs a local server on port {port}.</p>'

        # Option A: Forge Agent (primary)
        f'<div style="max-width:440px;width:100%;">'
        f'<button id="forge-agent-btn" onclick="startWithAgent()" '
        f'style="background:#0066FF;color:white;border:none;padding:14px 28px;border-radius:8px;'
        f'cursor:pointer;font-size:15px;font-weight:600;width:100%;margin-bottom:8px;">'
        f'▶ Start with Forge Agent</button>'
        f'<p id="agent-status" style="color:#888;font-size:12px;text-align:center;'
        f'margin:0 0 4px;min-height:16px;"></p>'
        f'</div>'

        # Divider
        f'<div style="max-width:440px;width:100%;border-top:1px solid #2a2a2a;'
        f'margin:12px 0;padding-top:14px;text-align:left;">'
        f'<div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:0.5px;'
        f'margin-bottom:8px;">Or run manually in your terminal:</div>'
        f'<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;'
        f'padding:14px 16px;font-family:ui-monospace,Menlo,monospace;font-size:13px;'
        f'color:#c3e88d;cursor:pointer;user-select:all;line-height:1.5;white-space:pre-wrap;"'
        f' onclick="navigator.clipboard.writeText(this.innerText)" title="Click to copy">'
        f'{manual_cmd_esc}</div>'
        f'<button onclick="location.reload()" style="margin-top:12px;background:#1f1f1f;'
        f'border:1px solid #2a2a2a;color:#ccc;padding:10px 20px;border-radius:6px;'
        f'cursor:pointer;font-size:13px;width:100%;">I started it — reload</button>'
        f'</div>'

        f'<div style="font-size:11px;color:#444;margin-top:12px;">The backend runs on your machine. '
        f'Forge never touches your data.</div>'
        f'</div>\n'

        # Script: Forge Agent integration + backend health poll
        f'<script>\n'
        f'var _forgeAgentToken = null;\n'
        f'var _backendPort = {port};\n'
        f'var _healthPath = "{health_path}";\n'
        f'var _dockerImage = "{docker_image_esc}";\n'
        f'var _appSlug = "{slug_esc}";\n'
        f'\n'
        f'// Check if forge-agent is running; update UI accordingly\n'
        f'(async function checkAgent() {{\n'
        f'  var btn = document.getElementById("forge-agent-btn");\n'
        f'  var status = document.getElementById("agent-status");\n'
        f'  try {{\n'
        f'    var r = await fetch("http://localhost:4242/health");\n'
        f'    if (r.ok) {{\n'
        f'      // Agent is running — fetch the auth token\n'
        f'      try {{\n'
        f'        var tr = await fetch("/api/agent/token");\n'
        f'        var td = await tr.json();\n'
        f'        if (td.token) _forgeAgentToken = td.token;\n'
        f'      }} catch(e) {{}}\n'
        f'      status.textContent = "";\n'
        f'    }}\n'
        f'  }} catch(e) {{\n'
        f'    btn.style.opacity = "0.7";\n'
        f'    status.innerHTML = \'Forge Agent not detected. \' +'
        f'      \'<a href="https://github.com/forge/agent" target="_blank" style="color:#0066FF;">Install it →</a>\' +'
        f'      \' or use the manual command below.\';\n'
        f'  }}\n'
        f'}})();\n'
        f'\n'
        f'async function startWithAgent() {{\n'
        f'  var btn = document.getElementById("forge-agent-btn");\n'
        f'  var status = document.getElementById("agent-status");\n'
        f'  btn.disabled = true;\n'
        f'  btn.textContent = "⏳ Connecting...";\n'
        f'  // Ensure token\n'
        f'  if (!_forgeAgentToken) {{\n'
        f'    try {{ var tr = await fetch("/api/agent/token"); var td = await tr.json(); if (td.token) _forgeAgentToken = td.token; }} catch(e) {{}}\n'
        f'  }}\n'
        f'  if (!_forgeAgentToken) {{\n'
        f'    btn.textContent = "▶ Start with Forge Agent"; btn.disabled = false;\n'
        f'    status.innerHTML = \'Could not get auth token. <a href="https://github.com/forge/agent" target="_blank" style="color:#0066FF;">Install Forge Agent →</a>\';\n'
        f'    return;\n'
        f'  }}\n'
        f'  // SSE streaming request\n'
        f'  try {{\n'
        f'    var r = await fetch("http://localhost:4242/run", {{\n'
        f'      method: "POST",\n'
        f'      headers: {{"Content-Type":"application/json","X-Forge-Token":_forgeAgentToken}},\n'
        f'      body: JSON.stringify({{type:"docker",image:_dockerImage,port:_backendPort,name:_appSlug,stream:true}})\n'
        f'    }});\n'
        f'    if (!r.ok) {{ var e = await r.json().catch(function(){{return {{}}}}); throw new Error(e.message||e.error||"HTTP "+r.status); }}\n'
        f'    // Read SSE stream\n'
        f'    var reader = r.body.getReader();\n'
        f'    var decoder = new TextDecoder();\n'
        f'    var buf = "";\n'
        f'    var layersDone = 0;\n'
        f'    while (true) {{\n'
        f'      var chunk = await reader.read();\n'
        f'      if (chunk.done) break;\n'
        f'      buf += decoder.decode(chunk.value, {{stream:true}});\n'
        f'      var lines = buf.split("\\n");\n'
        f'      buf = lines.pop();\n'
        f'      for (var i = 0; i < lines.length; i++) {{\n'
        f'        var line = lines[i];\n'
        f'        if (!line.startsWith("data: ")) continue;\n'
        f'        try {{ var evt = JSON.parse(line.slice(6)); }} catch(x) {{ continue; }}\n'
        f'        if (evt.type === "pulling") {{\n'
        f'          btn.textContent = "⏳ Downloading...";\n'
        f'          status.textContent = evt.message || "Pulling image...";\n'
        f'        }} else if (evt.type === "layer" || evt.type === "cached_layer") {{\n'
        f'          layersDone = evt.layers_done || layersDone + 1;\n'
        f'          var bar = "█".repeat(Math.min(layersDone, 20)) + "░".repeat(Math.max(0, 20 - layersDone));\n'
        f'          btn.textContent = "⏳ Downloading...";\n'
        f'          status.textContent = bar + "  " + layersDone + " layers";\n'
        f'        }} else if (evt.type === "cached") {{\n'
        f'          btn.textContent = "⏳ Using cached image...";\n'
        f'          status.textContent = evt.message || "";\n'
        f'        }} else if (evt.type === "pulled") {{\n'
        f'          btn.textContent = "⏳ Image ready...";\n'
        f'          status.textContent = evt.message || "";\n'
        f'        }} else if (evt.type === "starting") {{\n'
        f'          btn.textContent = "⏳ Starting container...";\n'
        f'          status.textContent = "";\n'
        f'        }} else if (evt.type === "started") {{\n'
        f'          btn.textContent = "✓ Running — waiting for app...";\n'
        f'          btn.style.background = "#1a7f4b";\n'
        f'          status.textContent = "Container started. Health check polling every 3s...";\n'
        f'        }} else if (evt.type === "error") {{\n'
        f'          btn.textContent = "✗ Failed";\n'
        f'          status.textContent = evt.message || "Unknown error";\n'
        f'        }} else if (evt.type === "info" || evt.type === "progress") {{\n'
        f'          status.textContent = evt.message || "";\n'
        f'        }}\n'
        f'      }}\n'
        f'    }}\n'
        f'  }} catch(e) {{\n'
        f'    if (e.message && e.message.includes("Failed to fetch")) {{\n'
        f'      btn.textContent = "▶ Start with Forge Agent"; btn.disabled = false;\n'
        f'      status.innerHTML = "Forge Agent not reachable. Use the terminal command below.";\n'
        f'    }} else {{\n'
        f'      btn.textContent = "✗ Failed";\n'
        f'      status.textContent = e.message || "Unknown error";\n'
        f'      setTimeout(function(){{ btn.textContent="▶ Start with Forge Agent"; btn.disabled=false; }}, 3000);\n'
        f'    }}\n'
        f'  }}\n'
        f'}}\n'
        f'\n'
        f'// Backend health poll (same as before — detects backend regardless of how it was started)\n'
        f'(function() {{\n'
        f'  var overlay = document.getElementById("forge-backend-overlay");\n'
        f'  if (!overlay) return;\n'
        f'  overlay.style.display = "flex";\n'
        f'  function check() {{\n'
        f'    fetch("http://localhost:" + _backendPort + _healthPath, {{mode:"no-cors"}})\n'
        f'      .then(function() {{ overlay.style.display = "none"; }})\n'
        f'      .catch(function() {{ overlay.style.display = "flex"; }});\n'
        f'  }}\n'
        f'  check();\n'
        f'  setInterval(check, 3000);\n'
        f'}})();\n'
        f'</script>\n'
    )

    # Inject right after <body> (or after our bridge injection point)
    match = _BODY_OPEN_RE.search(html)
    if match:
        idx = match.end()
        return html[:idx] + overlay + html[idx:]
    return overlay + html


# -------------------- Demo data endpoint --------------------

@apps_bp.route("/api/apps/<int:tool_id>/demo-data", methods=["GET"])
def get_demo_data(tool_id):
    """Return the demo_data JSON for preview mode."""
    with db.get_db() as cur:
        cur.execute("SELECT demo_data FROM tools WHERE id = %s", (tool_id,))
        row = cur.fetchone()
    if not row or not row.get("demo_data"):
        return jsonify({"tool_id": tool_id, "demo_data": {}})
    try:
        data = json.loads(row["demo_data"])
    except (json.JSONDecodeError, TypeError):
        data = {}
    return jsonify({"tool_id": tool_id, "demo_data": data})


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
