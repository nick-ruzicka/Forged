"""
Synthesizer agent — aggregates all agent results into a final recommendation.

Single Claude call using Haiku. Applies safety thresholds (strict, block on fail)
and quality thresholds (advisory, warn but don't block). Produces structured
feedback with 3-5 issues, line references, and suggested fixes.
"""
from __future__ import annotations

import json
from datetime import datetime

from agents.base import HAIKU, get_client, parse_json_response, timed
from api import db

SYNTHESIZER_PROMPT = """You are the final reviewer in a 6-agent security and quality pipeline for a developer tool marketplace.

You receive results from 5 preceding agents. Your job: synthesize a final recommendation.

SAFETY RULES (strict — these MUST block):
- If attacks_succeeded > 0: recommend "block"
- If injection_risk is true: recommend "block"
- If data_exfil_risk is true: recommend "block"
- If the skill handles data at a higher class than declared (data_class_mismatch): recommend "block"
- If a safety-critical agent (red_team or security_scanner) timed out: recommend "needs_revision" with reason "automated review incomplete"

QUALITY RULES (advisory ONLY — these NEVER block or trigger needs_revision on their own):
- Low invocation precision or high false-fire rate: add to advisory_warnings array
- Low output consistency: add to advisory_warnings array
- Quality metrics are informational. They do NOT affect agent_recommendation.

DECISION LOGIC:
- Any safety rule violated → "block"
- Safety-critical agent timed out → "needs_revision"
- ALL safety rules pass (even if quality scores are low) → "approve"

Quality warnings are returned alongside an "approve" recommendation so the author can improve, but they NEVER change the recommendation from approve to needs_revision.

Produce 3-5 structured issues only for "block" or "needs_revision" recommendations. For "approve" with quality warnings, return issues=[] and put concerns in advisory_warnings.

Respond with ONLY valid JSON:
{
  "agent_recommendation": "approve" | "needs_revision" | "block",
  "agent_confidence": 0.0-1.0,
  "review_summary": "1-2 sentences",
  "issues": [{"line_ref": "SKILL.md:L1-5", "category": "...", "summary": "...", "suggested_fix": "..."}],
  "advisory_warnings": [{"metric": "...", "observed": 0.0, "baseline": 0.0}],
  "data_class_mismatch": false
}"""


@timed("synthesizer")
def run(skill_id: int, review_id: int, *, all_results: dict,
        declared_data_sensitivity: str = None) -> dict:
    client = get_client()

    # Check for timed-out agents
    timed_out = [name for name, r in all_results.items()
                 if isinstance(r, dict) and r.get("timed_out")]

    user_msg = (
        f"Agent results:\n\n{json.dumps(all_results, indent=2, default=str)}\n\n"
        f"Declared data sensitivity: {declared_data_sensitivity or 'not specified'}\n\n"
        f"Timed out agents: {timed_out or 'none'}"
    )

    resp = client.messages.create(
        model=HAIKU,
        max_tokens=1500,
        messages=[{"role": "user", "content": user_msg}],
        system=SYNTHESIZER_PROMPT,
    )
    text = resp.content[0].text

    try:
        result = parse_json_response(text)
    except (json.JSONDecodeError, ValueError):
        # Re-prompt once on parse failure
        resp2 = client.messages.create(
            model=HAIKU,
            max_tokens=1500,
            messages=[
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": text},
                {"role": "user", "content": "Your response was not valid JSON. Please respond with ONLY valid JSON matching the required schema."},
            ],
            system=SYNTHESIZER_PROMPT,
        )
        text = resp2.content[0].text
        try:
            result = parse_json_response(text)
        except (json.JSONDecodeError, ValueError):
            # Second parse also failed — persist a fallback row so the
            # review is marked needs_revision with a readable summary.
            result = {
                "agent_recommendation": "needs_revision",
                "agent_confidence": 0.0,
                "review_summary": "synthesizer produced unparseable output twice",
                "issues": [],
                "advisory_warnings": [],
                "data_class_mismatch": False,
            }

    db.update_agent_review(review_id,
        agent_recommendation=result.get("agent_recommendation", "needs_revision"),
        agent_confidence=result.get("agent_confidence", 0.5),
        review_summary=result.get("review_summary", ""),
        issues=result.get("issues", []),
        advisory_warnings=result.get("advisory_warnings", []),
        data_class_mismatch=bool(result.get("data_class_mismatch", False)),
        completed_at=datetime.utcnow(),
    )
    return result
