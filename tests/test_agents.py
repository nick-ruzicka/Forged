"""Tests for the agents package."""
import os
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder")


def test_timed_decorator_logs_success(db):
    """@timed logs a success row to reviews_timing."""
    from api import db as forge_db

    # Create a skill and review to reference
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Timing Test", "prompt", "pending"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]
    review_id = forge_db.create_review(skill_id, "skill")

    from agents.base import timed

    @timed("test_agent")
    def fake_agent(skill_id, review_id):
        return {"result": "ok"}

    result = fake_agent(skill_id, review_id)
    assert result == {"result": "ok"}

    # Check timing row was written
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM reviews_timing WHERE review_id = %s AND agent_name = %s",
            (review_id, "test_agent"),
        )
        row = cur.fetchone()
        if isinstance(row, tuple):
            pytest.skip("dict cursor not available")
        assert row is not None
        assert row["outcome"] == "success"
        assert row["duration_ms"] >= 0


def test_timed_decorator_logs_error(db):
    """@timed logs an error row when the agent raises."""
    from api import db as forge_db

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Error Test", "prompt", "pending"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]
    review_id = forge_db.create_review(skill_id, "skill")

    from agents.base import timed

    @timed("error_agent")
    def failing_agent(skill_id, review_id):
        raise RuntimeError("something broke")

    result = failing_agent(skill_id, review_id)
    assert "error" in result

    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM reviews_timing WHERE review_id = %s AND agent_name = %s",
            (review_id, "error_agent"),
        )
        row = cur.fetchone()
        if isinstance(row, tuple):
            pytest.skip("dict cursor not available")
        assert row["outcome"] == "error"
        assert "something broke" in row["error_detail"]
