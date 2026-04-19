"""
Security Scanner agent — regex patterns + Claude judgment.

Step 1: Regex scan for skill-specific dangerous patterns.
Step 2: Claude (Haiku) evaluates whether regex hits are real risks or false positives.
"""
from __future__ import annotations

import json
import re

from agents.base import HAIKU, get_client, parse_json_response, timed
from api import db

# Skill-specific security patterns
PATTERNS = {
    "credential_paths": re.compile(
        r"~/\.ssh|~/\.env|~/\.aws|~/\.config|id_rsa|credentials\.json|\.pem\b",
        re.IGNORECASE,
    ),
    "unknown_urls": re.compile(
        r"https?://(?!localhost|127\.0\.0\.1|example\.com)[a-zA-Z0-9._\-]+",
        re.IGNORECASE,
    ),
    "destructive_commands": re.compile(
        r"rm\s+-rf|--no-verify|--force\b|git\s+push\s+-f|DROP\s+TABLE|TRUNCATE\b",
        re.IGNORECASE,
    ),
    "hook_skipping": re.compile(
        r"--no-verify|--no-gpg-sign|commit\.gpgsign\s*=\s*false",
        re.IGNORECASE,
    ),
}

SCANNER_PROMPT = """You are a security scanner for a developer tool marketplace.

A SKILL.md file has been scanned for dangerous patterns. The regex scan found the hits listed below.

Your job: determine whether each hit represents a REAL security risk or a FALSE POSITIVE in context.

Consider: Is the skill instructing Claude to actually read credentials, exfiltrate data, or run destructive commands? Or is it merely mentioning these things in documentation, examples, or safety instructions?

Respond with ONLY valid JSON:
{
  "pii_risk": false,
  "injection_risk": false,
  "data_exfil_risk": false,
  "security_score": 0-100,
  "security_flags": "comma-separated categories or 'none'",
  "analysis": "brief explanation"
}"""


@timed("security_scanner")
def run(skill_id: int, review_id: int, *, skill_text: str) -> dict:
    # Step 1: Regex scan
    regex_hits = []
    for name, pattern in PATTERNS.items():
        matches = pattern.findall(skill_text)
        if matches:
            regex_hits.append({"pattern": name, "matches": matches[:5]})

    # Step 2: Claude judgment
    client = get_client()
    user_msg = f"SKILL.md contents:\n\n{skill_text}\n\nRegex scan results:\n{json.dumps(regex_hits, indent=2)}"

    resp = client.messages.create(
        model=HAIKU,
        max_tokens=500,
        messages=[{"role": "user", "content": user_msg}],
        system=SCANNER_PROMPT,
    )
    text = resp.content[0].text
    result = parse_json_response(text)
    result["regex_hits"] = regex_hits

    db.update_agent_review(review_id,
        security_scan_output=text,
        security_flags=result.get("security_flags", "none"),
        security_score=result.get("security_score", 0),
        pii_risk=result.get("pii_risk", False),
        injection_risk=result.get("injection_risk", False),
        data_exfil_risk=result.get("data_exfil_risk", False),
    )
    return result
