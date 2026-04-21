"""Visual UX audit agent.

Screenshots each Forge page at desktop + mobile, sends the images to Claude
with a UX rubric, and records findings in tests/reports/ux_report.json so the
test dashboard can surface them.

Runs once and exits. Heavy — makes ~18 screenshots and ~9 Claude calls.
Tune PAGES if cost is an issue.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("FORGE_URL", "http://localhost:8090")
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
SHOT_DIR = REPORT_DIR / "ux_shots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SHOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "ux_report.json"

PAGES = [
    ("catalog",     "/",                                            "The tool catalog — users land here first."),
    ("tool_detail", "/tool.html?slug=account-research-brief",       "A prompt-tool detail page with run form."),
    ("submit",      "/submit.html",                                 "Tool submission — first step asks which format."),
    ("creator",     "/creator.html",                                "Plain-English tool creator (AI designer)."),
    ("workflow",    "/workflow.html",                               "Two-tool chain builder (workflow composer)."),
    ("skills",      "/skills.html",                                 "Skills library — copy/paste prompt templates."),
    ("my_tools",    "/my-tools.html",                               "User's own submissions across statuses."),
    ("admin",       "/admin.html",                                  "Admin review queue (gated)."),
    ("app_kanban",  "/apps/job-search-pipeline",                    "A live app — kanban for job search tracking."),
]

RUBRIC = """You are a senior product designer auditing a dark-themed internal
AI tool marketplace called Forge.

Analyze the TWO screenshots (desktop 1440px and mobile 375px) of a single
page. Return STRICT JSON of the form:

{
  "findings": [
    {
      "severity": "high" | "medium" | "low",
      "category": "navigation" | "visual_hierarchy" | "typography" | "copy" |
                  "affordance" | "accessibility" | "empty_state" | "mobile" |
                  "consistency" | "information_density" | "other",
      "viewport": "desktop" | "mobile" | "both",
      "observation": "<what you see>",
      "impact": "<what this costs the user>",
      "fix": "<concrete remediation>"
    }
  ],
  "strengths": ["<one or two things that genuinely work well>"],
  "summary": "<one sentence overall>"
}

Rules:
- Do not invent features that aren't visible. Only critique what's on screen.
- One finding per issue — don't duplicate the same complaint across viewports.
- Prefer specifics ("the two ? icons side-by-side in the header") over vague
  adjectives ("cluttered").
- Ignore dummy data being obviously synthetic. Focus on UX of the shell.
- If the page looks good, return an empty findings array and explain why in
  the summary.
- Return JSON only. No preamble, no markdown fences."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_pair(page_obj, url: str, label: str) -> tuple[str, str] | None:
    """Screenshot page at desktop + mobile. Returns (desktop_path, mobile_path)."""
    desktop_path = SHOT_DIR / f"desktop_{label}.png"
    mobile_path = SHOT_DIR / f"mobile_{label}.png"
    try:
        page_obj.set_viewport_size({"width": 1440, "height": 900})
        page_obj.goto(url, wait_until="networkidle", timeout=15000)
        page_obj.screenshot(path=str(desktop_path), full_page=True)

        page_obj.set_viewport_size({"width": 375, "height": 812})
        page_obj.goto(url, wait_until="networkidle", timeout=15000)
        page_obj.screenshot(path=str(mobile_path), full_page=True)
        return str(desktop_path), str(mobile_path)
    except Exception as exc:
        print(f"[ux_auditor] screenshot failed for {label}: {exc}")
        return None


def _encode_image(path: str) -> dict:
    with open(path, "rb") as fh:
        data = base64.standard_b64encode(fh.read()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": data},
    }


def _audit_page(client, name: str, description: str, desktop_path: str,
                mobile_path: str) -> dict:
    """Send the two screenshots to Claude and parse the rubric response."""
    content = [
        {"type": "text", "text": f"PAGE: {name} — {description}"},
        {"type": "text", "text": "DESKTOP (1440×900) screenshot:"},
        _encode_image(desktop_path),
        {"type": "text", "text": "MOBILE (375×812) screenshot:"},
        _encode_image(mobile_path),
        {"type": "text", "text": RUBRIC},
    ]
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": content}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        data = json.loads(text)
        data["_ok"] = True
        return data
    except json.JSONDecodeError as exc:
        return {"_ok": False, "error": f"invalid JSON from model: {exc}",
                "raw": text[:500] if "text" in dir() else None}
    except Exception as exc:
        return {"_ok": False, "error": f"{type(exc).__name__}: {exc}"}


def run_cycle() -> dict:
    """One full audit pass across all PAGES."""
    try:
        from playwright.sync_api import sync_playwright
        from anthropic import Anthropic
    except ImportError as exc:
        return {"_ok": False, "error": f"missing dep: {exc}"}

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"_ok": False, "error": "ANTHROPIC_API_KEY not set"}

    client = Anthropic()
    pages_report: list = []
    total_high = 0
    total_medium = 0
    total_low = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        for label, path, description in PAGES:
            url = f"{BASE_URL}{path}"
            try:
                captured = _capture_pair(page, url, label)
                if not captured:
                    pages_report.append({
                        "page": label, "url": url,
                        "error": "screenshot capture failed",
                        "findings": [], "strengths": [], "summary": "",
                    })
                    continue

                desktop_path, mobile_path = captured
                audit = _audit_page(client, label, description,
                                    desktop_path, mobile_path)
                if not audit.get("_ok"):
                    pages_report.append({
                        "page": label, "url": url,
                        "error": audit.get("error"),
                        "findings": [], "strengths": [], "summary": "",
                    })
                    continue

                for f in audit.get("findings", []):
                    sev = f.get("severity", "low")
                    if sev == "high":
                        total_high += 1
                    elif sev == "medium":
                        total_medium += 1
                    else:
                        total_low += 1

                pages_report.append({
                    "page": label,
                    "url": url,
                    "description": description,
                    "findings": audit.get("findings", []),
                    "strengths": audit.get("strengths", []),
                    "summary": audit.get("summary", ""),
                })
            except Exception:
                pages_report.append({
                    "page": label, "url": url,
                    "error": traceback.format_exc(limit=3),
                    "findings": [], "strengths": [], "summary": "",
                })

        browser.close()

    report = {
        "timestamp": now(),
        "base_url": BASE_URL,
        "counts": {
            "high": total_high,
            "medium": total_medium,
            "low": total_low,
            "total": total_high + total_medium + total_low,
        },
        "pages": pages_report,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    return report


def main() -> int:
    print(f"[ux_auditor] Report: {REPORT_FILE}")
    try:
        report = run_cycle()
    except Exception:
        print(f"[ux_auditor] crash:\n{traceback.format_exc()}")
        return 1
    if report.get("_ok") is False:
        print(f"[ux_auditor] error: {report.get('error')}")
        return 1
    c = report["counts"]
    print(f"[ux_auditor] {report['timestamp']} "
          f"pages={len(report['pages'])} "
          f"high={c['high']} medium={c['medium']} low={c['low']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
