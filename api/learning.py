"""Learning layer: plain-English tool explainer + prompt remix suggestions."""
import json
import os

from flask import Blueprint, jsonify, request

from api import db

learning_bp = Blueprint("learning", __name__, url_prefix="/api/learning")

_client = None


def _anthropic():
    global _client
    if _client is None:
        from anthropic import Anthropic
        _client = Anthropic()
    return _client


EXPLAIN_SYSTEM = (
    "You are a patient teacher explaining how an AI tool works to a "
    "non-technical RevOps professional. Explain clearly, use simple language, "
    "no jargon."
)

REMIX_SYSTEM = (
    "You are a prompt engineer helping a user remix an existing AI tool prompt. "
    "Apply the requested change while preserving the tool's core purpose and "
    "every {{variable}} placeholder from the original. Return STRICT JSON — "
    "no preamble, no markdown fences."
)


def _coerce_schema(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


@learning_bp.route("/explain", methods=["POST"])
def explain():
    body = request.get_json(silent=True) or {}
    tool_id = body.get("tool_id")
    if not tool_id:
        return jsonify({"error": "tool_id_required"}), 400
    try:
        tool_id_int = int(tool_id)
    except (TypeError, ValueError):
        return jsonify({"error": "tool_id_invalid"}), 400

    tool = db.get_tool(tool_id_int)
    if not tool:
        return jsonify({"error": "not_found"}), 404

    schema = _coerce_schema(tool.get("input_schema"))
    prompt = tool.get("hardened_prompt") or tool.get("system_prompt") or ""

    user_msg = (
        "Explain this tool in plain English:\n"
        f"name={tool.get('name')}\n"
        f"tagline={tool.get('tagline')}\n"
        f"prompt={prompt}\n"
        f"inputs={json.dumps(schema)}\n"
        f"output_type={tool.get('output_type')}\n\n"
        "Explain: what it does, how the prompt works, what each input field is "
        "for, what to expect in the output, and one tip for getting better "
        "results. Keep it under 200 words."
    )

    try:
        resp = _anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=EXPLAIN_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        explanation = resp.content[0].text.strip()
    except Exception as exc:
        return jsonify({"error": "llm_failure", "message": str(exc)}), 500

    return jsonify({"tool_id": tool_id_int, "explanation": explanation})


@learning_bp.route("/suggest-remix", methods=["POST"])
def suggest_remix():
    body = request.get_json(silent=True) or {}
    tool_id = body.get("tool_id")
    remix_description = (body.get("remix_description") or "").strip()
    if not tool_id or not remix_description:
        return jsonify({"error": "tool_id_and_remix_description_required"}), 400
    try:
        tool_id_int = int(tool_id)
    except (TypeError, ValueError):
        return jsonify({"error": "tool_id_invalid"}), 400

    tool = db.get_tool(tool_id_int)
    if not tool:
        return jsonify({"error": "not_found"}), 404

    original = tool.get("hardened_prompt") or tool.get("system_prompt") or ""
    user_msg = (
        f"Original prompt:\n\"\"\"\n{original}\n\"\"\"\n\n"
        f"User's remix request: {remix_description}\n\n"
        "Return JSON:\n"
        "{\n"
        "  \"remixed_prompt\": \"<modified prompt; keep every {{variable}}>\",\n"
        "  \"changed_fields\": [\"<bullet of what changed>\"],\n"
        "  \"explanation\": \"<1-2 sentence summary>\"\n"
        "}"
    )

    try:
        resp = _anthropic().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=REMIX_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return jsonify({"error": "invalid_json_from_model", "message": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": "llm_failure", "message": str(exc)}), 500

    if not isinstance(data, dict) or "remixed_prompt" not in data:
        return jsonify({"error": "malformed_model_response", "body": data}), 500

    return jsonify({
        "tool_id": tool_id_int,
        "remixed_prompt": data.get("remixed_prompt"),
        "changed_fields": data.get("changed_fields") or [],
        "explanation": data.get("explanation") or "",
    })
