"""
Tests for individual agents in agents/.

All Claude API calls are mocked via unittest.mock.patch so no external network
requests are made. Agents not yet written (imports that fail) are skipped.
"""
import json
from unittest.mock import MagicMock, patch

import pytest


def _mock_anthropic_response(text: str):
    """Create a mock Anthropic response with a single text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(output_tokens=100, input_tokens=50)
    return resp


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------
def test_base_agent_parses_json_from_fenced_output():
    from agents.base import BaseAgent

    agent = BaseAgent(name="tester", model=BaseAgent.HAIKU)
    text = '```json\n{"a": 1, "b": 2}\n```'
    parsed = agent._parse_json(text)
    assert parsed == {"a": 1, "b": 2}


def test_base_agent_parses_plain_json():
    from agents.base import BaseAgent

    agent = BaseAgent(name="tester", model=BaseAgent.HAIKU)
    parsed = agent._parse_json('{"x": "y"}')
    assert parsed == {"x": "y"}


def test_base_agent_handles_invalid_json_gracefully():
    from agents.base import BaseAgent

    agent = BaseAgent(name="tester", model=BaseAgent.HAIKU)
    parsed = agent._parse_json("not actually json at all")
    assert parsed is None


def test_base_agent_call_claude_mocks_cleanly():
    from agents.base import BaseAgent

    agent = BaseAgent(name="tester", model=BaseAgent.HAIKU)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("hello world")
    agent._client = mock_client
    out = agent._call_claude("system", "user")
    assert "hello world" in out
    assert mock_client.messages.create.called


# ---------------------------------------------------------------------------
# Classifier Agent
# ---------------------------------------------------------------------------
def test_classifier_returns_structured_output():
    try:
        from agents.classifier import ClassifierAgent
    except Exception:
        pytest.skip("agents.classifier not implemented yet (T2)")

    agent = ClassifierAgent()
    payload = {
        "output_type": "probabilistic",
        "reliability_score": 70,
        "safety_score": 80,
        "data_sensitivity": "internal",
        "complexity_score": 85,
        "detected_category": "account_research",
        "reasoning": "ok",
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client

    result = agent.run({
        "name": "Research Brief",
        "description": "Account research",
        "system_prompt": "Research {{company}}",
        "input_schema": [{"name": "company", "type": "text", "required": True}],
    })
    assert isinstance(result, dict)
    assert "output_type" in result or "reliability_score" in result


def test_classifier_handles_invalid_json():
    try:
        from agents.classifier import ClassifierAgent
    except Exception:
        pytest.skip("agents.classifier not implemented yet (T2)")

    agent = ClassifierAgent()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response("not json")
    agent._client = mock_client
    result = agent.run({
        "name": "x", "description": "x", "system_prompt": "x",
        "input_schema": [{"name": "x", "type": "text", "required": True}],
    })
    assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Security Scanner
# ---------------------------------------------------------------------------
def test_security_scanner_returns_structured_output():
    try:
        from agents.security_scanner import SecurityScannerAgent
    except Exception:
        pytest.skip("agents.security_scanner not implemented yet (T2)")

    agent = SecurityScannerAgent()
    payload = {
        "security_score": 85,
        "flags": [],
        "pii_risk": False,
        "injection_risk": False,
        "data_exfil_risk": False,
        "recommendation": "approve",
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client
    result = agent.run({
        "name": "x", "description": "x", "system_prompt": "x",
        "input_schema": [{"name": "x", "type": "text", "required": True}],
    })
    assert isinstance(result, dict)
    assert "security_score" in result or "flags" in result


# ---------------------------------------------------------------------------
# Red Team Agent
# ---------------------------------------------------------------------------
def test_red_team_returns_structured_output():
    try:
        from agents.red_team import RedTeamAgent
    except Exception:
        pytest.skip("agents.red_team not implemented yet (T2)")

    agent = RedTeamAgent()
    payload = {
        "attacks_attempted": 10,
        "attacks_succeeded": 1,
        "vulnerabilities": [],
        "hardening_suggestions": [],
        "overall_resilience": 0.9,
        "recommendation": "approve",
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client
    result = agent.run({
        "name": "x", "description": "x", "system_prompt": "x",
        "input_schema": [{"name": "x", "type": "text", "required": True}],
    })
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Prompt Hardener
# ---------------------------------------------------------------------------
def test_prompt_hardener_returns_hardened_prompt():
    try:
        from agents.prompt_hardener import PromptHardenerAgent
    except Exception:
        pytest.skip("agents.prompt_hardener not implemented yet (T2)")

    agent = PromptHardenerAgent()
    payload = {
        "hardened_prompt": "Hardened text",
        "changes": [],
        "hardening_summary": "Added 3 guards",
        "red_team_patches_applied": 1,
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client
    result = agent.run({
        "name": "x", "description": "x", "system_prompt": "x",
        "input_schema": [{"name": "x", "type": "text", "required": True}],
    })
    assert isinstance(result, dict)
    assert "hardened_prompt" in result or "hardening_summary" in result


# ---------------------------------------------------------------------------
# QA Tester
# ---------------------------------------------------------------------------
def test_qa_tester_returns_test_cases():
    try:
        from agents.qa_tester import QATesterAgent
    except Exception:
        pytest.skip("agents.qa_tester not implemented yet (T2)")

    agent = QATesterAgent()
    payload = {
        "test_cases": [{"inputs": {}, "output": "x", "evaluation": {"score": 4.0}}],
        "qa_pass_rate": 0.9,
        "issues": [],
        "recommendation": "approve",
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client
    result = agent.run({
        "name": "x", "description": "x", "system_prompt": "x",
        "hardened_prompt": "x",
        "input_schema": [{"name": "x", "type": "text", "required": True}],
    })
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Review Synthesizer
# ---------------------------------------------------------------------------
def test_synthesizer_returns_summary():
    try:
        from agents.synthesizer import SynthesizerAgent
    except Exception:
        pytest.skip("agents.synthesizer not implemented yet (T2)")

    agent = SynthesizerAgent()
    payload = {
        "overall_recommendation": "approve",
        "confidence": 0.9,
        "trust_tier": "verified",
        "governance_scores": {
            "reliability": 80, "safety": 85, "data_sensitivity": "internal",
            "complexity": 75, "verified": 50,
        },
        "summary": "looks good",
        "required_changes": [],
        "optional_improvements": [],
        "reviewer_checklist": [],
    }
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(json.dumps(payload))
    agent._client = mock_client

    agent_outputs = {
        "classifier": {"output_type": "probabilistic"},
        "security": {"security_score": 90},
        "red_team": {"attacks_attempted": 10, "attacks_succeeded": 0},
        "hardener": {"hardened_prompt": "x"},
        "qa": {"qa_pass_rate": 0.95},
    }
    result = agent.run(agent_outputs)
    assert isinstance(result, dict)
