"""
Forge config agent — writes config files to an app directory based on a schema.

Given a validated ConfigSchema and a dict of user answers, this module:
1. Writes config files (YAML, Markdown, freeform) into the app directory
2. Validates that required fields are present
3. Optionally runs a verification command
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

import yaml

from api.config_schema import ConfigSchema, ConfigFile, ConfigSection


def configure_app(schema: ConfigSchema, answers: dict, app_dir: str) -> dict:
    """
    Takes a validated schema and user answers, writes config files to app_dir.

    Returns {success: bool, files_written: list, errors: list, verification: dict}
    """
    files_written: list[str] = []
    errors: list[str] = []

    # 1. Validate required fields
    missing = _check_required_fields(schema, answers)
    if missing:
        errors.extend(f"Missing required field: {f}" for f in missing)

    # 2. Write each config file
    for cf in schema.config_files:
        try:
            _write_config_file(cf, answers, app_dir)
            files_written.append(cf.path)
        except Exception as exc:
            errors.append(f"Error writing {cf.path}: {exc}")

    # 3. Run verification if specified
    verification: dict[str, Any] = {}
    if schema.verification and not errors:
        verification = _run_verification(schema.verification.command,
                                         schema.verification.success_pattern,
                                         app_dir)

    success = len(errors) == 0
    if verification.get("passed") is False:
        success = False

    return {
        "success": success,
        "files_written": files_written,
        "errors": errors,
        "verification": verification,
    }


def _check_required_fields(schema: ConfigSchema, answers: dict) -> list[str]:
    """Return list of missing required field keys."""
    missing = []

    # Check profile_fields
    for pf in schema.profile_fields:
        if pf.required and not answers.get(pf.key):
            missing.append(pf.key)

    # Check config_file sections
    for cf in schema.config_files:
        for section in cf.sections:
            for field in section.fields:
                if field.required:
                    # Try dotted key, bare key, and freeform fallbacks
                    dotted = f"{section.name}.{field.key}"
                    val = answers.get(dotted) or answers.get(field.key)
                    # For freeform_file fields, also try path-derived keys
                    if not val and field.type == "freeform_file":
                        stem = os.path.splitext(os.path.basename(cf.path))[0]
                        val = answers.get(f"{stem}_content") or answers.get(stem)
                    if not val:
                        missing.append(dotted)

    return missing


def _write_config_file(cf: ConfigFile, answers: dict, app_dir: str) -> None:
    """Write a single config file based on its type and template."""
    out_path = os.path.join(app_dir, cf.path)

    # Check for freeform_file — write content directly
    if _is_freeform(cf):
        content = _get_freeform_content(cf, answers)
        _ensure_parent(out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    fmt = (cf.format or "").lower()

    if fmt == "yaml" and cf.template:
        _write_yaml_from_template(cf, answers, app_dir, out_path)
    elif fmt == "yaml":
        _write_yaml_from_scratch(cf, answers, out_path)
    else:
        # Fallback: freeform or markdown — try to find content in answers
        content = _get_freeform_content(cf, answers)
        _ensure_parent(out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)


def _is_freeform(cf: ConfigFile) -> bool:
    """Check if any field in the config file is freeform_file type."""
    for section in cf.sections:
        for field in section.fields:
            if field.type == "freeform_file":
                return True
    return False


def _get_freeform_content(cf: ConfigFile, answers: dict) -> str:
    """Extract freeform content from answers for a config file."""
    for section in cf.sections:
        for field in section.fields:
            if field.type == "freeform_file":
                dotted = f"{section.name}.{field.key}"
                val = answers.get(dotted) or answers.get(f"{field.key}_{section.name}") or answers.get(field.key)
                # Also try a key derived from the file path, e.g. cv_content for cv.md
                if not val:
                    stem = os.path.splitext(os.path.basename(cf.path))[0]
                    val = answers.get(f"{stem}_content") or answers.get(stem)
                return str(val) if val else ""
    return ""


def _write_yaml_from_template(cf: ConfigFile, answers: dict, app_dir: str, out_path: str) -> None:
    """Read a YAML template, overlay answers, write the result."""
    template_path = os.path.join(app_dir, cf.template)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read())

    if not isinstance(data, dict):
        data = {}

    # Overlay answers onto the template based on section/field mapping
    for section in cf.sections:
        section_name = section.name
        if section_name not in data:
            data[section_name] = {}

        section_data = data[section_name]
        if not isinstance(section_data, dict):
            section_data = {}
            data[section_name] = section_data

        for field in section.fields:
            # Try dotted key first, then bare key
            dotted = f"{section_name}.{field.key}"
            val = answers.get(dotted) if dotted in answers else answers.get(field.key)

            if val is not None and val != "":
                # User provided a value — use it
                section_data[field.key] = val
            elif not field.required and field.key in section_data:
                # Optional field with no user answer — remove template default
                # to prevent example data (like "janesmith") leaking through
                del section_data[field.key]

    _ensure_parent(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _write_yaml_from_scratch(cf: ConfigFile, answers: dict, out_path: str) -> None:
    """Build a YAML file from scratch using section/field definitions and answers."""
    data: dict[str, Any] = {}

    for section in cf.sections:
        section_data: dict[str, Any] = {}
        for field in section.fields:
            dotted = f"{section.name}.{field.key}"
            val = answers.get(dotted) if dotted in answers else answers.get(field.key)
            if val is not None:
                section_data[field.key] = val
        if section_data:
            data[section.name] = section_data

    _ensure_parent(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _run_verification(command: str, success_pattern: str, app_dir: str) -> dict:
    """Run a verification command in the app directory and check output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = result.stdout + result.stderr
        matched = bool(re.search(success_pattern, combined))
        return {
            "command": command,
            "exit_code": result.returncode,
            "passed": matched,
            "output": combined[:2000],
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": -1,
            "passed": False,
            "output": "Verification timed out after 30 seconds",
        }
    except Exception as exc:
        return {
            "command": command,
            "exit_code": -1,
            "passed": False,
            "output": str(exc),
        }


def _ensure_parent(path: str) -> None:
    """Create parent directories if they don't exist."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
