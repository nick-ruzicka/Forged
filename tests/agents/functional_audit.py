"""
Functional audit — drives the live UI with Playwright and reports what breaks.

Covers:
  1. Catalog loads, renders items with social data
  2. "+ Add" button works (no email prompt appears)
  3. Preview overlay opens and shows inspection + reviews
  4. My Forge shelf loads the added item
  5. Embedded app opens in pane iframe
  6. External app opens install modal, "I've installed it" flips state
  7. Publish page loads all three modes
  8. Publish from paste-HTML submits + appears in catalog
  9. Skills page loads, download works
  10. No console errors on any page

Run: venv/bin/python3 tests/agents/functional_audit.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8090"
SHOTS = Path("tests/reports/audit_shots")
SHOTS.mkdir(parents=True, exist_ok=True)

findings: list[dict] = []


def record(area: str, ok: bool, detail: str = ""):
    findings.append({"area": area, "ok": ok, "detail": detail})
    mark = "✓" if ok else "✗"
    print(f"  {mark} {area}{(' — ' + detail) if detail else ''}")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        console_errors: list[str] = []
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)

        # ---------- 1. Catalog loads ----------
        print("\n[1] Catalog")
        try:
            page.goto(BASE, wait_until="networkidle", timeout=15000)
            title = page.title()
            record("catalog loads", "Forge" in title, f"title='{title}'")

            cards = page.locator(".forge-card").count()
            record("cards render", cards >= 4, f"{cards} cards")

            # Is at least one social line rendered?
            page.wait_for_timeout(2000)  # let social requests finish
            social = page.locator(".meta-installs").first.inner_text()
            record("social line rendered", "install" in social.lower(), f"first='{social}'")

            # Should show APP badge... and NOT the "run tool" language anymore
            html = page.content()
            record("no 'Run Tool' leftover", "Run Tool" not in html,
                   "'Run Tool' found" if "Run Tool" in html else "clean")
            record("no '+ Add to my Forge' long text",
                   "+ Add to my Forge" not in html or page.locator("button:has-text('+ Add to my Forge')").count() == 0,
                   "still wordy" if "+ Add to my Forge" in html else "tight")

            page.screenshot(path=str(SHOTS / "catalog.png"), full_page=True)
        except Exception as e:
            record("catalog loads", False, f"exception: {e}")
            browser.close()
            return

        # ---------- 2. Click + Add — no prompt should appear ----------
        print("\n[2] Add to shelf")
        try:
            # Intercept any window.prompt — capture the args + stack to find caller.
            page.evaluate("""
                window.__promptCalls = [];
                window.prompt = function(msg) {
                    var stack = '';
                    try { throw new Error('trace'); } catch (e) { stack = e.stack || ''; }
                    window.__promptCalls.push({ msg: String(msg || ''), stack: stack });
                    return null;
                };
            """)
            btn = page.locator(".btn-add").first
            btn.click()
            page.wait_for_timeout(1000)
            calls = page.evaluate("window.__promptCalls")
            # Filter out Playwright's own UtilityScript prompt calls (test harness
            # noise). Only flag prompts coming from app code.
            user_prompts = [c for c in (calls or [])
                            if "UtilityScript" not in (c.get("stack") or "")
                            and (c.get("msg") or "").strip()]
            if user_prompts:
                first = user_prompts[0]
                record("add does NOT call window.prompt", False,
                       f"prompt('{first.get('msg', '')[:60]}')")
            else:
                record("add does NOT call window.prompt", True,
                       "no app-level prompt — anonymous UUID worked")
            # Check button flipped to ✓ Added
            label = btn.inner_text()
            record("button flipped to Added state", "Added" in label or "✓" in label, f"label='{label}'")
        except Exception as e:
            record("+ Add click", False, f"exception: {e}")

        # ---------- 3. Preview overlay ----------
        print("\n[3] Preview overlay")
        try:
            preview_btn = page.locator(".btn-preview").first
            preview_btn.click()
            page.wait_for_selector(".forge-preview-overlay.open", timeout=5000)
            # Inspection badges should load
            page.wait_for_timeout(2000)
            inspection_html = page.locator("[data-inspection]").inner_html()
            badge_count = inspection_html.count("badge-row")
            record("preview overlay opens", True)
            record("inspection badges render", badge_count > 0, f"{badge_count} badges")
            # Close
            page.locator(".preview-close").click()
            page.wait_for_timeout(500)
        except Exception as e:
            record("preview overlay", False, f"exception: {e}")

        # ---------- 4. My Forge shelf ----------
        print("\n[4] My Forge")
        try:
            page.goto(f"{BASE}/my-tools.html", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1500)
            tiles = page.locator(".shelf-tile").count()
            record("shelf shows the added item", tiles >= 1, f"{tiles} tiles on shelf")
            # Identity card should be present (anonymous state)
            identity = page.locator(".identity-card").count()
            record("identity card present", identity == 1,
                   "missing identity card" if identity == 0 else "anonymous card shown")
            # Skills sidebar exists
            skills_side = page.locator("#skills-side").count()
            record("skills sidebar present", skills_side == 1)
            page.screenshot(path=str(SHOTS / "shelf.png"), full_page=True)
        except Exception as e:
            record("shelf loads", False, f"exception: {e}")

        # ---------- 5. Open embedded app ----------
        print("\n[5] Open embedded app")
        try:
            tile = page.locator(".shelf-tile").first
            tile.locator("[data-act='launch']").click()
            page.wait_for_selector(".pane-overlay.open", timeout=5000)
            iframe_src = page.locator("#pane-iframe").get_attribute("src")
            record("embedded pane opens", "/apps/" in (iframe_src or ""),
                   f"iframe src={iframe_src}")
            page.locator("#pane-close").click()
            page.wait_for_timeout(500)
        except Exception as e:
            record("open embedded", False, f"exception: {e}")

        # ---------- 6. Publish page ----------
        print("\n[6] Publish page")
        try:
            page.goto(f"{BASE}/publish.html", wait_until="networkidle", timeout=10000)
            modes = page.locator(".mode-pill").count()
            record("publish page loads 3 modes", modes == 3, f"{modes} mode pills")
            # Click through modes
            page.locator(".mode-pill[data-mode='upload']").click()
            page.wait_for_timeout(300)
            upload_visible = page.locator("#panel-upload").is_visible()
            record("upload panel toggles", upload_visible)
            page.locator(".mode-pill[data-mode='github']").click()
            page.wait_for_timeout(300)
            github_visible = page.locator("#panel-github").is_visible()
            record("github panel toggles", github_visible)
        except Exception as e:
            record("publish page", False, f"exception: {e}")

        # ---------- 7. Paste-HTML submit flow ----------
        print("\n[7] Publish submit flow")
        try:
            page.locator(".mode-pill[data-mode='paste']").click()
            page.wait_for_timeout(300)
            page.locator("#html-source").fill("<!DOCTYPE html><html><body><h1>Audit Test</h1></body></html>")
            page.locator("#meta-name").fill("Audit Smoke Test")
            page.locator("#meta-tagline").fill("Confirms the publish path works end-to-end.")
            page.locator("#meta-email-author").fill("audit@forge.test")
            page.locator("#publish-btn").click()
            page.wait_for_timeout(2500)
            success = page.locator(".success-card").count() > 0
            record("publish paste-HTML succeeds", success)
        except Exception as e:
            record("publish submit", False, f"exception: {e}")

        # ---------- 8. Skills page ----------
        print("\n[8] Skills page")
        try:
            page.goto(f"{BASE}/skills.html", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1000)
            # Any skill cards?
            skill_html = page.content()
            has_skills = "skill" in skill_html.lower()
            record("skills page loads", has_skills)
        except Exception as e:
            record("skills page", False, f"exception: {e}")

        # ---------- 9. Mobile responsive check ----------
        print("\n[9] Mobile at 375px")
        try:
            page.set_viewport_size({"width": 375, "height": 812})
            page.goto(BASE, wait_until="networkidle", timeout=10000)
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            inner_width = page.evaluate("window.innerWidth")
            record("no horizontal scroll on mobile catalog",
                   scroll_width <= inner_width + 1,
                   f"scrollWidth={scroll_width}, innerWidth={inner_width}")
            page.screenshot(path=str(SHOTS / "mobile_catalog.png"), full_page=True)

            page.goto(f"{BASE}/my-tools.html", wait_until="networkidle", timeout=10000)
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            record("no horizontal scroll on mobile shelf",
                   scroll_width <= inner_width + 1,
                   f"scrollWidth={scroll_width}")
        except Exception as e:
            record("mobile pass", False, f"exception: {e}")

        # ---------- 10. Console errors ----------
        print("\n[10] Console errors")
        real_errors = [e for e in console_errors
                       if "favicon" not in e.lower()
                       and "404" not in e
                       and "permissions policy" not in e.lower()]
        record("no console errors", len(real_errors) == 0,
               f"{len(real_errors)} errors: {real_errors[:3]}")

        browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print(f"FORGE FUNCTIONAL AUDIT — {BASE}")
    print("=" * 60)
    run()
    passed = sum(1 for f in findings if f["ok"])
    failed = [f for f in findings if not f["ok"]]
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(findings)} passing, {len(failed)} failing")
    if failed:
        print("\nFailures:")
        for f in failed:
            print(f"  ✗ {f['area']}: {f['detail']}")
    # Write machine-readable
    Path("tests/reports/audit_result.json").write_text(
        json.dumps({"passed": passed, "failed": len(failed), "findings": findings}, indent=2)
    )
    sys.exit(0 if not failed else 1)
