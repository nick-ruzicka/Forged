"""Forge dataclasses. Hydrated from psycopg2 RealDictRows.

Each class: from_row(row, cursor) classmethod and to_dict() method.
Fields kept here are deliberately the post-demolition set — prompt-era
columns (system_prompt, hardened_prompt, governance scores, etc.) are gone.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, fields as dc_fields
from datetime import datetime
from typing import Any, Dict, Optional


def _serialize(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _row_to_dict(row, cursor=None) -> Dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if cursor is not None and getattr(cursor, "description", None):
        return {col.name: row[i] for i, col in enumerate(cursor.description)}
    return dict(row)


def _filter_known(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    known = {f.name for f in dc_fields(cls)}
    return {k: v for k, v in data.items() if k in known}


# ---------------------------------------------------------------------------
# Tool — the catalog item. App-only post-demolition.
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    id: Optional[int] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None

    trust_tier: str = "verified"
    security_tier: int = 1
    requires_review: bool = False

    app_type: str = "app"
    app_html: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_channel: Optional[str] = None

    # Shelf / delivery (migration 009)
    delivery: str = "embedded"
    install_command: Optional[str] = None
    source_url: Optional[str] = None
    launch_url: Optional[str] = None
    icon: Optional[str] = None

    # Catalog signals (migration 010)
    install_count: int = 0
    review_count: int = 0
    setup_complexity: str = "one-click"

    # Source (migration 011)
    source: str = "internal"
    github_stars: Optional[int] = None
    github_license: Optional[str] = None
    github_last_commit: Optional[str] = None

    # Screenshots (migration 013)
    screenshots: Optional[str] = None  # JSON array of image URLs
    # Structured install config (migration 014)
    install_meta: Optional[str] = None  # JSON: {type, formula/package/url, ...}
    # Role tags (migration 015)
    role_tags: Optional[str] = None  # JSON array: ["AE", "SDR", "RevOps"]
    # Demo data (migration 016)
    demo_data: Optional[str] = None  # JSON: {key: value} for preview mode
    preview_tip: Optional[str] = None

    # Backend-aware (migration 012)
    has_local_backend: bool = False
    backend_port: Optional[int] = None
    backend_docker_image: Optional[str] = None
    backend_start_script: Optional[str] = None
    backend_health_path: str = "/health"

    # Status / authorship
    status: str = "draft"
    version: int = 1
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    fork_of: Optional[int] = None
    parent_version: Optional[int] = None

    # Deployment
    deployed: bool = False
    deployed_at: Optional[datetime] = None
    endpoint_url: Optional[str] = None
    access_token: Optional[str] = None
    instructions_url: Optional[str] = None

    # Usage stats (legacy, populated by older flows; harmless if zero)
    run_count: int = 0
    unique_users: int = 0
    avg_rating: float = 0.0
    flag_count: int = 0

    # Sandbox (migration 006)
    container_mode: bool = False
    container_id: Optional[str] = None
    container_status: str = "stopped"
    container_port: Optional[int] = None
    image_tag: Optional[str] = None
    last_request_at: Optional[datetime] = None

    # Timestamps
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Tool":
        return cls(**_filter_known(cls, _row_to_dict(row, cursor)))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dc_fields(self):
            v = getattr(self, f.name)
            # Heavy fields (full HTML) are only included when explicitly requested.
            if f.name == "app_html" and v is not None and len(v) > 200:
                # Keep the field but flag for callers; trim the wire payload
                pass
            out[f.name] = _serialize(v)
        return out


# ---------------------------------------------------------------------------
# Skill — a SKILL.md for Claude Code.
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    prompt_text: Optional[str] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    author_name: Optional[str] = None
    upvotes: int = 0
    copy_count: int = 0
    featured: bool = False
    source_url: Optional[str] = None

    # Governance (migration 018)
    review_status: str = "pending"
    review_id: Optional[int] = None
    version: int = 1
    parent_skill_id: Optional[int] = None
    data_sensitivity: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
    author_user_id: Optional[str] = None

    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "Skill":
        return cls(**_filter_known(cls, _row_to_dict(row, cursor)))

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: _serialize(getattr(self, f.name)) for f in dc_fields(self)}


# ---------------------------------------------------------------------------
# User — anonymous-by-default identity.
# ---------------------------------------------------------------------------

@dataclass
class User:
    user_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    team: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row, cursor=None) -> "User":
        return cls(**_filter_known(cls, _row_to_dict(row, cursor)))

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: _serialize(getattr(self, f.name)) for f in dc_fields(self)}


# ---------------------------------------------------------------------------
# Trust tier helper (kept for catalog rendering).
# ---------------------------------------------------------------------------

def compute_trust_tier(reliability: int = 0, safety: int = 0, verified: int = 0,
                       security_tier: int = 1, data_sensitivity: str = "internal",
                       run_count: int = 0) -> str:
    """Legacy helper. After demolition, most apps are simply 'verified' or 'trusted'."""
    if security_tier >= 3 or data_sensitivity in ("confidential", "pii"):
        return "restricted"
    if reliability >= 80 and safety >= 80 and verified >= 75:
        return "trusted"
    if reliability >= 60 and safety >= 60:
        return "verified"
    if run_count < 3:
        return "unverified"
    return "caution"
