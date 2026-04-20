# Discovery Page — Design Spec

**Date:** 2026-04-20
**Vision alignment:** Extends VISION.md principle #4 ("Social signals drive discovery, not taxonomies") outside the team boundary — surfaces external open-source AI work as a signal channel into the Forge catalog.
**Scope:** v1 ships as a **reading surface only** (lanes + drawer + save + search). The "Add as external app" action is **locked behind v2** (disabled-CTA in drawer). See §9.

## 1. Problem

The current catalog answers *"what has my team built?"* That's correct and is Forge's moat. But users also need an answer to *"what's worth building next?"* — and today they leave Forge to answer it (GitHub Trending, Twitter, newsletters).

A Discovery page inside Forge:
- Keeps users in-product when they're between builds (sticky)
- Provides the raw input for the eventual "fork external repo → draft Forge app" flow (v2)
- Surfaces **hidden gems** — small, runnable AI apps that could *be* Forge apps but haven't broken GitHub Trending

**Explicit non-goal:** Forge is not becoming an npm/GitHub marketplace for all code (VISION.md). Discovered repos are *inputs*, not catalog entries. Nothing on this page lives in the `tools` table.

## 2. Anchor decisions (locked in during brainstorming)

- **Layout:** lanes-led editorial. Hero pick + 4–6 dynamic theme lanes + always-on Hidden Gems lane. Small search bar, not search-led.
- **Sources:** EXA semantic queries + GitHub Trending API. Haiku (not EXA contents) for explainer paragraphs and classification.
- **Cadence:** daily ingestion, append-only (diff by README ETag). Lane re-cluster only when ≥30 new repos accumulate OR >5 days since last cluster.
- **Lanes:** LLM-generated themes that shift over time. Hidden Gems lane is fixed (hand-defined semantic query).
- **Click action:** opens a detail drawer (README preview, EXA explainer paragraph, stars sparkline, actions).
- **Library handling:** show all repos. Classify each as `app` / `library` / `hybrid`. No install gate — all repos link to GitHub. Only the v2 install CTA is conditional on `app`/`hybrid`.
- **Refresh is global, saves are per-user.** One ingestion per Forge install; each user has their own saved list.
- **v1 has no personalization** (no role-aware reordering, no team intel layer). Those need real usage data.

## 3. Information architecture

**Sidebar nav** (`web/components/sidebar.tsx`): insert **Discover** between Apps and Skills. Icon: `Compass` (lucide-react).

**Routes:**
| Route | Renders |
|---|---|
| `/discover` | Main page — hero + lanes + search |
| `/discover/r/<owner>--<name>` | Detail drawer on top of `/discover` when navigated in-app (shallow routing). Direct-load renders a full standalone page with the same detail component. |
| `/discover/saved` | User's saved repos, flat grid |
| `/my-forge` | Existing page, plus a new "Saved from Discover" sub-section mirroring `/discover/saved` |

**Detail-view component** (`RepoDetailView`) is used in both drawer and full-page contexts — one component, two layouts (drawer has a close X, page has a back link + full-width layout).

## 4. Data model

Three new tables. No changes to existing tables.

```sql
-- 022_discovery.sql

CREATE TABLE discovery_repos (
    id            SERIAL PRIMARY KEY,
    owner         TEXT NOT NULL,
    name          TEXT NOT NULL,
    full_name     TEXT NOT NULL UNIQUE,           -- "owner/name"
    stars         INT NOT NULL DEFAULT 0,
    language      TEXT,
    license       TEXT,                           -- SPDX id if present
    default_branch TEXT,
    description   TEXT,                           -- from GitHub API

    -- LLM-generated (Haiku on README)
    exa_explainer TEXT,                           -- 1 paragraph, "what this is"
    classification TEXT CHECK (classification IN ('app','library','hybrid')),
    classification_confidence REAL,
    topics        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ['agents','rag',...]
    install_hint  TEXT,                           -- 'git_clone'|'pip'|'npm'|'brew'|'none'

    readme_etag   TEXT,                           -- skip re-enrich if unchanged
    archived_at   TIMESTAMPTZ,                    -- soft-delete for 404/deleted repos
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_enriched_at TIMESTAMPTZ
);
CREATE INDEX discovery_repos_topics_gin ON discovery_repos USING GIN (topics);
CREATE INDEX discovery_repos_classification ON discovery_repos (classification);
CREATE INDEX discovery_repos_last_seen ON discovery_repos (last_seen_at DESC);

CREATE TABLE discovery_repo_stars (
    repo_id INT NOT NULL REFERENCES discovery_repos(id) ON DELETE CASCADE,
    date    DATE NOT NULL,
    stars   INT NOT NULL,
    PRIMARY KEY (repo_id, date)
);
-- Prune rows older than 90 days in the daily job.

CREATE TABLE discovery_lanes (
    id           SERIAL PRIMARY KEY,
    slug         TEXT NOT NULL UNIQUE,            -- 'hero', 'hidden-gems', 'agent-frameworks', ...
    title        TEXT NOT NULL,
    blurb        TEXT,
    kind         TEXT NOT NULL CHECK (kind IN ('hero','theme','hidden_gems')),
    repo_ids     INT[] NOT NULL,                  -- ordered, usually 3–8 entries
    position     INT NOT NULL DEFAULT 0,          -- display order; hero=0, hidden_gems=999
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_meta JSONB NOT NULL DEFAULT '{}'::jsonb  -- model, prompt_version, input_count
);

CREATE TABLE user_discovery_saves (
    user_id  INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    repo_id  INT NOT NULL REFERENCES discovery_repos(id) ON DELETE CASCADE,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note     TEXT,                                -- optional user note (v2)
    PRIMARY KEY (user_id, repo_id)
);
CREATE INDEX user_discovery_saves_user ON user_discovery_saves (user_id, saved_at DESC);
```

