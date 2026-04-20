# Discovery — Plan 1 of 3: Backend Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the daily ingestion pipeline that populates `discovery_repos`, `discovery_repo_stars`, and `discovery_lanes` with AI-related open-source repos from EXA + GitHub. Ships as a CLI (`scripts/discovery_ingest.py`) ready to wire to cron. No user-facing UI in this plan.

**Architecture:** Single `api/discovery/` package with focused modules: `clients.py` (GitHub + EXA HTTP), `enrich.py` (Haiku classification), `cluster.py` (Sonnet lane generation), `pipeline.py` (5-stage orchestrator), `scrape.py` (BeautifulSoup failover), `topics.py` (fixed vocabulary). Tests live in `tests/discovery/`. Each stage is idempotent and separately testable.

**Tech Stack:** Python 3.11, Flask, psycopg2 (RealDictCursor), `anthropic==0.40.0` (already in deps), `exa-py` (new), `beautifulsoup4` (new), pytest.

**Depends on:** spec `docs/superpowers/specs/2026-04-20-discovery-page-design.md`

---

## File structure

**New files:**
- `db/migrations/024_discovery.sql` — 4 tables + indexes
- `api/discovery/__init__.py` — package marker
- `api/discovery/topics.py` — fixed topic vocabulary
- `api/discovery/clients.py` — GitHub + EXA API wrappers
- `api/discovery/enrich.py` — Haiku enrichment (prompt + parser)
- `api/discovery/cluster.py` — Sonnet lane clustering (prompt + validator)
- `api/discovery/pipeline.py` — 5-stage orchestrator
- `api/discovery/scrape.py` — BeautifulSoup fallback
- `scripts/discovery_ingest.py` — CLI entry
- `tests/discovery/__init__.py`
- `tests/discovery/conftest.py` — shared fixtures
- `tests/discovery/test_clients.py`
- `tests/discovery/test_enrich.py`
- `tests/discovery/test_cluster.py`
- `tests/discovery/test_pipeline.py`
- `tests/discovery/test_scrape.py`
- `tests/discovery/fixtures/` — README samples, API response cassettes

**Modified files:**
- `requirements.txt` — add `exa-py`, `beautifulsoup4`
- `api/models.py` — add `DiscoveryRepo`, `DiscoveryLane` dataclasses

---

## Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append new deps**

Edit `requirements.txt`, add two lines at the bottom:

```
exa-py==1.0.9
beautifulsoup4==4.12.3
```

- [ ] **Step 2: Install locally**

Run: `pip install -r requirements.txt`
Expected: installs exa-py and beautifulsoup4.

- [ ] **Step 3: Verify imports**

Run: `python -c "import exa_py; import bs4; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps(discovery): add exa-py and beautifulsoup4"
```

---

## Task 2: Migration 024 — schema

**Files:**
- Create: `db/migrations/024_discovery.sql`

- [ ] **Step 1: Write migration**

```sql
-- db/migrations/024_discovery.sql
-- Discovery page tables. See docs/superpowers/specs/2026-04-20-discovery-page-design.md

CREATE TABLE IF NOT EXISTS discovery_repos (
    id             SERIAL PRIMARY KEY,
    owner          TEXT NOT NULL,
    name           TEXT NOT NULL,
    full_name      TEXT NOT NULL UNIQUE,
    stars          INT NOT NULL DEFAULT 0,
    language       TEXT,
    license        TEXT,
    default_branch TEXT,
    description    TEXT,
    exa_explainer  TEXT,
    classification TEXT CHECK (classification IN ('app','library','hybrid')),
    classification_confidence REAL,
    topics         JSONB NOT NULL DEFAULT '[]'::jsonb,
    install_hint   TEXT,
    readme_etag    TEXT,
    archived_at    TIMESTAMPTZ,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_enriched_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS discovery_repos_topics_gin ON discovery_repos USING GIN (topics);
CREATE INDEX IF NOT EXISTS discovery_repos_classification ON discovery_repos (classification);
CREATE INDEX IF NOT EXISTS discovery_repos_last_seen ON discovery_repos (last_seen_at DESC);

CREATE TABLE IF NOT EXISTS discovery_repo_stars (
    repo_id INT NOT NULL REFERENCES discovery_repos(id) ON DELETE CASCADE,
    date    DATE NOT NULL,
    stars   INT NOT NULL,
    PRIMARY KEY (repo_id, date)
);

CREATE TABLE IF NOT EXISTS discovery_lanes (
    id              SERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    blurb           TEXT,
    kind            TEXT NOT NULL CHECK (kind IN ('hero','theme','hidden_gems')),
    repo_ids        INT[] NOT NULL,
    position        INT NOT NULL DEFAULT 0,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS user_discovery_saves (
    user_id  TEXT NOT NULL,
    repo_id  INT NOT NULL REFERENCES discovery_repos(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note     TEXT,
    PRIMARY KEY (user_id, repo_id)
);
CREATE INDEX IF NOT EXISTS user_discovery_saves_user ON user_discovery_saves (user_id, saved_at DESC);
```

- [ ] **Step 2: Apply migration**

Run: `python scripts/run_migrations.py`
Expected: `Applied 024_discovery.sql`.

- [ ] **Step 3: Verify schema**

Run:
```bash
psql "$DATABASE_URL" -c "\d discovery_repos" -c "\d discovery_lanes" -c "\d user_discovery_saves" -c "\d discovery_repo_stars"
```
Expected: all four tables listed with the right columns; `discovery_repos_topics_gin` shown as a GIN index.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/024_discovery.sql
git commit -m "feat(discovery): migration 024 — discovery tables"
```

---

## Task 3: Package skeleton + topic vocabulary

**Files:**
- Create: `api/discovery/__init__.py`
- Create: `api/discovery/topics.py`

- [ ] **Step 1: Create `__init__.py` (empty)**

```python
# api/discovery/__init__.py
"""Discovery page — external AI repo ingestion + lane curation."""
```

- [ ] **Step 2: Create `topics.py` with fixed vocabulary**

```python
# api/discovery/topics.py
"""Fixed topic vocabulary for classifying discovery repos.

Prompt instructs the model to pick from this list. Unknown tags are
filtered out during parsing; see enrich.parse_enrichment_response.
"""

TOPICS: frozenset[str] = frozenset({
    "agents",
    "rag",
    "voice",
    "multimodal",
    "eval",
    "agent-memory",
    "computer-use",
    "small-models",
    "infra",
    "ui",
})


def normalize_topics(raw: list[str]) -> list[str]:
    """Lowercase, strip, keep only members of TOPICS, preserve order, dedupe."""
    seen: set[str] = set()
    out: list[str] = []
    for t in raw or []:
        if not isinstance(t, str):
            continue
        t = t.strip().lower()
        if t in TOPICS and t not in seen:
            seen.add(t)
            out.append(t)
    return out
```

- [ ] **Step 3: Quick smoke test in REPL**

Run:
```bash
python -c "from api.discovery.topics import normalize_topics; print(normalize_topics(['Agents', 'rag', 'bogus', 'AGENTS']))"
```
Expected: `['agents', 'rag']`

- [ ] **Step 4: Commit**

```bash
git add api/discovery/__init__.py api/discovery/topics.py
git commit -m "feat(discovery): package skeleton + topic vocabulary"
```

---

## Task 4: Dataclasses in `api/models.py`

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: Append dataclasses**

Open `api/models.py` and append at the bottom (just before `__all__` if one exists — if not, after the last dataclass):

```python
# ---------------------------------------------------------------------------
# Discovery — external AI repos surfaced by the Discovery page (migration 024)
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryRepo:
    id: Optional[int] = None
    owner: Optional[str] = None
    name: Optional[str] = None
    full_name: Optional[str] = None
    stars: int = 0
    language: Optional[str] = None
    license: Optional[str] = None
    default_branch: Optional[str] = None
    description: Optional[str] = None
    exa_explainer: Optional[str] = None
    classification: Optional[str] = None
    classification_confidence: Optional[float] = None
    topics: Optional[list] = None
    install_hint: Optional[str] = None
    readme_etag: Optional[str] = None
    archived_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_enriched_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "DiscoveryRepo":
        d = _row_to_dict(row, cursor)
        # topics comes back from psycopg2 as a Python list (JSONB auto-decoded)
        return cls(**_filter_known(cls, d))

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: _serialize(getattr(self, f.name)) for f in dc_fields(self)}


@dataclass
class DiscoveryLane:
    id: Optional[int] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    blurb: Optional[str] = None
    kind: Optional[str] = None            # 'hero' | 'theme' | 'hidden_gems'
    repo_ids: Optional[list] = None       # int[]
    position: int = 0
    generated_at: Optional[datetime] = None
    generation_meta: Optional[dict] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "DiscoveryLane":
        d = _row_to_dict(row, cursor)
        return cls(**_filter_known(cls, d))

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: _serialize(getattr(self, f.name)) for f in dc_fields(self)}
```

- [ ] **Step 2: Verify import**

Run:
```bash
python -c "from api.models import DiscoveryRepo, DiscoveryLane; print(DiscoveryRepo(id=1, full_name='a/b').to_dict())"
```
Expected: a dict printed, `full_name='a/b'` visible.

- [ ] **Step 3: Commit**

```bash
git add api/models.py
git commit -m "feat(discovery): DiscoveryRepo and DiscoveryLane dataclasses"
```

---

## Task 5: GitHub client (TDD)

**Files:**
- Create: `tests/discovery/__init__.py` (empty)
- Create: `tests/discovery/conftest.py`
- Create: `tests/discovery/test_clients.py`
- Create: `api/discovery/clients.py`

- [ ] **Step 1: Test scaffolding**

```python
# tests/discovery/__init__.py
```

```python
# tests/discovery/conftest.py
"""Fixtures for discovery tests."""
import json
import pytest


