"""
Dataclasses mapping to Forge DB rows.
Each class: from_row(row, cursor) classmethod and to_dict() method.
"""
from dataclasses import dataclass, field, fields as dc_fields
from datetime import datetime, date
from typing import Any, Dict, Optional
import json


def _serialize(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _row_to_dict(row, cursor) -> Dict[str, Any]:
    """Accept a dict-like row or a tuple with cursor.description."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if cursor is not None and getattr(cursor, "description", None):
        names = [d[0] for d in cursor.description]
        return dict(zip(names, row))
    return dict(row)


def _filter_known(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    known = {f.name for f in dc_fields(cls)}
    return {k: v for k, v in data.items() if k in known}


@dataclass
class Tool:
    id: Optional[int] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None

    reliability_score: int = 0
    safety_score: int = 0
    data_sensitivity: str = "internal"
    complexity_score: int = 0
    verified_score: int = 0
    trust_tier: str = "unverified"

    output_type: Optional[str] = None
    output_classification: Optional[str] = None
    output_format: str = "text"

    security_tier: int = 1
    requires_review: bool = False

    tool_type: str = "prompt"
    app_type: str = "prompt"
    app_html: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_channel: Optional[str] = None
    system_prompt: Optional[str] = None
    hardened_prompt: Optional[str] = None
    prompt_diff: Optional[str] = None
    input_schema: str = "[]"
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 1000
    temperature: float = 0.3

    status: str = "draft"
    version: int = 1

    author_name: Optional[str] = None
    author_email: Optional[str] = None
    fork_of: Optional[int] = None
    parent_version: Optional[int] = None

    deployed: bool = False
    deployed_at: Optional[datetime] = None
    endpoint_url: Optional[str] = None
    access_token: Optional[str] = None
    instructions_url: Optional[str] = None

    run_count: int = 0
    unique_users: int = 0
    avg_rating: float = 0.0
    flag_count: int = 0

    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    last_run_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Tool":
        data = _row_to_dict(row, cursor)
        return cls(**_filter_known(cls, data))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dc_fields(self):
            v = getattr(self, f.name)
            out[f.name] = _serialize(v)
        if isinstance(out.get("input_schema"), str):
            try:
                out["input_schema"] = json.loads(out["input_schema"]) if out["input_schema"] else []
            except (json.JSONDecodeError, TypeError):
                pass
        return out


@dataclass
class Run:
    id: Optional[int] = None
    tool_id: Optional[int] = None
    tool_version: int = 1
    input_data: Optional[str] = None
    rendered_prompt: Optional[str] = None
    output_data: Optional[str] = None
    output_parsed: Optional[str] = None
    output_flagged: bool = False
    flag_reason: Optional[str] = None
    run_duration_ms: Optional[int] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    source: str = "web"
    session_id: Optional[str] = None
    rating: Optional[int] = None
    rating_note: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Run":
        data = _row_to_dict(row, cursor)
        return cls(**_filter_known(cls, data))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dc_fields(self):
            out[f.name] = _serialize(getattr(self, f.name))
        if isinstance(out.get("input_data"), str):
            try:
                out["input_data"] = json.loads(out["input_data"]) if out["input_data"] else {}
            except (json.JSONDecodeError, TypeError):
                pass
        return out


@dataclass
class AgentReview:
    id: Optional[int] = None
    tool_id: Optional[int] = None

    classifier_output: Optional[str] = None
    detected_output_type: Optional[str] = None
    detected_category: Optional[str] = None
    classification_confidence: Optional[float] = None

    security_scan_output: Optional[str] = None
    security_flags: Optional[str] = None
    security_score: Optional[int] = None
    pii_risk: bool = False
    injection_risk: bool = False
    data_exfil_risk: bool = False

    red_team_output: Optional[str] = None
    red_team_attacks_succeeded: int = 0
    attacks_attempted: int = 0
    attacks_succeeded: int = 0
    vulnerabilities: Optional[str] = None
    hardening_suggestions: Optional[str] = None

    hardener_output: Optional[str] = None
    original_prompt: Optional[str] = None
    hardened_prompt: Optional[str] = None
    changes_made: Optional[str] = None
    hardening_summary: Optional[str] = None

    qa_output: Optional[str] = None
    test_cases: Optional[str] = None
    qa_pass_rate: Optional[float] = None
    qa_issues: Optional[str] = None

    agent_recommendation: Optional[str] = None
    agent_confidence: Optional[float] = None
    review_summary: Optional[str] = None
    review_duration_ms: Optional[int] = None

    human_decision: Optional[str] = None
    human_reviewer: Optional[str] = None
    human_notes: Optional[str] = None
    human_overrides: Optional[str] = None

    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "AgentReview":
        data = _row_to_dict(row, cursor)
        return cls(**_filter_known(cls, data))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dc_fields(self):
            out[f.name] = _serialize(getattr(self, f.name))
        return out


@dataclass
class Skill:
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    prompt_text: Optional[str] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    author_name: Optional[str] = None
    source_url: Optional[str] = None
    upvotes: int = 0
    copy_count: int = 0
    featured: bool = False
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Skill":
        data = _row_to_dict(row, cursor)
        return cls(**_filter_known(cls, data))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dc_fields(self):
            out[f.name] = _serialize(getattr(self, f.name))
        return out


def compute_trust_tier(reliability: int, safety: int, verified: int,
                       security_tier: int = 1, data_sensitivity: str = "internal",
                       run_count: int = 0) -> str:
    """Compute trust tier from governance scores. Matches SPEC.md rules."""
    if security_tier >= 3 or data_sensitivity in ("confidential", "pii"):
        return "restricted"
    if run_count < 3 and verified == 0:
        return "unverified"
    if reliability >= 80 and safety >= 80 and verified >= 75:
        return "trusted"
    if reliability >= 60 and safety >= 60 and verified >= 50:
        return "verified"
    return "caution"