## 5. Backend pipeline

Single daily job: `scripts/discovery_ingest.py`. Runs at 03:00 UTC. Idempotent — safe to re-run same-day. Each stage writes its output, so a crash in stage 4 doesn't require re-running stages 1–3.

### Stage 1 — Fetch raw candidates (no LLM)

**GitHub Trending** via the GitHub REST API (authenticated). Query topics: `ai`, `agents`, `llm`, `rag`, `voice`, `multimodal`, `evaluation`. Languages: `python`, `typescript`, `rust`, `go`.
- Endpoint: `GET /search/repositories?q=topic:<t>+pushed:>YYYY-MM-DD&sort=stars&order=desc`
- Auth: `GITHUB_DISCOVERY_TOKEN` env var (classic PAT, `public_repo` scope)

**EXA semantic queries** via the `exa-py` SDK. Six standing queries (tunable — see §10):
1. *"Open-source AI agent framework released or meaningfully updated in the last 90 days"*
2. *"Novel LLM evaluation or observability tool"*
3. *"Open-source RAG or retrieval system"*
4. *"Voice / speech / multimodal AI tool"*
5. *"Computer-use or browser-automation agent"*
6. *"Small-model / efficient inference tool"*

Plus one fixed **Hidden Gems** query:
- *"Standalone open-source AI application with fewer than 1000 stars, functionally complete"*

Each EXA query returns ~25 results. Daily EXA call budget: ~8 calls (6 themes + 1 hidden gems + 1 slack). Budget is enforced in code.

Write all raw hits to an in-memory candidate set, deduped by `owner/name`.

### Stage 2 — Diff

For each candidate: upsert into `discovery_repos` on `full_name`.
- If row didn't exist → flag for enrichment.
- If row exists → update `stars`, `last_seen_at`. Flag for re-enrichment **only if** README ETag has changed (checked in stage 3 via a conditional GET).

### Stage 3 — Enrich new/changed repos (Haiku)

For each flagged repo:
1. Fetch README via GitHub API with `If-None-Match: <readme_etag>` header. `304` → skip, clear the flag.
2. `200` → capture new ETag, download README body (truncate to 50KB to cap token cost).
3. Single Haiku call with JSON-mode prompt that returns:
   ```json
   {
     "explainer": "A one-paragraph description of what this is and who it's for.",
     "classification": "app" | "library" | "hybrid",
     "classification_confidence": 0.0-1.0,
     "topics": ["agents", "rag", "voice"],   // 3–5 entries, lowercase, from a fixed vocabulary
     "install_hint": "git_clone" | "pip" | "npm" | "brew" | "none"
   }
   ```
   The fixed topic vocabulary (agents, rag, voice, multimodal, eval, agents-memory, computer-use, small-models, infra, ui) lives in `api/discovery/topics.py`. Prompt instructs the model to pick from this list; unknown tags are rejected on parse.
4. Persist to `discovery_repos`. Set `last_enriched_at`.

**Cost math:** ~50 new repos/day × ~1k input tokens + ~200 output = ~60k tokens Haiku ≈ **$0.06/day**. One-time backfill on first run ≈ $0.50–2 depending on seed size.

### Stage 4 — Stars sparkline

For every repo seen in stage 1 (not just new ones): insert `(repo_id, today, stars)` into `discovery_repo_stars` with `ON CONFLICT DO UPDATE`. Prune rows older than 90 days.

### Stage 5 — Lane re-cluster (conditional)

Gate: run **only if** ≥30 repos classified since last cluster OR last cluster > 5 days ago. Otherwise skip.