@pytest.fixture
def fake_github_search_response():
    """Minimal shape matching GitHub /search/repositories response."""
    return {
        "total_count": 2,
        "items": [
            {
                "full_name": "browser-use/browser-use",
                "owner": {"login": "browser-use"},
                "name": "browser-use",
                "stargazers_count": 3200,
                "language": "Python",
                "license": {"spdx_id": "MIT"},
                "default_branch": "main",
                "description": "Agents that drive Chromium",
            },
            {
                "full_name": "mem0ai/mem0",
                "owner": {"login": "mem0ai"},
                "name": "mem0",
                "stargazers_count": 14500,
                "language": "Python",
                "license": {"spdx_id": "Apache-2.0"},
                "default_branch": "main",
                "description": "Long-term memory for AI agents",
            },
        ],
    }
```

- [ ] **Step 2: Write failing tests**

```python
# tests/discovery/test_clients.py
from unittest.mock import Mock, patch

import pytest

from api.discovery.clients import GitHubClient, ExaClient


class TestGitHubClient:
    def test_fetch_trending_by_topic_parses_response(self, fake_github_search_response):
        client = GitHubClient(token="fake-token")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = fake_github_search_response
            mock_get.return_value.headers = {"X-RateLimit-Remaining": "4000"}
            results = client.fetch_trending_by_topic("ai", language="python", days=30)

        assert len(results) == 2
        assert results[0]["full_name"] == "browser-use/browser-use"
        assert results[0]["stars"] == 3200
        assert results[0]["license"] == "MIT"

    def test_fetch_trending_retries_on_rate_limit(self):
        client = GitHubClient(token="fake-token", max_retries=2, backoff_base=0.01)
        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = [
                Mock(status_code=403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1"}, json=lambda: {}),
                Mock(status_code=200, headers={"X-RateLimit-Remaining": "100"}, json=lambda: {"items": []}),
            ]
            results = client.fetch_trending_by_topic("ai")

        assert results == []
        assert mock_get.call_count == 2

    def test_fetch_readme_returns_none_on_304(self):
        client = GitHubClient(token="fake-token")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 304
            body, etag = client.fetch_readme("owner", "repo", etag='"abc"')
        assert body is None
        assert etag == '"abc"'

    def test_fetch_readme_returns_body_and_new_etag_on_200(self):
        client = GitHubClient(token="fake-token")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = "# README\n\nHello."
            mock_get.return_value.headers = {"ETag": '"new"'}
            body, etag = client.fetch_readme("owner", "repo", etag='"old"')
        assert body == "# README\n\nHello."
        assert etag == '"new"'


class TestExaClient:
    def test_semantic_search_returns_normalized_results(self):
        client = ExaClient(api_key="fake-key")
        mock_resp = Mock()
        mock_resp.results = [
            Mock(url="https://github.com/owner/repo-a", title="repo-a", text="desc"),
            Mock(url="https://github.com/owner/repo-b", title="repo-b", text="desc"),
        ]
        with patch.object(client, "_sdk") as mock_sdk:
            mock_sdk.search.return_value = mock_resp
            results = client.semantic_search("agent frameworks", num_results=2)
        assert len(results) == 2
        assert results[0]["full_name"] == "owner/repo-a"

    def test_semantic_search_skips_non_github_urls(self):
        client = ExaClient(api_key="fake-key")
        mock_resp = Mock()
        mock_resp.results = [
            Mock(url="https://example.com/blog", title="blog", text=""),
            Mock(url="https://github.com/owner/repo", title="repo", text=""),
        ]
        with patch.object(client, "_sdk") as mock_sdk:
            mock_sdk.search.return_value = mock_resp
            results = client.semantic_search("query")
        assert len(results) == 1
        assert results[0]["full_name"] == "owner/repo"
```

- [ ] **Step 3: Run tests — expect ImportError**

Run: `pytest tests/discovery/test_clients.py -v`
Expected: `ModuleNotFoundError: No module named 'api.discovery.clients'`.

- [ ] **Step 4: Implement `clients.py`**

```python
# api/discovery/clients.py
"""Thin API wrappers for GitHub + EXA. No business logic here."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional
from urllib.parse import quote

import requests

log = logging.getLogger("forge.discovery.clients")


class GitHubClient:
    """GitHub REST v3 client. Authenticated via PAT in GITHUB_DISCOVERY_TOKEN.

    Resilient to 403/429 with exponential backoff. Raises on persistent failure.
    """

    BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, max_retries: int = 4, backoff_base: float = 1.0):
        self.token = token or os.environ.get("GITHUB_DISCOVERY_TOKEN", "")
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def _headers(self, etag: Optional[str] = None) -> dict:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if etag:
            h["If-None-Match"] = etag
        return h

    def _get(self, url: str, etag: Optional[str] = None) -> requests.Response:
        """GET with exponential backoff on rate limits."""
        for attempt in range(self.max_retries):
            resp = requests.get(url, headers=self._headers(etag), timeout=30)
            if resp.status_code in (403, 429):
                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining == "0" and attempt < self.max_retries - 1:
                    wait = self.backoff_base * (2 ** attempt)
                    log.warning("github rate-limited, sleeping %.1fs (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                    continue
            return resp
        return resp

    def fetch_trending_by_topic(
        self,
        topic: str,
        language: Optional[str] = None,
        days: int = 30,
        per_page: int = 30,
    ) -> list[dict]:
        """Search repos with the given topic pushed in the last N days.

        Returns a normalized list of repo dicts (NOT raw GitHub shape).
        """
        from datetime import date, timedelta
        since = (date.today() - timedelta(days=days)).isoformat()
        q_parts = [f"topic:{topic}", f"pushed:>{since}"]
        if language:
            q_parts.append(f"language:{language}")
        query = quote(" ".join(q_parts), safe=":>")
        url = f"{self.BASE}/search/repositories?q={query}&sort=stars&order=desc&per_page={per_page}"

        resp = self._get(url)
        if resp.status_code != 200:
            log.warning("github search failed topic=%s status=%d", topic, resp.status_code)
            return []
        items = resp.json().get("items", []) or []
        return [self._normalize_repo(it) for it in items]

    def fetch_readme(self, owner: str, name: str, etag: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
        """Fetch README markdown. Returns (body, etag).

        If the ETag matches (304), body is None and the passed etag is returned.
        If the repo has no README or 404s, returns (None, None).
        """
        url = f"{self.BASE}/repos/{owner}/{name}/readme"
        resp = requests.get(
            url,
            headers={
                **self._headers(etag),
                "Accept": "application/vnd.github.raw+json",  # raw markdown body
            },
            timeout=30,
        )
        if resp.status_code == 304:
            return None, etag
        if resp.status_code == 200:
            return resp.text, resp.headers.get("ETag")
        return None, None

    @staticmethod
    def _normalize_repo(raw: dict) -> dict:
        return {
            "full_name": raw.get("full_name"),
            "owner": (raw.get("owner") or {}).get("login"),
            "name": raw.get("name"),
            "stars": int(raw.get("stargazers_count") or 0),
            "language": raw.get("language"),
            "license": ((raw.get("license") or {}).get("spdx_id")),
            "default_branch": raw.get("default_branch"),
            "description": raw.get("description"),
        }


class ExaClient:
    """Wraps exa-py SDK. Single purpose: semantic search that returns GitHub repos.

    Non-GitHub URLs are filtered out — we only care about repos.
    """

    GITHUB_URL_PREFIX = "https://github.com/"

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("EXA_API_KEY", "")
        from exa_py import Exa
        self._sdk = Exa(api_key)

    def semantic_search(self, query: str, num_results: int = 25) -> list[dict]:
        resp = self._sdk.search(query, num_results=num_results, type="neural")
        out: list[dict] = []
        for r in getattr(resp, "results", []) or []:
            url = getattr(r, "url", "") or ""
            if not url.startswith(self.GITHUB_URL_PREFIX):
                continue
            path = url[len(self.GITHUB_URL_PREFIX):].strip("/")
            parts = path.split("/")
            if len(parts) < 2:
                continue
            owner, name = parts[0], parts[1]
            out.append({
                "full_name": f"{owner}/{name}",
                "owner": owner,
                "name": name,
                "stars": 0,  # EXA doesn't carry star count; resolved by GitHub fetch later
                "language": None,
                "license": None,
                "default_branch": None,
                "description": getattr(r, "title", "") or "",
            })
        return out
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/discovery/test_clients.py -v`
Expected: all 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/discovery/clients.py tests/discovery/__init__.py tests/discovery/conftest.py tests/discovery/test_clients.py
git commit -m "feat(discovery): GitHub + EXA clients"
```

---

## Task 6: Haiku enrichment (TDD)

**Files:**
- Create: `tests/discovery/test_enrich.py`
- Create: `tests/discovery/fixtures/README_app.md`
- Create: `tests/discovery/fixtures/README_library.md`
- Create: `api/discovery/enrich.py`

- [ ] **Step 1: Create README fixtures**

```markdown
<!-- tests/discovery/fixtures/README_app.md -->
# browser-use

Drive Chromium with an AI agent. Works with GPT-4 or Claude.

## Install

```
pip install browser-use
```

## Example

```python
from browser_use import Agent
agent = Agent(task="book me a flight")
agent.run()
```
```

```markdown
<!-- tests/discovery/fixtures/README_library.md -->
# mem0

Open-source memory framework for AI agents.

Mem0 enhances AI assistants with an intelligent memory layer. Import it into
your Python project.

```python
from mem0 import Memory
m = Memory()
m.add("user prefers concise answers")
```

MIT Licensed.
```

- [ ] **Step 2: Write failing tests**

```python
# tests/discovery/test_enrich.py
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from api.discovery.enrich import (
    build_enrichment_prompt,
    parse_enrichment_response,
    enrich_repo,
    EnrichmentError,
)


FIXTURES = Path(__file__).parent / "fixtures"


class TestParseEnrichmentResponse:
    def test_valid_json_parses(self):
        raw = json.dumps({
            "explainer": "Test description.",
            "classification": "app",
            "classification_confidence": 0.9,
            "topics": ["agents", "computer-use"],
            "install_hint": "git_clone",
        })
        result = parse_enrichment_response(raw)
        assert result["explainer"] == "Test description."
        assert result["classification"] == "app"
        assert result["classification_confidence"] == 0.9
        assert result["topics"] == ["agents", "computer-use"]
        assert result["install_hint"] == "git_clone"

    def test_strips_code_fence_wrapper(self):
        raw = '```json\n{"explainer":"x","classification":"app","classification_confidence":0.5,"topics":[],"install_hint":"none"}\n```'
        result = parse_enrichment_response(raw)
        assert result["explainer"] == "x"

    def test_rejects_unknown_topics(self):
        raw = json.dumps({
            "explainer": "x",
            "classification": "app",
            "classification_confidence": 0.5,
            "topics": ["agents", "made-up-topic"],
            "install_hint": "none",
        })
        result = parse_enrichment_response(raw)
        assert result["topics"] == ["agents"]

    def test_rejects_invalid_classification(self):
        raw = json.dumps({
            "explainer": "x",
            "classification": "not-a-real-class",
            "classification_confidence": 0.5,
            "topics": [],
            "install_hint": "none",
        })
        with pytest.raises(EnrichmentError, match="classification"):
            parse_enrichment_response(raw)

    def test_clamps_confidence_to_0_1(self):
        raw = json.dumps({
            "explainer": "x",
            "classification": "app",
            "classification_confidence": 1.5,  # out of range
            "topics": [],
            "install_hint": "none",
        })
        result = parse_enrichment_response(raw)
        assert result["classification_confidence"] == 1.0

    def test_rejects_malformed_json(self):
        with pytest.raises(EnrichmentError):
            parse_enrichment_response("not json at all")


class TestBuildEnrichmentPrompt:
    def test_includes_repo_name_and_readme(self):
        prompt = build_enrichment_prompt(
            full_name="owner/repo",
            description="short desc",
            readme="# Title\n\nBody.",
        )
        assert "owner/repo" in prompt
        assert "short desc" in prompt
        assert "# Title" in prompt

    def test_truncates_long_readme(self):
        long = "x" * 100000
        prompt = build_enrichment_prompt("a/b", "d", long)
        # README section capped at 50_000 chars per spec
        assert len(prompt) < 80_000


class TestEnrichRepo:
    def test_calls_haiku_and_returns_parsed_result(self):
        fake_response = Mock()
        fake_response.content = [Mock(text=json.dumps({
            "explainer": "A Python agent framework.",
            "classification": "library",
            "classification_confidence": 0.85,
            "topics": ["agents"],
            "install_hint": "pip",
        }))]
        with patch("api.discovery.enrich._anthropic_client") as mock_client:
            mock_client.return_value.messages.create.return_value = fake_response
            result = enrich_repo(
                full_name="owner/repo",
                description="d",
                readme=(FIXTURES / "README_library.md").read_text(),
            )
        assert result["classification"] == "library"
        assert "agents" in result["topics"]
```

- [ ] **Step 3: Run tests — expect ImportError**

Run: `pytest tests/discovery/test_enrich.py -v`
Expected: `ModuleNotFoundError: No module named 'api.discovery.enrich'`.

- [ ] **Step 4: Implement `enrich.py`**

```python
# api/discovery/enrich.py
"""Haiku-based enrichment: produces explainer + classification + topics.

One LLM call per new repo. Called from pipeline.stage3_enrich_new.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from api.discovery.topics import TOPICS, normalize_topics

log = logging.getLogger("forge.discovery.enrich")

MODEL = os.environ.get("DISCOVERY_ENRICH_MODEL", "claude-haiku-4-5-20251001")
README_CAP = 50_000
VALID_CLASSIFICATIONS = {"app", "library", "hybrid"}
VALID_INSTALL_HINTS = {"git_clone", "pip", "npm", "brew", "cargo", "go", "none"}


class EnrichmentError(Exception):
    """Raised when LLM output can't be parsed into a valid enrichment dict."""


_SYSTEM_PROMPT = """You classify open-source AI repositories for Forge, an internal AI app marketplace.

Given a repo's name, description, and README, return JSON with these fields:
- explainer: One paragraph (2-4 sentences) describing what this is, who it's for, and what makes it interesting. Plain language.
- classification: Exactly one of "app" (a runnable end-user application), "library" (a package imported by other code), or "hybrid" (both).
- classification_confidence: Your confidence as a float 0.0-1.0.
- topics: Between 3 and 5 lowercase tags, ALL drawn from this fixed vocabulary: {topic_list}. Do not invent tags.
- install_hint: One of "git_clone", "pip", "npm", "brew", "cargo", "go", "none".

Output ONLY the JSON object. No prose, no code fences."""


def _anthropic_client():
    """Wrapped for testability."""
    from anthropic import Anthropic
    return Anthropic()


def build_enrichment_prompt(full_name: str, description: str, readme: str) -> str:
    truncated = (readme or "")[:README_CAP]
    return (
        f"Repo: {full_name}\n"
        f"Description: {description or '(none)'}\n\n"
        f"--- README ---\n{truncated}\n--- END README ---"
    )


def parse_enrichment_response(raw: str) -> dict[str, Any]:
    """Parse model output into a validated enrichment dict. Raises EnrichmentError on any fail."""
    # Strip optional ```json fences
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise EnrichmentError(f"malformed json: {e}") from e

    if not isinstance(data, dict):
        raise EnrichmentError("response is not a json object")

    explainer = data.get("explainer")
    classification = data.get("classification")
    confidence = data.get("classification_confidence")
    topics_raw = data.get("topics") or []
    install_hint = data.get("install_hint")

    if not isinstance(explainer, str) or not explainer.strip():
        raise EnrichmentError("missing or empty explainer")
    if classification not in VALID_CLASSIFICATIONS:
        raise EnrichmentError(f"invalid classification: {classification!r}")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as e:
        raise EnrichmentError("invalid confidence") from e
    confidence = max(0.0, min(1.0, confidence))
    if install_hint not in VALID_INSTALL_HINTS:
        install_hint = "none"
    topics = normalize_topics(topics_raw)

    return {
        "explainer": explainer.strip(),
        "classification": classification,
        "classification_confidence": confidence,
        "topics": topics,
        "install_hint": install_hint,
    }


def enrich_repo(full_name: str, description: str, readme: str) -> dict[str, Any]:
    """Run Haiku on a repo; return validated enrichment dict. Raises EnrichmentError on failure."""
    system = _SYSTEM_PROMPT.format(topic_list=", ".join(sorted(TOPICS)))
    user = build_enrichment_prompt(full_name, description, readme)
    client = _anthropic_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if hasattr(block, "text"))
    return parse_enrichment_response(text)
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/discovery/test_enrich.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/discovery/enrich.py tests/discovery/test_enrich.py tests/discovery/fixtures/
git commit -m "feat(discovery): Haiku enrichment (explainer + classification + topics)"
```

---

## Task 7: Sonnet lane clustering (TDD)

**Files:**
- Create: `tests/discovery/test_cluster.py`
- Create: `api/discovery/cluster.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/discovery/test_cluster.py
import json
from unittest.mock import Mock, patch

