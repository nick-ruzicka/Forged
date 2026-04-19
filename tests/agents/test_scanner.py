"""Unit tests for forge_agent.scanner — pure-function scanner for installed apps."""
from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from forge_agent import scanner


def _make_app(root: Path, name: str, bundle_id: str | None, bundle_name: str | None = None) -> Path:
    """Create a fake .app bundle. Pass bundle_id=None to skip CFBundleIdentifier."""
    app_dir = root / f"{name}.app" / "Contents"
    app_dir.mkdir(parents=True, exist_ok=True)
    plist = {}
    if bundle_id is not None:
        plist["CFBundleIdentifier"] = bundle_id
    if bundle_name is not None:
        plist["CFBundleName"] = bundle_name
    (app_dir / "Info.plist").write_bytes(plistlib.dumps(plist))
    return app_dir.parent


def test_scan_returns_normal_app(tmp_path):
    _make_app(tmp_path, "Pluely", "com.pluely.Pluely", "Pluely")
    result = scanner._scan_applications(root=str(tmp_path))
    assert {"bundle_id": "com.pluely.Pluely",
            "name": "Pluely",
            "path": str(tmp_path / "Pluely.app")} in result


def test_scan_uses_filename_when_bundle_name_missing(tmp_path):
    _make_app(tmp_path, "Raycast", "com.raycast.macos", bundle_name=None)
    result = scanner._scan_applications(root=str(tmp_path))
    names = [r["name"] for r in result]
    assert "Raycast" in names


def test_scan_skips_app_without_bundle_id(tmp_path):
    _make_app(tmp_path, "Broken", bundle_id=None, bundle_name="Broken")
    result = scanner._scan_applications(root=str(tmp_path))
    assert result == []


def test_scan_skips_app_with_no_info_plist(tmp_path):
    (tmp_path / "Empty.app" / "Contents").mkdir(parents=True)
    result = scanner._scan_applications(root=str(tmp_path))
    assert result == []


def test_scan_includes_nested_apps_at_depth_two(tmp_path):
    """Suite bundles like Xcode contain helper .app at Contents/Applications/*.app."""
    inner = tmp_path / "Xcode.app" / "Contents" / "Applications"
    inner.mkdir(parents=True)
    _make_app(inner, "Instruments", "com.apple.Instruments", "Instruments")
    # Also add the outer app
    _make_app(tmp_path, "Xcode", "com.apple.Xcode", "Xcode")
    result = scanner._scan_applications(root=str(tmp_path))
    bundle_ids = {r["bundle_id"] for r in result}
    assert "com.apple.Xcode" in bundle_ids
    assert "com.apple.Instruments" in bundle_ids


def test_scan_returns_empty_when_root_missing(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert scanner._scan_applications(root=str(missing)) == []


def test_brew_list_returns_lines(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "node\nraycast\n\nyarn\n"
    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    assert scanner._brew_list(cask=False) == ["node", "raycast", "yarn"]


def test_brew_list_returns_empty_when_brew_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("brew not in PATH")
    monkeypatch.setattr(scanner.subprocess, "run", boom)
    assert scanner._brew_list(cask=False) == []


def test_brew_list_returns_empty_on_nonzero_exit(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    assert scanner._brew_list(cask=True) == []


def test_brew_list_casks_uses_cask_flag(monkeypatch):
    seen_cmds: list[list[str]] = []

    class FakeProc:
        returncode = 0
        stdout = "raycast\n"

    def fake_run(cmd, **k):
        seen_cmds.append(cmd)
        return FakeProc()

    monkeypatch.setattr(scanner.subprocess, "run", fake_run)
    scanner._brew_list(cask=True)
    assert seen_cmds[-1] == ["brew", "list", "--cask"]


def test_scan_composes_apps_and_brew(monkeypatch, tmp_path):
    _make_app(tmp_path, "Pluely", "com.pluely.Pluely", "Pluely")

    class FakeProc:
        returncode = 0
        stdout = "node\n"

    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.setattr(scanner, "DEFAULT_APPLICATIONS_ROOT", str(tmp_path))

    payload = scanner.scan()
    assert any(a["bundle_id"] == "com.pluely.Pluely" for a in payload["apps"])
    assert payload["brew"] == ["node"]
    assert payload["brew_casks"] == ["node"]  # same fake; just proves both calls
