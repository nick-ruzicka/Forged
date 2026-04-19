"""Smoke test: agent's /scan handler caches results and POSTs to backend."""
from unittest.mock import MagicMock, patch

import pytest


def test_scan_endpoint_caches_within_ttl(monkeypatch):
    from forge_agent import agent as agent_mod

    # Reset cache
    agent_mod._scan_cache["ts"] = 0.0
    agent_mod._scan_cache["result"] = None

    fake_scan = {"apps": [], "brew": [], "brew_casks": []}
    monkeypatch.setattr(agent_mod, "scanner",
                        type("S", (), {"scan": staticmethod(lambda: fake_scan)}))

    backend_calls = []

    def fake_urlopen(req, timeout=15):
        backend_calls.append(req)
        class R:
            def read(self): return b'{"matched": 0, "detected": 0, "unmarked": 0}'
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return R()

    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", fake_urlopen)

    handler = MagicMock()
    handler.headers = {"X-Forge-User-Id": "user-A"}
    handler._json_args = []
    handler._json = lambda body, status=200: handler._json_args.append((body, status)) or None

    # AgentHandler is at forge_agent/agent.py:286.
    bound = agent_mod.AgentHandler._handle_scan

    bound(handler)
    assert len(backend_calls) == 1
    bound(handler)  # within TTL
    assert len(backend_calls) == 1, "Second call within TTL should hit cache"
    assert handler._json_args[-1][0]["matched"] == 0
