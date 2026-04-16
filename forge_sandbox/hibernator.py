"""
Ad-hoc hibernator: stop idle containers and pre-warm hot tools.

Runs the same idle-sweep as the Celery beat schedule (see forge_sandbox.tasks),
then pre-warms any stopped container whose parent tool has run_count > 10.

Usage:
    venv/bin/python3 -m forge_sandbox.hibernator
"""
from __future__ import annotations

from api import db
from forge_sandbox.manager import SandboxManager


def main() -> int:
    mgr = SandboxManager()
    count = mgr.hibernate_idle_containers()
    print(f"Hibernated {count} idle containers")

    with db.get_db() as cur:
        cur.execute(
            """
            SELECT id FROM tools
            WHERE container_mode = TRUE
              AND run_count > 10
              AND container_status = 'stopped'
            """
        )
        rows = cur.fetchall()

    warmed = 0
    for row in rows:
        try:
            if mgr.pre_warm(row["id"]) is not None:
                warmed += 1
        except Exception as exc:
            print(f"pre_warm failed tool_id={row.get('id')}: {exc}")
    print(f"Pre-warmed {warmed} hot containers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
