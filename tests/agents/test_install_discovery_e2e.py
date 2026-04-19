"""End-to-end: synthetic scan payloads round-trip through reconciler and shelf list."""
import json
import uuid


def test_full_round_trip(client, db, sample_tool):
    """A scan that includes our catalog tool by bundle id + an unknown app:
       - Both appear on /me/items
       - A second scan that drops both unmarks them; they vanish from /me/items
    """
    with db.cursor() as cur:
        cur.execute("UPDATE tools SET app_bundle_id = %s WHERE id = %s",
                    ("com.test.bundle", sample_tool["id"]))
    uid = f"user-{uuid.uuid4().hex[:8]}"

    # Scan 1: both present
    p1 = {
        "apps": [
            {"bundle_id": "com.test.bundle", "name": "Test", "path": "/Applications/Test.app"},
            {"bundle_id": "com.unknown.foo", "name": "Foo", "path": "/Applications/Foo.app"},
        ],
        "brew": [], "brew_casks": [],
    }
    r = client.post("/api/agent/scan", json=p1, headers={"X-Forge-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["matched"] == 1
    assert body["detected"] == 1
    assert body["unmarked"] == 0

    shelf = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    matched = [i for i in shelf if i.get("tool_id") == sample_tool["id"]]
    unknown = [i for i in shelf if i.get("detected_bundle_id") == "com.unknown.foo"]
    assert len(matched) == 1 and matched[0]["installed_locally"] is True
    assert len(unknown) == 1 and unknown[0]["name"] == "Foo"

    # Scan 2: both removed
    p2 = {"apps": [], "brew": [], "brew_casks": []}
    r2 = client.post("/api/agent/scan", json=p2, headers={"X-Forge-User-Id": uid})
    body2 = r2.get_json()
    assert body2["unmarked"] >= 2

    shelf2 = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    # Matched tool persists (still on shelf, but installed_locally=False)
    assert any(i.get("tool_id") == sample_tool["id"] and i["installed_locally"] is False for i in shelf2)
    # Unknown app: rendered tiles filter installed_locally=False, so it disappears
    assert all(i.get("detected_bundle_id") != "com.unknown.foo" for i in shelf2)


def test_hide_then_rescan_unknown_does_not_reappear(client, db):
    uid = f"user-{uuid.uuid4().hex[:8]}"
    p = {"apps": [{"bundle_id": "com.x.y", "name": "X", "path": "/x"}],
         "brew": [], "brew_casks": []}
    client.post("/api/agent/scan", json=p, headers={"X-Forge-User-Id": uid})

    shelf = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    target = next(i for i in shelf if i.get("detected_bundle_id") == "com.x.y")

    client.post(f"/api/me/items/{target['id']}/hide", headers={"X-Forge-User-Id": uid})

    # Re-scan: hidden flag must persist
    client.post("/api/agent/scan", json=p, headers={"X-Forge-User-Id": uid})
    shelf2 = client.get(f"/api/me/items?user_id={uid}").get_json()["items"]
    assert all(i.get("detected_bundle_id") != "com.x.y" for i in shelf2)
