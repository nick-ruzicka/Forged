"""
Forge auto-deployer.

Called from the webhook background thread when GitHub pushes to main/master.
Clones the repo shallowly, reads `forge.yaml` (or synthesises one from
`index.html`), POSTs the HTML bundle to Forge, and posts a commit status back
to GitHub so the push shows a Forge deployment check.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

import yaml


LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "deploy.log")

log = logging.getLogger("forge_bot.deployer")
log.setLevel(logging.INFO)
if not log.handlers:
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(stream)


TMP_ROOT = "/tmp/forge-deploy"
ALLOWED_CATEGORIES = {
    "Account Research", "Email Generation", "Contact Scoring", "Data Lookup",
    "Reporting", "Onboarding", "Forecasting", "Other", "other",
}
ALLOWED_TYPES = {"app", "prompt"}


def _forge_base() -> str:
    return (os.environ.get("FORGE_API_URL") or "http://localhost:8090").rstrip("/")


def _forge_key() -> str:
    return os.environ.get("FORGE_API_KEY") or os.environ.get("ADMIN_KEY") or ""


def _github_token() -> str:
    return os.environ.get("GITHUB_TOKEN") or ""


# -------------------- forge.yaml loading --------------------

def _auto_forge_yaml(repo_name: str) -> Dict[str, Any]:
    pretty = repo_name.replace("-", " ").replace("_", " ").strip().title() or "Forge App"
    return {
        "name": pretty,
        "tagline": f"Auto-deployed from the {repo_name} repository.",
        "category": "Other",
        "entry": "index.html",
        "type": "app",
    }


def _load_forge_config(workdir: str, repo_name: str) -> Dict[str, Any]:
    yaml_path = os.path.join(workdir, "forge.yaml")
    index_path = os.path.join(workdir, "index.html")
    if os.path.isfile(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("forge.yaml must be a mapping")
    elif os.path.isfile(index_path):
        log.info("no forge.yaml found — auto-generating from index.html")
        data = _auto_forge_yaml(repo_name)
    else:
        raise FileNotFoundError("repo has neither forge.yaml nor index.html")

    data.setdefault("name", _auto_forge_yaml(repo_name)["name"])
    data.setdefault("tagline", "Published via GitHub auto-deploy.")
    data.setdefault("description", "")
    data.setdefault("category", "Other")
    data.setdefault("entry", "index.html")
    data.setdefault("type", "app")

    if data["type"] not in ALLOWED_TYPES:
        raise ValueError(f"forge.yaml type must be one of {ALLOWED_TYPES}")
    if data["category"] not in ALLOWED_CATEGORIES:
        log.warning("category %r not in whitelist — defaulting to Other", data["category"])
        data["category"] = "Other"
    return data


# -------------------- HTTP helpers --------------------

def _post_json(url: str, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None,
               method: str = "POST") -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return {"status": resp.status, "body": json.loads(raw) if raw.strip() else {}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") or ""
        try:
            body = json.loads(raw) if raw.strip() else {"error": raw}
        except json.JSONDecodeError:
            body = {"error": raw}
        return {"status": e.code, "body": body}


# -------------------- Forge submit / update --------------------

def _submit_to_forge(payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {}
    key = _forge_key()
    if key:
        headers["X-Admin-Key"] = key
    # Endpoint shipped by the forge-cli track.
    url = f"{_forge_base()}/api/submit/app"
    log.info("POST %s (name=%s)", url, payload.get("name"))
    return _post_json(url, payload, headers=headers)


def _update_html(tool_id: int, html: str) -> Dict[str, Any]:
    url = f"{_forge_base()}/api/admin/tools/{tool_id}/update-html"
    headers = {"X-Admin-Key": _forge_key()}
    log.info("POST %s (in-place update, html=%d bytes)", url, len(html))
    return _post_json(url, {"html": html}, headers=headers)


# -------------------- GitHub commit status --------------------

def _post_commit_status(owner: str, repo: str, sha: str, state: str,
                        target_url: str, description: str) -> None:
    token = _github_token()
    if not token or not owner or not repo or not sha:
        log.info("skipping commit status (missing token or repo coords)")
        return
    url = f"https://api.github.com/repos/{owner}/{repo}/statuses/{sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = {
        "state": state,
        "target_url": target_url,
        "description": description[:140],
        "context": "forge/deploy",
    }
    result = _post_json(url, body, headers=headers)
    log.info("commit status %s -> %s", state, result.get("status"))


# -------------------- main entrypoint --------------------

def handle_push(repo_url: str, repo_name: str, commit_sha: str,
                owner: str = "", repo: str = "") -> Dict[str, Any]:
    """Clone the repo, publish it to Forge, post a GitHub commit status."""
    os.makedirs(TMP_ROOT, exist_ok=True)
    workdir = os.path.join(TMP_ROOT, f"{repo_name}-{commit_sha[:12]}")
    if os.path.exists(workdir):
        shutil.rmtree(workdir, ignore_errors=True)

    log.info("handle_push start repo=%s sha=%s", repo_name, commit_sha[:7])

    try:
        clone_url = _inject_token(repo_url)
        subprocess.run(
            ["git", "clone", "--depth=1", clone_url, workdir],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode("utf-8", errors="replace")
        log.error("git clone failed: %s", msg.strip())
        _post_commit_status(owner, repo, commit_sha, "error",
                            target_url=_forge_base(),
                            description="Forge deploy: git clone failed")
        return {"ok": False, "error": "clone_failed", "detail": msg}
    except subprocess.TimeoutExpired:
        log.error("git clone timed out")
        _post_commit_status(owner, repo, commit_sha, "error",
                            target_url=_forge_base(),
                            description="Forge deploy: clone timeout")
        return {"ok": False, "error": "clone_timeout"}

    try:
        config = _load_forge_config(workdir, repo_name)
        entry = config["entry"]
        entry_path = os.path.join(workdir, entry)
        if not os.path.isfile(entry_path):
            raise FileNotFoundError(f"entry file not found: {entry}")
        with open(entry_path, "r", encoding="utf-8") as f:
            app_html = f.read()

        payload = {
            "name": config["name"],
            "tagline": config.get("tagline", ""),
            "description": config.get("description", ""),
            "category": config.get("category", "Other"),
            "app_type": config.get("type", "app"),
            "app_html": app_html,
            "schedule_cron": config.get("schedule") or None,
            "schedule_channel": config.get("slack_channel") or None,
            "author_name": config.get("author_name") or f"{owner} via GitHub" if owner else "GitHub auto-deploy",
            "author_email": config.get("author_email") or f"{owner}@users.noreply.github.com" if owner else "bot@forge.internal",
            "source": "github",
            "source_repo": f"{owner}/{repo}" if owner and repo else repo_name,
            "source_commit": commit_sha,
        }

        result = _submit_to_forge(payload)
        status = result.get("status", 0)
        body = result.get("body") or {}

        # Handle slug collision — tool already exists, update in place instead.
        if status in (409, 422) or (
            isinstance(body, dict) and body.get("error") in ("slug_exists", "duplicate", "exists")
        ):
            existing_id = body.get("id") or body.get("tool_id")
            if existing_id:
                log.info("slug collision — updating existing tool id=%s", existing_id)
                upd = _update_html(int(existing_id), app_html)
                if upd.get("status") == 200:
                    forge_url = (upd.get("body") or {}).get("url") or f"{_forge_base()}/apps/{(upd.get('body') or {}).get('slug', '')}"
                    _post_commit_status(owner, repo, commit_sha, "success",
                                        target_url=forge_url,
                                        description="Redeployed to Forge")
                    return {"ok": True, "mode": "update", "tool_id": existing_id, "url": forge_url}
                log.error("update-html failed: %s", upd)
                _post_commit_status(owner, repo, commit_sha, "error",
                                    target_url=_forge_base(),
                                    description="Forge deploy: update failed")
                return {"ok": False, "error": "update_failed", "detail": upd}

        if status in (200, 201):
            tool_id = body.get("id") or body.get("tool_id")
            slug = body.get("slug") or ""
            forge_url = body.get("url") or (f"{_forge_base()}/apps/{slug}" if slug else _forge_base())
            _post_commit_status(owner, repo, commit_sha, "success",
                                target_url=forge_url,
                                description="Deployed to Forge")
            log.info("deploy success tool_id=%s slug=%s", tool_id, slug)
            return {"ok": True, "mode": "create", "tool_id": tool_id, "slug": slug, "url": forge_url}

        log.error("forge submit failed status=%s body=%s", status, body)
        _post_commit_status(owner, repo, commit_sha, "failure",
                            target_url=_forge_base(),
                            description=f"Forge deploy failed ({status})")
        return {"ok": False, "error": "submit_failed", "status": status, "body": body}

    except FileNotFoundError as e:
        log.error("deploy aborted: %s", e)
        _post_commit_status(owner, repo, commit_sha, "failure",
                            target_url=_forge_base(),
                            description=str(e)[:140])
        return {"ok": False, "error": "missing_file", "detail": str(e)}
    except Exception as e:
        log.exception("deploy failed unexpectedly")
        _post_commit_status(owner, repo, commit_sha, "error",
                            target_url=_forge_base(),
                            description="Forge deploy: internal error")
        return {"ok": False, "error": "exception", "detail": str(e)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _inject_token(clone_url: str) -> str:
    """If GITHUB_TOKEN is set and the clone URL is HTTPS, embed it for private repos."""
    token = _github_token()
    if not token or not clone_url.startswith("https://"):
        return clone_url
    # Avoid re-embedding if the URL already has credentials.
    if "@" in clone_url.split("://", 1)[1]:
        return clone_url
    return clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
