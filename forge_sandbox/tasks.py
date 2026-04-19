"""
Celery wrapper for sandbox lifecycle jobs and skill review pipeline.

Registered via autodiscovery (see celery_app.py). The beat schedule entry
"hibernate-idle-containers" calls hibernate_idle every 5 minutes.
"""
from __future__ import annotations

import os

from celery_app import celery_app


@celery_app.task(name="forge_sandbox.tasks.hibernate_idle")
def hibernate_idle() -> dict:
    try:
        from forge_sandbox.manager import SandboxManager
        return {"hibernated": SandboxManager().hibernate_idle_containers()}
    except Exception as e:
        return {"error": str(e)}


@celery_app.task(name="forge_sandbox.tasks.skill_review_pipeline")
def skill_review_pipeline(skill_id: int) -> dict:
    """Run the 6-agent review pipeline on a submitted skill.

    Controlled by SKILL_REVIEW_MODE env var:
    - 'stub' (default): auto-approve immediately. For Phase 1.
    - 'real': run actual agents. Wired in Phase 2.
    """
    from datetime import datetime

    from api import db

    mode = os.environ.get("SKILL_REVIEW_MODE", "real")

    skill = db.get_skill(skill_id)
    if not skill:
        return {"error": f"skill {skill_id} not found"}

    # Create the review row
    review_id = db.create_review(skill_id, "skill")

    if mode == "stub":
        # Auto-approve: write passing results to the review row
        db.update_agent_review(review_id,
            classifier_output="auto-classified (stub)",
            detected_category=skill.get("category") or "other",
            classification_confidence=1.0,
            security_flags="none",
            pii_risk=False,
            injection_risk=False,
            data_exfil_risk=False,
            red_team_attacks_succeeded=0,
            attacks_attempted=0,
            attacks_succeeded=0,
            qa_pass_rate=1.0,
            agent_recommendation="approve",
            agent_confidence=1.0,
            review_summary="Auto-approved (stub mode, Phase 1)",
            completed_at=datetime.utcnow(),
        )
        db.update_skill(skill_id,
            review_status="approved",
            review_id=review_id,
            approved_at=datetime.utcnow(),
        )
        return {"skill_id": skill_id, "review_id": review_id, "review_status": "approved"}

    # mode == 'real' — run 6-agent pipeline
    from agents.base import TIMEOUTS, with_timeout
    from agents import classifier, scanner, red_team, hardener, qa, synthesizer

    skill_text = skill.get("prompt_text") or ""
    parent_skill_id = skill.get("parent_skill_id")
    declared_sensitivity = skill.get("data_sensitivity")

    results = {}

    # 1. Classifier
    results["classifier"] = with_timeout(
        classifier.run, TIMEOUTS["classifier"],
        skill_id, review_id, skill_text=skill_text,
        declared_category=skill.get("category") or "",
    )

    # 2. Security Scanner
    results["security_scanner"] = with_timeout(
        scanner.run, TIMEOUTS["security_scanner"],
        skill_id, review_id, skill_text=skill_text,
    )

    # 3. Red Team
    results["red_team"] = with_timeout(
        red_team.run, TIMEOUTS["red_team"],
        skill_id, review_id, skill_text=skill_text,
        parent_skill_id=parent_skill_id,
    )

    # 4. Prompt Hardener (uses red team output)
    rt = results.get("red_team", {})
    results["prompt_hardener"] = with_timeout(
        hardener.run, TIMEOUTS["prompt_hardener"],
        skill_id, review_id, skill_text=skill_text,
        vulnerabilities=rt.get("vulnerabilities", "[]"),
        hardening_suggestions=rt.get("hardening_suggestions", "[]"),
    )

    # 5. QA Tester
    results["qa_tester"] = with_timeout(
        qa.run, TIMEOUTS["qa_tester"],
        skill_id, review_id, skill_text=skill_text,
    )

    # 6. Synthesizer
    results["synthesizer"] = with_timeout(
        synthesizer.run, TIMEOUTS["synthesizer"],
        skill_id, review_id, all_results=results,
        declared_data_sensitivity=declared_sensitivity,
    )

    # Set final skill status
    synth = results.get("synthesizer", {})
    recommendation = synth.get("agent_recommendation", "needs_revision")

    if synth.get("timed_out") or synth.get("error"):
        # Synthesizer failed — fallback
        recommendation = "needs_revision"
        reason = "review pipeline incomplete — synthesizer unavailable"
        db.update_skill(skill_id,
            review_status="needs_revision",
            review_id=review_id,
            blocked_reason=reason,
        )
    elif recommendation == "approve":
        db.update_skill(skill_id,
            review_status="approved",
            review_id=review_id,
            approved_at=datetime.utcnow(),
        )
    elif recommendation == "block":
        reason = synth.get("review_summary", "blocked by review pipeline")
        db.update_skill(skill_id,
            review_status="blocked",
            review_id=review_id,
            blocked_reason=reason,
            blocked_at=datetime.utcnow(),
        )
    else:  # needs_revision
        db.update_skill(skill_id,
            review_status="needs_revision",
            review_id=review_id,
        )

    return {"skill_id": skill_id, "review_id": review_id, "review_status": recommendation}


@celery_app.task(name="forge_sandbox.tasks.async_skill_sweep")
def async_skill_sweep() -> dict:
    """Post-approval sweep: re-check approved skills with deferred quality checks.

    Runs twice daily via Celery beat. Picks top 10 approved skills
    (by install popularity) and runs dogfooding, temperature variation,
    and multi-turn adversarial checks.

    On failure: sets review_status='under_review', logs to skill_admin_actions.
    """
    from datetime import datetime
    import json

    from api import db
    from agents import sweep

    candidates = db.get_sweep_candidates(limit=10)
    if not candidates:
        return {"checked": 0, "flagged": 0, "message": "no approved skills to sweep"}

    checked = 0
    flagged = 0
    results = []

    for skill in candidates:
        skill_id = skill["id"]
        skill_text = skill.get("prompt_text") or ""
        skill_title = skill.get("title") or ""

        if not skill_text:
            continue

        # Create a review row for timing tracking
        review_id = db.create_review(skill_id, "skill")

        try:
            result = sweep.run(
                skill_id, review_id,
                skill_text=skill_text,
                skill_title=skill_title,
            )
            checked += 1

            if not result.get("overall_pass", True):
                # Flag the skill
                failed = result.get("failed_checks", [])
                reason = f"async sweep flagged: {', '.join(failed)}"

                db.update_skill(skill_id, review_status="under_review")
                db.insert_skill_admin_action(
                    skill_id=skill_id,
                    action="async_sweep_flag",
                    reason=reason,
                    reviewer="system:async_sweep",
                    from_status="approved",
                    to_status="under_review",
                )
                flagged += 1
                results.append({"skill_id": skill_id, "title": skill_title,
                                "status": "flagged", "failed_checks": failed})
            else:
                results.append({"skill_id": skill_id, "title": skill_title,
                                "status": "passed"})

        except Exception as e:
            results.append({"skill_id": skill_id, "title": skill_title,
                            "status": "error", "error": str(e)[:200]})

    return {"checked": checked, "flagged": flagged, "results": results}
