#!/usr/bin/env python3
"""
CLI wrapper for the 6-agent review pipeline.

Usage:
    python3 scripts/run_pipeline.py --tool-id 123
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from repo root without installing as a package
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from agents.pipeline import run_pipeline  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Run the Forge agent pipeline.")
    parser.add_argument("--tool-id", type=int, required=True,
                        help="ID of the tool to review")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    result = run_pipeline(args.tool_id)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