1. Select input set: top 100 repos ordered by `stars_weekly_delta DESC NULLS LAST, last_enriched_at DESC`, limited to `classification != 'library'` (libraries are still shown on cards but excluded from lane-clustering to keep themes app-centric). `stars_weekly_delta` is computed at query time as `today_stars - stars_7_days_ago` from `discovery_repo_stars`; NULL when fewer than 7 days of history exist.
2. Single Sonnet call (clustering benefits from stronger model than Haiku): feed `[{full_name, explainer, topics, stars, stars_weekly_delta}]`, ask for:
   ```json
   {
     "hero": {"full_name": "...", "blurb": "..."},
     "lanes": [
       {"slug": "computer-use-agents", "title": "Computer-use agents", "blurb": "...", "full_names": [...]},
       ...
     ]
   }
   ```
3. Validate output: 4–6 lanes, each with ≥3 repos, all `full_name`s resolve in DB.
4. If validation passes → transactional update: truncate `discovery_lanes` WHERE `kind = 'theme'`, insert new rows. Hero row replaced. Hidden Gems lane untouched.
5. If validation fails → log, keep previous lanes. Admin notification (see §11).

Hidden Gems lane is rebuilt separately by the same job: take top 10 repos from the EXA Hidden Gems query with `stars < 1000` and `classification IN ('app','hybrid')`, write as a single `discovery_lanes` row with `kind='hidden_gems'`.

### Rate limiting & failure modes

- **GitHub 403/429:** exponential backoff (1m → 2m → 4m → 8m → 16m, cap). If >1h stalled, mark the job `paused_at` in a state file; next cron retry resumes. If >6h paused, admin surface shows a yellow badge.
- **EXA failure:** caught per-query. Stage 1 continues with GitHub-only candidates. Lane re-cluster still runs but with a narrower input set.
- **Haiku failure on a repo:** row stays in DB without enrichment, gets retried next day. Lanes skip un-enriched rows at render time (never show half-cards).
- **Sonnet clustering failure or validation failure:** previous lanes persist, re-cluster gated on next trigger.

## 6. Secondary sources (failover)

Scraping is a last resort, not a signal source. Two fallbacks:

- **GitHub API down but github.com up:** `scripts/discovery_scrape.py` fetches `https://github.com/trending?since=daily&spoken_language_code=en` and parses with BeautifulSoup. Produces a narrow repo list (no topic filtering, no language filter, no pagination). Feeds stage 1 as an emergency substitute. Clearly logged as `source=scrape`.
- **EXA down long-term:** fallback Hidden Gems query becomes a SQL heuristic: `SELECT * FROM discovery_repos WHERE stars < 1000 AND classification IN ('app','hybrid') ORDER BY (stars_weekly_delta::float / GREATEST(stars,1)) DESC LIMIT 10`. Crude but preserves the lane's existence.

Neither fallback is exercised in the golden path. Both are covered by tests that force-fail the primary source.

## 7. API surface

All under `api/routes/discover.py` (new blueprint, mounted at `/api/discover`).

```
GET  /api/discover/lanes
  → { hero: {...}, lanes: [{slug, title, blurb, kind, repos: [...]}], generated_at }

GET  /api/discover/repo/<full_name>
  → { repo: {...}, stars_series: [{date, stars}], saved: bool }

GET  /api/discover/search?q=<query>&limit=20
  → { results: [repo, ...] }  // EXA search scoped to the discovery_repos corpus

POST /api/discover/saves    body: { full_name }
DELETE /api/discover/saves  body: { full_name }
GET  /api/discover/saves
  → { repos: [repo, ...] }
```

Read endpoints cache at the edge for 5 minutes (lanes change ≤daily). Save endpoints bust the user's saves cache only.

## 8. Frontend

**New components** in `web/components/`:

- `discover-page.tsx` — top-level layout orchestrator
- `discover-hero.tsx` — hero pick card
- `discover-lane.tsx` — lane (title + blurb + horizontal-scroll row of `RepoCard`)
- `repo-card.tsx` — dense card (owner/name, desc, stars, language pill, save heart)
- `repo-detail-view.tsx` — the dual-mode drawer/page body
- `discover-search.tsx` — debounced search input with result overlay
- `hidden-gems-lane.tsx` — thin wrapper around `discover-lane` with gem-specific styling accents

**Reuses:**
- `Skeleton`, `Sheet`, `Button`, `Input` from `web/components/ui/` (shadcn)
- `CategoryPills` pattern for topic chips
- `AppIcon` for repo avatars (fallback to initial)
- Existing sidebar, providers, theme

