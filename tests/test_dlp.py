"""Tests for api.dlp — Runtime DLP masking engine and executor integration."""
import json
from unittest.mock import patch

import pytest


dlp_mod = pytest.importorskip(
    "api.dlp",
    reason="api.dlp is owned by T3_NEW and not yet written",
)
DLPEngine = dlp_mod.DLPEngine


# ---------------------------------------------------------------------------
# detect_pii
# ---------------------------------------------------------------------------
def test_detect_pii_email():
    engine = DLPEngine()
    matches = engine.detect_pii("Reach me at alice@example.com today")
    assert any(m["type"] == "email" and m["value"] == "alice@example.com" for m in matches)


def test_detect_pii_phone():
    engine = DLPEngine()
    matches = engine.detect_pii("Call 555-123-4567 for details")
    assert any(m["type"] == "phone" and "555" in m["value"] for m in matches)


def test_detect_pii_ssn():
    engine = DLPEngine()
    matches = engine.detect_pii("SSN on file: 123-45-6789")
    assert any(m["type"] == "ssn" and m["value"] == "123-45-6789" for m in matches)


def test_detect_pii_credit_card():
    engine = DLPEngine()
    matches = engine.detect_pii("Card 4111-1111-1111-1111 declined")
    assert any(m["type"] == "credit_card" for m in matches)


def test_detect_pii_none_when_clean():
    engine = DLPEngine()
    assert engine.detect_pii("Just a normal sentence.") == []


def test_detect_pii_multiple_types():
    engine = DLPEngine()
    text = "Email bob@x.com or 555-999-1234; ssn 111-22-3333"
    kinds = {m["type"] for m in engine.detect_pii(text)}
    assert {"email", "phone", "ssn"}.issubset(kinds)


# ---------------------------------------------------------------------------
# mask_text / get_token_map
# ---------------------------------------------------------------------------
def test_mask_text_replaces_email_with_token():
    engine = DLPEngine()
    masked = engine.mask_text("email alice@example.com now")
    assert "alice@example.com" not in masked
    assert "[EMAIL_1]" in masked
    assert engine.get_token_map()["[EMAIL_1]"] == "alice@example.com"


def test_mask_text_replaces_phone_with_token():
    engine = DLPEngine()
    masked = engine.mask_text("ring 555-123-4567")
    assert "555-123-4567" not in masked
    assert "[PHONE_1]" in masked


def test_mask_text_replaces_ssn_with_token():
    engine = DLPEngine()
    masked = engine.mask_text("ssn 123-45-6789 please")
    assert "123-45-6789" not in masked
    assert "[SSN_1]" in masked


def test_mask_text_replaces_credit_card_with_token():
    engine = DLPEngine()
    masked = engine.mask_text("card 4111-1111-1111-1111")
    assert "4111-1111-1111-1111" not in masked
    assert "[CC_1]" in masked


def test_mask_text_reuses_token_for_repeated_value():
    engine = DLPEngine()
    masked = engine.mask_text("a@b.com and a@b.com again")
    # Same raw value should collapse to the same token.
    assert masked.count("[EMAIL_1]") == 2
    assert "[EMAIL_2]" not in masked


def test_mask_text_numbers_distinct_values():
    engine = DLPEngine()
    masked = engine.mask_text("first a@b.com then c@d.com")
    assert "[EMAIL_1]" in masked and "[EMAIL_2]" in masked
    assert engine.token_count() == 2


def test_mask_text_noop_on_clean_input():
    engine = DLPEngine()
    clean = "just a plain line, no PII"
    assert engine.mask_text(clean) == clean
    assert engine.get_token_map() == {}


def test_mask_text_handles_non_string():
    engine = DLPEngine()
    assert engine.mask_text(None) is None
    assert engine.mask_text(42) == 42


