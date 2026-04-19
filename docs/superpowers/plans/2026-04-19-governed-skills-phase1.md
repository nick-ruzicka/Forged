# Governed Skills Phase 1: Schema + Pipeline Reuse

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add review-state columns to skills, extend agent_reviews for skills, create test-case and admin-audit tables, wire the submission flow to enqueue a stubbed review pipeline, and update the API layer so the contract is final for frontend and pipeline work to proceed in parallel.

**Architecture:** Schema-first approach. Migration adds all columns/tables needed through Phase 5. API layer updated to filter by review_status and accept test sets at submission. Celery task stubbed behind a config flag so Phase 2 can wire real agents without a code deploy. Unified `create_review()` function replaces the split tool/skill pattern.

**Tech Stack:** PostgreSQL (psycopg2), Flask, Celery + Redis, pytest

**Spec:** `docs/superpowers/specs/SPEC-governed-skills-v2.md` — read before implementing.

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `db/migrations/018_governed_skills.sql` | Schema: review columns on skills, XOR on agent_reviews, skill_test_cases, skill_admin_actions |
| Modify | `api/db.py` | Unified `create_review()`, skill review queries, test-case insert/query, admin-action insert/query, `list_skills()` default filter |
| Modify | `api/models.py` | Add new Skill fields to dataclass |
| Modify | `api/server.py` | Submission accepts test set, returns `pending`, admin override endpoint, review status endpoint |
| Modify | `forge_sandbox/tasks.py` | `skill_review_pipeline` Celery task (stubbed behind flag) |
| Modify | `celery_app.py` | Autodiscover unchanged (already discovers `forge_sandbox`) |
| Modify | `tests/test_skills_api.py` | Fix tests for new default filter, add governance tests |
| Modify | `tests/conftest.py` | Add `sample_skill` fixture with `review_status='approved'` |

---

### Task 1: Migration — `018_governed_skills.sql`

