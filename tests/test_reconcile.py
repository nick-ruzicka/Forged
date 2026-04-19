"""Unit tests for backend reconciliation helpers."""
import json
import uuid

import pytest


@pytest.fixture
def seeded_user(db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    return uid


@pytest.fixture
def insert_tool(db):
    def _insert(slug, **kw):
        cols = {
            "slug": slug,
            "name": kw.pop("name", slug),
            "tagline": "test",
            "description": "test",
            "category": "other",
            "status": "approved",
            "delivery": kw.pop("delivery", "external"),
            "app_bundle_id": kw.pop("app_bundle_id", None),
            "install_meta": kw.pop("install_meta", None),
        }
        cols.update(kw)
        with db.cursor() as cur:
            keys = ", ".join(cols.keys())
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO tools ({keys}) VALUES ({placeholders}) RETURNING id",
                list(cols.values()),
            )
            return cur.fetchone()[0]
    return _insert


def test_reconcile_matches_by_bundle_id(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    payload = {
        "apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/Applications/Pluely.app"}],
        "brew": [],
        "brew_casks": [],
    }

    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched

    with db.cursor() as cur:
        cur.execute(
            "SELECT installed_locally, source FROM user_items WHERE user_id = %s AND tool_id = %s",
            (seeded_user, tool_id),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] is True or row[0] == True  # installed_locally
    assert row[1] == "detected"  # source


def test_reconcile_matches_by_brew_formula(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("nodejs",
                          install_meta=json.dumps({"type": "brew", "formula": "node"}))
    payload = {"apps": [], "brew": ["node"], "brew_casks": []}
    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched


def test_reconcile_matches_by_brew_cask(db, seeded_user, insert_tool):
    from api import server

    tool_id = insert_tool("raycast",
                          install_meta=json.dumps({"type": "brew", "cask": "raycast"}))
    payload = {"apps": [], "brew": [], "brew_casks": ["raycast"]}
    matched = server._reconcile_matches(seeded_user, payload, db.cursor())
    assert tool_id in matched


def test_reconcile_matches_does_not_overwrite_manual(db, seeded_user, insert_tool):
    """Manual-source rows that are already installed_locally=TRUE keep source='manual'."""
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, installed_at, source)
            VALUES (%s, %s, TRUE, NOW(), 'manual')
            """,
            (seeded_user, tool_id),
        )
    payload = {"apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/x"}],
               "brew": [], "brew_casks": []}
    server._reconcile_matches(seeded_user, payload, db.cursor())
    with db.cursor() as cur:
        cur.execute("SELECT source FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (seeded_user, tool_id))
        assert cur.fetchone()[0] == "manual"


def test_reconcile_matches_upgrades_manual_uninstalled_to_installed(db, seeded_user, insert_tool):
    """A manual row with installed_locally=FALSE flips to TRUE on detection but source stays manual."""
    from api import server

    tool_id = insert_tool("pluely", app_bundle_id="com.pluely.Pluely")
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, installed_locally, source)
            VALUES (%s, %s, FALSE, 'manual')
            """,
            (seeded_user, tool_id),
        )
    payload = {"apps": [{"bundle_id": "com.pluely.Pluely", "name": "Pluely", "path": "/x"}],
               "brew": [], "brew_casks": []}
    server._reconcile_matches(seeded_user, payload, db.cursor())
    with db.cursor() as cur:
        cur.execute("SELECT installed_locally, source FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (seeded_user, tool_id))
        row = cur.fetchone()
        assert row[0] is True
        assert row[1] == "manual"
