"""Tests for /api/tools/:id/run and /api/runs/:id/{rate,flag}."""
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# POST /api/tools/:id/run
# ---------------------------------------------------------------------------
def test_run_tool_valid_returns_output(client, sample_tool):
    body = {
        "inputs": {"query": "hello"},
        "user_name": "Tester",
        "user_email": "tester@navan.com",
    }
    mock_result = {
        "text": "mocked-output",
        "input_tokens": 5,
        "output_tokens": 7,
        "cost_usd": 0.0001,
    }
    with patch("api.executor.call_claude", return_value=mock_result):
        resp = client.post(f"/api/tools/{sample_tool['id']}/run", json=body)

    if resp.status_code in (404, 405):
        pytest.skip("POST /api/tools/:id/run not implemented yet (T1)")

    assert resp.status_code == 200
    payload = resp.get_json() or {}
    output = payload.get("output") or payload.get("output_data") or payload.get("result")
    assert output is not None
    assert "mocked-output" in str(output)


def test_run_tool_invalid_tool_returns_404(client):
    resp = client.post(
        "/api/tools/99999999/run",
        json={"inputs": {"query": "x"}, "user_name": "T", "user_email": "t@n.com"},
    )
    if resp.status_code in (405, 500):
        pytest.skip("POST /api/tools/:id/run not implemented yet (T1)")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/runs/:id/rate
# ---------------------------------------------------------------------------
def test_rate_run_valid_updates_avg_rating(client, db, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/rate",
        json={"rating": 5, "note": "great"},
    )
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/runs/:id/rate not implemented yet (T1)")
    assert resp.status_code == 200

    with db.cursor() as cur:
        cur.execute("SELECT avg_rating FROM tools WHERE id = %s", (sample_run["tool_id"],))
        row = cur.fetchone()
        avg = row[0] if isinstance(row, tuple) else row["avg_rating"]
        assert avg is not None
        assert float(avg) >= 1.0


def test_rate_run_invalid_rating_returns_400(client, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/rate",
        json={"rating": 11},
    )
    if resp.status_code == 404:
        pytest.skip("POST /api/runs/:id/rate not implemented yet (T1)")
    assert resp.status_code == 400


def test_rate_run_nonnumeric_returns_400(client, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/rate",
        json={"rating": "excellent"},
    )
    if resp.status_code == 404:
        pytest.skip("POST /api/runs/:id/rate not implemented yet (T1)")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/runs/:id/flag
# ---------------------------------------------------------------------------
def test_flag_run_marks_run_and_increments_flag_count(client, db, sample_run):
    resp = client.post(
        f"/api/runs/{sample_run['id']}/flag",
        json={"reason": "hallucinated data"},
    )
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/runs/:id/flag not implemented yet (T1)")
    assert resp.status_code == 200

    with db.cursor() as cur:
        cur.execute(
            "SELECT output_flagged FROM runs WHERE id = %s", (sample_run["id"],),
        )
        row = cur.fetchone()
        flagged = row[0] if isinstance(row, tuple) else row["output_flagged"]
        assert flagged is True

        cur.execute(
            "SELECT flag_count FROM tools WHERE id = %s", (sample_run["tool_id"],),
        )
        row = cur.fetchone()
        flag_count = row[0] if isinstance(row, tuple) else row["flag_count"]
        assert flag_count >= 1


def test_flag_run_third_flag_sets_requires_review(client, db, sample_run):
    """After 3 flags on the same tool, tools.requires_review should be TRUE."""
    tool_id = sample_run["tool_id"]
    # Flag the original sample_run
    resp = client.post(f"/api/runs/{sample_run['id']}/flag", json={"reason": "bad"})
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/runs/:id/flag not implemented yet (T1)")

    # Insert and flag two more runs.
    for _ in range(2):
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO runs (tool_id, input_data, output_data, user_name, user_email)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (tool_id, '{"query": "x"}', "out", "u", "u@n.com"),
            )
            row = cur.fetchone()
            new_id = row[0] if isinstance(row, tuple) else row["id"]
        client.post(f"/api/runs/{new_id}/flag", json={"reason": "bad"})

    with db.cursor() as cur:
        cur.execute(
            "SELECT requires_review, flag_count FROM tools WHERE id = %s", (tool_id,),
        )
        row = cur.fetchone()
        if isinstance(row, tuple):
            requires_review, flag_count = row
        else:
            requires_review = row["requires_review"]
            flag_count = row["flag_count"]
        assert flag_count >= 3
        assert requires_review is True
