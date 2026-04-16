"""Tests for api.executor — tool prompt interpolation, sanitization, and run execution."""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest


executor = pytest.importorskip(
    "api.executor",
    reason="api.executor is owned by T1 and has not been written yet",
)


# ---------------------------------------------------------------------------
# interpolate_prompt
# ---------------------------------------------------------------------------
def test_interpolate_prompt_substitutes_variables():
    prompt = "Hello {{name}}, welcome to {{place}}!"
    result = executor.interpolate_prompt(prompt, {"name": "Ada", "place": "Forge"})
    assert "Ada" in result
    assert "Forge" in result
    assert "{{name}}" not in result
    assert "{{place}}" not in result


def test_interpolate_prompt_missing_variable_raises():
    prompt = "Hello {{name}} from {{company}}"
    with pytest.raises(ValueError):
        executor.interpolate_prompt(prompt, {"name": "Ada"})


def test_interpolate_prompt_handles_whitespace():
    prompt = "Value: {{ slot }}"
    assert executor.interpolate_prompt(prompt, {"slot": "x"}) == "Value: x"


# ---------------------------------------------------------------------------
# sanitize_inputs
# ---------------------------------------------------------------------------
def test_sanitize_inputs_valid_passes():
    tool = {
        "id": 1, "name": "demo",
        "input_schema": json.dumps([
            {"name": "query", "type": "text", "required": True},
        ]),
    }
    cleaned = executor.sanitize_inputs(tool, {"query": "hello"})
    assert cleaned["query"] == "hello"


def test_sanitize_inputs_missing_required_raises():
    tool = {
        "id": 1, "name": "demo",
        "input_schema": json.dumps([
            {"name": "query", "type": "text", "required": True},
        ]),
    }
    with pytest.raises(ValueError):
        executor.sanitize_inputs(tool, {})


def test_sanitize_inputs_strips_html():
    tool = {
        "id": 1, "name": "demo",
        "input_schema": json.dumps([
            {"name": "body", "type": "textarea", "required": True},
        ]),
    }
    cleaned = executor.sanitize_inputs(tool, {"body": "hello <script>alert(1)</script>"})
    assert "<script>" not in cleaned["body"]
    assert "hello" in cleaned["body"]


def test_sanitize_inputs_logs_pii(caplog):
    """PII patterns detected in inputs should be logged via the 'forge.dlp' logger."""
    tool = {
        "id": 42, "name": "pii-test",
        "input_schema": json.dumps([
            {"name": "body", "type": "textarea", "required": True},
        ]),
    }
    with caplog.at_level(logging.WARNING, logger="forge.dlp"):
        executor.sanitize_inputs(
            tool, {"body": "Reach me at foo@bar.com or 555-123-4567"},
        )
    # At least one warning should be emitted. Exact count depends on regex behavior.
    records = [r for r in caplog.records if r.name == "forge.dlp"]
    assert records, "expected a PII warning on the forge.dlp logger"


def test_sanitize_inputs_number_validation():
    tool = {
        "id": 1, "name": "demo",
        "input_schema": json.dumps([
            {"name": "n", "type": "number", "required": True},
        ]),
    }
    with pytest.raises(ValueError):
        executor.sanitize_inputs(tool, {"n": "not-a-number"})


# ---------------------------------------------------------------------------
# call_claude
# ---------------------------------------------------------------------------
def test_call_claude_uses_mocked_client():
    """Mock the anthropic client so no network call happens."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "hello world"
    mock_response.content = [mock_block]
    mock_response.usage = MagicMock(input_tokens=3, output_tokens=7)
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        result = executor.call_claude(
            system_prompt="sys",
            user_msg="hi",
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            temp=0.2,
        )

    assert isinstance(result, dict)
    assert "hello world" in result.get("text", "")
    assert result.get("input_tokens") == 3
    assert result.get("output_tokens") == 7
    assert mock_client.messages.create.called
    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs.get("model") == "claude-haiku-4-5-20251001"
    assert kwargs.get("max_tokens") == 50
    assert kwargs.get("temperature") == 0.2


# ---------------------------------------------------------------------------
# run_tool
# ---------------------------------------------------------------------------
def test_run_tool_logs_run_and_increments_count(db, sample_tool):
    """run_tool should log a run row and bump tools.run_count."""
    mock_result = {
        "text": "mocked output",
        "input_tokens": 10,
        "output_tokens": 20,
        "cost_usd": 0.0001,
    }
    with patch("api.executor.call_claude", return_value=mock_result) as mock_call:
        result = executor.run_tool(
            tool_id=sample_tool["id"],
            inputs={"query": "hello"},
            user_name="Tester",
            user_email="tester@navan.com",
        )
    assert mock_call.called
    assert result is not None
    assert "run_id" in result
    assert "output" in result
    assert "mocked output" in result["output"]

    with db.cursor() as cur:
        cur.execute("SELECT run_count FROM tools WHERE id = %s", (sample_tool["id"],))
        row = cur.fetchone()
        count = row[0] if isinstance(row, tuple) else row["run_count"]
        assert count >= 1

        cur.execute("SELECT COUNT(*) FROM runs WHERE tool_id = %s", (sample_tool["id"],))
        row = cur.fetchone()
        run_count = row[0] if isinstance(row, tuple) else list(row.values())[0]
        assert run_count >= 1


def test_run_tool_missing_tool_raises():
    with pytest.raises(ValueError):
        executor.run_tool(tool_id=99999999, inputs={"query": "x"})
