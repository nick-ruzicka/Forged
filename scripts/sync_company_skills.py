"""Sync company skills from markdown files to Postgres.

Git is the source of truth. Postgres is the read cache.

Run: PYTHONPATH=. python3 scripts/sync_company_skills.py
"""
import glob
import json
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import db

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "config", "company_skills")


def parse_skill_file(path: str) -> dict:
    """Parse a company skill markdown file with YAML frontmatter."""
    with open(path, "r") as f:
        raw = f.read()

    # Split frontmatter from content
    if not raw.startswith("---"):
        raise ValueError(f"No YAML frontmatter in {path}")

    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Malformed frontmatter in {path}")

    meta = yaml.safe_load(parts[1])
    content = parts[2].strip()

    return {
        "slug": meta["slug"],
        "title": meta["title"],
        "description": meta.get("description", ""),
        "content": content,
        "required_sections": json.dumps(meta.get("required_sections", [])),
        "behavior_tests": json.dumps(meta.get("behavior_tests", [])),
        "category": meta.get("category", "governance"),
        "is_default": meta.get("is_default", False),
    }


def main():
    print("Syncing company skills from markdown → Postgres...")
    files = sorted(glob.glob(os.path.join(SKILLS_DIR, "*.md")))

    if not files:
        print(f"  No .md files found in {SKILLS_DIR}")
        return

    for path in files:
        try:
            data = parse_skill_file(path)
            skill_id = db.upsert_company_skill(data)
            print(f"  ✓ {data['slug']} (id={skill_id})")
        except Exception as e:
            print(f"  ✗ {os.path.basename(path)}: {e}")

    # Summary
    all_skills = db.list_company_skills()
    print(f"\n{len(all_skills)} company skills in database:")
    for s in all_skills:
        default_tag = " [DEFAULT]" if s.get("is_default") else ""
        print(f"  {s['slug']}{default_tag} — {s['title']}")


if __name__ == "__main__":
    main()
