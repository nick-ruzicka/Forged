"""
Forge deployment module.
Called when an admin approves a tool. Provisions endpoint, generates
usage instructions (Markdown + PDF), notifies Slack, and marks the tool
as deployed in the database.

Owned by: T5 (Deployment)
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from api import db

# Make scripts/ importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = logging.getLogger("forge.deploy")

FORGE_HOST = os.environ.get("FORGE_HOST", "http://localhost:8090").rstrip("/")
STATIC_DIR = _REPO_ROOT / "static"
INSTRUCTIONS_DIR = STATIC_DIR / "instructions"


def _ensure_dirs() -> None:
    INSTRUCTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _build_urls(tool: Dict[str, Any], access_token: str) -> Dict[str, str]:
    slug = tool.get("slug") or f"tool-{tool['id']}"
    endpoint_url = f"{FORGE_HOST}/tools/{slug}/run"
    shareable_url = f"{FORGE_HOST}/t/{access_token}"
    instructions_url = f"{FORGE_HOST}/static/instructions/{tool['id']}.md"
    return {
        "endpoint_url": endpoint_url,
        "shareable_url": shareable_url,
        "instructions_url": instructions_url,
    }


def deploy_tool(tool_id: int) -> Dict[str, Any]:
    """
    Provision a tool for live use. Idempotent: re-running reuses the
    existing access_token if present.
    """
    _ensure_dirs()

    tool = db.get_tool(tool_id)
    if not tool:
        return {"success": False, "error": f"tool {tool_id} not found"}

    access_token = tool.get("access_token") or str(uuid.uuid4())
    urls = _build_urls(tool, access_token)

    tool_for_generation = dict(tool)
    tool_for_generation["access_token"] = access_token
    tool_for_generation["endpoint_url"] = urls["endpoint_url"]
    tool_for_generation["shareable_url"] = urls["shareable_url"]

    # Generate Markdown instructions
    md_path = INSTRUCTIONS_DIR / f"{tool_id}.md"
    markdown_content = ""
    try:
        from scripts.generate_instructions import generate_instructions_content
        markdown_content = generate_instructions_content(tool_for_generation)
        md_path.write_text(markdown_content, encoding="utf-8")
    except Exception as exc:
        log.warning("instructions generation failed for tool %s: %s",
                    tool_id, exc)

    # Generate PDF (optional)
    pdf_path = None
    if markdown_content:
        try:
            from scripts.generate_pdf import generate_pdf
            pdf_path = generate_pdf(tool_id, markdown_content)
        except Exception as exc:
            log.warning("PDF generation failed for tool %s: %s",
                        tool_id, exc)

    # Persist deployment state on the tool record
    deployed_at = datetime.now(timezone.utc)
    try:
        db.update_tool(
            tool_id,
            deployed=True,
            deployed_at=deployed_at,
            endpoint_url=urls["endpoint_url"],
            access_token=access_token,
            instructions_url=urls["instructions_url"],
        )
    except Exception as exc:
        log.error("failed to persist deployment state for tool %s: %s",
                  tool_id, exc)
        return {"success": False, "error": f"db update failed: {exc}"}

    # Slack announcement (optional)
    try:
        from scripts.slack_notify import send_slack_announcement
        slack_payload = dict(tool_for_generation)
        slack_payload["instructions_url"] = urls["instructions_url"]
        send_slack_announcement(slack_payload)
    except Exception as exc:
        log.warning("slack announcement failed for tool %s: %s",
                    tool_id, exc)

    return {
        "success": True,
        "tool_id": tool_id,
        "endpoint_url": urls["endpoint_url"],
        "access_token": access_token,
        "shareable_url": urls["shareable_url"],
        "instructions_url": urls["instructions_url"],
        "pdf_url": (
            f"{FORGE_HOST}/static/instructions/{tool_id}.pdf"
            if pdf_path else None
        ),
    }


def deployment_status(tool_id: int) -> Dict[str, Any]:
    tool = db.get_tool(tool_id)
    if not tool:
        return {"found": False}
    return {
        "found": True,
        "deployed": bool(tool.get("deployed")),
        "deployed_at": tool.get("deployed_at"),
        "endpoint_url": tool.get("endpoint_url"),
        "access_token": tool.get("access_token"),
        "instructions_url": tool.get("instructions_url"),
    }


def regenerate_instructions(tool_id: int) -> Dict[str, Any]:
    tool = db.get_tool(tool_id)
    if not tool:
        return {"success": False, "error": f"tool {tool_id} not found"}
    _ensure_dirs()

    access_token = tool.get("access_token") or str(uuid.uuid4())
    urls = _build_urls(tool, access_token)
    payload = dict(tool)
    payload["access_token"] = access_token
    payload["endpoint_url"] = urls["endpoint_url"]
    payload["shareable_url"] = urls["shareable_url"]

    try:
        from scripts.generate_instructions import generate_instructions_content
        md = generate_instructions_content(payload)
        (INSTRUCTIONS_DIR / f"{tool_id}.md").write_text(md, encoding="utf-8")
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    try:
        from scripts.generate_pdf import generate_pdf
        generate_pdf(tool_id, md)
    except Exception as exc:
        log.warning("PDF regen failed: %s", exc)

    if not tool.get("access_token"):
        db.update_tool(tool_id, access_token=access_token,
                       instructions_url=urls["instructions_url"])

    return {"success": True, "instructions_url": urls["instructions_url"]}