import pytest

from api.discovery.cluster import (
    validate_cluster_output,
    ClusterError,
    cluster_lanes,
)


class TestValidateClusterOutput:
    def _valid_input(self):
        return [
            {"full_name": f"owner/repo-{i}", "stars": 100 * i}
            for i in range(1, 21)
        ]

    def _valid_output(self):
        return {
            "hero": {"full_name": "owner/repo-1", "blurb": "The best one."},
            "lanes": [
                {
                    "slug": "agents",
                    "title": "Agent frameworks",
                    "blurb": "Tools for building agents.",
                    "full_names": ["owner/repo-2", "owner/repo-3", "owner/repo-4", "owner/repo-5"],
                },
                {
                    "slug": "eval",
                    "title": "Eval & observability",
                    "blurb": "Measure LLM apps.",
                    "full_names": ["owner/repo-6", "owner/repo-7", "owner/repo-8"],
                },
                {
                    "slug": "rag",
                    "title": "RAG & retrieval",
                    "blurb": "Document search.",
                    "full_names": ["owner/repo-9", "owner/repo-10", "owner/repo-11"],
                },
                {
                    "slug": "voice",
                    "title": "Voice & multimodal",
                    "blurb": "Speech and vision.",
                    "full_names": ["owner/repo-12", "owner/repo-13", "owner/repo-14"],
                },
            ],
        }

    def test_accepts_valid(self):
        data = self._valid_output()
        ok = validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))
        assert ok == data  # returns normalized dict on success

    def test_rejects_too_few_lanes(self):
        data = self._valid_output()
        data["lanes"] = data["lanes"][:2]
        with pytest.raises(ClusterError, match="lane count"):
            validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))

    def test_rejects_lane_with_unknown_repo(self):
        data = self._valid_output()
        data["lanes"][0]["full_names"].append("ghost/repo")
        with pytest.raises(ClusterError, match="unknown"):
            validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))

    def test_rejects_lane_under_3_repos(self):
        data = self._valid_output()
        data["lanes"][0]["full_names"] = ["owner/repo-2", "owner/repo-3"]
        with pytest.raises(ClusterError, match="too few repos"):
            validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))

    def test_rejects_duplicate_lane_slug(self):
        data = self._valid_output()
        data["lanes"][1]["slug"] = data["lanes"][0]["slug"]
        with pytest.raises(ClusterError, match="duplicate slug"):
            validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))

    def test_rejects_missing_hero(self):
        data = self._valid_output()
        data["hero"] = {}
        with pytest.raises(ClusterError, match="hero"):
            validate_cluster_output(data, known_full_names=set(r["full_name"] for r in self._valid_input()))