# ---------------------------------------------------------------------------
# unmask_text
# ---------------------------------------------------------------------------
def test_unmask_text_restores_original_values():
    engine = DLPEngine()
    original = "email alice@example.com and call 555-123-4567"
    masked = engine.mask_text(original)
    restored = engine.unmask_text(masked, engine.get_token_map())
    assert restored == original


def test_unmask_text_handles_partial_tokens_in_output():
    engine = DLPEngine()
    engine.mask_text("ping bob@example.com")
    claude_output = "Hello [EMAIL_1], how are you?"
    restored = engine.unmask_text(claude_output, engine.get_token_map())
    assert "bob@example.com" in restored


def test_unmask_text_empty_map_returns_input():
    engine = DLPEngine()
    assert engine.unmask_text("just a line", {}) == "just a line"


def test_unmask_text_longest_token_wins():
    """Token [EMAIL_10] should restore before [EMAIL_1] prefix-matches."""
    engine = DLPEngine()
    token_map = {"[EMAIL_1]": "a@b.com", "[EMAIL_10]": "j@k.com"}
    out = engine.unmask_text("users [EMAIL_10] and [EMAIL_1]", token_map)
    assert out == "users j@k.com and a@b.com"


# ---------------------------------------------------------------------------
# mask_inputs
# ---------------------------------------------------------------------------
def test_mask_inputs_masks_strings_leaves_non_strings():
    engine = DLPEngine()
    out = engine.mask_inputs({
        "email": "alice@example.com",
        "age": 30,
        "active": True,
    })
    assert "alice@example.com" not in out["email"]
    assert out["age"] == 30
    assert out["active"] is True


# ---------------------------------------------------------------------------
# executor integration — run_tool masks before Claude, unmasks after
# ---------------------------------------------------------------------------
executor = pytest.importorskip(
    "api.executor",
    reason="api.executor is required for the integration test",
)


def test_run_tool_masks_pii_before_claude(db, sample_tool):
    """The rendered prompt sent to Claude must contain the token, not the raw PII."""
    captured = {}

    def fake_call_claude(system_prompt, user_msg, model, max_tokens, temp):
        captured["system_prompt"] = system_prompt
        return {
            "text": "Thanks [EMAIL_1]!",
            "input_tokens": 5,
            "output_tokens": 3,
            "cost_usd": 0.0001,
        }

    with patch("api.executor.call_claude", side_effect=fake_call_claude):
        result = executor.run_tool(
            tool_id=sample_tool["id"],
            inputs={"query": "Contact me at secret@vault.com please"},
            user_name="Tester",
            user_email="tester@navan.com",
        )

    # The Claude-facing prompt must be masked.
    assert "secret@vault.com" not in captured["system_prompt"]
    assert "[EMAIL_1]" in captured["system_prompt"]

    # The output returned to the caller must have the token restored.
    assert "[EMAIL_1]" not in result["output"]
    assert "secret@vault.com" in result["output"]

    # And the run row should have recorded the token count.
    with db.cursor() as cur:
        cur.execute(
            "SELECT dlp_tokens_found FROM runs WHERE id = %s",
            (result["run_id"],),
        )
        row = cur.fetchone()
        val = row[0] if isinstance(row, tuple) else row["dlp_tokens_found"]
        assert int(val) >= 1


def test_run_tool_records_zero_when_no_pii(db, sample_tool):
    def fake_call_claude(system_prompt, user_msg, model, max_tokens, temp):
        return {
            "text": "ok",
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_usd": 0.0,
        }

    with patch("api.executor.call_claude", side_effect=fake_call_claude):
        result = executor.run_tool(
            tool_id=sample_tool["id"],
            inputs={"query": "plain text with no PII"},
            user_name="Tester",
            user_email="tester@navan.com",
        )

    with db.cursor() as cur:
        cur.execute(
            "SELECT dlp_tokens_found FROM runs WHERE id = %s",
            (result["run_id"],),
        )
        row = cur.fetchone()
        val = row[0] if isinstance(row, tuple) else row["dlp_tokens_found"]
        assert int(val) == 0
