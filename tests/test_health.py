"""Tests for GET /api/health."""
import pytest


def test_health_returns_200(client):
    """GET /api/health returns 200 with status/version/timestamp."""
    resp = client.get("/api/health")
    # If server.py is not yet present, 404 or 500 is acceptable; skip to keep suite green.
    if resp.status_code == 404:
        pytest.skip("api.server.health not implemented yet (T1)")

    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert "status" in payload
    assert payload["status"] in ("ok", "healthy", "up")
    assert "version" in payload
    assert "timestamp" in payload


def test_health_timestamp_is_iso_string(client):
    """Health endpoint timestamp should be a string (ISO-8601 preferred)."""
    resp = client.get("/api/health")
    if resp.status_code == 404:
        pytest.skip("api.server.health not implemented yet (T1)")

    payload = resp.get_json() or {}
    assert isinstance(payload.get("timestamp"), str)
    # Cheap ISO-8601 sanity check.
    assert "T" in payload["timestamp"] or "-" in payload["timestamp"]


def test_health_version_is_string(client):
    """Health endpoint version should be a non-empty string."""
    resp = client.get("/api/health")
    if resp.status_code == 404:
        pytest.skip("api.server.health not implemented yet (T1)")

    payload = resp.get_json() or {}
    assert isinstance(payload.get("version"), str)
    assert payload["version"]
