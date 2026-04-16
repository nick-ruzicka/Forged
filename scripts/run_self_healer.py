#!/usr/bin/env python3
"""
CLI wrapper for the self-healer. Intended for cron / Celery Beat.

Usage:
    python3 scripts/run_self_healer.py
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from agents.self_healer import heal_underperforming_tools  # noqa: E402


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    try:
        summary = heal_underperforming_tools()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        sys.exit(1)

    print(json.dumps(summary, indent=2, default=str))
    # Exit 0 always so cron doesn't mark the job failed just because no
    # candidates were found or some individual tool raised.
    sys.exit(0)


if __name__ == "__main__":
    main()
