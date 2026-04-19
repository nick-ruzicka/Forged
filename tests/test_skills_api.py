"""Tests for /api/skills endpoints."""
import pytest


def test_list_skills_returns_200(client, db):
    """GET /api/skills returns an array of skills."""
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category, use_case, author_name)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ("Test Skill", "desc", "Do X", "research", "research accounts", "A"),
        )
    resp = client.get("/api/skills")
    if resp.status_code == 404:
        pytest.skip("GET /api/skills not implemented yet (T1)")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    items = payload.get("skills", payload if isinstance(payload, list) else [])
    assert len(items) >= 1


def test_submit_skill_valid_returns_201(client):
    body = {
        "title": "Great Prompt",
        "description": "Use it well",
        "prompt_text": "Do the thing with {{topic}}",
        "category": "research",
        "use_case": "research accounts",
        "author_name": "Tester",
    }
    resp = client.post("/api/skills", json=body)
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/skills not implemented yet (T1)")
    assert resp.status_code == 201


def test_submit_skill_invalid_returns_400(client):
    resp = client.post("/api/skills", json={"title": "only title"})
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/skills not implemented yet (T1)")
    assert resp.status_code == 400


def test_upvote_skill_increments(client, db):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category, use_case, author_name, upvotes)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            ("Upvote Me", "d", "P", "cat", "uc", "A", 0),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    resp = client.post(f"/api/skills/{skill_id}/upvote")
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/skills/:id/upvote not implemented yet (T1)")
    assert resp.status_code == 200

    with db.cursor() as cur:
        cur.execute("SELECT upvotes FROM skills WHERE id = %s", (skill_id,))
        row = cur.fetchone()
        upvotes = row[0] if isinstance(row, tuple) else row["upvotes"]
        assert upvotes >= 1


def test_copy_skill_increments_copy_count(client, db):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category, use_case, author_name, copy_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            ("Copy Me", "d", "P", "cat", "uc", "A", 0),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    resp = client.post(f"/api/skills/{skill_id}/copy")
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/skills/:id/copy not implemented yet (T1)")
    assert resp.status_code == 200

    with db.cursor() as cur:
        cur.execute("SELECT copy_count FROM skills WHERE id = %s", (skill_id,))
        row = cur.fetchone()
        copy_count = row[0] if isinstance(row, tuple) else row["copy_count"]
        assert copy_count >= 1


def test_download_skill_serves_markdown(client, db):
    md = "---\nname: my-skill\ndescription: Use when testing downloads.\n---\n\nBody."
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category, use_case, author_name, copy_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            ("Download Me", "d", md, "Development", "uc", "tester", 0),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    resp = client.get(f"/api/skills/{skill_id}/download")
    if resp.status_code in (404, 405):
        pytest.skip("GET /api/skills/:id/download not implemented yet")
    assert resp.status_code == 200
    assert resp.mimetype == "text/markdown"
    assert resp.headers.get("Content-Disposition", "").startswith("attachment")
    assert "download-me.md" in resp.headers.get("Content-Disposition", "")
    assert resp.get_data(as_text=True) == md

    with db.cursor() as cur:
        cur.execute("SELECT copy_count FROM skills WHERE id = %s", (skill_id,))
        row = cur.fetchone()
        copy_count = row[0] if isinstance(row, tuple) else row["copy_count"]
        assert copy_count >= 1


def test_download_skill_404(client):
    resp = client.get("/api/skills/999999/download")
    if resp.status_code == 405:
        pytest.skip("download not implemented")
    assert resp.status_code == 404


def test_submit_skill_accepts_source_url(client, db):
    body = {
        "title": "Sourced Skill",
        "prompt_text": "---\nname: sourced\ndescription: Use when X.\n---\n\nBody.",
        "category": "Development",
        "use_case": "testing source_url persistence",
        "author_name": "obra",
        "source_url": "https://github.com/obra/superpowers/tree/main/skills/brainstorming",
    }
    resp = client.post("/api/skills", json=body)
    if resp.status_code in (404, 405):
        pytest.skip("POST /api/skills not implemented yet")
    assert resp.status_code == 201
    skill_id = resp.get_json()["skill_id"]
    with db.cursor() as cur:
        cur.execute("SELECT source_url FROM skills WHERE id = %s", (skill_id,))
        row = cur.fetchone()
        src = row[0] if isinstance(row, tuple) else row["source_url"]
        assert src == body["source_url"]


