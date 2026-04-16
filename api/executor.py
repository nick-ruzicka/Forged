"""
Tool execution engine. Runtime DLP, prompt interpolation, Claude API calls.
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

from api import db
from api.dlp import DLPEngine

LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)

_dlp_logger = logging.getLogger("forge.dlp")
if not _dlp_logger.handlers:
    _handler = logging.FileHandler(os.path.join(LOG_DIR, "dlp.log"))
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    _dlp_logger.addHandler(_handler)
    _dlp_logger.setLevel(logging.INFO)

HTML_TAG_RE = re.compile(r"<[^>]+>")

PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
}

# Approx Claude Haiku pricing per million tokens (USD).
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
}


def strip_html(value: str) -> str:
    if not isinstance(value, str):
        return value
    return HTML_TAG_RE.sub("", value)


def _parse_schema(schema: Any) -> list:
    if isinstance(schema, list):
        return schema
    if isinstance(schema, str):
        try:
            data = json.loads(schema) if schema else []
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def validate_required_fields(schema: Any, inputs: Dict[str, Any]) -> None:
    for field in _parse_schema(schema):
        if not isinstance(field, dict):
            continue
        name = field.get("name") or field.get("field_name")
        if not name:
            continue
        required = field.get("required", False)
        ftype = field.get("type", "text")
        if required:
            val = inputs.get(name)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                raise ValueError(f"Missing required field: {name}")
        if name in inputs and inputs[name] is not None:
            v = inputs[name]
            if ftype == "number":
                try:
                    float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"Field '{name}' must be a number")


def scan_for_pii(tool: Dict[str, Any], inputs: Dict[str, Any]) -> list:
    found = []
    tool_id = tool.get("id") if isinstance(tool, dict) else None
    tool_name = tool.get("name") if isinstance(tool, dict) else None
    user_email = inputs.get("_user_email") or inputs.get("user_email") or "unknown"
    for field_name, value in inputs.items():
        if not isinstance(value, str):
            continue
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(value):
                found.append({"field": field_name, "type": pii_type})
                _dlp_logger.warning(
                    "PII detected tool_id=%s tool_name=%s field=%s type=%s user=%s",
                    tool_id, tool_name, field_name, pii_type, user_email,
                )
    return found


def sanitize_inputs(tool: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Runtime DLP Layer: strip HTML, validate schema, log PII."""
    if isinstance(tool, dict):
        schema = tool.get("input_schema", "[]")
    else:
        schema = getattr(tool, "input_schema", "[]")

    cleaned: Dict[str, Any] = {}
    for field_name, value in (input_data or {}).items():
        if isinstance(value, str):
            cleaned[field_name] = strip_html(value)
        else:
            cleaned[field_name] = value

    validate_required_fields(schema, cleaned)
    scan_for_pii(tool if isinstance(tool, dict) else {}, cleaned)
    return cleaned


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def interpolate_prompt(template: str, inputs: Dict[str, Any]) -> str:
    if not template:
        return ""
    missing = []

    def _sub(m):
        key = m.group(1)
        if key not in inputs or inputs[key] is None:
            missing.append(key)
            return ""
        return str(inputs[key])

    rendered = _VAR_RE.sub(_sub, template)
    if missing:
        raise ValueError(
            f"Missing variables in inputs: {', '.join(sorted(set(missing)))}"
        )
    return rendered


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model) or MODEL_PRICING["claude-haiku-4-5-20251001"]
    cost = (input_tokens / 1_000_000) * pricing["input"] + \
           (output_tokens / 1_000_000) * pricing["output"]
    return round(cost, 6)


def call_claude(system_prompt: str, user_msg: str,
                model: str = "claude-haiku-4-5-20251001",
                max_tokens: int = 1000,
                temp: float = 0.3) -> Dict[str, Any]:
    """Call Anthropic API. Returns {text, input_tokens, output_tokens, cost_usd}."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(f"anthropic SDK not installed: {e}")

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temp,
        system=system_prompt or "",
        messages=[{"role": "user", "content": user_msg or ""}],
    )

    text_parts = []
    for block in getattr(msg, "content", []) or []:
        if hasattr(block, "text"):
            text_parts.append(block.text)
        elif isinstance(block, dict) and "text" in block:
            text_parts.append(block["text"])
    text = "".join(text_parts)

    usage = getattr(msg, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    cost = _compute_cost(model, input_tokens, output_tokens)

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }


def run_tool(tool_id: int, inputs: Dict[str, Any],
             user_name: Optional[str] = None,
             user_email: Optional[str] = None,
             source: str = "web") -> Dict[str, Any]:
    """Execute a tool end-to-end. Logs a row in runs. Returns result."""
    tool = db.get_tool(tool_id)
    if not tool:
        raise ValueError(f"Tool {tool_id} not found")

    if tool.get("status") not in ("approved", "draft", "pending_review"):
        # Still allow draft/pending runs by author; main gating happens at HTTP layer.
        pass

    cleaned = sanitize_inputs(tool, inputs)

    # Runtime DLP: mask PII in string inputs before prompt interpolation so the
    # Claude API only ever sees tokens like [EMAIL_1], [PHONE_1]. We unmask any
    # surviving tokens in the output below.
    dlp = DLPEngine()
    masked_inputs = dlp.mask_inputs(cleaned)
    dlp_tokens_found = dlp.token_count()

    prompt_template = tool.get("hardened_prompt") or tool.get("system_prompt") or ""
    rendered = interpolate_prompt(prompt_template, masked_inputs)

    model = tool.get("model") or "claude-haiku-4-5-20251001"
    max_tokens = tool.get("max_tokens") or 1000
    temperature = tool.get("temperature")
    if temperature is None:
        temperature = 0.3

    start = time.time()
    try:
        result = call_claude(
            system_prompt=rendered,
            user_msg="Run the tool with the provided context.",
            model=model,
            max_tokens=max_tokens,
            temp=float(temperature),
        )
        output_text = result["text"]
        input_tokens = result["input_tokens"]
        output_tokens = result["output_tokens"]
        cost_usd = result["cost_usd"]
        error = None
    except Exception as e:
        output_text = f"[Execution error: {e}]"
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
        error = str(e)

    duration_ms = int((time.time() - start) * 1000)

    if dlp_tokens_found:
        output_text = dlp.unmask_text(output_text)

    run_data = {
        "tool_id": tool_id,
        "tool_version": tool.get("version", 1),
        "input_data": json.dumps(cleaned),
        "rendered_prompt": rendered,
        "output_data": output_text,
        "run_duration_ms": duration_ms,
        "model_used": model,
        "tokens_used": (input_tokens or 0) + (output_tokens or 0),
        "cost_usd": cost_usd,
        "user_name": user_name,
        "user_email": user_email,
        "source": source,
        "dlp_tokens_found": dlp_tokens_found,
    }
    run_id = db.insert_run(run_data)
    db.increment_run_count(tool_id)

    return {
        "run_id": run_id,
        "output": output_text,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "tokens_used": run_data["tokens_used"],
        "model": model,
        "error": error,
    }