class TestClusterLanes:
    def test_calls_sonnet_and_returns_validated(self):
        input_repos = [
            {"full_name": f"o/r{i}", "explainer": f"repo {i}", "topics": ["agents"], "stars": 100, "stars_weekly_delta": 10}
            for i in range(1, 21)
        ]
        valid_out = {
            "hero": {"full_name": "o/r1", "blurb": "b"},
            "lanes": [
                {"slug": s, "title": s, "blurb": "b", "full_names": [f"o/r{i}" for i in range(2, 6)]}
                for s in ["a", "b", "c", "d"]
            ],
        }
        fake_resp = Mock()
        fake_resp.content = [Mock(text=json.dumps(valid_out))]
        with patch("api.discovery.cluster._anthropic_client") as mc:
            mc.return_value.messages.create.return_value = fake_resp
            result = cluster_lanes(input_repos)
        assert len(result["lanes"]) == 4
        assert result["hero"]["full_name"] == "o/r1"
```

- [ ] **Step 2: Run — expect ImportError**

Run: `pytest tests/discovery/test_cluster.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `cluster.py`**

```python
# api/discovery/cluster.py
"""Sonnet-based lane clustering. Runs when ≥30 new enriched repos accumulate.

One LLM call produces: 1 hero pick + 4-6 themed lanes (each with ≥3 repos).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

log = logging.getLogger("forge.discovery.cluster")

MODEL = os.environ.get("DISCOVERY_CLUSTER_MODEL", "claude-sonnet-4-6")
PROMPT_VERSION = 1
MIN_LANES = 4
MAX_LANES = 6
MIN_REPOS_PER_LANE = 3


class ClusterError(Exception):
    """Raised on invalid cluster output."""


_SYSTEM_PROMPT = """You curate a weekly "what's shipping in AI" discovery page for Forge engineers.

Given a list of open-source AI repositories (with their explainers, topics, stars, weekly star velocity),
produce an editorial selection:

1. One "hero" pick — the single most interesting repo this week. Include a 1-sentence blurb that tells
   a builder why it matters.
2. {min_lanes}-{max_lanes} themed lanes. Each lane:
   - slug: kebab-case, unique (e.g. "computer-use-agents")
   - title: 2-4 word headline
   - blurb: 1 sentence describing the theme
   - full_names: 3-6 repos from the input, ordered by editorial weight (not just stars)

Do NOT invent repos. Use full_name exactly as given.
Library repos may appear on theme lanes when they anchor a theme (e.g. langchain for agents).
Prefer breadth over depth — cover multiple themes, not minor variations on one.

Output ONLY the JSON object. No prose, no code fences.

Schema:
{{
  "hero": {{ "full_name": "owner/repo", "blurb": "..." }},
  "lanes": [
    {{ "slug": "...", "title": "...", "blurb": "...", "full_names": ["...", "..."] }},
    ...
  ]
}}"""


def _anthropic_client():
    from anthropic import Anthropic
    return Anthropic()


def build_cluster_prompt(repos: list[dict]) -> str:
    """Serialize repo list into the user message."""
    lines = []
    for r in repos:
        topics = r.get("topics") or []
        lines.append(
            f"- {r['full_name']} | stars={r.get('stars', 0)} "
            f"delta7d={r.get('stars_weekly_delta', 0)} "
            f"topics={','.join(topics) if topics else '-'}\n"
            f"  {r.get('explainer', '')[:280]}"
        )
    return "Candidate repos:\n\n" + "\n".join(lines)


def validate_cluster_output(data: Any, known_full_names: set[str]) -> dict:
    """Validate the parsed JSON against our schema + input repos. Raises ClusterError on any fail."""
    if not isinstance(data, dict):
        raise ClusterError("not a json object")

    hero = data.get("hero")
    if not isinstance(hero, dict) or not hero.get("full_name") or not hero.get("blurb"):
        raise ClusterError("hero missing or incomplete")
    if hero["full_name"] not in known_full_names:
        raise ClusterError(f"hero references unknown repo: {hero['full_name']}")

    lanes = data.get("lanes")
    if not isinstance(lanes, list) or not (MIN_LANES <= len(lanes) <= MAX_LANES):
        raise ClusterError(f"invalid lane count: {len(lanes) if isinstance(lanes, list) else 'not-a-list'}")

    slugs: set[str] = set()
    for lane in lanes:
        if not isinstance(lane, dict):
            raise ClusterError("lane is not an object")
        slug = lane.get("slug")
        title = lane.get("title")
        blurb = lane.get("blurb")
        names = lane.get("full_names")
        if not all([slug, title, blurb]) or not isinstance(names, list):
            raise ClusterError(f"lane missing required fields: {lane}")
        if slug in slugs:
            raise ClusterError(f"duplicate slug: {slug}")
        slugs.add(slug)
        if len(names) < MIN_REPOS_PER_LANE:
            raise ClusterError(f"lane {slug} has too few repos ({len(names)})")
        unknown = [n for n in names if n not in known_full_names]
        if unknown:
            raise ClusterError(f"lane {slug} references unknown repos: {unknown}")
    return data


def parse_cluster_response(raw: str, known_full_names: set[str]) -> dict:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClusterError(f"malformed json: {e}") from e
    return validate_cluster_output(data, known_full_names)


def cluster_lanes(repos: list[dict]) -> dict:
    """Run Sonnet on enriched repos. Returns validated {hero, lanes}. Raises ClusterError on failure."""
    if len(repos) < MIN_LANES * MIN_REPOS_PER_LANE:
        raise ClusterError(f"not enough repos to cluster ({len(repos)})")

    system = _SYSTEM_PROMPT.format(min_lanes=MIN_LANES, max_lanes=MAX_LANES)
    user = build_cluster_prompt(repos)
    client = _anthropic_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if hasattr(block, "text"))
    known = {r["full_name"] for r in repos}
    return parse_cluster_response(text, known)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_cluster.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/cluster.py tests/discovery/test_cluster.py
git commit -m "feat(discovery): Sonnet lane clustering with validator"
```

---

## Task 8: Pipeline stage 1 — fetch candidates

**Files:**
- Create: `tests/discovery/test_pipeline_stages.py`
- Create: `api/discovery/pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/discovery/test_pipeline_stages.py
from unittest.mock import Mock, patch

import pytest


class TestStage1:
    def test_fetches_github_trending_across_topics_and_languages(self):
        from api.discovery import pipeline

        mock_gh = Mock()
        mock_gh.fetch_trending_by_topic.side_effect = lambda topic, language=None, days=30: [
            {"full_name": f"g/{topic}-{language or 'any'}", "owner": "g", "name": f"{topic}-{language or 'any'}",
             "stars": 100, "language": language, "license": None, "default_branch": "main",
             "description": f"{topic} {language}"}
        ]
        mock_exa = Mock()
        mock_exa.semantic_search.side_effect = lambda q, num_results=25: [
            {"full_name": "e/ai-agent", "owner": "e", "name": "ai-agent", "stars": 0,
             "language": None, "license": None, "default_branch": None, "description": q[:40]}
        ]

        candidates = pipeline.stage1_fetch_candidates(mock_gh, mock_exa)

        # GitHub: N topics × M languages calls
        assert mock_gh.fetch_trending_by_topic.call_count >= 4
        # EXA: 6 standing queries + 1 hidden gems = 7
        assert mock_exa.semantic_search.call_count == 7
        # Dedup by full_name
        full_names = [c["full_name"] for c in candidates]
        assert len(full_names) == len(set(full_names))
        # Contains at least the hidden-gems result
        assert any("ai-agent" in fn for fn in full_names)

    def test_continues_when_exa_raises(self):
        from api.discovery import pipeline
        mock_gh = Mock()
        mock_gh.fetch_trending_by_topic.return_value = [
            {"full_name": "g/x", "owner": "g", "name": "x", "stars": 0, "language": "Python",
             "license": None, "default_branch": "main", "description": ""}
        ]
        mock_exa = Mock()
        mock_exa.semantic_search.side_effect = RuntimeError("exa down")

        candidates = pipeline.stage1_fetch_candidates(mock_gh, mock_exa)
        assert any(c["full_name"] == "g/x" for c in candidates)
```

