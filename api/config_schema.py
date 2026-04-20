"""
Forge config schema validator.

Parses and validates a forge.config.yml YAML schema string,
returning typed dataclass objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml


VALID_FIELD_TYPES = {"string", "url", "email", "phone", "list", "freeform_file", "object_list"}
VALID_PROFILE_TYPES = {"string", "url", "email", "phone"}


@dataclass
class ConfigField:
    key: str
    type: str
    prompt: Optional[str] = None
    required: bool = False
    items: Optional[dict[str, Any]] = None


@dataclass
class ConfigSection:
    name: str
    fields: list[ConfigField] = field(default_factory=list)


@dataclass
class ConfigFile:
    path: str
    template: Optional[str] = None
    format: Optional[str] = None
    sections: list[ConfigSection] = field(default_factory=list)


@dataclass
class ProfileField:
    key: str
    prompt: str
    type: str
    source: Optional[str] = None
    required: bool = False


@dataclass
class Verification:
    command: str
    success_pattern: str

    def __post_init__(self) -> None:
        try:
            re.compile(self.success_pattern)
        except re.error as e:
            raise ValueError(f"Invalid success_pattern regex: {e}") from e


@dataclass
class Capabilities:
    network: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)


@dataclass
class ConfigSchema:
    schema_version: int
    app: str
    profile_fields: list[ProfileField]
    config_files: list[ConfigFile]
    verification: Optional[Verification] = None
    capabilities: Optional[Capabilities] = None


def _parse_field(raw: dict[str, Any]) -> ConfigField:
    if "key" not in raw or "type" not in raw:
        raise ValueError(f"Field missing required 'key' or 'type': {raw}")
    ftype = raw["type"]
    if ftype not in VALID_FIELD_TYPES:
        raise ValueError(f"Invalid field type '{ftype}' for key '{raw['key']}'. Must be one of {VALID_FIELD_TYPES}")
    return ConfigField(
        key=raw["key"],
        type=ftype,
        prompt=raw.get("prompt"),
        required=raw.get("required", False),
        items=raw.get("items"),
    )


def _parse_section(raw: dict[str, Any]) -> ConfigSection:
    if "name" not in raw:
        raise ValueError(f"Section missing 'name': {raw}")
    fields = [_parse_field(f) for f in raw.get("fields", [])]
    return ConfigSection(name=raw["name"], fields=fields)


def _parse_config_file(raw: dict[str, Any]) -> ConfigFile:
    if "path" not in raw:
        raise ValueError(f"Config file missing 'path': {raw}")
    sections = [_parse_section(s) for s in raw.get("sections", [])]
    return ConfigFile(
        path=raw["path"],
        template=raw.get("template"),
        format=raw.get("format"),
        sections=sections,
    )


def _parse_profile_field(raw: dict[str, Any]) -> ProfileField:
    for req in ("key", "prompt", "type", "required"):
        if req not in raw:
            raise ValueError(f"Profile field missing '{req}': {raw}")
    ptype = raw["type"]
    if ptype not in VALID_PROFILE_TYPES:
        raise ValueError(f"Invalid profile field type '{ptype}'. Must be one of {VALID_PROFILE_TYPES}")
    return ProfileField(
        key=raw["key"],
        prompt=raw["prompt"],
        type=ptype,
        source=raw.get("source"),
        required=raw["required"],
    )


def validate(schema_yaml: str) -> ConfigSchema:
    """Parse and validate a YAML schema string. Raises ValueError on invalid input."""
    try:
        data = yaml.safe_load(schema_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Schema must be a YAML mapping at the top level")

    # Required top-level keys
    for key in ("schema_version", "app", "profile_fields", "config_files"):
        if key not in data:
            raise ValueError(f"Missing required top-level key: '{key}'")

    sv = data["schema_version"]
    if not isinstance(sv, int) or sv < 1:
        raise ValueError(f"schema_version must be a positive integer, got: {sv}")

    app = data["app"]
    if not isinstance(app, str) or not app.strip():
        raise ValueError("app must be a non-empty string")

    profile_fields = [_parse_profile_field(pf) for pf in data["profile_fields"]]
    config_files = [_parse_config_file(cf) for cf in data["config_files"]]

    verification = None
    if "verification" in data:
        v = data["verification"]
        if "command" not in v or "success_pattern" not in v:
            raise ValueError("verification requires 'command' and 'success_pattern'")
        verification = Verification(command=v["command"], success_pattern=v["success_pattern"])

    capabilities = None
    if "capabilities" in data:
        c = data["capabilities"]
        capabilities = Capabilities(
            network=c.get("network", []),
            reads=c.get("reads", []),
            writes=c.get("writes", []),
        )

    return ConfigSchema(
        schema_version=sv,
        app=app,
        profile_fields=profile_fields,
        config_files=config_files,
        verification=verification,
        capabilities=capabilities,
    )
