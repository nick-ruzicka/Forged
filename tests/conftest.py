"""
Shared pytest fixtures for the Forge test suite.

Fixtures provided:
- app():                Flask application configured for testing
- client():             Flask test client bound to ``app``
- db():                 Creates the schema in a fresh PostgreSQL database and
                        tears it down after the test
- sample_tool():        Inserts an approved tool and yields its row
- sample_pending_tool():Inserts a pending tool and yields its row
- sample_run():         Inserts a run for ``sample_tool`` and yields its row
- admin_headers():      dict containing the X-Admin-Key header
"""
import json
import os
import uuid

import pytest

# Force Flask to load in testing mode before the application is imported so that
# configuration paths that inspect FLASK_ENV / TESTING pick up the right values.
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://forge:forge@localhost:5432/forge_test",
    ),
)
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-placeholder")


# ---------------------------------------------------------------------------
# Flask app / client fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    """Return the Flask application for testing.

    If ``api.server`` is missing (T1 has not landed yet) we build a tiny stand-in
    Flask app so the rest of the suite can still collect. All tests that rely on
    real routes should therefore either skip or be rewritten once server.py
    lands.
    """
    try:
        from api.server import app as flask_app  # type: ignore
    except Exception:  # pragma: no cover - T1 hasn't shipped server.py yet
        from flask import Flask
        flask_app = Flask(__name__)

    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def db():
    """Create the Forge schema in a test database and tear it down afterwards.

    This fixture looks for db/migrations/*.sql, executes them in alphabetical
    order, yields a connection (via api.db.get_connection), and then drops
    every created table inside a ``finally`` block.
    """
    import glob
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        pytest.skip("psycopg2 is not installed; cannot run DB-backed tests")

    try:
        from api import db as forge_db  # type: ignore
    except Exception:  # pragma: no cover - T1 not ready
        forge_db = None

    # Apply migrations.
    migrations_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "db", "migrations",
    )
    conn = None
    try:
        if forge_db is not None:
            conn = forge_db.get_connection()
        else:
            conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = True
    except Exception:
        # If the DB is genuinely unavailable, skip rather than hard-fail.
        pytest.skip("PostgreSQL is not available for the test database")

    # Apply migrations per-file with try/except, mirroring api/db.py:init_db.
    # Some migrations are intentionally order-sensitive in a way that only
    # resolves later (e.g. 020 references agent_reviews which is recreated
    # by 021). Aborting on the first failure would skip every test; instead
    # we log-and-continue, matching production init_db semantics.
    if os.path.isdir(migrations_dir):
        for path in sorted(glob.glob(os.path.join(migrations_dir, "*.sql"))):
            with open(path, "r") as fh:
                sql = fh.read()
            if not sql.strip():
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
            except Exception as exc:
                print(f"[conftest] migration {os.path.basename(path)} failed: {exc}")

    try:
        yield conn
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DO $$ DECLARE
                      r RECORD;
                    BEGIN
                      FOR r IN (
                        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
                      ) LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                      END LOOP;
                    END $$;
                    """
                )
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool / run fixtures
# ---------------------------------------------------------------------------
def _insert_tool(db, **overrides):
    slug = overrides.pop("slug", f"tool-{uuid.uuid4().hex[:8]}")
    row = {
        "slug": slug,
        "name": overrides.pop("name", "Test Tool"),
        "tagline": overrides.pop("tagline", "A tool used by the test suite"),
        "description": overrides.pop("description", "Test description"),
        "category": overrides.pop("category", "other"),
        "app_type": overrides.pop("app_type", "app"),
        "app_html": overrides.pop("app_html", "<html><body>test</body></html>"),
        "status": overrides.pop("status", "approved"),
        "author_name": overrides.pop("author_name", "Test Author"),
        "author_email": overrides.pop("author_email", "test@navan.com"),
    }
    row.update(overrides)

    cols = ", ".join(row.keys())
    placeholders = ", ".join(["%s"] * len(row))
    with db.cursor() as cur:
        cur.execute(
            f"INSERT INTO tools ({cols}) VALUES ({placeholders}) RETURNING *",
            list(row.values()),
        )
        result = cur.fetchone()
        if isinstance(result, tuple):
            cur.execute(
                "SELECT * FROM tools WHERE slug = %s", (row["slug"],),
            )
            return dict(zip([d[0] for d in cur.description], cur.fetchone()))
        return dict(result) if result else None


@pytest.fixture
def sample_tool(db):
    """Insert and return an approved tool."""
    return _insert_tool(db, status="approved")


@pytest.fixture
def sample_pending_tool(db):
    """Insert and return a pending tool (status='pending_review').

    The admin queue filters on ('pending_review', 'agent_reviewing', 'submitted'),
    so we use 'pending_review' to ensure admin tests find it.
    """
    return _insert_tool(db, status="pending_review", slug=f"pending-{uuid.uuid4().hex[:6]}")


@pytest.fixture
def sample_run(db, sample_tool):
    """Insert a run for ``sample_tool`` and return its row."""
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO runs (tool_id, input_data, output_data, user_name, user_email)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING *""",
            (
                sample_tool["id"],
                json.dumps({"query": "hello"}),
                "hello world",
                "Test User",
                "user@navan.com",
            ),
        )
        result = cur.fetchone()
        if isinstance(result, tuple):
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, result))
        return dict(result) if result else None


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


@pytest.fixture
def admin_headers():
    """Return the X-Admin-Key header dictionary."""
    return {"X-Admin-Key": os.environ.get("ADMIN_KEY", "test-admin-key")}
