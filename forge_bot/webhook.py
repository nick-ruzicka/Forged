"""
Forge GitHub webhook receiver.

Flask app listening on port 8093 (8091 is reserved for the test dashboard).
GitHub App -> POST /webhook -> verify HMAC -> dispatch handle_push() in a
background thread so we return 200 to GitHub within its 10-second window.

Env vars:
    GITHUB_WEBHOOK_SECRET   shared secret configured on the GitHub App
    FORGE_API_URL           base URL of the Forge API (for deployer.py)
    FORGE_API_KEY           admin key forwarded by deployer.py
    GITHUB_TOKEN            token used to post commit statuses back to GitHub
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from hashlib import sha256
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request

from forge_bot import deployer

PORT = int(os.environ.get("FORGE_WEBHOOK_PORT", "8093"))
HOST = os.environ.get("FORGE_WEBHOOK_HOST", "0.0.0.0")

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "webhook.log")

log = logging.getLogger("forge_bot.webhook")
log.setLevel(logging.INFO)
if not log.handlers:
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(stream)

app = Flask(__name__)


def _signature_valid(secret: str, body: bytes, header: str) -> bool:
    """Timing-safe comparison of X-Hub-Signature-256 against HMAC(secret, body)."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def _dispatch_async(repo_url: str, repo_name: str, commit_sha: str, owner: str, repo: str) -> None:
    def _run() -> None:
        try:
            deployer.handle_push(
                repo_url=repo_url,
                repo_name=repo_name,
                commit_sha=commit_sha,
                owner=owner,
                repo=repo,
            )
        except Exception as exc:
            log.exception("handle_push failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "forge-webhook", "port": PORT})


@app.route("/webhook", methods=["POST"])
def webhook():
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        log.error("GITHUB_WEBHOOK_SECRET is not set — rejecting webhook")
        return jsonify({"error": "webhook_secret_not_configured"}), 500

    body = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _signature_valid(secret, body, signature):
        log.warning("Invalid signature from %s", request.remote_addr)
        return jsonify({"error": "invalid_signature"}), 401

    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery", "")

    if event == "ping":
        log.info("ping delivery=%s", delivery)
        return jsonify({"ok": True, "pong": True})

    if event != "push":
        log.info("ignoring event=%s delivery=%s", event, delivery)
        return jsonify({"ok": True, "ignored": event})

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        log.error("invalid JSON body: %s", exc)
        return jsonify({"error": "invalid_json"}), 400

    ref = payload.get("ref") or ""
    if ref not in ("refs/heads/main", "refs/heads/master"):
        log.info("ignoring push to %s delivery=%s", ref, delivery)
        return jsonify({"ok": True, "ignored_ref": ref})

    repository = payload.get("repository") or {}
    repo_url = repository.get("clone_url") or ""
    repo_name = repository.get("name") or ""
    full_name = repository.get("full_name") or ""
    owner, _, repo = full_name.partition("/")
    commit_sha = (payload.get("after")
                  or (payload.get("head_commit") or {}).get("id")
                  or "")

    if not repo_url or not commit_sha or not repo_name:
        log.error("missing repo/commit info delivery=%s", delivery)
        return jsonify({"error": "missing_fields"}), 400

    log.info(
        "push accepted repo=%s sha=%s delivery=%s",
        full_name, commit_sha[:7], delivery,
    )
    _dispatch_async(repo_url, repo_name, commit_sha, owner, repo)
    return jsonify({"ok": True, "queued": True, "commit": commit_sha[:7]}), 202


if __name__ == "__main__":
    log.info("starting forge webhook on %s:%d", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False)