- [ ] **Step 2: Run — expect ImportError**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage1 -v`
Expected: `ModuleNotFoundError: No module named 'api.discovery.pipeline'`.

- [ ] **Step 3: Implement stage 1 (create `pipeline.py`)**

```python
# api/discovery/pipeline.py
"""Five-stage daily discovery ingestion.

Stage 1: fetch raw candidates (cheap, no LLM)
Stage 2: diff against DB
Stage 3: enrich new repos (Haiku)
Stage 4: append stars sparkline, prune old
Stage 5: re-cluster lanes (gated on delta)

Each stage is separately testable and idempotent.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from api.discovery.clients import ExaClient, GitHubClient

log = logging.getLogger("forge.discovery.pipeline")

# Stage 1 configuration
GITHUB_TOPICS = ["ai", "agents", "llm", "rag", "voice", "multimodal", "evaluation"]
GITHUB_LANGUAGES = ["python", "typescript", "rust", "go"]
EXA_THEME_QUERIES = [
    "Open-source AI agent framework released or meaningfully updated in the last 90 days",
    "Novel LLM evaluation or observability tool",
    "Open-source RAG or retrieval system",
    "Voice, speech, or multimodal AI tool",
    "Computer-use or browser-automation agent",
    "Small-model or efficient-inference tool",
]
EXA_HIDDEN_GEMS_QUERY = (
    "Standalone open-source AI application with fewer than 1000 stars, "
    "functionally complete, recently updated"
)
EXA_RESULTS_PER_QUERY = 25


def stage1_fetch_candidates(gh: GitHubClient, exa: ExaClient) -> list[dict]:
    """Fetch raw candidate repos from GitHub + EXA. Returns deduped list."""
    seen: dict[str, dict] = {}

    # GitHub trending: cross-product of topics × languages
    for topic in GITHUB_TOPICS:
        for lang in GITHUB_LANGUAGES:
            try:
                results = gh.fetch_trending_by_topic(topic, language=lang, days=30)
                for r in results:
                    fn = r.get("full_name")
                    if fn and fn not in seen:
                        seen[fn] = dict(r, source="github")
            except Exception as e:
                log.warning("github fetch failed topic=%s lang=%s: %s", topic, lang, e)

    # EXA semantic lanes
    for q in EXA_THEME_QUERIES:
        try:
            results = exa.semantic_search(q, num_results=EXA_RESULTS_PER_QUERY)
            for r in results:
                fn = r.get("full_name")
                if fn and fn not in seen:
                    seen[fn] = dict(r, source="exa")
        except Exception as e:
            log.warning("exa query failed: %s", e)

    # Hidden gems — always runs, gets its own slot
    try:
        results = exa.semantic_search(EXA_HIDDEN_GEMS_QUERY, num_results=EXA_RESULTS_PER_QUERY)
        for r in results:
            fn = r.get("full_name")
            if fn and fn not in seen:
                seen[fn] = dict(r, source="exa_hidden_gems")
    except Exception as e:
        log.warning("exa hidden-gems query failed: %s", e)

    return list(seen.values())
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage1 -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): pipeline stage 1 — fetch candidates"
```

---

## Task 9: Pipeline stage 2 — diff against DB

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

Add to `tests/discovery/test_pipeline_stages.py`:

```python
class TestStage2:
    def test_new_repos_marked_for_enrichment(self, db):
        from api.discovery import pipeline
        candidates = [
            {"full_name": "new/repo", "owner": "new", "name": "repo", "stars": 100,
             "language": "Python", "license": "MIT", "default_branch": "main",
             "description": "d"},
        ]
        result = pipeline.stage2_diff(candidates)
        assert len(result["new"]) == 1
        assert len(result["existing"]) == 0

    def test_existing_repos_updated_and_not_marked_new(self, db, sample_discovery_repo):
        from api.discovery import pipeline
        # sample_discovery_repo has full_name="existing/repo"
        candidates = [
            {"full_name": "existing/repo", "owner": "existing", "name": "repo", "stars": 999,
             "language": "Python", "license": "MIT", "default_branch": "main",
             "description": "updated desc"},
        ]
        result = pipeline.stage2_diff(candidates)
        assert len(result["new"]) == 0
        assert len(result["existing"]) == 1

        # Confirm stars bump persisted
        from api import db as dbmod
        with dbmod.get_db() as cur:
            cur.execute("SELECT stars FROM discovery_repos WHERE full_name = %s", ("existing/repo",))
            row = cur.fetchone()
            assert row["stars"] == 999
```

Add to `tests/discovery/conftest.py`:

```python
@pytest.fixture
def sample_discovery_repo(db):
    """Insert a pre-existing discovery_repos row for diff tests."""
    from api import db as dbmod
    with dbmod.get_db() as cur:
        cur.execute(
            """INSERT INTO discovery_repos (owner, name, full_name, stars, language)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            ("existing", "repo", "existing/repo", 50, "Python"),
        )
        rid = cur.fetchone()["id"]
    return rid
```

- [ ] **Step 2: Run — expect fail (stage2_diff missing)**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage2 -v`
Expected: `AttributeError: module 'api.discovery.pipeline' has no attribute 'stage2_diff'`.

- [ ] **Step 3: Implement stage 2**

Append to `api/discovery/pipeline.py`:

```python
from api import db as _db


def stage2_diff(candidates: list[dict]) -> dict[str, list[dict]]:
    """Upsert candidates into discovery_repos. Return {new, existing} lists.

    - New: row didn't exist → flagged for stage 3 enrichment.
    - Existing: row existed → stars + last_seen_at bumped. README ETag check happens in stage 3.
    """
    new_list: list[dict] = []
    existing_list: list[dict] = []

    with _db.get_db() as cur:
        for cand in candidates:
            fn = cand.get("full_name")
            if not fn:
                continue
            # Check existence
            cur.execute("SELECT id, readme_etag FROM discovery_repos WHERE full_name = %s", (fn,))
            row = cur.fetchone()
            if row:
                # Update stars + last_seen
                cur.execute(
                    """UPDATE discovery_repos
                       SET stars = %s,
                           language = COALESCE(%s, language),
                           license = COALESCE(%s, license),
                           description = COALESCE(%s, description),
                           default_branch = COALESCE(%s, default_branch),
                           last_seen_at = NOW()
                       WHERE id = %s""",
                    (cand.get("stars", 0), cand.get("language"), cand.get("license"),
                     cand.get("description"), cand.get("default_branch"), row["id"]),
                )
                existing_list.append({**cand, "id": row["id"], "readme_etag": row["readme_etag"]})
            else:
                cur.execute(
                    """INSERT INTO discovery_repos
                       (owner, name, full_name, stars, language, license, default_branch, description)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (cand["owner"], cand["name"], fn, cand.get("stars", 0),
                     cand.get("language"), cand.get("license"),
                     cand.get("default_branch"), cand.get("description")),
                )
                new_id = cur.fetchone()["id"]
                new_list.append({**cand, "id": new_id})

    return {"new": new_list, "existing": existing_list}
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage2 -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py tests/discovery/conftest.py
git commit -m "feat(discovery): pipeline stage 2 — diff against DB"
```

---

## Task 10: Pipeline stage 3 — enrich new repos

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestStage3:
    def test_enriches_new_repos_and_persists(self, db, monkeypatch):
        from api.discovery import pipeline
        from api import db as dbmod

        # Insert an un-enriched row
        with dbmod.get_db() as cur:
            cur.execute(
                """INSERT INTO discovery_repos (owner, name, full_name, stars)
                   VALUES ('fresh', 'repo', 'fresh/repo', 100) RETURNING id""")
            rid = cur.fetchone()["id"]

        # Mock GitHub readme fetch
        mock_gh = Mock()
        mock_gh.fetch_readme.return_value = ("# readme body", '"etag-abc"')

        # Mock enrichment
        monkeypatch.setattr(
            "api.discovery.pipeline._enrich_repo",
            lambda full_name, description, readme: {
                "explainer": "A tool.",
                "classification": "app",
                "classification_confidence": 0.9,
                "topics": ["agents"],
                "install_hint": "pip",
            },
        )

        new_list = [{"id": rid, "full_name": "fresh/repo", "owner": "fresh", "name": "repo",
                     "description": "d", "readme_etag": None}]
        result = pipeline.stage3_enrich_new(new_list, mock_gh)
        assert result["enriched"] == 1

        with dbmod.get_db() as cur:
            cur.execute("SELECT classification, exa_explainer, readme_etag, topics FROM discovery_repos WHERE id = %s", (rid,))
            row = cur.fetchone()
        assert row["classification"] == "app"
        assert row["exa_explainer"] == "A tool."
        assert row["readme_etag"] == '"etag-abc"'
        assert row["topics"] == ["agents"]

    def test_skips_when_etag_matches_304(self, db, sample_discovery_repo):
        from api.discovery import pipeline

        mock_gh = Mock()
        mock_gh.fetch_readme.return_value = (None, '"unchanged"')  # 304 path

        existing_list = [{"id": sample_discovery_repo, "full_name": "existing/repo",
                          "owner": "existing", "name": "repo", "description": "d",
                          "readme_etag": '"unchanged"'}]
        result = pipeline.stage3_enrich_new(existing_list, mock_gh)
        assert result["enriched"] == 0
        assert result["skipped_etag"] == 1
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage3 -v`
Expected: `AttributeError: ... stage3_enrich_new`.

- [ ] **Step 3: Append stage 3**

Append to `api/discovery/pipeline.py`:

```python
from api.discovery.enrich import enrich_repo as _enrich_repo, EnrichmentError
import json as _json


