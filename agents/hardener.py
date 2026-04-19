"""
Prompt Hardener agent — rewrites SKILL.md with safety mitigations.

Single Claude call using Sonnet. Takes original skill text + Red Team
findings and produces a hardened version. The hardened version is stored
as feedback for the author, not auto-applied.
"""
from __future__ import annotations

import json

from agents.base import SONNET, get_client, timed
from api import db

HARDENER_PROMPT = """You are a prompt security hardener for a developer tool marketplace.

Given a SKILL.md file and any vulnerabilities found by the red team, rewrite the skill to resist the identified attacks while preserving its intended functionality.

If no vulnerabilities were found, apply generic hardening:
- Add clear instruction boundaries
- Add explicit refusal patterns for credential access and data exfiltration
- Ensure the skill cannot be instruction-overridden

Respond with ONLY valid JSON:
{
  "hardened_prompt": "the full rewritten SKILL.md text",
  "changes_made": "summary of what changed",
  "hardening_summary": "1-2 sentence overview"
}"""


@timed("prompt_hardener")
def run(skill_id: int, review_id: int, *, skill_text: str,
        vulnerabilities: str = "[]", hardening_suggestions: str = "[]") -> dict:
    client = get_client()
    user_msg = (
        f"Original SKILL.md:\n\n{skill_text}\n\n"
        f"---\n\nVulnerabilities found:\n{vulnerabilities}\n\n"
        f"Hardening suggestions:\n{hardening_suggestions}"
    )

    resp = client.messages.create(
        model=SONNET,
        max_tokens=4000,
        messages=[{"role": "user", "content": user_msg}],
        system=HARDENER_PROMPT,
    )
    text = resp.content[0].text
    result = json.loads(text)

    db.update_agent_review(review_id,
        hardener_output=text,
        original_prompt=skill_text,
        hardened_prompt=result.get("hardened_prompt", ""),
        changes_made=result.get("changes_made", ""),
        hardening_summary=result.get("hardening_summary", ""),
    )
    return result