**Files:**
- Create: `db/migrations/018_governed_skills.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- 018_governed_skills.sql
-- Governed skills: review state, test cases, admin audit log.
-- Rollback: see DOWN section at bottom.

-- ============================================================
-- UP
-- ============================================================

-- 1. Extend skills with review state
ALTER TABLE skills
  ADD COLUMN IF NOT EXISTS review_status     TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS review_id         INTEGER REFERENCES agent_reviews(id),
  ADD COLUMN IF NOT EXISTS version           INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS parent_skill_id   INTEGER REFERENCES skills(id),
  ADD COLUMN IF NOT EXISTS data_sensitivity  TEXT,
  ADD COLUMN IF NOT EXISTS submitted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS approved_at       TIMESTAMP,
  ADD COLUMN IF NOT EXISTS blocked_reason    TEXT,
  ADD COLUMN IF NOT EXISTS blocked_at        TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_skills_review_status ON skills(review_status);

-- 2. Make agent_reviews support both tools and skills (XOR)
ALTER TABLE agent_reviews
  ADD COLUMN IF NOT EXISTS skill_id INTEGER REFERENCES skills(id);

-- Make tool_id nullable (existing rows all have tool_id set, so this is safe)
ALTER TABLE agent_reviews
  ALTER COLUMN tool_id DROP NOT NULL;

-- XOR constraint: exactly one of tool_id or skill_id must be set.
-- Validate existing rows first — all have tool_id set, skill_id is NULL.
DO $$
DECLARE
  bad_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO bad_count
  FROM agent_reviews
  WHERE tool_id IS NULL AND skill_id IS NULL;
  IF bad_count > 0 THEN
    RAISE EXCEPTION 'Pre-migration check failed: % agent_reviews rows have neither tool_id nor skill_id', bad_count;
  END IF;
END $$;

-- Safe to add constraint now — but use NOT VALID + VALIDATE to avoid full table lock
-- on large tables. For our scale it's fine either way.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agent_reviews_target_check'
  ) THEN
    ALTER TABLE agent_reviews
      ADD CONSTRAINT agent_reviews_target_check
        CHECK ((tool_id IS NULL) <> (skill_id IS NULL));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_agent_reviews_skill_id ON agent_reviews(skill_id);

-- 3. Skill test cases (author-supplied positive/negative examples)
CREATE TABLE IF NOT EXISTS skill_test_cases (
    id          SERIAL PRIMARY KEY,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('positive', 'negative')),
    prompt      TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_test_cases_skill_id ON skill_test_cases(skill_id);

-- 4. Admin audit log for overrides and retroactive actions
CREATE TABLE IF NOT EXISTS skill_admin_actions (
    id              SERIAL PRIMARY KEY,
    skill_id        INTEGER NOT NULL REFERENCES skills(id),
    action          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    reviewer        TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skill_admin_actions_skill_id ON skill_admin_actions(skill_id);

-- 5. Backfill existing skills to 'approved' so they remain visible in catalog.
-- These were submitted before governance existed — they should not disappear.
UPDATE skills SET review_status = 'approved' WHERE review_status = 'pending';

-- ============================================================
-- DOWN (manual rollback — run these in reverse if needed)
-- ============================================================
-- DROP INDEX IF EXISTS idx_skill_admin_actions_skill_id;
-- DROP TABLE IF EXISTS skill_admin_actions;
-- DROP INDEX IF EXISTS idx_skill_test_cases_skill_id;
-- DROP TABLE IF EXISTS skill_test_cases;
-- DROP INDEX IF EXISTS idx_agent_reviews_skill_id;
-- ALTER TABLE agent_reviews DROP CONSTRAINT IF EXISTS agent_reviews_target_check;
-- ALTER TABLE agent_reviews DROP COLUMN IF EXISTS skill_id;
-- ALTER TABLE agent_reviews ALTER COLUMN tool_id SET NOT NULL;
-- DROP INDEX IF EXISTS idx_skills_review_status;
-- ALTER TABLE skills
--   DROP COLUMN IF EXISTS blocked_at,
--   DROP COLUMN IF EXISTS blocked_reason,
--   DROP COLUMN IF EXISTS approved_at,
--   DROP COLUMN IF EXISTS submitted_at,
--   DROP COLUMN IF EXISTS data_sensitivity,
--   DROP COLUMN IF EXISTS parent_skill_id,
--   DROP COLUMN IF EXISTS version,
--   DROP COLUMN IF EXISTS review_id,
--   DROP COLUMN IF EXISTS review_status;
```

- [ ] **Step 2: Verify migration applies cleanly**

Run: `psql $DATABASE_URL -f db/migrations/018_governed_skills.sql`
Expected: No errors. Run twice to verify idempotency (IF NOT EXISTS guards).

- [ ] **Step 3: Verify rollback script works**

Run the commented-out DOWN section manually against a test DB, then re-run the UP.
Expected: Clean round-trip.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/018_governed_skills.sql
git commit -m "feat(schema): add governed skills tables — review state, test cases, admin audit"
```

---

### Task 2: Unified review function + skill DB helpers in `api/db.py`

**Files:**
- Modify: `api/db.py:316-353` (agent reviews section)
- Modify: `api/db.py:368-433` (skills section)
- Test: `tests/test_skills_api.py`

- [ ] **Step 1: Write tests for the new DB functions**

Add to `tests/test_skills_api.py`:

```python
def test_create_review_for_skill(db):
    """create_review('skill', id) creates an agent_reviews row with skill_id set."""
    from api import db as forge_db
    # Insert a skill first
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_skills_api.py::test_create_review_for_skill tests/test_skills_api.py::test_create_review_for_tool tests/test_skills_api.py::test_list_skills_default_filter_approved_only tests/test_skills_api.py::test_insert_skill_test_cases -v`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Add unified `create_review` and skill review helpers to `api/db.py`**

Replace the agent reviews section (`api/db.py` starting at line 316) and extend the skills section:

```python
# -------- Agent reviews (unified for tools + skills) --------