def stage3_enrich_new(repos: list[dict], gh: GitHubClient) -> dict[str, int]:
    """Fetch README + enrich each repo with Haiku. Respects ETag for 304 short-circuit.

    `repos` may be the `new` list (no etag yet) or the `existing` list (etag to compare).
    Returns counts: {enriched, skipped_etag, failed}.
    """
    counts = {"enriched": 0, "skipped_etag": 0, "failed": 0}
    for r in repos:
        owner = r["owner"]
        name = r["name"]
        fn = r["full_name"]
        etag_in = r.get("readme_etag")

        try:
            body, etag_out = gh.fetch_readme(owner, name, etag=etag_in)
        except Exception as e:
            log.warning("readme fetch failed %s: %s", fn, e)
            counts["failed"] += 1
            continue

        if body is None and etag_in and etag_out == etag_in:
            counts["skipped_etag"] += 1
            continue
        if body is None:
            # Repo has no README or 404 — skip enrichment, soft-mark archived if repeated
            counts["failed"] += 1
            continue

        try:
            enrich = _enrich_repo(full_name=fn, description=r.get("description") or "", readme=body)
        except EnrichmentError as e:
            log.warning("enrichment failed %s: %s", fn, e)
            counts["failed"] += 1
            continue
        except Exception as e:
            log.warning("enrichment crashed %s: %s", fn, e)
            counts["failed"] += 1
            continue

        with _db.get_db() as cur:
            cur.execute(
                """UPDATE discovery_repos
                   SET exa_explainer = %s,
                       classification = %s,
                       classification_confidence = %s,
                       topics = %s,
                       install_hint = %s,
                       readme_etag = %s,
                       last_enriched_at = NOW()
                   WHERE id = %s""",
                (enrich["explainer"], enrich["classification"], enrich["classification_confidence"],
                 _json.dumps(enrich["topics"]), enrich["install_hint"],
                 etag_out, r["id"]),
            )
        counts["enriched"] += 1
    return counts
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage3 -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): pipeline stage 3 — enrich new repos (Haiku + ETag)"
```

---

## Task 11: Pipeline stage 4 — stars sparkline

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestStage4:
    def test_appends_today_and_prunes_90_day(self, db, sample_discovery_repo, monkeypatch):
        from api.discovery import pipeline
        from api import db as dbmod
        from datetime import date, timedelta

        # Insert a >90-day-old row to be pruned
        with dbmod.get_db() as cur:
            old = date.today() - timedelta(days=100)
            cur.execute(
                "INSERT INTO discovery_repo_stars (repo_id, date, stars) VALUES (%s, %s, %s)",
                (sample_discovery_repo, old, 10),
            )

        pipeline.stage4_append_stars([{"id": sample_discovery_repo, "stars": 77}])

        with dbmod.get_db() as cur:
            cur.execute(
                "SELECT date, stars FROM discovery_repo_stars WHERE repo_id = %s ORDER BY date",
                (sample_discovery_repo,),
            )
            rows = cur.fetchall()
        # Old row pruned; today's row added
        assert len(rows) == 1
        assert rows[0]["stars"] == 77

    def test_upsert_when_rerun_same_day(self, db, sample_discovery_repo):
        from api.discovery import pipeline
        from api import db as dbmod
        pipeline.stage4_append_stars([{"id": sample_discovery_repo, "stars": 50}])
        pipeline.stage4_append_stars([{"id": sample_discovery_repo, "stars": 60}])  # rerun

        with dbmod.get_db() as cur:
            cur.execute(
                "SELECT stars FROM discovery_repo_stars WHERE repo_id = %s",
                (sample_discovery_repo,),
            )
            rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0]["stars"] == 60
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage4 -v`
Expected: `AttributeError: ... stage4_append_stars`.

- [ ] **Step 3: Append stage 4**

```python
def stage4_append_stars(repos: list[dict]) -> None:
    """Append today's (repo_id, stars) to discovery_repo_stars. Upsert on conflict. Prune >90d."""
    if not repos:
        return
    today = date.today()
    cutoff = today - timedelta(days=90)
    with _db.get_db() as cur:
        for r in repos:
            cur.execute(
                """INSERT INTO discovery_repo_stars (repo_id, date, stars)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (repo_id, date) DO UPDATE SET stars = EXCLUDED.stars""",
                (r["id"], today, r.get("stars", 0)),
            )
        cur.execute("DELETE FROM discovery_repo_stars WHERE date < %s", (cutoff,))
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage4 -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): pipeline stage 4 — stars sparkline with pruning"
```

---

## Task 12: Pipeline stage 5 — lane re-cluster (gated)

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestStage5:
    def _seed_enriched_repos(self, count: int, db):
        """Insert `count` enriched app-classified repos with recent activity."""
        from api import db as dbmod
        import json as _j
        ids = []
        with dbmod.get_db() as cur:
            for i in range(count):
                cur.execute(
                    """INSERT INTO discovery_repos
                       (owner, name, full_name, stars, classification, classification_confidence,
                        topics, exa_explainer, last_enriched_at)
                       VALUES (%s, %s, %s, %s, 'app', 0.9, %s, %s, NOW())
                       RETURNING id""",
                    ("o", f"r{i}", f"o/r{i}", 100 + i, _j.dumps(["agents"]), f"Explainer for r{i}"),
                )
                ids.append(cur.fetchone()["id"])
        return ids

    def test_gated_off_when_too_few_new_repos(self, db):
        from api.discovery import pipeline
        ids = self._seed_enriched_repos(5, db)  # <30 threshold
        result = pipeline.stage5_recluster_lanes(min_new_repos=30, max_age_days=5)
        assert result["ran"] is False

    def test_runs_when_enough_delta_and_persists_lanes(self, db, monkeypatch):
        from api.discovery import pipeline
        from api import db as dbmod

        ids = self._seed_enriched_repos(20, db)
        known = {f"o/r{i}" for i in range(20)}

        fake_cluster = {
            "hero": {"full_name": "o/r0", "blurb": "Hero blurb."},
            "lanes": [
                {"slug": f"lane-{i}", "title": f"Lane {i}", "blurb": "B",
                 "full_names": [f"o/r{i*3}", f"o/r{i*3+1}", f"o/r{i*3+2}"]}
                for i in range(1, 5)
            ],
        }
        monkeypatch.setattr("api.discovery.pipeline._cluster_lanes", lambda _: fake_cluster)

        result = pipeline.stage5_recluster_lanes(min_new_repos=10, max_age_days=5)
        assert result["ran"] is True

        with dbmod.get_db() as cur:
            cur.execute("SELECT slug, kind FROM discovery_lanes ORDER BY position")
            lanes = cur.fetchall()
        assert any(l["kind"] == "hero" for l in lanes)
        assert sum(1 for l in lanes if l["kind"] == "theme") == 4
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage5 -v`
Expected: `AttributeError: ... stage5_recluster_lanes`.

- [ ] **Step 3: Append stage 5**

```python
from api.discovery.cluster import cluster_lanes as _cluster_lanes, ClusterError, PROMPT_VERSION as _CLUSTER_PROMPT_VERSION


def stage5_recluster_lanes(
    min_new_repos: int = 30,
    max_age_days: int = 5,
    max_input_repos: int = 100,
) -> dict:
    """Re-cluster theme lanes if gate conditions are met. Idempotent.

    Gate: run if (new enriched repos since last cluster ≥ min_new_repos)
    OR (days since last cluster ≥ max_age_days).
    """
    with _db.get_db() as cur:
        # Last theme cluster generation time
        cur.execute(
            "SELECT MAX(generated_at) AS last_gen FROM discovery_lanes WHERE kind = 'theme'"
        )
        last_gen = cur.fetchone()["last_gen"]

        if last_gen is None:
            gate_ok = True  # no prior cluster → always cluster
        else:
            cur.execute(
                "SELECT COUNT(*) AS n FROM discovery_repos WHERE last_enriched_at > %s",
                (last_gen,),
            )
            new_count = cur.fetchone()["n"]
            cur.execute("SELECT EXTRACT(EPOCH FROM (NOW() - %s)) / 86400.0 AS days_old", (last_gen,))
            days_old = float(cur.fetchone()["days_old"])
            gate_ok = (new_count >= min_new_repos) or (days_old >= max_age_days)

        if not gate_ok:
            log.info("stage5 skipped: gate not satisfied")
            return {"ran": False}

        # Build input repo set
        cur.execute(
            """SELECT dr.id, dr.full_name, dr.stars, dr.exa_explainer, dr.topics,
                     COALESCE(
                       (SELECT s_today.stars - s_week.stars
                        FROM discovery_repo_stars s_today, discovery_repo_stars s_week
                        WHERE s_today.repo_id = dr.id AND s_today.date = CURRENT_DATE
                          AND s_week.repo_id = dr.id AND s_week.date = CURRENT_DATE - INTERVAL '7 days'),
                       0
                     ) AS stars_weekly_delta
               FROM discovery_repos dr
               WHERE dr.classification IS NOT NULL
                 AND dr.classification != 'library'
                 AND dr.archived_at IS NULL
               ORDER BY stars_weekly_delta DESC NULLS LAST, dr.last_enriched_at DESC
               LIMIT %s""",
            (max_input_repos,),
        )
        input_repos = [dict(r) for r in cur.fetchall()]

    if len(input_repos) < 12:
        log.warning("stage5 skipped: only %d candidate repos", len(input_repos))
        return {"ran": False, "reason": "insufficient_input"}

    try:
        cluster_result = _cluster_lanes(input_repos)
    except ClusterError as e:
        log.warning("cluster failed, keeping prior lanes: %s", e)
        return {"ran": False, "reason": "cluster_error", "error": str(e)}

    # Resolve full_names → repo_ids
    fn_to_id = {r["full_name"]: r["id"] for r in input_repos}

    with _db.get_db() as cur:
        # Replace theme + hero rows atomically
        cur.execute("DELETE FROM discovery_lanes WHERE kind IN ('hero', 'theme')")

        hero_fn = cluster_result["hero"]["full_name"]
        hero_blurb = cluster_result["hero"]["blurb"]
        hero_id = fn_to_id.get(hero_fn)
        if hero_id is None:
            log.warning("hero full_name %s not in input set — aborting", hero_fn)
            return {"ran": False, "reason": "hero_missing"}

        cur.execute(
            """INSERT INTO discovery_lanes
               (slug, title, blurb, kind, repo_ids, position, generation_meta)
               VALUES ('hero', 'Editor''s pick', %s, 'hero', %s, 0, %s)""",
            (hero_blurb, [hero_id], _json.dumps({
                "model": os.environ.get("DISCOVERY_CLUSTER_MODEL", "claude-sonnet-4-6"),
                "prompt_version": _CLUSTER_PROMPT_VERSION,
                "input_count": len(input_repos),
            })),
        )

        for pos, lane in enumerate(cluster_result["lanes"], start=1):
            repo_ids = [fn_to_id[fn] for fn in lane["full_names"] if fn in fn_to_id]
            cur.execute(
                """INSERT INTO discovery_lanes
                   (slug, title, blurb, kind, repo_ids, position, generation_meta)
                   VALUES (%s, %s, %s, 'theme', %s, %s, '{}'::jsonb)""",
                (lane["slug"], lane["title"], lane["blurb"], repo_ids, pos),
            )

    return {"ran": True, "lanes": len(cluster_result["lanes"])}
