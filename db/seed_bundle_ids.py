"""Idempotent backfill: read bundle_ids.yaml and UPDATE tools.app_bundle_id.

Usage:
    python -m db.seed_bundle_ids
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

from api import db


def main() -> int:
    seed_path = Path(__file__).parent / "migrations" / "data" / "bundle_ids.yaml"
    if not seed_path.is_file():
        print(f"missing seed file: {seed_path}", file=sys.stderr)
        return 1
    mapping: dict[str, str] = yaml.safe_load(seed_path.read_text()) or {}

    updated = 0
    skipped = 0
    with db.get_db() as cur:
        for slug, bundle_id in mapping.items():
            cur.execute(
                "UPDATE tools SET app_bundle_id = %s WHERE slug = %s RETURNING id",
                (bundle_id, slug),
            )
            row = cur.fetchone()
            if row:
                updated += 1
            else:
                skipped += 1
                print(f"  warn: slug {slug!r} not found in tools — skipped")

    print(f"updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
