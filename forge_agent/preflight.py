"""
Pre-install security checks.

- check_docker_image: Trivy CVE scan (graceful if Trivy not installed)
- check_skill_md: pattern scan for malicious SKILL.md content
"""
from __future__ import annotations

import json
import re
import subprocess


def check_docker_image(image: str) -> dict:
    """Run Trivy CVE scan. Returns {safe, critical, high, findings, trivy_available}."""
    try:
        r = subprocess.run(
            ["trivy", "image", "--format", "json",
             "--severity", "HIGH,CRITICAL", "--quiet", image],
            capture_output=True, text=True, timeout=120,
        )
        data = json.loads(r.stdout)
        results = data.get("Results") or []
        critical = sum(1 for res in results for v in res.get("Vulnerabilities", [])
                       if v.get("Severity") == "CRITICAL")
        high = sum(1 for res in results for v in res.get("Vulnerabilities", [])
                   if v.get("Severity") == "HIGH")
        findings = [
            {"id": v.get("VulnerabilityID"),
             "severity": v.get("Severity"),
             "title": (v.get("Title") or "")[:100],
             "fixed": v.get("FixedVersion") or "no fix"}
            for res in results
            for v in res.get("Vulnerabilities", [])
            if v.get("Severity") in ("CRITICAL", "HIGH")
        ][:10]
        return {"safe": critical == 0, "trivy_available": True,
                "critical": critical, "high": high, "findings": findings}
    except FileNotFoundError:
        return {"safe": True, "trivy_available": False,
                "message": "Trivy not installed — scan skipped"}
    except Exception as e:
        return {"safe": True, "trivy_available": True,
                "message": f"Scan failed: {str(e)[:100]}"}


def check_skill_md(content: str) -> dict:
    """Scan SKILL.md for malicious patterns. Returns {safe, warnings, auto_reject}."""
    warnings = []

    env_patterns = [
        r"\$ANTHROPIC_API_KEY", r"\$AWS_", r"\$GITHUB_TOKEN",
        r"process\.env\.", r"os\.environ\[", r"os\.getenv\(",
    ]
    for p in env_patterns:
        if re.search(p, content):
            warnings.append({"type": "env_var_access", "severity": "HIGH",
                             "detail": f"References sensitive env var: {p}"})

    if re.search(r"https?://.*\$\{.*\}", content):
        warnings.append({"type": "dynamic_url", "severity": "HIGH",
                         "detail": "Constructs URLs with variable data"})

    if re.search(r"subprocess|shell=True|exec\(|eval\(|os\.system", content):
        warnings.append({"type": "code_execution", "severity": "CRITICAL",
                         "detail": "Instructions to execute shell commands"})

    return {
        "safe": not any(w["severity"] == "CRITICAL" for w in warnings),
        "warnings": warnings,
        "auto_reject": any(w["severity"] == "CRITICAL" for w in warnings),
    }
