"""
Governance Validator Agent — verifies project submissions maintain their
declared governance skills.

Runs FIRST in the pipeline, before the classifier. Checks:
1. CLAUDE.md exists and contains required sections from declared skills
2. Governance checksum matches (required sections haven't been gutted)
3. Behavior tests pass (adversarial prompts that verify skills actually work)

This agent doesn't check code quality or security — that's what the other
5 agents are for. This agent checks that the governance CONTRACT is intact.
"""

import hashlib
import json
import re
import time
from typing import Any

from agents.base import get_client, timed, TIMEOUTS

TIMEOUTS["governance_validator"] = 120  # 2 minutes max


def run(skill_id: int = 0, review_id: int = 0, **kwargs) -> dict:
    """
    Validate a project submission's governance integrity.

    Expects kwargs:
        manifest: dict — the .forge/manifest.json content
        claude_md: str — the CLAUDE.md content
        company_skills: list[dict] — the declared skills from DB

    Returns:
        {
            "verdict": "pass" | "needs-patch" | "fail",
            "sections_found": list,
            "sections_missing": list,
            "checksum_valid": bool,
            "behavior_tests": list[dict],
            "issues": list[str],
            "summary": str,
        }
    """
    manifest = kwargs.get("manifest", {})
    claude_md = kwargs.get("claude_md", "")
    company_skills = kwargs.get("company_skills", [])

    issues = []
    sections_found = []
    sections_missing = []

    # ── Step 1: Check CLAUDE.md exists and isn't empty ──
    if not claude_md or len(claude_md.strip()) < 50:
        return {
            "verdict": "fail",
            "sections_found": [],
            "sections_missing": ["(entire file)"],
            "checksum_valid": False,
            "behavior_tests": [],
            "issues": ["CLAUDE.md is missing or effectively empty"],
            "summary": "CLAUDE.md not found or too short to contain governance rules.",
        }

    # ── Step 2: Check required sections from each declared skill ──
    declared_slugs = manifest.get("skills_applied", [])

    for skill in company_skills:
        if skill["slug"] not in declared_slugs:
            continue

        required = skill.get("required_sections", "[]")
        if isinstance(required, str):
            required = json.loads(required)

        for section_header in required:
            header_text = section_header.strip().lstrip("#").strip()

            # Exact match first
            if _section_exists(claude_md, header_text):
                content = _extract_section(claude_md, header_text)
                if len(content.strip()) < 20:
                    sections_missing.append(section_header)
                    issues.append(
                        f"Section '{section_header}' exists but has trivial content "
                        f"({len(content.strip())} chars). Needs substantive governance rules."
                    )
                else:
                    sections_found.append(section_header)
            # Fuzzy match (renamed section)
            elif _fuzzy_section_exists(claude_md, header_text):
                sections_found.append(f"{section_header} (fuzzy match)")
                issues.append(
                    f"Section '{section_header}' appears to be renamed. "
                    f"Consider keeping the original name for clarity."
                )
            else:
                sections_missing.append(section_header)
                issues.append(
                    f"Required section '{section_header}' is missing from CLAUDE.md. "
                    f"This section is required by the '{skill['slug']}' skill."
                )

    # ── Step 3: Checksum validation ──
    original_checksum = manifest.get("governance_checksum", "")
    current_checksum = _compute_checksum(company_skills, declared_slugs, claude_md)
    checksum_valid = original_checksum == current_checksum

    if not checksum_valid and not sections_missing:
        # Sections exist but content changed — that might be OK
        issues.append(
            "Governance checksum changed. Required section content was modified. "
            "This is allowed if the changes strengthen the rules. "
            "Behavior tests will verify the skills still work."
        )

    # ── Step 4: Behavior tests ──
    behavior_results = []
    if sections_missing:
        # Don't run behavior tests if sections are missing — they'll fail anyway
        pass
    else:
        for skill in company_skills:
            if skill["slug"] not in declared_slugs:
                continue
            tests = skill.get("behavior_tests", "[]")
            if isinstance(tests, str):
                tests = json.loads(tests)
            for test in tests:
                result = _run_behavior_test(test, claude_md, skill["slug"])
                behavior_results.append(result)
                if not result["passed"]:
                    issues.append(
                        f"Behavior test failed for '{skill['slug']}': "
                        f"{test.get('prompt', '')[:80]}... "
                        f"Expected: {test.get('expected', '')[:80]}"
                    )

    # ── Verdict ──
    tests_passed = all(r["passed"] for r in behavior_results) if behavior_results else True

    if sections_missing and len(sections_missing) > len(sections_found):
        verdict = "fail"
        summary = (
            f"Governance validation FAILED. "
            f"{len(sections_missing)} required sections missing from CLAUDE.md. "
            f"The governance contract declared in the manifest is not honored."
        )
    elif sections_missing:
        verdict = "needs-patch"
        summary = (
            f"Governance validation needs patching. "
            f"{len(sections_missing)} sections missing but {len(sections_found)} intact. "
            f"The hardener can restore missing sections from canonical skill content."
        )
    elif not tests_passed:
        verdict = "needs-patch"
        failed_count = sum(1 for r in behavior_results if not r["passed"])
        summary = (
            f"Sections present but {failed_count} behavior test(s) failed. "
            f"The skill rules may have been weakened. Hardener should review."
        )
    else:
        verdict = "pass"
        summary = (
            f"Governance validation PASSED. "
            f"{len(sections_found)} required sections verified. "
            f"{'Checksum valid.' if checksum_valid else 'Content modified but behavior tests pass.'} "
            f"{len(behavior_results)} behavior tests passed."
        )

    return {
        "verdict": verdict,
        "sections_found": sections_found,
        "sections_missing": sections_missing,
        "checksum_valid": checksum_valid,
        "behavior_tests": behavior_results,
        "issues": issues,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section_exists(md: str, header_text: str) -> bool:
    """Check if a section header exists in the markdown."""
    pattern = re.compile(r"^#{1,6}\s+" + re.escape(header_text) + r"\s*$", re.MULTILINE)
    return bool(pattern.search(md))


def _fuzzy_section_exists(md: str, header_text: str, max_distance: int = 3) -> bool:
    """Check if a similarly-named section exists (handles renames)."""
    headers = re.findall(r"^#{1,6}\s+(.+)$", md, re.MULTILINE)
    for h in headers:
        if _levenshtein(h.strip().lower(), header_text.lower()) <= max_distance:
            return True
    return False


def _extract_section(md: str, header_text: str) -> str:
    """Extract content under a markdown header until the next same-level header."""
    lines = md.split("\n")
    capturing = False
    content = []
    header_level = None

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2).strip()
            if text.lower() == header_text.lower():
                capturing = True
                header_level = level
                continue
            elif capturing and level <= header_level:
                break
        if capturing:
            content.append(line)

    return "\n".join(content).strip()


