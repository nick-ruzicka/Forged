"""
Generate the human-readable usage guide for a deployed tool.

Primary API:
    generate_instructions_content(tool_dict) -> Markdown string

Uses Claude (if ANTHROPIC_API_KEY is set) to craft a polished guide;
falls back to a deterministic template if the API call fails so the
deployment pipeline never gets blocked on LLM availability.

CLI:
    python3 scripts/generate_instructions.py --tool-id 123
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("forge.instructions")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

TRUST_TIER_COPY = {
    "trusted": (
        "This is a **TRUSTED** tool. Outputs are consistent and have been "
        "validated against ground truth. Safe to act on directly."
    ),
    "verified": (
        "This is a **VERIFIED** tool. It has been reviewed and tested. "
        "Use with standard professional judgment."
    ),
    "caution": (
        "This is a **CAUTION** tool. Outputs may vary or have not been "
        "fully validated. Review carefully before acting on results."
    ),
    "restricted": (
        "This is a **RESTRICTED** tool. Access is gated. Contact the "
        "platform admin if you need elevated permissions."
    ),
    "unverified": (
        "This is an **UNVERIFIED** tool. Treat output as experimental "
        "until the tool has been exercised by multiple reviewers."
    ),
}


def _parse_input_schema(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    return []


def _fallback_template(tool: Dict[str, Any]) -> str:
    name = tool.get("name", "Untitled Tool")
    tagline = tool.get("tagline", "")
    description = tool.get("description") or tagline or "(no description)"
    trust_tier = (tool.get("trust_tier") or "unverified").lower()
    tier_copy = TRUST_TIER_COPY.get(trust_tier, TRUST_TIER_COPY["unverified"])
    author = tool.get("author_name") or "the Forge team"
    shareable = tool.get("shareable_url") or tool.get("endpoint_url") or ""
    endpoint = tool.get("endpoint_url") or ""
    output_type = tool.get("output_type") or "probabilistic"
    output_format = tool.get("output_format") or "text"

    schema = _parse_input_schema(tool.get("input_schema"))
    field_lines: List[str] = []
    for idx, field in enumerate(schema, start=1):
        label = field.get("label") or field.get("name") or f"field {idx}"
        fname = field.get("name") or label
        ftype = field.get("type") or "text"
        required = field.get("required")
        req_marker = " *(required)*" if required else ""
        placeholder = field.get("placeholder") or field.get("help") or ""
        detail = f" — {placeholder}" if placeholder else ""
        field_lines.append(
            f"{idx}. **{label}** (`{fname}`, {ftype}){req_marker}{detail}"
        )
    if not field_lines:
        field_lines.append("This tool takes no inputs — just run it.")

    limitations: List[str] = []
    if output_type == "probabilistic":
        limitations.append(
            "Output will vary between runs — this tool is probabilistic by "
            "design. Review each result."
        )
    if (tool.get("safety_score") or 0) < 60:
        limitations.append(
            "Safety score is below 60. Do not act on output without human "
            "review."
        )
    if (tool.get("data_sensitivity") or "").lower() in ("pii", "confidential"):
        limitations.append(
            f"Handles **{tool['data_sensitivity']}** data. Follow your team's "
            "data-handling policy."
        )
    if not limitations:
        limitations.append("No known limitations at this time.")

    today = date.today().isoformat()

    return f"""# {name} — Usage Guide

_Generated automatically on {today}_

## What this tool does

{tagline}

{description}

## How to access it

- **Open in browser:** {shareable or '(pending)'}
- **Direct API endpoint:** `{endpoint or '(pending)'}`
- **Find it in the catalog:** browse Forge and search for "{name}"

## How to use it

{chr(10).join(field_lines)}

## Understanding the output

{tier_copy}

- Output type: `{output_type}`
- Output format: `{output_format}`

## When to use this

Reach for **{name}** when you need: {tagline.lower() if tagline else 'a quick AI-assisted task'}.

## Limitations

{chr(10).join(f"- {item}" for item in limitations)}

## Questions?

Ping **{author}** or ask in `#forge-help` on Slack.
"""


def _render_with_claude(tool: Dict[str, Any]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except Exception as exc:
        raise RuntimeError(f"anthropic SDK unavailable: {exc}")

    schema = _parse_input_schema(tool.get("input_schema"))
    trust_tier = (tool.get("trust_tier") or "unverified").lower()
    context = {
        "name": tool.get("name"),
        "tagline": tool.get("tagline"),
        "description": tool.get("description"),
        "category": tool.get("category"),
        "trust_tier": trust_tier,
        "trust_tier_copy": TRUST_TIER_COPY.get(trust_tier, ""),
        "output_type": tool.get("output_type"),
        "output_format": tool.get("output_format"),
        "safety_score": tool.get("safety_score"),
        "reliability_score": tool.get("reliability_score"),
        "data_sensitivity": tool.get("data_sensitivity"),
        "author_name": tool.get("author_name"),
        "shareable_url": tool.get("shareable_url"),
        "endpoint_url": tool.get("endpoint_url"),
        "input_fields": schema,
    }

    prompt = (
        "You are writing a concise user-facing usage guide in Markdown "
        "for an internal AI tool. Use these exact section headings in "
        "order: \n"
        "# <Tool Name> — Usage Guide\n"
        "## What this tool does\n"
        "## How to access it\n"
        "## How to use it\n"
        "## Understanding the output\n"
        "## When to use this\n"
        "## Limitations\n"
        "## Questions?\n\n"
        "Write for non-engineers on a RevOps team. Be direct. "
        "No preamble, no closing remarks — only the Markdown document.\n\n"
        "Tool context (JSON):\n"
        f"{json.dumps(context, indent=2, default=str)}"
    )

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.environ.get("FORGE_DOC_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    chunks: List[str] = []
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    out = "".join(chunks).strip()
    if not out:
        raise RuntimeError("Claude returned empty instructions")
    return out


def generate_instructions_content(tool: Dict[str, Any]) -> str:
    """
    Build a Markdown usage guide for a tool.
    Tries Claude first, falls back to the deterministic template.
    """
    try:
        return _render_with_claude(tool)
    except Exception as exc:
        log.info("Claude instructions failed, using template: %s", exc)
        return _fallback_template(tool)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Generate tool instructions")
    parser.add_argument("--tool-id", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=str(_REPO_ROOT / "static" / "instructions"),
        help="Directory for the generated Markdown file",
    )
    args = parser.parse_args(argv)

    from api import db
    tool = db.get_tool(args.tool_id)
    if not tool:
        print(f"tool {args.tool_id} not found", file=sys.stderr)
        return 1

    md = generate_instructions_content(tool)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.tool_id}.md"
    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
