"""
Auto-derive a "Behind the scenes" trust card for an app's HTML/JS.

Run at submit + on demand. Stores results in tool_inspections.
Output is plain-English badges, never engineering jargon — non-technical
users should immediately understand what an app does and doesn't do.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List
from urllib.parse import urlparse

from api import db


# Patterns we sniff for. Conservative: false positives are better than false negatives.
PATTERNS = {
    "ai_runtool":    re.compile(r"window\.ForgeAPI\.runTool\s*\(", re.IGNORECASE),
    "ai_anthropic":  re.compile(r"\b(anthropic|messages\.create|claude-?\w+)\b", re.IGNORECASE),
    "ai_openai":     re.compile(r"\b(openai|chat\.completions)\b", re.IGNORECASE),
    "data_sf":       re.compile(r"window\.ForgeAPI\.data\.salesforce", re.IGNORECASE),
    "data_get":      re.compile(r"window\.ForgeAPI\.getData\s*\(", re.IGNORECASE),
    "storage_set":   re.compile(r"(window\.ForgeAPI\.setData|localStorage\.setItem)\s*\("),
    "fetch_call":    re.compile(r"\bfetch\s*\(\s*['\"]([^'\"]+)['\"]"),
    "url_literal":   re.compile(r"['\"](https?://[a-zA-Z0-9_.\-]+(?::\d+)?(?:/[^\s'\"<>]*)?)['\"]"),
    "uses_eval":     re.compile(r"\b(eval|new\s+Function|innerHTML\s*=\s*[^=])"),
}


def inspect_app_html(html: str) -> Dict:
    """Return a dict that maps to the tool_inspections schema."""
    if not html:
        return _empty_result()

    ai_calls: List[Dict[str, str]] = []
    if PATTERNS["ai_runtool"].search(html):
        ai_calls.append({"fn": "ForgeAPI.runTool", "intent": "Calls Forge's prompt runner"})
    if PATTERNS["ai_anthropic"].search(html):
        ai_calls.append({"fn": "anthropic", "intent": "Calls Claude API"})
    if PATTERNS["ai_openai"].search(html):
        ai_calls.append({"fn": "openai", "intent": "Calls OpenAI API"})

    reads_data: List[str] = []
    if PATTERNS["data_sf"].search(html):
        reads_data.append("Salesforce")
    if PATTERNS["data_get"].search(html):
        reads_data.append("Your Forge profile")

    writes_data = bool(PATTERNS["storage_set"].search(html))

    # External hosts: from fetch() literal URLs and from any string that looks like https://...
    hosts = set()
    for m in PATTERNS["fetch_call"].finditer(html):
        url = m.group(1)
        if url.startswith("/"):
            continue  # same-origin
        try:
            host = urlparse(url).hostname
            if host:
                hosts.add(host)
        except Exception:
            pass
    for m in PATTERNS["url_literal"].finditer(html):
        try:
            host = urlparse(m.group(1)).hostname
            if host and "localhost" not in host and "127.0.0.1" not in host:
                hosts.add(host)
        except Exception:
            pass

    # Filter known-safe CDNs from "external hosts" — they're cosmetic, not data exfil.
    SAFE_CDNS = {
        "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com",
        "fonts.googleapis.com", "fonts.gstatic.com",
    }
    real_hosts = sorted([h for h in hosts if h not in SAFE_CDNS])

    return {
        "uses_ai": len(ai_calls) > 0,
        "ai_calls": json.dumps(ai_calls),
        "reads_data": json.dumps(reads_data),
        "writes_data": writes_data,
        "external_hosts": json.dumps(real_hosts),
        "uses_storage": writes_data or "localStorage" in html,
        "uses_eval": bool(PATTERNS["uses_eval"].search(html)),
    }


def _empty_result() -> Dict:
    return {
        "uses_ai": False, "ai_calls": "[]", "reads_data": "[]",
        "writes_data": False, "external_hosts": "[]",
        "uses_storage": False, "uses_eval": False,
    }


def store_inspection(tool_id: int, html: str) -> Dict:
    """Inspect + persist + return the result dict (with tool_id)."""
    result = inspect_app_html(html)
    with db.get_db() as cur:
        cur.execute(
            """
            INSERT INTO tool_inspections (
              tool_id, uses_ai, ai_calls, reads_data, writes_data,
              external_hosts, uses_storage, uses_eval, inspected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (tool_id) DO UPDATE SET
              uses_ai = EXCLUDED.uses_ai,
              ai_calls = EXCLUDED.ai_calls,
              reads_data = EXCLUDED.reads_data,
              writes_data = EXCLUDED.writes_data,
              external_hosts = EXCLUDED.external_hosts,
              uses_storage = EXCLUDED.uses_storage,
              uses_eval = EXCLUDED.uses_eval,
              inspected_at = NOW()
            """,
            (
                tool_id, result["uses_ai"], result["ai_calls"], result["reads_data"],
                result["writes_data"], result["external_hosts"],
                result["uses_storage"], result["uses_eval"],
            ),
        )
    result["tool_id"] = tool_id
    return result


def get_inspection(tool_id: int) -> Dict | None:
    """Read the latest inspection for a tool. Returns None if never inspected."""
    with db.get_db() as cur:
        cur.execute(
            "SELECT * FROM tool_inspections WHERE tool_id = %s",
            (tool_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    out = dict(row)
    for key in ("ai_calls", "reads_data", "external_hosts"):
        try:
            out[key] = json.loads(out.get(key) or "[]")
        except json.JSONDecodeError:
            out[key] = []
    return out


def render_badges(inspection: Dict) -> List[Dict[str, str]]:
    """Convert raw inspection into user-facing badges. Plain English only."""
    if not inspection:
        return [{"icon": "🔍", "label": "Not yet inspected", "tone": "muted"}]
    badges: List[Dict[str, str]] = []
    if inspection.get("uses_ai"):
        ai = inspection.get("ai_calls") or []
        intents = ", ".join(c.get("intent") for c in ai if c.get("intent"))
        badges.append({
            "icon": "🤖",
            "label": f"Uses AI: {intents or 'yes'}",
            "tone": "info",
            "detail": "AI output may vary. Review before acting.",
        })
    else:
        badges.append({
            "icon": "✓",
            "label": "No AI — deterministic behavior",
            "tone": "ok",
        })
    reads = inspection.get("reads_data") or []
    if reads:
        badges.append({
            "icon": "🔌",
            "label": f"Reads: {', '.join(reads)}",
            "tone": "info",
        })
    if inspection.get("writes_data"):
        badges.append({
            "icon": "💾",
            "label": "Stores data per user",
            "tone": "info",
            "detail": "Your data stays in your Forge profile. Other users can't see it.",
        })
    hosts = inspection.get("external_hosts") or []
    if hosts:
        badges.append({
            "icon": "🌐",
            "label": f"External: {', '.join(hosts[:3])}{'…' if len(hosts) > 3 else ''}",
            "tone": "warn",
            "detail": "Sends data to hosts outside your company.",
        })
    if inspection.get("uses_eval"):
        badges.append({
            "icon": "⚠",
            "label": "Uses eval / innerHTML",
            "tone": "warn",
            "detail": "Could execute arbitrary code. Reviewers should look closely.",
        })
    return badges
