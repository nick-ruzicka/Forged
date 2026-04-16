"""
Forge Workflow Composability v1 — Blueprint owned by T4_NEW.

Lets users chain approved tools together. Step N's output can be referenced by
step N+1's inputs via the token ``{{stepN.output}}`` (1-indexed).

Registered in server.py:

    from api.workflow import workflow_bp
    app.register_blueprint(workflow_bp)

Endpoints:
    POST /api/workflows/run  — execute a sequence of tool steps
    GET  /api/workflows/tools — list approved tools suitable for chaining
    GET  /api/workflows/suggest?tool_slug=SLUG — pairing suggestions for a first step
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from api import db, executor

log = logging.getLogger("forge.workflow")

workflow_bp = Blueprint("workflow", __name__, url_prefix="/api/workflows")


_STEP_REF_RE = re.compile(r"\{\{\s*step(\d+)\.output\s*\}\}")


def substitute_step_refs(value: Any, step_outputs: List[str]) -> Any:
    """Replace ``{{stepN.output}}`` tokens with prior step outputs.

    Step numbers are 1-indexed. References to steps that haven't run yet or
    that don't exist are replaced with an empty string.
    """
    if isinstance(value, dict):
        return {k: substitute_step_refs(v, step_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_step_refs(v, step_outputs) for v in value]
    if not isinstance(value, str):
        return value

    def _replace(match: "re.Match[str]") -> str:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(step_outputs):
            return step_outputs[idx] or ""
        return ""

    return _STEP_REF_RE.sub(_replace, value)


def _normalize_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("workflow_steps must be a non-empty array")
    steps: List[Dict[str, Any]] = []
    for i, item in enumerate(raw_steps, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Step {i} must be an object")
        tool_id = item.get("tool_id")
        try:
            tool_id_int = int(tool_id)
        except (TypeError, ValueError):
            raise ValueError(f"Step {i} tool_id must be an integer")
        inputs = item.get("inputs") or item.get("input_data") or {}
        if not isinstance(inputs, dict):
            raise ValueError(f"Step {i} inputs must be an object")
        steps.append({
            "step_order": item.get("step_order") or i,
            "tool_id": tool_id_int,
            "inputs": inputs,
        })
    return steps


@workflow_bp.route("/run", methods=["POST"])
def run_workflow():
    body = request.get_json(silent=True) or {}
    user_name = body.get("user_name") or ""
    user_email = body.get("user_email") or ""

    raw_steps = body.get("workflow_steps") or body.get("steps") or []
    try:
        steps = _normalize_steps(raw_steps)
    except ValueError as exc:
        return jsonify({"error": "validation", "message": str(exc)}), 400

    results: List[Dict[str, Any]] = []
    step_outputs: List[str] = []

    for i, step in enumerate(steps, start=1):
        resolved_inputs = substitute_step_refs(step["inputs"], step_outputs)
        try:
            result = executor.run_tool(
                tool_id=step["tool_id"],
                inputs=resolved_inputs,
                user_name=user_name,
                user_email=user_email,
                source="workflow",
            )
        except ValueError as exc:
            return jsonify({
                "error": "validation",
                "message": f"Step {i}: {exc}",
                "step": i,
                "results": results,
            }), 400
        except Exception as exc:
            log.exception("workflow step %s failed", i)
            return jsonify({
                "error": "execution_error",
                "message": f"Step {i}: {exc}",
                "step": i,
                "results": results,
            }), 500

        output_text = result.get("output") or ""
        step_outputs.append(output_text)
        results.append({
            "step": i,
            "tool_id": step["tool_id"],
            "run_id": result.get("run_id"),
            "inputs": resolved_inputs,
            "output": output_text,
            "duration_ms": result.get("duration_ms"),
            "cost_usd": result.get("cost_usd"),
            "tokens_used": result.get("tokens_used"),
            "model": result.get("model"),
            "error": result.get("error"),
        })

    return jsonify({
        "ok": True,
        "step_count": len(results),
        "results": results,
    })


@workflow_bp.route("/tools", methods=["GET"])
def list_chainable_tools():
    """Minimal tool list for the workflow builder dropdowns."""
    try:
        rows, _ = db.list_tools(status="approved", page=1, limit=100, sort="alphabetical")
    except Exception as exc:
        log.warning("list_tools failed: %s", exc)
        rows = []

    tools: List[Dict[str, Any]] = []
    for r in rows or []:
        tools.append({
            "id": r.get("id"),
            "slug": r.get("slug"),
            "name": r.get("name"),
            "tagline": r.get("tagline"),
            "category": r.get("category"),
            "trust_tier": r.get("trust_tier"),
            "input_schema": r.get("input_schema"),
            "output_format": r.get("output_format"),
        })
    return jsonify({"tools": tools, "count": len(tools)})


# Hardcoded pairing suggestions. Keyed by first-step slug -> list of second-step
# slugs with human-readable reason. Keep this in sync with seed tools.
# TODO(forge-data-driven): once `workflow_steps` has >50 rows, replace this with
# a query that ranks second-step tools by actual co-occurrence in executed
# workflows. Strip the hardcoded map then.
_WORKFLOW_PAIRING_HINTS: Dict[str, List[Dict[str, str]]] = {
    "account-research-brief": [
        {"slug": "prospect-email-draft",
         "reason": "Turn the research into a cold outreach email for the account."},
        {"slug": "call-prep-summary",
         "reason": "Compress the briefing into a pre-call one-pager."},
        {"slug": "icp-qualification-check",
         "reason": "Score the researched account against your ICP to decide pursue/pass."},
    ],
    "icp-qualification-check": [
        {"slug": "account-research-brief",
         "reason": "For qualified fits, dig deeper before outreach."},
        {"slug": "prospect-email-draft",
         "reason": "Draft the first-touch email only for ICP-fit accounts."},
    ],
    "prospect-email-draft": [
        {"slug": "call-prep-summary",
         "reason": "If the prospect replies, prep the call the email landed."},
        {"slug": "churn-risk-check",
         "reason": "For expansion plays, sanity-check retention signals first."},
    ],
    "call-prep-summary": [
        {"slug": "churn-risk-check",
         "reason": "Before an expansion call, check if the account is at risk."},
        {"slug": "prospect-email-draft",
         "reason": "After the call, send a personalized follow-up."},
    ],
    "churn-risk-check": [
        {"slug": "call-prep-summary",
         "reason": "If at-risk, prep the save-call immediately."},
        {"slug": "account-research-brief",
         "reason": "Refresh account context before the save conversation."},
    ],
}


@workflow_bp.route("/suggest", methods=["GET"])
def suggest_pairings():
    """Return a ranked list of second-step tool suggestions for a given first-step tool.

    v1: hardcoded pairings keyed by slug (see ``_WORKFLOW_PAIRING_HINTS``).
    v2 (future, gated on >50 real workflow runs): rank by co-occurrence.
    """
    tool_slug = (request.args.get("tool_slug") or "").strip()
    if not tool_slug:
        return jsonify({"error": "tool_slug_required"}), 400

    hints = _WORKFLOW_PAIRING_HINTS.get(tool_slug, [])
    if not hints:
        return jsonify({"tool_slug": tool_slug, "suggestions": [], "source": "hardcoded"})

    # Resolve each hint to a usable dropdown-ready row.
    suggestions: List[Dict[str, Any]] = []
    try:
        rows, _ = db.list_tools(status="approved", page=1, limit=200, sort="alphabetical")
    except Exception as exc:
        log.warning("suggest: list_tools failed: %s", exc)
        rows = []
    by_slug = {r.get("slug"): r for r in (rows or []) if r.get("slug")}

    for idx, hint in enumerate(hints):
        row = by_slug.get(hint["slug"])
        if not row:
            continue  # tool not approved / not in catalog
        suggestions.append({
            "slug": hint["slug"],
            "name": row.get("name"),
            "tagline": row.get("tagline"),
            "category": row.get("category"),
            "trust_tier": row.get("trust_tier"),
            "reason": hint["reason"],
            "order": idx + 1,
        })

    return jsonify({
        "tool_slug": tool_slug,
        "suggestions": suggestions,
        "source": "hardcoded",
    })
