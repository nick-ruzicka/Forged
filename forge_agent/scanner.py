"""Local scanner for installed Mac apps and Homebrew packages.

Pure functions — no HTTP, no global state. Called from forge_agent/agent.py.
"""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

DEFAULT_APPLICATIONS_ROOT = "/Applications"
_APPLICATIONS_GLOB_DEPTH = 2  # /Applications/*.app and /Applications/*/Contents/Applications/*.app


def scan() -> dict:
    """Return the full scan payload for POSTing to the backend."""
    return {
        "apps": _scan_applications(root=DEFAULT_APPLICATIONS_ROOT),
        "brew": _brew_list(cask=False),
        "brew_casks": _brew_list(cask=True),
    }


def _scan_applications(root: str = DEFAULT_APPLICATIONS_ROOT) -> list[dict]:
    """Find every *.app under root (depth 2), return [{bundle_id, name, path}].

    Skips bundles without Info.plist or without CFBundleIdentifier.
    Returns [] if root doesn't exist or is unreadable.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    results: list[dict] = []
    seen_paths: set[str] = set()
    try:
        # Depth 1: /Applications/*.app
        # Depth 2: /Applications/*/Contents/Applications/*.app (suite helpers like Xcode)
        candidates = list(root_path.glob("*.app")) + list(root_path.glob("*/Contents/Applications/*.app"))
    except OSError:
        return []

    for app in candidates:
        path_str = str(app)
        if path_str in seen_paths:
            continue
        seen_paths.add(path_str)
        info = app / "Contents" / "Info.plist"
        if not info.is_file():
            continue
        try:
            with info.open("rb") as fh:
                plist = plistlib.load(fh)
        except Exception:
            continue
        bundle_id = plist.get("CFBundleIdentifier")
        if not bundle_id:
            continue
        name = plist.get("CFBundleName") or app.stem
        results.append({"bundle_id": bundle_id, "name": name, "path": path_str})
    return results


def _brew_list(cask: bool) -> list[str]:
    """Return brew formulas (or casks). Empty list on failure or missing brew."""
    cmd = ["brew", "list"] + (["--cask"] if cask else ["--formula"])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