```

Also add `import os` at the top of `pipeline.py` if not already present.

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestStage5 -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): pipeline stage 5 — gated lane re-cluster"
```

---

## Task 13: Hidden Gems lane builder

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestHiddenGemsLane:
    def test_builds_from_low_star_apps(self, db):
        from api.discovery import pipeline
        from api import db as dbmod
        import json as _j

        with dbmod.get_db() as cur:
            # 5 apps under 1k stars
            for i in range(5):
                cur.execute(
                    """INSERT INTO discovery_repos
                       (owner, name, full_name, stars, classification, classification_confidence,
                        topics, exa_explainer, last_enriched_at)
                       VALUES ('gem', %s, %s, %s, 'app', 0.8, %s, 'x', NOW())""",
                    (f"g{i}", f"gem/g{i}", 100 + i * 10, _j.dumps(["agents"])),
                )
            # 1 library (should NOT appear)
            cur.execute(
                """INSERT INTO discovery_repos
                   (owner, name, full_name, stars, classification, topics, exa_explainer, last_enriched_at)
                   VALUES ('gem', 'lib1', 'gem/lib1', 500, 'library', %s, 'x', NOW())""",
                (_j.dumps(["infra"]),),
            )

        pipeline.rebuild_hidden_gems_lane()

        with dbmod.get_db() as cur:
            cur.execute("SELECT repo_ids FROM discovery_lanes WHERE kind = 'hidden_gems'")
            row = cur.fetchone()
        assert row is not None
        repo_ids = row["repo_ids"]
        assert len(repo_ids) >= 3

        with dbmod.get_db() as cur:
            cur.execute("SELECT classification FROM discovery_repos WHERE id = ANY(%s)", (repo_ids,))
            classes = [r["classification"] for r in cur.fetchall()]
        assert all(c in ("app", "hybrid") for c in classes)
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestHiddenGemsLane -v`
Expected: `AttributeError: ... rebuild_hidden_gems_lane`.

- [ ] **Step 3: Append builder**

```python
def rebuild_hidden_gems_lane(max_repos: int = 10) -> None:
    """Rebuild the single hidden_gems lane. Always present. Not LLM-clustered."""
    with _db.get_db() as cur:
        cur.execute(
            """SELECT id FROM discovery_repos
               WHERE stars < 1000
                 AND classification IN ('app', 'hybrid')
                 AND archived_at IS NULL
                 AND classification_confidence >= 0.6
               ORDER BY
                 COALESCE(
                   (SELECT s_t.stars - s_w.stars
                    FROM discovery_repo_stars s_t, discovery_repo_stars s_w
                    WHERE s_t.repo_id = discovery_repos.id AND s_t.date = CURRENT_DATE
                      AND s_w.repo_id = discovery_repos.id AND s_w.date = CURRENT_DATE - INTERVAL '7 days'),
                   0
                 )::float / GREATEST(stars, 1) DESC,
                 last_enriched_at DESC
               LIMIT %s""",
            (max_repos,),
        )
        rows = cur.fetchall()
        repo_ids = [r["id"] for r in rows]

        if not repo_ids:
            # Nothing yet — clear any existing hidden_gems row
            cur.execute("DELETE FROM discovery_lanes WHERE slug = 'hidden-gems'")
            return

        cur.execute(
            """INSERT INTO discovery_lanes
               (slug, title, blurb, kind, repo_ids, position)
               VALUES ('hidden-gems', 'Hidden gems',
                       'Small AI apps you probably missed — under 1000 stars.',
                       'hidden_gems', %s, 999)
               ON CONFLICT (slug) DO UPDATE SET
                 repo_ids = EXCLUDED.repo_ids,
                 generated_at = NOW()""",
            (repo_ids,),
        )
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestHiddenGemsLane -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): hidden gems lane builder (SQL-driven, no LLM)"
```

---

## Task 14: Pipeline orchestrator `run()`

**Files:**
- Modify: `api/discovery/pipeline.py` (append)
- Modify: `tests/discovery/test_pipeline_stages.py` (append)

- [ ] **Step 1: Append failing test**

```python
class TestPipelineRun:
    def test_orchestrates_all_stages(self, db, monkeypatch):
        from api.discovery import pipeline

        mock_gh = Mock()
        mock_gh.fetch_trending_by_topic.return_value = [
            {"full_name": "t/a", "owner": "t", "name": "a", "stars": 100,
             "language": "Python", "license": "MIT", "default_branch": "main", "description": ""}
        ]
        mock_gh.fetch_readme.return_value = ("# readme", '"e"')

        mock_exa = Mock()
        mock_exa.semantic_search.return_value = []

        monkeypatch.setattr("api.discovery.pipeline._gh_client", lambda: mock_gh)
        monkeypatch.setattr("api.discovery.pipeline._exa_client", lambda: mock_exa)
        monkeypatch.setattr(
            "api.discovery.pipeline._enrich_repo",
            lambda full_name, description, readme: {
                "explainer": "x", "classification": "app", "classification_confidence": 0.9,
                "topics": ["agents"], "install_hint": "pip",
            },
        )

        stats = pipeline.run()

        assert "fetched" in stats
        assert "enriched" in stats
        assert stats["fetched"] >= 1
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestPipelineRun -v`
Expected: `AttributeError: ... run`.

- [ ] **Step 3: Append orchestrator**

```python
def _gh_client() -> GitHubClient:
    return GitHubClient()


def _exa_client() -> ExaClient:
    return ExaClient()


def run(
    min_new_repos_for_recluster: int = 30,
    max_cluster_age_days: int = 5,
) -> dict:
    """Run the full pipeline. Returns summary stats."""
    log.info("discovery pipeline starting")
    gh = _gh_client()
    exa = _exa_client()

    # Stage 1
    candidates = stage1_fetch_candidates(gh, exa)
    log.info("stage1: %d candidates", len(candidates))

    # Stage 2
    diff = stage2_diff(candidates)
    log.info("stage2: %d new, %d existing", len(diff["new"]), len(diff["existing"]))

    # Stage 3: enrich new + existing-with-etag
    to_enrich = diff["new"] + diff["existing"]
    enrich_counts = stage3_enrich_new(to_enrich, gh)
    log.info("stage3: %s", enrich_counts)

    # Stage 4
    stage4_append_stars([{"id": r["id"], "stars": r.get("stars", 0)} for r in (diff["new"] + diff["existing"])])

    # Stage 5 (gated)
    cluster_result = stage5_recluster_lanes(min_new_repos=min_new_repos_for_recluster,
                                             max_age_days=max_cluster_age_days)
    log.info("stage5: %s", cluster_result)

    # Hidden gems — always rebuild
    rebuild_hidden_gems_lane()

    return {
        "fetched": len(candidates),
        "new": len(diff["new"]),
        "existing": len(diff["existing"]),
        "enriched": enrich_counts["enriched"],
        "skipped_etag": enrich_counts["skipped_etag"],
        "enrich_failed": enrich_counts["failed"],
        "cluster_ran": cluster_result.get("ran", False),
    }
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/discovery/test_pipeline_stages.py::TestPipelineRun -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add api/discovery/pipeline.py tests/discovery/test_pipeline_stages.py
git commit -m "feat(discovery): pipeline orchestrator run()"
```

---

## Task 15: BeautifulSoup scraping fallback

**Files:**
- Create: `api/discovery/scrape.py`
- Create: `tests/discovery/test_scrape.py`
- Create: `tests/discovery/fixtures/github_trending.html` (sample page)

- [ ] **Step 1: Grab a sample trending page for fixture**

Save this slim HTML (representative of github.com/trending structure) to `tests/discovery/fixtures/github_trending.html`:

```html
<!DOCTYPE html>
<html><body>
<article class="Box-row">
  <h2 class="h3"><a href="/vercel/ai">vercel / ai</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4">The AI Toolkit for TypeScript.</p>
  <a class="Link--muted" href="/vercel/ai/stargazers">
    <svg></svg>
    12,345
  </a>
