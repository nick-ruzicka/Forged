"""
Shared infrastructure for the 6-agent review pipeline.

Provides:
- Claude client (cached)
- @timed decorator for per-agent timing
- with_timeout for hard agent timeouts
- Model and timeout constants
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from functools import wraps

from anthropic import Anthropic

from api import db

# Model constants
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

# Hard timeout budgets (seconds) — 3x each agent's p95
TIMEOUTS = {
    "classifier": 30,
    "security_scanner": 45,
    "red_team": 180,
    "prompt_hardener": 90,
    "qa_tester": 360,
    "synthesizer": 30,
}

_client = None


def get_client() -> Anthropic:
    """Return a cached Anthropic client instance."""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def timed(agent_name: str):
    """Decorator that logs per-agent timing to reviews_timing table.

    Catches TimeoutError (from with_timeout) and general exceptions.
    Always writes a timing row before returning.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(skill_id: int, review_id: int, *args, **kwargs):
            start = datetime.utcnow()
            try:
                result = fn(skill_id, review_id, *args, **kwargs)
                outcome = "success"
                error_detail = None
            except TimeoutError:
                result = {"timed_out": True, "agent_name": agent_name}
                outcome = "timeout"
                error_detail = f"{agent_name} exceeded {TIMEOUTS.get(agent_name)}s timeout"
            except Exception as e:
                result = {"error": str(e), "agent_name": agent_name}
                outcome = "error"
                error_detail = str(e)[:500]
            end = datetime.utcnow()
            duration_ms = int((end - start).total_seconds() * 1000)
            db.insert_review_timing(
                review_id=review_id,
                skill_id=skill_id,
                agent_name=agent_name,
                started_at=start,
                ended_at=end,
                duration_ms=duration_ms,
                outcome=outcome,
                error_detail=error_detail,
            )
            return result
        return wrapper
    return decorator


def with_timeout(fn, timeout_seconds, *args, **kwargs):
    """Run fn in a thread with a hard timeout.

    Returns the function's result, or raises TimeoutError if it
    doesn't complete within timeout_seconds.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout_seconds)


def parse_json_response(text: str) -> dict:
    """Parse JSON from a Claude response.

    Handles three common Claude output shapes:
      1. Bare JSON:                 {"a": 1}
      2. Fenced JSON:               ```json\n{"a": 1}\n```
      3. Prose + fenced JSON:       Here's the JSON:\n```json\n{"a": 1}\n```
      4. Prose + bare JSON:         Sure thing:\n{"a": 1}

    Extracts by content, not by position, so prose before/after the block
    doesn't break parsing. Raises json.JSONDecodeError if nothing parseable
    is found.
    """
    cleaned = (text or "").strip()

    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    else:
        bare = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if bare:
            cleaned = bare.group(1).strip()

    return json.loads(cleaned)