def create_review(target_id: int, target_type: str) -> int:
    """Create an agent_reviews row for a tool or skill.

    target_type must be 'tool' or 'skill'. The XOR constraint in the DB
    enforces that exactly one of tool_id/skill_id is set.
    """
    if target_type not in ("tool", "skill"):
        raise ValueError(f"target_type must be 'tool' or 'skill', got {target_type!r}")
    col = "tool_id" if target_type == "tool" else "skill_id"
    with get_db() as cur:
        cur.execute(
            f"INSERT INTO agent_reviews ({col}) VALUES (%s) RETURNING id",
            (target_id,),
        )
        row = cur.fetchone()
        return row["id"]


def create_agent_review(tool_id: int) -> int:
    """Backward-compatible wrapper. Prefer create_review(id, 'tool')."""
    return create_review(tool_id, "tool")


def update_agent_review(review_id: int, **fields):
    if not fields:
        return
    safe = {}
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            safe[k] = json.dumps(v)
        else:
            safe[k] = v
    sets = ", ".join(f"{k} = %s" for k in safe.keys())
    values = list(safe.values()) + [review_id]
    with get_db(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE agent_reviews SET {sets} WHERE id = %s", values
        )


def get_agent_review_by_tool(tool_id: int):
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM agent_reviews WHERE tool_id = %s "
            "ORDER BY id DESC LIMIT 1",
            (tool_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_review_by_skill(skill_id: int):
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM agent_reviews WHERE skill_id = %s "
            "ORDER BY id DESC LIMIT 1",
            (skill_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
```

Update `list_skills` to default-filter to `approved`:

```python
def list_skills(category: str = None, search: str = None, sort: str = "upvotes",
                review_status: str = "approved"):
    where = []
    params = []
    if review_status:
        where.append("review_status = %s")
        params.append(review_status)
    if category and category != "All":
        where.append("category = %s")
        params.append(category)
    if search:
        where.append("(title ILIKE %s OR description ILIKE %s OR use_case ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_by = {
        "newest": "created_at DESC",
        "copies": "copy_count DESC, upvotes DESC",
        "upvotes": "upvotes DESC, created_at DESC",
    }.get(sort, "upvotes DESC, created_at DESC")
    with get_db() as cur:
        cur.execute(
            f"SELECT * FROM skills {where_sql} ORDER BY {order_by}",
            params,
        )
        return [dict(r) for r in cur.fetchall()]
```

Add test-case and admin-action helpers:

```python
# -------- Skill test cases --------

def insert_skill_test_cases(skill_id: int, cases: list):
    """Insert author-supplied test cases for a skill.

    cases: list of {"kind": "positive"|"negative", "prompt": str}
    """
    with get_db(dict_cursor=False) as cur:
        for case in cases:
            cur.execute(
                "INSERT INTO skill_test_cases (skill_id, kind, prompt) VALUES (%s, %s, %s)",
                (skill_id, case["kind"], case["prompt"]),
            )


def get_skill_test_cases(skill_id: int) -> list:
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM skill_test_cases WHERE skill_id = %s ORDER BY kind, id",
            (skill_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# -------- Skill admin actions --------

def insert_skill_admin_action(skill_id: int, action: str, reason: str,
                               reviewer: str, from_status: str = None,
                               to_status: str = None) -> int:
    with get_db() as cur:
        cur.execute(
            """INSERT INTO skill_admin_actions
               (skill_id, action, reason, reviewer, from_status, to_status)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (skill_id, action, reason, reviewer, from_status, to_status),
        )
        row = cur.fetchone()
        return row["id"]


def list_skill_admin_actions(skill_id: int) -> list:
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM skill_admin_actions WHERE skill_id = %s ORDER BY created_at DESC",
            (skill_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def update_skill(skill_id: int, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [skill_id]
    with get_db(dict_cursor=False) as cur:
        cur.execute(f"UPDATE skills SET {sets} WHERE id = %s", values)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_skills_api.py -v`
Expected: All new tests PASS. Existing tests may still fail (fixed in Task 5).

- [ ] **Step 5: Commit**

```bash
git add api/db.py tests/test_skills_api.py
git commit -m "feat(db): unified create_review, skill test cases, admin actions, approved-only default"
```

---

### Task 3: Update `Skill` model in `api/models.py`

**Files:**
- Modify: `api/models.py:147-168`

- [ ] **Step 1: Add new fields to the Skill dataclass**

Update the `Skill` class at `api/models.py:148`:

```python
@dataclass
class Skill:
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    prompt_text: Optional[str] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    author_name: Optional[str] = None
    upvotes: int = 0
    copy_count: int = 0
    featured: bool = False
    source_url: Optional[str] = None

    # Governance (migration 018)
    review_status: str = "pending"
    review_id: Optional[int] = None
    version: int = 1
    parent_skill_id: Optional[int] = None
    data_sensitivity: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None

    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Skill":
        return cls(**_filter_known(cls, _row_to_dict(row, cursor)))

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: _serialize(getattr(self, f.name)) for f in dc_fields(self)}
```

- [ ] **Step 2: Verify model hydrates correctly**

Run: `python -c "from api.models import Skill; s = Skill.from_row({'id': 1, 'title': 'test', 'review_status': 'approved', 'prompt_text': 'p'}); print(s.to_dict())"`
Expected: Dict includes `review_status: 'approved'` and all new fields with defaults.

- [ ] **Step 3: Commit**

```bash
git add api/models.py
git commit -m "feat(models): add governance fields to Skill dataclass"
```

---

### Task 4: Stubbed Celery pipeline task in `forge_sandbox/tasks.py`

**Files:**
- Modify: `forge_sandbox/tasks.py`
- Test: `tests/test_skills_api.py`

- [ ] **Step 1: Write a test for the stubbed pipeline**

Add to `tests/test_skills_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_skills_api.py::test_skill_review_pipeline_stub_approves -v`
Expected: FAIL — function doesn't exist.

- [ ] **Step 3: Implement the stubbed pipeline task**

Replace `forge_sandbox/tasks.py`:

```python
"""
Celery wrapper for sandbox lifecycle jobs and skill review pipeline.

Registered via autodiscovery (see celery_app.py). The beat schedule entry
"hibernate-idle-containers" calls hibernate_idle every 5 minutes.
"""
from __future__ import annotations

import os

from celery_app import celery_app


@celery_app.task(name="forge_sandbox.tasks.hibernate_idle")
def hibernate_idle() -> dict:
    try:
        from forge_sandbox.manager import SandboxManager
        return {"hibernated": SandboxManager().hibernate_idle_containers()}
    except Exception as e:
        return {"error": str(e)}


@celery_app.task(name="forge_sandbox.tasks.skill_review_pipeline")
def skill_review_pipeline(skill_id: int) -> dict:
    """Run the 6-agent review pipeline on a submitted skill.

    Controlled by SKILL_REVIEW_MODE env var:
    - 'stub' (default): auto-approve immediately. For Phase 1.
    - 'real': run actual agents. Wired in Phase 2.
    """
    from datetime import datetime

    from api import db

    mode = os.environ.get("SKILL_REVIEW_MODE", "stub")

    skill = db.get_skill(skill_id)
    if not skill:
        return {"error": f"skill {skill_id} not found"}

    # Create the review row
    review_id = db.create_review(skill_id, "skill")

    if mode == "stub":
        # Auto-approve: write passing results to the review row
        db.update_agent_review(review_id,
            classifier_output="auto-classified (stub)",
            detected_category=skill.get("category") or "other",
            classification_confidence=1.0,
            security_flags="none",
            pii_risk=False,
            injection_risk=False,
            data_exfil_risk=False,
            red_team_attacks_succeeded=0,
            attacks_attempted=0,
            attacks_succeeded=0,
            qa_pass_rate=1.0,
            agent_recommendation="approve",
            agent_confidence=1.0,
            review_summary="Auto-approved (stub mode, Phase 1)",
            completed_at=datetime.utcnow(),
        )
        db.update_skill(skill_id,
            review_status="approved",
            review_id=review_id,
            approved_at=datetime.utcnow(),
        )
        return {"skill_id": skill_id, "review_id": review_id, "review_status": "approved"}

    # mode == 'real' — Phase 2 wires this path
    # classifier -> security_scanner -> red_team -> prompt_hardener -> qa_tester -> synthesizer
    raise NotImplementedError(
        f"Real review pipeline not yet implemented (SKILL_REVIEW_MODE={mode}). "
        "Set SKILL_REVIEW_MODE=stub or implement Phase 2."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_skills_api.py::test_skill_review_pipeline_stub_approves -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forge_sandbox/tasks.py tests/test_skills_api.py
git commit -m "feat(pipeline): stubbed skill_review_pipeline behind SKILL_REVIEW_MODE flag"
```

---

### Task 5: Update API endpoints in `api/server.py`

**Files:**
- Modify: `api/server.py:1482-1548` (skills section)

- [ ] **Step 1: Write tests for updated submission and new endpoints**

Add to `tests/test_skills_api.py`:

```python
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
    from api import db as forge_db
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_skills_api.py::test_submit_skill_returns_pending tests/test_skills_api.py::test_submit_skill_without_test_cases_still_works tests/test_skills_api.py::test_get_skill_review_status tests/test_skills_api.py::test_admin_override_skill -v`
Expected: FAIL

- [ ] **Step 3: Update the skills section in `api/server.py`**

Replace the skills section starting at line 1482:

```python
# -------------------- Skills --------------------

@app.route("/api/skills", methods=["GET"])
def list_skills():
    category = request.args.get("category")
    search = request.args.get("search")
    # Admin can see all statuses; default is approved-only
    include = request.args.get("include")
    if include == "pending":
        admin_check = _require_admin()
        if admin_check:
            return admin_check
        review_status = None  # no filter — show all
    else:
        review_status = "approved"
    rows = db.list_skills(category=category, search=search, review_status=review_status)
    return jsonify({
        "skills": [Skill.from_row(r).to_dict() for r in rows],
        "count": len(rows),
    })


@app.route("/api/skills", methods=["POST"])
def submit_skill():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    prompt_text = (body.get("prompt_text") or "").strip()
    if not title:
        return jsonify({"error": "validation", "message": "title required"}), 400
    if not prompt_text:
        return jsonify({"error": "validation", "message": "prompt_text required"}), 400

    data = {
        "title": title,
        "description": body.get("description") or "",
        "prompt_text": prompt_text,
        "category": body.get("category") or "other",
        "use_case": body.get("use_case") or "",
        "author_name": body.get("author_name") or "",
        "source_url": body.get("source_url") or "",
        "review_status": "pending",
    }

    # Handle data_sensitivity if provided
    sensitivity = body.get("data_sensitivity")
    if sensitivity and sensitivity in ("public", "internal", "confidential"):
        data["data_sensitivity"] = sensitivity

    skill_id = db.insert_skill(data)

    # Store author-supplied test cases if provided
    test_cases_raw = body.get("test_cases")
    if test_cases_raw and isinstance(test_cases_raw, dict):
        cases = []
        for prompt in (test_cases_raw.get("positive") or []):
            cases.append({"kind": "positive", "prompt": prompt})
        for prompt in (test_cases_raw.get("negative") or []):
            cases.append({"kind": "negative", "prompt": prompt})
        if cases:
            db.insert_skill_test_cases(skill_id, cases)

    # Enqueue the review pipeline
    try:
        from forge_sandbox.tasks import skill_review_pipeline
        skill_review_pipeline.delay(skill_id)
    except Exception as exc:
        # Pipeline enqueue failed — skill stays pending, log the error.
        # Fail-closed: skill remains in 'pending' until pipeline runs.
        print(f"[server] skill_review_pipeline enqueue failed for skill {skill_id}: {exc}")

    return jsonify({"skill_id": skill_id, "status": "pending"}), 201


@app.route("/api/skills/<int:skill_id>/review", methods=["GET"])
def get_skill_review(skill_id):
    """Return review status and feedback for a skill."""
    skill = db.get_skill(skill_id)
    if not skill:
        return jsonify({"error": "not_found"}), 404

    result = {
        "skill_id": skill_id,
        "review_status": skill.get("review_status", "pending"),
        "review_id": skill.get("review_id"),
        "blocked_reason": skill.get("blocked_reason"),
        "approved_at": skill["approved_at"].isoformat() if skill.get("approved_at") else None,
        "blocked_at": skill["blocked_at"].isoformat() if skill.get("blocked_at") else None,
    }

    # Include review details if a review exists
    if skill.get("review_id"):
        review = db.get_review_by_skill(skill_id)
        if review:
            result["review"] = {
                "recommendation": review.get("agent_recommendation"),
                "confidence": review.get("agent_confidence"),
                "summary": review.get("review_summary"),
            }

    # Include test cases
    result["test_cases"] = db.get_skill_test_cases(skill_id)

    return jsonify(result)


@app.route("/api/admin/skills/<int:skill_id>/override", methods=["POST"])
def admin_override_skill(skill_id):
    """Admin override: approve, block, retroactively block, or unblock a skill."""
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized

    skill = db.get_skill(skill_id)
    if not skill:
        return jsonify({"error": "not_found"}), 404

    body = request.get_json(silent=True) or {}
    action = body.get("action")
    reason = (body.get("reason") or "").strip()

    valid_actions = {"override_approve", "override_block", "retroactive_block", "unblock", "manual_rereview"}
    if action not in valid_actions:
        return jsonify({"error": "validation", "message": f"action must be one of {sorted(valid_actions)}"}), 400
    if len(reason) < 20:
        return jsonify({"error": "validation", "message": "reason must be at least 20 characters"}), 400

    from_status = skill.get("review_status")

    # Determine new status
    status_map = {
        "override_approve": "approved",
        "override_block": "blocked",
        "retroactive_block": "blocked",
        "unblock": "approved",
        "manual_rereview": "pending",
    }
    to_status = status_map[action]

    # Update skill
    update_fields = {"review_status": to_status}
    if to_status == "approved":
        from datetime import datetime as dt
        update_fields["approved_at"] = dt.utcnow()
        update_fields["blocked_reason"] = None
        update_fields["blocked_at"] = None
    elif to_status == "blocked":
        from datetime import datetime as dt
        update_fields["blocked_reason"] = f"{action}:{reason}"
        update_fields["blocked_at"] = dt.utcnow()

    db.update_skill(skill_id, **update_fields)

    # Log the admin action
    reviewer = request.headers.get("X-Admin-User", "admin")
    db.insert_skill_admin_action(
        skill_id=skill_id,
        action=action,
        reason=reason,
        reviewer=reviewer,
        from_status=from_status,
        to_status=to_status,
    )

    # If manual_rereview, enqueue pipeline again
    if action == "manual_rereview":
        try:
            from forge_sandbox.tasks import skill_review_pipeline
            skill_review_pipeline.delay(skill_id)
        except Exception as exc:
            print(f"[server] re-review enqueue failed for skill {skill_id}: {exc}")

    return jsonify({
        "skill_id": skill_id,
        "review_status": to_status,
        "action": action,
    })
```

Keep the existing upvote/copy/download endpoints unchanged (they still work on approved skills).

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_skills_api.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/server.py tests/test_skills_api.py
git commit -m "feat(api): skill submission returns pending, admin override endpoint, review status endpoint"
```

---

### Task 6: Fix existing tests for new default filter

**Files:**
- Modify: `tests/test_skills_api.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add `sample_skill` fixture to `tests/conftest.py`**

Add after the `sample_run` fixture:

```python
@pytest.fixture
def sample_skill(db):
    """Insert and return an approved skill."""
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category,
                                   use_case, author_name, review_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            ("Test Skill", "desc", "Do X", "research", "research accounts", "A", "approved"),
        )
        result = cur.fetchone()
        if isinstance(result, tuple):
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, result))
        return dict(result) if result else None
```

- [ ] **Step 2: Fix `test_list_skills_returns_200` to insert an approved skill**

Update the test at `tests/test_skills_api.py:5`:

```python
def test_list_skills_returns_200(client, db):
    """GET /api/skills returns an array of approved skills."""
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO skills (title, description, prompt_text, category, use_case, author_name, review_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            ("Test Skill", "desc", "Do X", "research", "research accounts", "A", "approved"),
        )
    resp = client.get("/api/skills")
    if resp.status_code == 404:
        pytest.skip("GET /api/skills not implemented yet (T1)")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    items = payload.get("skills", payload if isinstance(payload, list) else [])
    assert len(items) >= 1
```

- [ ] **Step 3: Fix `test_list_skills_sort_by_copies` to use approved skills**

Update the test at `tests/test_skills_api.py:143`:

```python
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
```

- [ ] **Step 4: Fix `test_submit_skill_valid_returns_201` to expect new response shape**

Update the test at `tests/test_skills_api.py:22`:

```python
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
    data = resp.get_json()
    assert data["status"] == "pending"
    assert "skill_id" in data
```

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/test_skills_api.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_skills_api.py tests/conftest.py
git commit -m "fix(tests): update skills tests for approved-only default filter and new response shape"
```

---

### Task 7: End-to-end verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -40`
Expected: All skills tests pass. No regressions in other tests.

- [ ] **Step 2: Verify migration is idempotent**

Run: `psql $DATABASE_URL -f db/migrations/018_governed_skills.sql && psql $DATABASE_URL -f db/migrations/018_governed_skills.sql`
Expected: Both runs succeed without errors.

- [ ] **Step 3: Verify the stub pipeline approves a skill end-to-end**

Run in Python:
```python
import os
os.environ["SKILL_REVIEW_MODE"] = "stub"
from api import db
db.init_db()

# Submit a skill
skill_id = db.insert_skill({
    "title": "E2E Test Skill",
    "prompt_text": "Do the thing",
    "category": "research",
    "review_status": "pending",
})
print(f"Inserted skill {skill_id}, status=pending")

# Run pipeline directly (not via Celery broker)
from forge_sandbox.tasks import skill_review_pipeline
result = skill_review_pipeline(skill_id)
print(f"Pipeline result: {result}")

# Verify
skill = db.get_skill(skill_id)
print(f"Final status: {skill['review_status']}")
assert skill["review_status"] == "approved"
assert skill["review_id"] is not None
print("E2E verification passed.")
```

Expected: `E2E verification passed.`

- [ ] **Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: address any issues found during e2e verification"
```

---

## Phase 1 Done State

Phase 1 is complete when:
1. Migration `018` applies cleanly and is idempotent
2. `GET /api/skills` returns only `approved` skills
3. `POST /api/skills` returns `{"skill_id": N, "status": "pending"}` and enqueues pipeline
4. Stubbed pipeline (with `SKILL_REVIEW_MODE=stub`) auto-approves the skill
5. `GET /api/skills/:id/review` returns review status and feedback
6. `POST /api/admin/skills/:id/override` changes status and logs to `skill_admin_actions`
7. All existing tests pass with the new default filter
8. `skill_test_cases` table exists and accepts author-supplied test cases

Next: Phase 2 (QA harness — real agents behind the `SKILL_REVIEW_MODE=real` flag).
