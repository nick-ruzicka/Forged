"""
Orchestrates the 6-agent review pipeline.

Order of execution (per SPEC.md):
  Pre-flight -> Classifier -> (SecurityScanner || RedTeam) -> PromptHardener
  -> QATester -> Synthesizer

Security scanner and red team run in parallel via threading.
Each agent's output is persisted to agent_reviews as it completes so the
admin UI can poll for progress.
"""
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from agents.classifier import ClassifierAgent
from agents.prompt_hardener import PromptHardenerAgent
from agents.qa_tester import QATesterAgent
from agents.red_team import RedTeamAgent
from agents.security_scanner import SecurityScannerAgent
from agents.synthesizer import SynthesizerAgent
from agents.trust_calculator import compute_trust_tier

try:
    from api import db
except ImportError:
    db = None


INJECTION_STRINGS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard the above",
    "system prompt:",
    "<|im_start|>",
)


def pre_flight_check(tool: dict):
    """Validate the submission before spending Claude calls. Return (ok, error)."""
    if not tool:
        return False, "tool not found"
    prompt = (tool.get("system_prompt") or "").strip()
    if not prompt:
        return False, "system_prompt is empty"

    schema_raw = tool.get("input_schema")
    if not schema_raw:
        return False, "input_schema is missing"
    if isinstance(schema_raw, str):
        try:
            schema = json.loads(schema_raw)
        except json.JSONDecodeError:
            return False, "input_schema is not valid JSON"
    else:
        schema = schema_raw
    if isinstance(schema, dict):
        fields = schema.get("fields") or schema.get("properties") or schema
        if not fields:
            return False, "input_schema has no fields"
    elif isinstance(schema, list):
        if not schema:
            return False, "input_schema has no fields"
    else:
        return False, "input_schema must be object or list"

    low = prompt.lower()
    for needle in INJECTION_STRINGS:
        if needle in low:
            return False, f"prompt contains injection pattern: {needle!r}"

    if not tool.get("name") or not str(tool.get("name")).strip():
        return False, "tool name is empty"

    return True, None


def _safe_run(agent, *args, **kwargs):
    start = time.time()
    try:
        result = agent.run(*args, **kwargs)
        elapsed = int((time.time() - start) * 1000)
        return {"ok": True, "data": result, "elapsed_ms": elapsed}
    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "error": f"{exc}",
            "trace": traceback.format_exc(),
            "elapsed_ms": elapsed,
        }


def _persist(review_id, fields):
    if db is None or review_id is None:
        return
    try:
        db.update_agent_review(review_id, **fields)
    except Exception as exc:
        # Log but don't blow up the whole pipeline if DB is down
        print(f"[pipeline] failed to persist review fields: {exc}")


