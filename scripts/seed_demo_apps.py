"""Seed the Forge catalog with key demo apps.

Run: PYTHONPATH=. python3 scripts/seed_demo_apps.py

Idempotent — uses ON CONFLICT DO NOTHING on slug.
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import db


def seed_app(data: dict):
    """Insert an app if it doesn't exist (by slug)."""
    slug = data["slug"]
    with db.get_db() as cur:
        cur.execute("SELECT id FROM tools WHERE slug = %s", (slug,))
        if cur.fetchone():
            print(f"  exists: {slug}")
            return
    tool_id = db.insert_tool(data)
    print(f"  added: {slug} (id={tool_id})")
    return tool_id


def seed_review(tool_slug: str, review_data: dict):
    """Insert an agent review for a tool.

    Uses the actual agent_reviews schema (from 021 migration):
    security_scan_output, agent_recommendation, qa_pass_rate, etc.
    """
    with db.get_db() as cur:
        cur.execute("SELECT id FROM tools WHERE slug = %s", (tool_slug,))
        row = cur.fetchone()
        if not row:
            print(f"  skip review: {tool_slug} not found")
            return
        tool_id = row["id"]
        cur.execute("SELECT id FROM agent_reviews WHERE tool_id = %s", (tool_id,))
        if cur.fetchone():
            print(f"  review exists: {tool_slug}")
            return
        cur.execute(
            """INSERT INTO agent_reviews (tool_id, classifier_output, detected_output_type, detected_category,
               classification_confidence, security_scan_output, security_score,
               red_team_output, attacks_attempted, attacks_succeeded,
               qa_output, qa_pass_rate, agent_recommendation, agent_confidence, review_summary)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tool_id,
             json.dumps(review_data.get("classifier", {})),
             review_data.get("output_type", ""),
             review_data.get("category", ""),
             review_data.get("confidence", 0.9),
             json.dumps(review_data.get("security", {})),
             review_data.get("security_score", 95),
             json.dumps(review_data.get("red_team", {})),
             review_data.get("attacks_attempted", 5),
             review_data.get("attacks_succeeded", 0),
             json.dumps(review_data.get("qa", {})),
             review_data.get("qa_pass_rate", 1.0),
             review_data.get("verdict", "approve"),
             review_data.get("agent_confidence", 0.92),
             review_data.get("summary", "Approved by governance pipeline.")),
        )
        print(f"  review added: {tool_slug}")


def main():
    print("Seeding Forge demo apps...")

    # 1. Hebbia Signal Engine (original — iframe to VPS)
    seed_app({
        "name": "Hebbia Signal Engine",
        "slug": "hebbia-signal-engine",
        "tagline": "AI-powered competitive intelligence — tracks transformation signals across 20 target institutions",
        "description": "Institutional outbound intelligence. Surfaces AI transformation signals across target accounts. Tracks hiring patterns, model adoption, funding rounds, and strategic pivots.",
        "category": "Developer Tools",
        "icon": "🔬",
        "status": "approved",
        "delivery": "embedded",
        "app_type": "app",
        "app_html": '<!DOCTYPE html><html><head><title>Hebbia Signal Engine</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0d0d0d;font-family:sans-serif}.forge-bar{height:32px;background:#111;border-bottom:1px solid #222;display:flex;align-items:center;padding:0 16px;gap:8px;font-size:12px;color:#666}.forge-bar a{color:#0066FF;text-decoration:none}.vps-badge{background:#1a3a1a;color:#4a9a4a;padding:2px 8px;border-radius:3px;font-size:11px}iframe{width:100%;height:calc(100vh - 32px);border:none}</style></head><body><div class="forge-bar"><a href="/">← Forge catalog</a><span>·</span><span>Running on VPS</span><span class="vps-badge">● LIVE</span></div><iframe src="http://5.161.66.31:8080/index.html" allowfullscreen></iframe></body></html>',
        "author_name": "Nick Ruzicka",
        "author_email": "nick.c.ruzicka@gmail.com",
        "source_url": "",
    })

    # 2. Chariot Signal Engine
    seed_app({
        "name": "Chariot Signal Engine",
        "slug": "chariot-signal-engine",
        "tagline": "Competitive intelligence for Chariot — tracking EV charging infrastructure signals",
        "description": "Fork of Hebbia Signal Engine focused on EV charging infrastructure competitive intelligence.",
        "category": "Developer Tools",
        "icon": "🏛️",
        "status": "approved",
        "delivery": "embedded",
        "app_type": "app",
        "app_html": "<h1>Chariot Signal Engine</h1><p>EV charging intelligence dashboard</p>",
        "author_name": "Nick Ruzicka",
        "author_email": "nick.c.ruzicka@gmail.com",
    })

    # 4. OpenSuperWhisper
    seed_app({
        "name": "OpenSuperWhisper",
        "slug": "opensuperwhisper",
        "tagline": "Free, open-source Whisper transcription app — runs entirely on your Mac",
        "description": "Local-first speech-to-text transcription using OpenAI's Whisper model. No cloud, no API key needed.",
        "category": "Meetings",
        "icon": "🎙",
        "status": "approved",
        "delivery": "external",
        "app_type": "app",
        "install_command": "brew install --cask opensuperwhisper",
        "install_meta": json.dumps({"type": "brew-cask", "cask": "opensuperwhisper"}),
        "author_name": "starmel",
        "source_url": "https://github.com/nicklasoverby/SuperWhisper",
    })

    # 5. Career-Ops
    seed_app({
        "name": "Career-Ops",
        "slug": "career-ops",
        "tagline": "AI-powered job search pipeline — evaluate offers, generate tailored CVs, track applications",
        "description": "Career-Ops turns any AI coding CLI into a full job search command center. Evaluates offers with a structured A-F scoring system, generates tailored ATS-optimized CVs, scans career portals automatically, processes in batch with sub-agents, and tracks everything in a single source of truth.",
        "category": "Planning",
        "icon": "🎯",
        "status": "approved",
        "delivery": "external",
        "app_type": "app",
        # install_command is the human-readable shell equivalent shown as a copy-paste fallback.
        "install_command": "git clone https://github.com/nick-ruzicka/nick-career-ops.git ~/forge-apps/career-ops && cd ~/forge-apps/career-ops && npm install && npx playwright install chromium",
        # install_meta drives the structured git_clone install flow in forge-agent.
        "install_meta": json.dumps({
            "type": "git_clone",
            "repo": "https://github.com/nick-ruzicka/nick-career-ops.git",
            "dest": "~/forge-apps/career-ops",
            "post_install": [
                {"type": "npm_install", "cwd": "~/forge-apps/career-ops"},
                {"type": "npx", "cwd": "~/forge-apps/career-ops", "cmd": "playwright install chromium"},
            ],
        }),
        "author_name": "Nick Ruzicka",
        "author_email": "nick.c.ruzicka@gmail.com",
        "source_url": "https://github.com/nick-ruzicka/nick-career-ops",
        "role_tags": "engineering,product,operations",
    })

    print("\nSeeding governance reviews...")

    seed_review("hebbia-signal-engine", {
        "classifier": {"category": "Developer Tools", "output_type": "interactive_dashboard", "confidence": 0.94},
        "output_type": "interactive_dashboard", "category": "Developer Tools", "confidence": 0.94,
        "security": {"risk_level": "low", "findings": [], "summary": "No security issues. Same-origin API calls only."},
        "security_score": 98,
        "red_team": {"risk_level": "low", "attacks_attempted": 5, "attacks_succeeded": 0},
        "attacks_attempted": 5, "attacks_succeeded": 0,
        "qa": {"pass": True, "tests_run": 8, "tests_passed": 8},
        "qa_pass_rate": 1.0,
        "verdict": "approve", "agent_confidence": 0.92,
        "summary": "Clean interactive dashboard. No security concerns. 5/5 agents agree on low risk.",
    })

    seed_review("career-ops", {
        "classifier": {"category": "Planning", "output_type": "cli_pipeline", "confidence": 0.96},
        "output_type": "cli_pipeline", "category": "Planning", "confidence": 0.96,
        "security": {"risk_level": "low", "findings": [{"severity": "info", "description": "Playwright browses external career sites — expected."}], "summary": "Low risk. Local-only data."},
        "security_score": 95,
        "red_team": {"risk_level": "low", "attacks_attempted": 3, "attacks_succeeded": 0},
        "attacks_attempted": 3, "attacks_succeeded": 0,
        "qa": {"pass": True, "tests_run": 5, "tests_passed": 5},
        "qa_pass_rate": 1.0,
        "verdict": "approve", "agent_confidence": 0.95,
        "summary": "Well-structured CLI pipeline. No security concerns. 5/5 agents agree.",
    })

    # Note: rejected submissions can't have agent_reviews due to XOR constraint
    # (tool_id IS NULL requires skill_id IS NOT NULL). The rejected review
    # would need a dummy skill or tool. For now, skip seeding rejected reviews.
    print("  (skipped rejected review — XOR constraint requires a target)")

    print("\nDone! Run the Flask server to see the apps.")


if __name__ == "__main__":
    main()
