"""
Post a new-tool announcement to the #forge-releases Slack channel.

If SLACK_WEBHOOK_URL is not set, this is a no-op that returns False so
deployments do not fail on missing Slack configuration.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import requests

log = logging.getLogger("forge.slack")

TRUST_EMOJI = {
    "trusted": "🟢",
    "verified": "🔵",
    "caution": "🟡",
    "restricted": "🟠",
    "unverified": "⚪",
}


def _format_blocks(tool: Dict[str, Any]) -> Dict[str, Any]:
    name = tool.get("name") or "Untitled tool"
    tagline = tool.get("tagline") or ""
    trust_tier = (tool.get("trust_tier") or "unverified").lower()
    category = tool.get("category") or "uncategorized"
    author = tool.get("author_name") or "unknown"
    shareable = (
        tool.get("shareable_url") or tool.get("endpoint_url") or ""
    )
    instructions = tool.get("instructions_url") or ""
    emoji = TRUST_EMOJI.get(trust_tier, "⚪")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔨 New in Forge: {name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_{tagline}_"},
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Trust tier*\n{emoji} {trust_tier.title()}",
                },
                {"type": "mrkdwn", "text": f"*Category*\n{category}"},
                {"type": "mrkdwn", "text": f"*Built by*\n{author}"},
            ],
        },
    ]

    actions = []
    if shareable:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Run it", "emoji": True},
            "url": shareable,
            "style": "primary",
        })
    if instructions:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Instructions",
                     "emoji": True},
            "url": instructions,
        })
    if actions:
        blocks.append({"type": "actions", "elements": actions})

    return {
        "text": f"New tool live in Forge: {name}",
        "blocks": blocks,
    }


def send_slack_announcement(tool: Dict[str, Any]) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        log.info("SLACK_WEBHOOK_URL not set — skipping announcement")
        return False

    payload = _format_blocks(tool)
    try:
        resp = requests.post(
            webhook,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as exc:
        log.warning("Slack POST failed: %s", exc)
        return False

    if resp.status_code == 200:
        return True
    log.warning("Slack POST returned %s: %s",
                resp.status_code, resp.text[:200])
    return False
