"""Integration test for POST /api/agent/scan."""
import json
import uuid


def test_scan_endpoint_requires_user_id(client):
    r = client.post("/api/agent/scan", json={"apps": [], "brew": [], "brew_casks": []})
    assert r.status_code == 400
    assert "user_id" in r.get_json().get("error", "").lower()


def test_scan_endpoint_returns_counts(client, db, sample_tool):
    # Seed the catalog tool with a bundle id we can match against.
    with db.cursor() as cur:
        cur.execute(
            "UPDATE tools SET app_bundle_id = %s WHERE id = %s",
            ("com.test.bundle", sample_tool["id"]),
        )
    uid = f"user-{uuid.uuid4().hex[:8]}"
    payload = {
        "apps": [
            {"bundle_id": "com.test.bundle", "name": "Test", "path": "/x"},
            {"bundle_id": "com.unknown.zzz", "name": "Zzz", "path": "/y"},
        ],
        "brew": [],
        "brew_casks": [],
    }
    r = client.post("/api/agent/scan", json=payload, headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["matched"] == 1
    assert body["detected"] == 1


def test_scan_endpoint_round_trip_then_uninstall(client, db, sample_tool):
    """Two scans: first installs, second drops the app — row goes installed=False."""
    with db.cursor() as cur:
        cur.execute("UPDATE tools SET app_bundle_id = %s WHERE id = %s",
                    ("com.test.bundle", sample_tool["id"]))
    uid = f"user-{uuid.uuid4().hex[:8]}"

    p1 = {"apps": [{"bundle_id": "com.test.bundle", "name": "Test", "path": "/x"}],
          "brew": [], "brew_casks": []}
    r1 = client.post("/api/agent/scan", json=p1, headers={"X-Forge-User-Id": uid})
    assert r1.status_code == 200

    p2 = {"apps": [], "brew": [], "brew_casks": []}
    r2 = client.post("/api/agent/scan", json=p2, headers={"X-Forge-User-Id": uid})
    assert r2.status_code == 200
    assert r2.get_json()["unmarked"] >= 1

    with db.cursor() as cur:
        cur.execute("SELECT installed_locally FROM user_items WHERE user_id=%s AND tool_id=%s",
                    (uid, sample_tool["id"]))
        assert cur.fetchone()[0] is False


def test_hide_endpoint_marks_row_hidden(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source)
               VALUES (%s, %s, TRUE, 'detected') RETURNING id""",
            (uid, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["hidden"] is True

    with db.cursor() as cur:
        cur.execute("SELECT hidden FROM user_items WHERE id = %s", (ui_id,))
        assert cur.fetchone()[0] is True


def test_hide_endpoint_is_idempotent(client, db, sample_tool):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source, hidden)
               VALUES (%s, %s, TRUE, 'detected', TRUE) RETURNING id""",
            (uid, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["hidden"] is True


def test_hide_endpoint_rejects_other_users(client, db, sample_tool):
    owner = f"user-{uuid.uuid4().hex[:8]}"
    intruder = f"user-{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO user_items (user_id, tool_id, installed_locally, source)
               VALUES (%s, %s, TRUE, 'detected') RETURNING id""",
            (owner, sample_tool["id"]),
        )
        ui_id = cur.fetchone()[0]

    r = client.post(f"/api/me/items/{ui_id}/hide", headers={"X-Forge-User-Id": intruder})
    assert r.status_code == 404, "Other users must not be able to hide rows on someone else's shelf"
