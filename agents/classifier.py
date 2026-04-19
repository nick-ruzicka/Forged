"""
Classifier agent — detects skill category and output type.

Single Claude call using Haiku. Compares detected category against
the author's declared category and flags mismatches.
"""
from __future__ import annotations

import json

from agents.base import HAIKU, get_client, timed
from api import db

CLASSIFIER_PROMPT = """You are a skill classifier for a developer tool marketplace.

Given a SKILL.md file, determine:
1. The best-fit category from: Development, Testing, Debugging, Planning, Code Review, Documents, Other
2. The intended output type: code, text, structured-data, conversation, mixed
3. Your confidence in the classification (0.0 to 1.0)
4. Whether the declared category (provided separately) mismatches your detected category

Respond with ONLY valid JSON:
{
  "detected_category": "...",
  "detected_output_type": "...",
  "classification_confidence": 0.0,
  "category_mismatch": false
}"""


@timed("classifier")
def run(skill_id: int, review_id: int, *, skill_text: str, declared_category: str = "") -> dict:
    client = get_client()
    user_msg = f"SKILL.md contents:\n\n{skill_text}\n\nDeclared category: {declared_category or 'not specified'}"

    resp = client.messages.create(
        model=HAIKU,
        max_tokens=500,
        messages=[{"role": "user", "content": user_msg}],
        system=CLASSIFIER_PROMPT,
    )
    text = resp.content[0].text
    result = json.loads(text)

    db.update_agent_review(review_id,
        classifier_output=text,
        detected_category=result.get("detected_category"),
        detected_output_type=result.get("detected_output_type"),
        classification_confidence=result.get("classification_confidence"),
    )
    return result