def run_pipeline(tool_id: int) -> dict:
    """Run the full 6-agent pipeline for a tool. Returns a summary dict."""
    if db is None:
        raise RuntimeError("api.db not importable — cannot run pipeline")

    pipeline_start = time.time()
    tool = db.get_tool(tool_id)
    if not tool:
        return {"ok": False, "tool_id": tool_id, "error": "tool not found"}

    ok, error = pre_flight_check(tool)
    if not ok:
        db.update_tool(tool_id, status="rejected")
        review_id = db.create_agent_review(tool_id)
        _persist(review_id, {
            "agent_recommendation": "reject",
            "review_summary": f"Pre-flight failed: {error}",
            "completed_at": datetime.utcnow(),
        })
        return {"ok": False, "tool_id": tool_id, "stage": "pre_flight", "error": error}

    db.update_tool(tool_id, status="agent_reviewing")
    review_id = db.create_agent_review(tool_id)

    # Stage 1: classifier
    classifier = ClassifierAgent()
    cls_res = _safe_run(classifier, tool)
    cls_data = cls_res["data"] if cls_res["ok"] else {}
    _persist(review_id, {
        "classifier_output": cls_data,
        "detected_output_type": cls_data.get("output_type"),
        "detected_category": cls_data.get("detected_category"),
        "classification_confidence": cls_data.get("confidence"),
    })

    # Stage 2: security_scanner + red_team in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        sec_future = pool.submit(_safe_run, SecurityScannerAgent(), tool)
        rt_future = pool.submit(_safe_run, RedTeamAgent(), tool)
        sec_res = sec_future.result()
        rt_res = rt_future.result()

    sec_data = sec_res["data"] if sec_res["ok"] else {}
    rt_data = rt_res["data"] if rt_res["ok"] else {}
    _persist(review_id, {
        "security_scan_output": sec_data,
        "security_flags": sec_data.get("flags") or [],
        "security_score": sec_data.get("security_score"),
        "pii_risk": bool(sec_data.get("pii_risk")),
        "injection_risk": bool(sec_data.get("injection_risk")),
        "data_exfil_risk": bool(sec_data.get("data_exfil_risk")),
        "red_team_output": rt_data,
        "attacks_attempted": int(rt_data.get("attacks_attempted", 0) or 0),
        "attacks_succeeded": int(rt_data.get("attacks_succeeded", 0) or 0),
        "vulnerabilities": rt_data.get("vulnerabilities") or [],
        "hardening_suggestions": rt_data.get("hardening_suggestions") or [],
    })

    # Stage 3: prompt_hardener (uses outputs from stages 1-2)
    hardener = PromptHardenerAgent()
    hard_res = _safe_run(hardener, tool, sec_data.get("flags"), rt_data)
    hard_data = hard_res["data"] if hard_res["ok"] else {}
    hardened_prompt = hard_data.get("hardened_prompt") or tool.get("system_prompt")
    _persist(review_id, {
        "hardener_output": hard_data,
        "original_prompt": tool.get("system_prompt") or "",
        "hardened_prompt": hardened_prompt or "",
        "changes_made": hard_data.get("changes") or [],
        "hardening_summary": hard_data.get("hardening_summary") or "",
    })

    # Stage 4: qa_tester (runs hardened prompt)
    qa_res = _safe_run(QATesterAgent(), tool, hardened_prompt)
    qa_data = qa_res["data"] if qa_res["ok"] else {}
    _persist(review_id, {
        "qa_output": qa_data,
        "test_cases": qa_data.get("test_cases") or [],
        "qa_pass_rate": float(qa_data.get("qa_pass_rate", 0.0) or 0.0),
        "qa_issues": qa_data.get("issues") or [],
    })

    # Stage 5: synthesizer
    synth_res = _safe_run(
        SynthesizerAgent(), tool,
        classifier=cls_data, security=sec_data, red_team=rt_data,
        hardener=hard_data, qa=qa_data,
    )
    synth_data = synth_res["data"] if synth_res["ok"] else {}

    gs = synth_data.get("governance_scores") or {}
    reliability = int(gs.get("reliability", cls_data.get("reliability_score", 50)))
    safety = int(gs.get("safety", cls_data.get("safety_score", 50)))
    data_sensitivity = gs.get("data_sensitivity",
                               cls_data.get("data_sensitivity", "internal"))
    complexity = int(gs.get("complexity", cls_data.get("complexity_score", 50)))
    verified = int(gs.get("verified", 50 if qa_data else 0))
    trust_tier = synth_data.get("trust_tier") or compute_trust_tier(
        reliability, safety, data_sensitivity,
        complexity=complexity, verified=verified,
    )
    recommendation = synth_data.get("overall_recommendation") or "approve_with_modifications"
    confidence = float(synth_data.get("confidence", 0.5))

    total_elapsed_ms = int((time.time() - pipeline_start) * 1000)

    _persist(review_id, {
        "agent_recommendation": recommendation,
        "agent_confidence": confidence,
        "review_summary": synth_data.get("summary", ""),
        "review_duration_ms": total_elapsed_ms,
        "completed_at": datetime.utcnow(),
    })

    # Update the tool itself with hardened prompt, scores, trust tier
    db.update_tool(
        tool_id,
        status="pending_review",
        hardened_prompt=hardened_prompt or "",
        reliability_score=reliability,
        safety_score=safety,
        data_sensitivity=data_sensitivity,
        complexity_score=complexity,
        verified_score=verified,
        trust_tier=trust_tier,
    )

    return {
        "ok": True,
        "tool_id": tool_id,
        "review_id": review_id,
        "recommendation": recommendation,
        "confidence": confidence,
        "trust_tier": trust_tier,
        "governance_scores": {
            "reliability": reliability,
            "safety": safety,
            "data_sensitivity": data_sensitivity,
            "complexity": complexity,
            "verified": verified,
        },
        "summary": synth_data.get("summary", ""),
        "required_changes": synth_data.get("required_changes", []),
        "optional_improvements": synth_data.get("optional_improvements", []),
        "reviewer_checklist": synth_data.get("reviewer_checklist", []),
        "elapsed_ms": total_elapsed_ms,
        "stage_results": {
            "classifier": cls_res.get("ok"),
            "security": sec_res.get("ok"),
            "red_team": rt_res.get("ok"),
            "hardener": hard_res.get("ok"),
            "qa": qa_res.get("ok"),
            "synthesizer": synth_res.get("ok"),
        },
    }
