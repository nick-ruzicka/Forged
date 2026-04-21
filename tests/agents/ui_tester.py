"""UI testing agent. Uses Playwright to exercise the Forge frontend once; exits non-zero on failure."""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = os.environ.get("FORGE_URL", "http://localhost:8090")
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
SCREENSHOT_DIR = REPORT_DIR / "screenshots"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "ui_report.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(results: list, page: str, test_name: str, passed: bool,
           error: str | None = None, screenshot: str | None = None) -> None:
    results.append({
        "page": page,
        "test_name": test_name,
        "passed": passed,
        "error_message": error,
        "screenshot_path": screenshot,
        "timestamp": now(),
    })


def safe_screenshot(page_obj, label: str) -> str | None:
    """Save a screenshot; returns path or None on failure."""
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = SCREENSHOT_DIR / f"{label}-{stamp}.png"
        page_obj.screenshot(path=str(path), full_page=True)
        return str(path.relative_to(REPORT_DIR.parent.parent))
    except Exception:
        return None


def test_catalog(page, console_errors, results):
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
    except Exception as exc:
        record(results, "/", "load_catalog", False, str(exc),
               safe_screenshot(page, "catalog-load-fail"))
        return

    title = page.title()
    if "Forge" in title:
        record(results, "/", "title_contains_Forge", True)
    else:
        record(results, "/", "title_contains_Forge", False,
               f"title was '{title}'", safe_screenshot(page, "catalog-title"))

    # Hero banner (first-visit dismissible — may not always render)
    hero_visible = page.locator("#hero-container, .hero, [data-hero]").count() > 0
    record(results, "/", "hero_banner_exists", hero_visible)

    # Tool cards
    card_count = page.locator(".tool-card, [data-tool-card], article.card").count()
    if card_count > 0:
        record(results, "/", "tool_cards_present", True)
    else:
        record(results, "/", "tool_cards_present", False,
               f"found {card_count} cards",
               safe_screenshot(page, "catalog-no-cards"))


def test_tool_detail(page, results):
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        run_button = page.locator(
            "a:has-text('Run Tool'), button:has-text('Run Tool'), a.card-run"
        ).first
        if run_button.count() == 0:
            record(results, "/", "click_first_run_tool", False,
                   "no Run Tool button found",
                   safe_screenshot(page, "no-run-button"))
            return
        run_button.click()
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as exc:
        record(results, "/tool.html", "navigate_to_tool", False, str(exc),
               safe_screenshot(page, "tool-nav-fail"))
        return

    form_count = page.locator("form, .run-form, #run-form").count()
    if form_count > 0:
        record(results, "/tool.html", "form_renders", True)
    else:
        record(results, "/tool.html", "form_renders", False, "no form found",
               safe_screenshot(page, "tool-no-form"))
        return

    # Try to fill first text input and verify value
    try:
        text_inputs = page.locator("input[type='text'], textarea").first
        if text_inputs.count() > 0:
            text_inputs.fill("Acme Corp")
            val = text_inputs.input_value()
            record(results, "/tool.html", "input_accepts_value", val == "Acme Corp",
                   None if val == "Acme Corp" else f"value mismatch: {val!r}")
    except Exception as exc:
        record(results, "/tool.html", "input_accepts_value", False, str(exc))


def test_page_loads(page, path, label, results):
    try:
        page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=15000)
        record(results, path, f"{label}_loads", True)
    except Exception as exc:
        record(results, path, f"{label}_loads", False, str(exc),
               safe_screenshot(page, label + "-fail"))


def check_images_and_buttons(page, path, results):
    try:
        broken = page.evaluate(
            "Array.from(document.images).filter(i => !i.src || i.naturalWidth === 0).length"
        )
        record(results, path, "no_broken_images", broken == 0,
               None if broken == 0 else f"{broken} broken images")
        empty_btns = page.evaluate(
            "Array.from(document.querySelectorAll('button')).filter(b => "
            "!b.textContent.trim() && !b.getAttribute('aria-label')).length"
        )
        record(results, path, "no_empty_buttons", empty_btns == 0,
               None if empty_btns == 0 else f"{empty_btns} empty buttons")
    except Exception as exc:
        record(results, path, "image_button_audit", False, str(exc))


def test_mobile_responsive(page, results):
    try:
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        inner_width = page.evaluate("window.innerWidth")
        no_h_scroll = scroll_width <= inner_width + 1
        record(results, "/", "mobile_no_horizontal_scroll", no_h_scroll,
               None if no_h_scroll else f"scrollWidth={scroll_width}, innerWidth={inner_width}",
               None if no_h_scroll else safe_screenshot(page, "mobile-hscroll"))
        page.set_viewport_size({"width": 1440, "height": 900})
    except Exception as exc:
        record(results, "/", "mobile_responsive", False, str(exc))


def run_cycle(p) -> dict:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    console_errors: list = []
    page.on("pageerror", lambda e: console_errors.append(str(e)))
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

    results: list = []
    try:
        test_catalog(page, console_errors, results)
        test_tool_detail(page, results)
        test_page_loads(page, "/submit.html", "submit", results)
        check_images_and_buttons(page, "/submit.html", results)
        test_page_loads(page, "/skills.html", "skills", results)
        check_images_and_buttons(page, "/skills.html", results)
        test_page_loads(page, "/my-tools.html", "my_tools", results)
        check_images_and_buttons(page, "/my-tools.html", results)
        test_mobile_responsive(page, results)

        record(results, "*", "no_console_errors", len(console_errors) == 0,
               None if not console_errors else f"{len(console_errors)} errors: "
                                                f"{console_errors[:3]}")
    finally:
        context.close()
        browser.close()

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    report = {
        "timestamp": now(),
        "base_url": BASE_URL,
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "results": results,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    return report


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ui_tester] playwright not installed. run: venv/bin/pip install playwright "
              "&& venv/bin/playwright install chromium")
        return 1

    print(f"[ui_tester] Base URL: {BASE_URL}. Report: {REPORT_FILE}")
    with sync_playwright() as p:
        try:
            report = run_cycle(p)
        except Exception:
            print(f"[ui_tester] error:\n{traceback.format_exc()}")
            return 1
    print(
        f"[ui_tester] {report['timestamp']} "
        f"passed={report['passed']} failed={report['failed']}"
    )
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
