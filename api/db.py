"""
Database layer for the Forge platform.
PostgreSQL via psycopg2. No ORM.
"""
import glob
import json
import os
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://forge:forge@localhost:5432/forge"
)

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "db",
    "migrations",
)


def _connect_with_retry(attempts: int = 3, delay: float = 1.0):
    last_err = None
    for i in range(attempts):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False
            return conn
        except psycopg2.Error as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(delay)
    raise last_err


def get_connection():
    return _connect_with_retry()


@contextmanager
def get_db(dict_cursor: bool = True):
    """Context manager yielding cursor; commits on exit, rolls back on error."""
    conn = _connect_with_retry()
    cur = None
    try:
        if dict_cursor:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


@contextmanager
def cursor(dict_cursor: bool = True):
    """Backward-compatible alias for get_db()."""
    with get_db(dict_cursor=dict_cursor) as cur:
        yield cur


def init_db():
    """Run every .sql file in db/migrations/ in alphabetical order."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    conn = _connect_with_retry()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        for path in files:
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            if sql.strip():
                cur.execute(sql)
        cur.close()
    finally:
        conn.close()


# -------- Tool helpers --------

def get_tool(tool_id: int):
    with get_db() as cur:
        cur.execute("SELECT * FROM tools WHERE id = %s", (tool_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_tool_by_slug(slug: str):
    with get_db() as cur:
        cur.execute("SELECT * FROM tools WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_tool_by_access_token(token: str):
    with get_db() as cur:
        cur.execute("SELECT * FROM tools WHERE access_token = %s", (token,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_tool(tool_id: int, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [tool_id]
    with get_db(dict_cursor=False) as cur:
        cur.execute(f"UPDATE tools SET {sets} WHERE id = %s", values)


def list_tools(
    status: str = None,
    category: str = None,
    output_type: str = None,
    trust_tier: str = None,
    search: str = None,
    sort: str = "popular",
    page: int = 1,
    limit: int = 12,
    app_type: str = None,
):
    where = []
    params = []
    if status:
        where.append("status = %s")
        params.append(status)
    if category and category != "All":
        where.append("category = %s")
        params.append(category)
    if output_type:
        where.append("output_type = %s")
        params.append(output_type)
    if trust_tier:
        where.append("trust_tier = %s")
        params.append(trust_tier)
    if app_type:
        where.append("app_type = %s")
        params.append(app_type)
    if search:
        where.append(
            "(name ILIKE %s OR tagline ILIKE %s OR description ILIKE %s OR category ILIKE %s)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    order_by = {
        "popular": "run_count DESC NULLS LAST, created_at DESC",
        "newest": "created_at DESC",
        "rating": "avg_rating DESC NULLS LAST, run_count DESC",
        "az": "name ASC",
    }.get(sort, "run_count DESC NULLS LAST, created_at DESC")

    offset = max(0, (page - 1) * limit)

    sql = f"SELECT * FROM tools {where_sql} ORDER BY {order_by} LIMIT %s OFFSET %s"
    count_sql = f"SELECT COUNT(*) AS c FROM tools {where_sql}"

    with get_db() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]
        cur.execute(sql, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]
    return rows, total


def insert_tool(data: dict) -> int:
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)
    values = list(data.values())
    with get_db() as cur:
        cur.execute(
            f"INSERT INTO tools ({col_sql}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        row = cur.fetchone()
        return row["id"]


def slug_exists(slug: str) -> bool:
    with get_db() as cur:
        cur.execute("SELECT 1 FROM tools WHERE slug = %s", (slug,))
        return cur.fetchone() is not None


def recompute_avg_rating(tool_id: int):
    with get_db(dict_cursor=False) as cur:
        cur.execute(
            """UPDATE tools
               SET avg_rating = COALESCE(
                   (SELECT AVG(rating)::real FROM runs
                    WHERE tool_id = %s AND rating IS NOT NULL), 0)
               WHERE id = %s""",
            (tool_id, tool_id),
        )


def increment_run_count(tool_id: int):
    with get_db(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE tools SET run_count = run_count + 1, last_run_at = NOW() WHERE id = %s",
            (tool_id,),
        )


def increment_flag_count(tool_id: int) -> int:
    with get_db() as cur:
        cur.execute(
            "UPDATE tools SET flag_count = flag_count + 1 WHERE id = %s RETURNING flag_count",
            (tool_id,),
        )
        row = cur.fetchone()
        return row["flag_count"] if row else 0


# -------- Tool versions --------

def insert_tool_version(tool_id: int, version: int, system_prompt: str,
                         hardened_prompt: str, input_schema: str,
                         change_summary: str, created_by: str) -> int:
    with get_db() as cur:
        cur.execute(
            """INSERT INTO tool_versions
               (tool_id, version, system_prompt, hardened_prompt,
                input_schema, change_summary, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (tool_id, version, system_prompt, hardened_prompt,
             input_schema, change_summary, created_by),
        )
        row = cur.fetchone()
        return row["id"]


def list_tool_versions(tool_id: int):
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM tool_versions WHERE tool_id = %s ORDER BY version DESC",
            (tool_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# -------- Runs --------

def insert_run(data: dict) -> int:
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)
    values = list(data.values())
    with get_db() as cur:
        cur.execute(
            f"INSERT INTO runs ({col_sql}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        row = cur.fetchone()
        return row["id"]


def get_run(run_id: int):
    with get_db() as cur:
        cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_run(run_id: int, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields.keys())
    values = list(fields.values()) + [run_id]
    with get_db(dict_cursor=False) as cur:
        cur.execute(f"UPDATE runs SET {sets} WHERE id = %s", values)


def list_recent_runs(tool_id: int, limit: int = 20):
    with get_db() as cur:
        cur.execute(
            """SELECT id, tool_id, rating, user_name, source,
                      run_duration_ms, created_at, output_flagged
               FROM runs WHERE tool_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (tool_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_recent_flagged_runs(tool_id: int, limit: int = 10):
    with get_db() as cur:
        cur.execute(
            """SELECT * FROM runs
               WHERE tool_id = %s AND output_flagged = TRUE
               ORDER BY created_at DESC LIMIT %s""",
            (tool_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def count_runs_by_ip(ip: str, since_timestamp: float) -> int:
    # IP not stored in schema; rate limit is enforced in-memory in server.py.
    return 0


# -------- Agent reviews --------

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


def get_underperforming_tools(min_flags: int = 2, max_rating: float = 3.0):
    with get_db() as cur:
        cur.execute(
            """SELECT * FROM tools
               WHERE status = 'approved'
                 AND flag_count >= %s
                 AND avg_rating <= %s""",
            (min_flags, max_rating),
        )
        return [dict(r) for r in cur.fetchall()]


# -------- Skills --------

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


def insert_skill(data: dict) -> int:
    cols = list(data.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)
    values = list(data.values())
    with get_db() as cur:
        cur.execute(
            f"INSERT INTO skills ({col_sql}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        row = cur.fetchone()
        return row["id"]


def increment_skill_upvotes(skill_id: int):
    with get_db(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE skills SET upvotes = upvotes + 1 WHERE id = %s RETURNING upvotes",
            (skill_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def increment_skill_copy_count(skill_id: int):
    with get_db(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE skills SET copy_count = copy_count + 1 WHERE id = %s RETURNING copy_count",
            (skill_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_skill(skill_id: int):
    with get_db() as cur:
        cur.execute("SELECT * FROM skills WHERE id = %s", (skill_id,))
        row = cur.fetchone()
        return dict(row) if row else None


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
