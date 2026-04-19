"""Verify migration 018 installs the install-discovery schema correctly."""
import pytest


def test_tools_has_app_bundle_id_column(db):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'tools' AND column_name = 'app_bundle_id'
            """
        )
        row = cur.fetchone()
    assert row is not None, "tools.app_bundle_id missing"
    nullable = row[1] if isinstance(row, tuple) else row["is_nullable"]
    assert nullable == "YES"


def test_tools_has_partial_index_on_bundle_id(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'tools' AND indexname = 'tools_bundle_id_idx'"
        )
        assert cur.fetchone() is not None


@pytest.mark.parametrize("col,default", [
    ("source", "manual"),
    ("hidden", "false"),
    ("detected_bundle_id", None),
    ("detected_name", None),
])
def test_user_items_has_new_columns(db, col, default):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_name = 'user_items' AND column_name = %s
            """,
            (col,),
        )
        row = cur.fetchone()
    assert row is not None, f"user_items.{col} missing"


def test_user_items_tool_id_is_nullable(db):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'user_items' AND column_name = 'tool_id'
            """
        )
        row = cur.fetchone()
    nullable = row[0] if isinstance(row, tuple) else row["is_nullable"]
    assert nullable == "YES", "tool_id should be NULL-able for unknown-app rows"


def test_user_items_detected_unique_index_exists(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'user_items' AND indexname = 'user_items_detected_unique'"
        )
        assert cur.fetchone() is not None


def test_can_insert_unknown_app_row(db):
    """Sanity-check: a row with tool_id=NULL + detected_bundle_id should insert and be unique per user."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name, source, installed_locally)
            VALUES ('user-A', NULL, 'com.test.app', 'TestApp', 'detected', TRUE)
            """
        )
        # Second insert with the same (user_id, detected_bundle_id) must violate the partial unique index
        with pytest.raises(Exception):
            cur.execute(
                """
                INSERT INTO user_items (user_id, tool_id, detected_bundle_id, detected_name, source, installed_locally)
                VALUES ('user-A', NULL, 'com.test.app', 'TestApp Again', 'detected', TRUE)
                """
            )