</article>
<article class="Box-row">
  <h2 class="h3"><a href="/langchain-ai/langchain">langchain-ai / langchain</a></h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Build LLM apps.</p>
  <a class="Link--muted" href="/langchain-ai/langchain/stargazers">
    <svg></svg>
    85,000
  </a>
</article>
</body></html>
```

- [ ] **Step 2: Write failing test**

```python
# tests/discovery/test_scrape.py
from pathlib import Path

from api.discovery.scrape import parse_trending_html, fetch_trending_fallback
from unittest.mock import patch, Mock

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_trending_html():
    html = (FIXTURES / "github_trending.html").read_text()
    repos = parse_trending_html(html)
    assert len(repos) == 2
    assert repos[0]["full_name"] == "vercel/ai"
    assert repos[0]["owner"] == "vercel"
    assert repos[0]["name"] == "ai"
    assert repos[0]["stars"] == 12345
    assert repos[1]["full_name"] == "langchain-ai/langchain"


def test_fetch_trending_fallback_handles_connection_error():
    with patch("requests.get") as mock_get:
        mock_get.side_effect = RuntimeError("down")
        repos = fetch_trending_fallback()
    assert repos == []
```

- [ ] **Step 3: Run — expect ImportError**

Run: `pytest tests/discovery/test_scrape.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `scrape.py`**

```python
# api/discovery/scrape.py
"""Emergency fallback for when the GitHub API is unavailable.

Scrapes https://github.com/trending for basic repo metadata. This is lossy
compared to the API (no topics, no license, no default branch), but keeps
the lights on during outages.

Only called when pipeline detects GitHub API is down. Not a primary source.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("forge.discovery.scrape")

TRENDING_URL = "https://github.com/trending"


def parse_trending_html(html: str) -> list[dict]:
    """Parse github.com/trending HTML into normalized repo dicts."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for article in soup.select("article.Box-row"):
        link = article.select_one("h2.h3 a")
        if not link:
            continue
        href = (link.get("href") or "").strip("/")
        parts = href.split("/")
        if len(parts) < 2:
            continue
        owner, name = parts[0], parts[1]

        desc_el = article.select_one("p.col-9")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        stars = 0
        star_el = article.select_one("a.Link--muted")
        if star_el:
            star_text = star_el.get_text(strip=True).replace(",", "")
            m = re.search(r"(\d+)", star_text)
            if m:
                stars = int(m.group(1))

        out.append({
            "full_name": f"{owner}/{name}",
            "owner": owner,
            "name": name,
            "stars": stars,
            "language": None,
            "license": None,
            "default_branch": None,
            "description": desc,
        })
    return out


def fetch_trending_fallback(url: str = TRENDING_URL) -> list[dict]:
    """Fetch + parse the public trending page. Returns [] on any error."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Forge-Discovery/1.0"})
        if resp.status_code != 200:
            return []
        return parse_trending_html(resp.text)
    except Exception as e:
        log.warning("trending scrape failed: %s", e)
        return []
```

- [ ] **Step 5: Run tests — expect pass**

Run: `pytest tests/discovery/test_scrape.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add api/discovery/scrape.py tests/discovery/test_scrape.py tests/discovery/fixtures/github_trending.html
git commit -m "feat(discovery): BeautifulSoup trending fallback"
```

---

## Task 16: CLI entry — `scripts/discovery_ingest.py`

**Files:**
- Create: `scripts/discovery_ingest.py`

- [ ] **Step 1: Write CLI**

```python
# scripts/discovery_ingest.py
"""Daily discovery ingestion CLI.

Usage:
    python scripts/discovery_ingest.py               # normal daily run
    python scripts/discovery_ingest.py --backfill    # first-time backfill (no-op if data exists)
    python scripts/discovery_ingest.py --force-cluster   # skip the cluster gate

Env vars required:
    DATABASE_URL
    GITHUB_DISCOVERY_TOKEN (PAT with public_repo scope)
    EXA_API_KEY
    ANTHROPIC_API_KEY
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Make sibling package importable regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from api.discovery import pipeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="First-time backfill mode")
    ap.add_argument("--force-cluster", action="store_true", help="Bypass cluster gate")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("forge.discovery.cli")

    for var in ("GITHUB_DISCOVERY_TOKEN", "EXA_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL"):
        if not os.environ.get(var):
            log.warning("missing env var: %s", var)

    min_new = 0 if args.force_cluster else 30
    max_age = 0 if args.force_cluster else 5

    try:
        stats = pipeline.run(
            min_new_repos_for_recluster=min_new,
            max_cluster_age_days=max_age,
        )
    except Exception as e:
        log.exception("pipeline crashed: %s", e)
        return 1

    log.info("pipeline complete: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify CLI help works**

Run: `python scripts/discovery_ingest.py --help`
Expected: argparse help text showing `--backfill`, `--force-cluster`, `--verbose`.

- [ ] **Step 3: Verify import path resolution**

Run: `python -c "import runpy; runpy.run_path('scripts/discovery_ingest.py', run_name='__smoke__')"`
Expected: no errors (the `__name__ == '__main__'` guard prevents actual run).

- [ ] **Step 4: Commit**

```bash
git add scripts/discovery_ingest.py
git commit -m "feat(discovery): daily ingestion CLI with --backfill flag"
```

---

## Task 17: End-to-end integration smoke test

**Files:**
- Create: `tests/discovery/test_pipeline_e2e.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/discovery/test_pipeline_e2e.py
"""End-to-end pipeline smoke test with all external calls mocked.

Not a VCR test — VCR cassette scaffolding can come later. This ensures the
wiring works when you run the CLI against a fresh DB.
"""
from unittest.mock import Mock, patch


def test_pipeline_run_end_to_end(db, monkeypatch):
    """One full pipeline invocation against an empty DB. All external I/O mocked."""
    from api.discovery import pipeline
    from api import db as dbmod

    # Mock GitHub: one topic returns 3 repos, others return empty
    def fake_trending(topic, language=None, days=30):
        if topic == "ai" and language == "python":
            return [
                {"full_name": f"e2e/repo-{i}", "owner": "e2e", "name": f"repo-{i}",
                 "stars": 100 + i, "language": "Python", "license": "MIT",
                 "default_branch": "main", "description": f"Test repo {i}"}
                for i in range(3)
            ]
        return []

    mock_gh = Mock()
    mock_gh.fetch_trending_by_topic.side_effect = fake_trending
    mock_gh.fetch_readme.return_value = ("# readme body", '"etag"')

    mock_exa = Mock()
    mock_exa.semantic_search.return_value = []

    monkeypatch.setattr("api.discovery.pipeline._gh_client", lambda: mock_gh)
    monkeypatch.setattr("api.discovery.pipeline._exa_client", lambda: mock_exa)
    monkeypatch.setattr(
        "api.discovery.pipeline._enrich_repo",
        lambda full_name, description, readme: {
            "explainer": f"Explainer for {full_name}.",
            "classification": "app",
            "classification_confidence": 0.85,
            "topics": ["agents"],
            "install_hint": "pip",
        },
    )

    # Cluster is gated (only 3 enriched repos); test that hidden gems still builds
    stats = pipeline.run(min_new_repos_for_recluster=100, max_cluster_age_days=100)

    assert stats["fetched"] == 3
    assert stats["new"] == 3
    assert stats["enriched"] == 3
    assert stats["cluster_ran"] is False  # gated off

    with dbmod.get_db() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repos WHERE classification IS NOT NULL")
        assert cur.fetchone()["n"] == 3
        cur.execute("SELECT COUNT(*) AS n FROM discovery_repo_stars")
        assert cur.fetchone()["n"] == 3
```

- [ ] **Step 2: Run**

Run: `pytest tests/discovery/test_pipeline_e2e.py -v`
Expected: pass.

- [ ] **Step 3: Run the whole discovery suite**

Run: `pytest tests/discovery/ -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/discovery/test_pipeline_e2e.py
git commit -m "test(discovery): end-to-end pipeline smoke test"
```

---

## Self-review — what Plan 1 delivers

After Plan 1, the following is shippable and testable independently:

- Migration 024 applied; 4 new tables exist.
- Running `python scripts/discovery_ingest.py --verbose` with valid env vars populates `discovery_repos` with ~200-500 AI repos, enriches them with Haiku, writes `discovery_repo_stars`, and rebuilds the hidden_gems lane.
- After ≥30 enrichments, the lane cluster runs and writes hero + 4-6 theme lanes to `discovery_lanes`.
- Inspection via psql confirms the data model.
- `pytest tests/discovery/` passes.
- No user-visible UI yet — Plan 2 adds that.

**Spec coverage check:**
- §4 schema → Task 2 ✓
- §5 stage 1 → Task 8 ✓
- §5 stage 2 → Task 9 ✓
- §5 stage 3 → Task 10 ✓
- §5 stage 4 → Task 11 ✓
- §5 stage 5 → Task 12 ✓ (hidden gems → Task 13)
- §5 rate-limit/backoff → Task 5 ✓
- §6 secondary sources → Task 15 ✓
- §7 API — deferred to Plan 2
- §8 frontend — deferred to Plan 2
- §11 admin — deferred to Plan 3
- §13 rollout step 3 (backfill) → Task 16 (--backfill flag) ✓

**Next up:** Plan 2 (API + frontend surface).