**Visual idiom:** Dark surface `#0a0a10`, border `#1a1a22`, accent `#5B9FFF`, serif headline (`DM Serif Display` already loaded in Hebbia HTML — reuse in `hero-pick` title). Card hover: border lightens to `#2a2a36`, no scale. Save heart: `text-white/40` idle, `text-[#ff6b9d]` saved.

**Detail drawer UX:** opens with `shadcn/sheet` from the right, width 560px on desktop, full-screen on mobile. Closes on `esc`, backdrop click, or route back. URL updates via Next.js shallow routing (`router.push('/discover/r/...', { shallow: true })`); back button closes it cleanly.

**Install action in drawer:** rendered as a disabled button with tooltip *"Coming in v2 — will publish this repo as an external app in your Forge."* The CTA stays visible so the v2 affordance is discoverable; only the click is gated.

**Search UX:** typing in `discover-search` replaces the curated lanes with a single "Results" lane. Clearing the query restores lanes. No separate search route — it's modal-to-the-page.

## 9. Scope — v1 vs v2

**v1 (this spec):**
- Full ingestion pipeline + data model
- Discover page with hero, lanes, Hidden Gems, search, drawer
- Save / unsave + saved view + My Forge integration
- Admin surface (§11)
- Failover scraping + degraded-mode lane persistence

**v2 (deferred, not in this ship):**
- Enable the drawer's "Add as external app" action (wire existing `git_clone` `install_meta` flow — classification and install_hint are already captured in v1)
- Role-aware lane ordering
- Team intel layer ("3 teammates saved this")
- Notes on saves
- Weekly email digest of new hidden gems

## 10. Testing

**Unit:**
- `tests/discovery/test_enrich_prompt.py` — Haiku classification returns valid JSON for 20 repo README fixtures (edge cases: minimal README, CJK README, monorepo, archived repo, no README at all)
- `tests/discovery/test_cluster_prompt.py` — Sonnet clustering with `temperature=0` returns stable lanes on a fixed input (snapshot test, regenerated intentionally when prompt changes)

**Integration:**
- `tests/discovery/test_pipeline.py` — end-to-end pipeline run against VCR cassettes of EXA+GitHub+Anthropic responses. Asserts: DB state after stage 2, after stage 3, after stage 5. Asserts pruning works.
- Failover tests: force EXA to fail → pipeline completes with GitHub-only input. Force GitHub API to fail → scrape fallback activates.

**API:**
- Standard tests for all `/api/discover/*` endpoints. Auth, not-found, empty state, full state.

**Frontend:**
- Smoke test per new component (lane renders, drawer opens, save toggles).
- No e2e required for v1.

**Eval harness (optional but cheap):** `tests/discovery/eval_lanes.py` — golden set of 10 "what lane titles should look like on a representative day." Regression check on cluster prompt changes. Not run in CI; invoked manually before deploys.

## 11. Admin surface

New route `/admin/discovery` (existing admin-key gating). Shows:

- Last ingestion run timestamp + duration + stage outcomes
- Repos scanned today / new today / failed enrichment
- Current lane definitions (slug, title, blurb, repo count, generated_at)
- **"Re-cluster now"** button — forces stage 5 regardless of gate
- **"Re-enrich repo"** input — takes a `full_name`, forces re-enrichment
- Pipeline pause/resume toggle (for emergencies)
- Scrape fallback status indicator

## 12. Open questions (deferred to implementation review)

- Exact wording of the 6 standing EXA queries — will iterate based on what the first week of data surfaces. Spec includes starting drafts (§5 Stage 1); tuning happens in the code, not in this doc.
- Whether the `app`/`library`/`hybrid` dot surfaces on cards or only in the drawer — defer until we see the first real dataset; low cost to add/remove.
- Lane count target (4–6) may flex after observing real LLM output variance. Not a spec decision.
- Scraping fallback: whether the BeautifulSoup path should try trending-by-language pages or just the global trending page. Punt to implementer.

## 13. Rollout

Not user-facing until cron runs once. First-run checklist:
1. Apply migration 022.
2. Set `GITHUB_DISCOVERY_TOKEN`, `EXA_API_KEY` env vars in Forge infra.
3. Invoke `scripts/discovery_ingest.py --backfill` once manually (may take 10–20 minutes). Confirm lane output looks reasonable before exposing the route.
4. Enable the sidebar nav item (feature flag or direct merge, depending on existing practice).
5. Set cron. Monitor admin dashboard for 1 week; tune standing queries as themes become visible.

## 14. Non-goals (explicit)

- Not indexing all of GitHub — only AI-topic repos
- Not a newsreader — no X / HN / arxiv integration in v1
- Not a GitHub alternative — every card links out; nothing is forked without explicit v2 action
- Not competing with GitHub Trending — we complement it by adding semantic curation and hidden gems
- Not per-team in v1 — everyone on the same Forge install sees the same lanes