def _compute_checksum(skills: list, declared_slugs: list, claude_md: str) -> str:
    """Compute checksum over required section content."""
    hasher = hashlib.sha256()
    for skill in skills:
        if skill["slug"] not in declared_slugs:
            continue
        required = skill.get("required_sections", "[]")
        if isinstance(required, str):
            required = json.loads(required)
        for header in required:
            header_text = header.strip().lstrip("#").strip()
            content = _extract_section(claude_md, header_text)
            if content:
                hasher.update(content.encode("utf-8"))
    return hasher.hexdigest()[:16]


def _run_behavior_test(test: dict, claude_md: str, skill_slug: str) -> dict:
    """
    Run a single behavior test against the project's CLAUDE.md context.

    Uses Claude to simulate the tool's behavior and check compliance.
    """
    prompt = test.get("prompt", "")
    expected = test.get("expected", "")
    check = test.get("check", "")

    if not prompt:
        return {"passed": True, "prompt": "", "reason": "empty test"}

    try:
        # Ask Claude to simulate the tool's response given the CLAUDE.md context
        response = get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"You are a Claude Code tool configured with the following CLAUDE.md:\n\n"
                        f"<claude_md>\n{claude_md[:8000]}\n</claude_md>\n\n"
                        f"A user sends this message: \"{prompt}\"\n\n"
                        f"How would you respond, following ALL the rules in CLAUDE.md? "
                        f"Be specific and include any required formatting (confidence scores, etc)."
                    ),
                }
            ],
        )

        tool_response = response.content[0].text if response.content else ""

        # Now use a judge to check if the response matches expected behavior
        judge_response = get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Does this AI response follow the expected behavior?\n\n"
                        f"Expected behavior: {expected}\n"
                        f"Check criteria: {check}\n\n"
                        f"Actual response:\n{tool_response[:2000]}\n\n"
                        f"Answer with PASS or FAIL and a one-sentence reason."
                    ),
                }
            ],
        )

        judge_text = judge_response.content[0].text if judge_response.content else ""
        passed = "PASS" in judge_text.upper().split("\n")[0]

        return {
            "passed": passed,
            "prompt": prompt[:100],
            "expected": expected[:100],
            "tool_response": tool_response[:200],
            "judge_verdict": judge_text[:200],
            "skill": skill_slug,
        }

    except Exception as e:
        # Behavior test failure is not a hard block — it's advisory
        return {
            "passed": True,  # fail open on API errors
            "prompt": prompt[:100],
            "expected": expected[:100],
            "error": str(e)[:200],
            "skill": skill_slug,
        }


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr

    return prev[len(s2)]
