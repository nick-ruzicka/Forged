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

    mode = os.environ.get("SKILL_REVIEW_MODE", "stub")

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

    # mode == 'real' — Phase 2 wires this path
    # classifier -> security_scanner -> red_team -> prompt_hardener -> qa_tester -> synthesizer
    raise NotImplementedError(
        f"Real review pipeline not yet implemented (SKILL_REVIEW_MODE={mode}). "
        "Set SKILL_REVIEW_MODE=stub or implement Phase 2."
    )
