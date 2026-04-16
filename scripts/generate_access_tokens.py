"""
Backfill missing access_tokens on approved + deployed tools.
Idempotent: only tools with NULL/empty access_token are updated.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api import db


def main() -> int:
    updated = 0
    with db.cursor() as cur:
        cur.execute(
            """SELECT id, slug FROM tools
               WHERE status = 'approved'
                 AND deployed = TRUE
                 AND (access_token IS NULL OR access_token = '')"""
        )
        rows = cur.fetchall()

    for row in rows:
        token = str(uuid.uuid4())
        db.update_tool(row["id"], access_token=token)
        print(f"tool {row['id']} ({row['slug']}): assigned token {token}")
        updated += 1

    if updated == 0:
        print("No tools needed an access_token.")
    else:
        print(f"Updated {updated} tool(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