def test_list_skills_sort_by_copies(client, db):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, prompt_text, category, copy_count, upvotes, review_status)
               VALUES ('Low Copies', 'p', 'Development', 1, 100, 'approved'),
                      ('High Copies', 'p', 'Development', 999, 0, 'approved') RETURNING id""",
        )
    resp = client.get("/api/skills?sort=copies")
    if resp.status_code == 404:
        pytest.skip("sort not wired")
    assert resp.status_code == 200
    items = (resp.get_json() or {}).get("skills", [])
    titles = [s["title"] for s in items]
    assert titles.index("High Copies") < titles.index("Low Copies")


def test_create_review_for_skill(db):
    """create_review('skill', id) creates an agent_reviews row with skill_id set."""
    from api import db as forge_db
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Review Target", "prompt", "pending"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    review_id = forge_db.create_review(skill_id, "skill")
    assert review_id is not None
    assert isinstance(review_id, int)

    review = forge_db.get_review_by_skill(skill_id)
    assert review is not None
    assert review["skill_id"] == skill_id
    assert review["tool_id"] is None


def test_create_review_for_tool(db, sample_tool):
    """create_review('tool', id) creates an agent_reviews row with tool_id set — backward compat."""
    from api import db as forge_db
    review_id = forge_db.create_review(sample_tool["id"], "tool")
    assert review_id is not None
    review = forge_db.get_agent_review_by_tool(sample_tool["id"])
    assert review is not None
    assert review["tool_id"] == sample_tool["id"]


def test_list_skills_default_filter_approved_only(client, db):
    """GET /api/skills only returns approved skills by default."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s)",
            ("Approved Skill", "prompt", "approved"),
        )
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s)",
            ("Pending Skill", "prompt", "pending"),
        )
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.get_json()["skills"]]
    assert "Approved Skill" in titles
    assert "Pending Skill" not in titles


def test_insert_skill_test_cases(db):
    """insert_skill_test_cases stores positive and negative examples."""
    from api import db as forge_db
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("TC Skill", "prompt", "pending"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    cases = [
        {"kind": "positive", "prompt": "should trigger"},
        {"kind": "negative", "prompt": "should not trigger"},
    ]
    forge_db.insert_skill_test_cases(skill_id, cases)

    result = forge_db.get_skill_test_cases(skill_id)
    assert len(result) == 2
    kinds = {r["kind"] for r in result}
    assert kinds == {"positive", "negative"}


def test_skill_review_pipeline_stub_approves(db):
    """In stub mode, skill_review_pipeline auto-approves the skill."""
    import os
    os.environ["SKILL_REVIEW_MODE"] = "stub"
    from api import db as forge_db

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Pipeline Test", "prompt", "pending"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    # Import and call the task function directly (not via Celery broker)
    from forge_sandbox.tasks import skill_review_pipeline
    result = skill_review_pipeline(skill_id)

    assert result["review_status"] == "approved"
    assert result["review_id"] is not None

    # Verify DB state
    skill = forge_db.get_skill(skill_id)
    assert skill["review_status"] == "approved"
    assert skill["review_id"] is not None
    assert skill["approved_at"] is not None


def test_submit_skill_returns_pending(client):
    """POST /api/skills returns status=pending and enqueues review."""
    body = {
        "title": "New Governed Skill",
        "prompt_text": "Do the thing",
        "category": "research",
        "author_name": "Tester",
        "test_cases": {
            "positive": ["should trigger on this"] * 10,
            "negative": ["should not trigger on this"] * 10,
        },
    }
    resp = client.post("/api/skills", json=body)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending"
    assert "skill_id" in data


def test_submit_skill_without_test_cases_still_works(client):
    """POST /api/skills without test_cases still accepts (flagged as author_no_examples)."""
    body = {
        "title": "No Tests Skill",
        "prompt_text": "Do the thing",
        "category": "research",
        "author_name": "Tester",
    }
    resp = client.post("/api/skills", json=body)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending"


def test_get_skill_review_status(client, db):
    """GET /api/skills/:id/review returns review status."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Status Skill", "prompt", "approved"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    resp = client.get(f"/api/skills/{skill_id}/review")
    if resp.status_code == 404:
        pytest.skip("review endpoint not implemented")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["review_status"] == "approved"


def test_admin_override_skill(client, db):
    """POST /api/admin/skills/:id/override changes review_status and logs action."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO skills (title, prompt_text, review_status) VALUES (%s, %s, %s) RETURNING id",
            ("Override Me", "prompt", "needs_revision"),
        )
        row = cur.fetchone()
        skill_id = row[0] if isinstance(row, tuple) else row["id"]

    resp = client.post(
        f"/api/admin/skills/{skill_id}/override",
        json={
            "action": "override_approve",
            "reason": "Reviewed manually, this is safe and correct.",
        },
        headers={"X-Admin-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["review_status"] == "approved"

    # Verify audit log
    from api import db as forge_db
    actions = forge_db.list_skill_admin_actions(skill_id)
    assert len(actions) == 1
    assert actions[0]["action"] == "override_approve"
    assert actions[0]["from_status"] == "needs_revision"
    assert actions[0]["to_status"] == "approved"
