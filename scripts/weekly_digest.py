"""
Weekly team digest — run via cron or Celery Beat.
Posts a summary of Forge activity to Slack.

Usage: python3 scripts/weekly_digest.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import db


def generate_digest():
    """Generate a plain-text weekly summary of Forge activity."""
    since = datetime.utcnow() - timedelta(days=7)
    lines = ["*📊 Forge Weekly Digest*", ""]

    # New installs this week
    with db.get_db() as cur:
        cur.execute(
            """
            SELECT t.name, t.icon, COUNT(*) as installs
            FROM user_items ui JOIN tools t ON t.id = ui.tool_id
            WHERE ui.added_at >= %s
            GROUP BY t.id, t.name, t.icon
            ORDER BY installs DESC LIMIT 5
            """,
            (since,),
        )
        top = cur.fetchall()

    if top:
        lines.append("*Most installed this week:*")
        for r in top:
            lines.append(f"  {r['icon'] or '⊞'} {r['name']} — {r['installs']} new installs")
        lines.append("")

    # Total activity
    with db.get_db() as cur:
        cur.execute("SELECT COUNT(*) as n FROM user_items WHERE added_at >= %s", (since,))
        total_installs = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM action_log WHERE created_at >= %s", (since,))
        total_actions = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(DISTINCT user_id) as n FROM user_items WHERE added_at >= %s", (since,))
        active_users = cur.fetchone()["n"]

    lines.append(f"*This week:* {total_installs} installs · {total_actions} actions · {active_users} active users")
    lines.append("")
    lines.append("_Browse the catalog: http://localhost:8090/_")

    return "\n".join(lines)


def post_to_slack(message):
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("SLACK_WEBHOOK_URL not set — printing digest instead:")
        print(message)
        return False
    payload = json.dumps({"text": message}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)
    return True


if __name__ == "__main__":
    digest = generate_digest()
    posted = post_to_slack(digest)
    if posted:
        print("Digest posted to Slack.")
    else:
        print("(Slack not configured — digest printed above)")
