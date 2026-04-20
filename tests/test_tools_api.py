"""Tests for the /api/tools endpoints.

The prompt-era submit / injection / search-by-prompt tests were removed in
migration 008 (the prompt stack was demolished). What remains exercises the
app-only surface: list, get-by-id, and fork.
"""
import uuid


def test_list_tools_returns_approved(client, sample_tool, sample_pending_tool):
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    items = payload.get("tools", payload if isinstance(payload, list) else [])
    slugs = [t["slug"] for t in items]
    assert sample_tool["slug"] in slugs
    assert sample_pending_tool["slug"] not in slugs


def test_list_tools_category_filter(client, db):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO tools
               (slug, name, tagline, description, category, app_type,
                app_html, status, author_name, author_email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                f"email-{uuid.uuid4().hex[:6]}", "Email Writer",
                "Write emails", "Email writer tool", "email_generation",
                "app", "<html></html>",
                "approved", "A", "a@navan.com",
            ),
        )

    resp = client.get("/api/tools?category=email_generation")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    items = payload.get("tools", [])
    assert len(items) >= 1
    for tool in items:
        assert tool["category"] == "email_generation"


def test_list_tools_search(client, db):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO tools
               (slug, name, tagline, description, category, app_type,
                app_html, status, author_name, author_email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                f"research-{uuid.uuid4().hex[:6]}", "Account Research Brief",
                "Company research", "Generate a research brief",
                "account_research", "app", "<html></html>",
                "approved", "A", "a@navan.com",
            ),
        )

    resp = client.get("/api/tools?q=research")
    assert resp.status_code == 200
    items = (resp.get_json() or {}).get("tools", [])
    assert len(items) >= 1


def test_list_tools_pagination(client, db):
    for idx in range(5):
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO tools
                   (slug, name, tagline, description, category, app_type,
                    app_html, status, author_name, author_email)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    f"pag-{idx}-{uuid.uuid4().hex[:4]}", f"Tool {idx}",
                    "pagination tool", "desc", "other", "app",
                    "<html></html>",
                    "approved", "A", "a@navan.com",
                ),
            )

    resp = client.get("/api/tools?limit=2")
    assert resp.status_code == 200
    items = (resp.get_json() or {}).get("tools", [])
    assert len(items) <= 2


def test_get_tool_by_id_returns_approved(client, sample_tool):
    resp = client.get(f"/api/tools/{sample_tool['id']}")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert payload.get("id") == sample_tool["id"] \
        or payload.get("tool", {}).get("id") == sample_tool["id"]


def test_get_tool_by_id_missing_returns_404(client):
    resp = client.get("/api/tools/99999999")
    assert resp.status_code == 404


def test_fork_sets_fork_of(client, db, sample_tool):
    resp = client.post(
        f"/api/tools/{sample_tool['id']}/fork",
        json={"author_name": "Forker", "author_email": "forker@navan.com"},
    )
    assert resp.status_code in (200, 201), resp.get_data(as_text=True)
    payload = resp.get_json() or {}
    new_id = payload.get("id") or payload.get("tool", {}).get("id")
    assert new_id is not None

    with db.cursor() as cur:
        cur.execute("SELECT fork_of FROM tools WHERE id = %s", (new_id,))
        row = cur.fetchone()
        fork_of = row[0] if isinstance(row, tuple) else row["fork_of"]
        assert fork_of == sample_tool["id"]
