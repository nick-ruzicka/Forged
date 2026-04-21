#!/usr/bin/env python3
"""
forge submit — packages a Forge project and submits it for governance review.

Run from inside a Forge project directory (contains .forge/manifest.json).

Usage:
    python3 ~/projects/forge/cli/forge_submit.py

Or:
    cd ~/forge-projects/my-tool
    forge-submit
"""

import json
import os
import sys
import tarfile
import tempfile
import io

# Default API endpoint
API_URL = os.environ.get("FORGE_API_URL", "http://localhost:8090")


def find_manifest():
    """Walk up from CWD to find .forge/manifest.json."""
    cwd = os.getcwd()
    while True:
        manifest_path = os.path.join(cwd, ".forge", "manifest.json")
        if os.path.exists(manifest_path):
            return manifest_path, cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            return None, None
        cwd = parent


def read_manifest(path):
    with open(path) as f:
        return json.load(f)


def package_project(project_dir, manifest):
    """Create a tar.gz of the project, excluding common build artifacts."""
    EXCLUDE_PATTERNS = {
        "node_modules", ".git", "__pycache__", "venv", ".venv",
        "dist", "build", ".next", ".DS_Store", "*.pyc",
        ".env", ".env.local", "credentials.json",
    }

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(project_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]

            for fname in files:
                # Skip excluded files
                if fname in EXCLUDE_PATTERNS or any(
                    fname.endswith(p.lstrip("*")) for p in EXCLUDE_PATTERNS if p.startswith("*")
                ):
                    continue

                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, project_dir)

                # Size limit: skip files > 1MB
                if os.path.getsize(full_path) > 1_000_000:
                    print(f"  skip (>1MB): {rel_path}")
                    continue

                tar.add(full_path, arcname=rel_path)

    buf.seek(0)
    return buf


def submit(project_dir, manifest):
    """Submit the packaged project to Forge's API."""
    import urllib.request
    import urllib.error

    slug = manifest.get("project_slug", os.path.basename(project_dir))
    print(f"\nSubmitting '{slug}' to Forge...")

    # Read CLAUDE.md for the validator
    claude_md_path = os.path.join(project_dir, "CLAUDE.md")
    claude_md = ""
    if os.path.exists(claude_md_path):
        with open(claude_md_path) as f:
            claude_md = f.read()

    payload = json.dumps({
        "manifest": manifest,
        "claude_md": claude_md,
        "project_slug": slug,
    }).encode()

    # Get user ID from forge config
    user_id = os.environ.get("FORGE_USER_ID", "")
    if not user_id:
        forge_user_path = os.path.expanduser("~/.forge/user-id")
        if os.path.exists(forge_user_path):
            user_id = open(forge_user_path).read().strip()
    if not user_id:
        user_id = "cli-user"

    req = urllib.request.Request(
        f"{API_URL}/api/submit-project",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Forge-User-Id": user_id,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"\n✓ Submitted successfully!")
            print(f"  Submission ID: {result.get('submission_id', '?')}")
            print(f"  Status: {result.get('status', 'pending')}")
            print(f"  Track at: {API_URL}/admin")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            print(f"\n✗ Submission failed: {err.get('error', body)}")
        except json.JSONDecodeError:
            print(f"\n✗ Submission failed ({e.code}): {body[:200]}")
        return None
    except urllib.error.URLError as e:
        print(f"\n✗ Could not reach Forge API at {API_URL}: {e.reason}")
        print("  Is the Forge server running?")
        return None


def main():
    print("forge submit — Forge Project Submission Tool")
    print("=" * 50)

    # Find manifest
    manifest_path, project_dir = find_manifest()
    if not manifest_path:
        print("\n✗ No .forge/manifest.json found.")
        print("  Run this from inside a Forge project directory.")
        print("  Create a project at: http://localhost:3002 → New Project")
        sys.exit(1)

    manifest = read_manifest(manifest_path)
    slug = manifest.get("project_slug", "unknown")
    skills = manifest.get("skills_applied", [])

    print(f"\nProject: {slug}")
    print(f"Directory: {project_dir}")
    print(f"Skills: {', '.join(skills) if skills else 'none'}")
    print(f"Checksum: {manifest.get('governance_checksum', 'none')}")

    # Check CLAUDE.md exists
    claude_md = os.path.join(project_dir, "CLAUDE.md")
    if not os.path.exists(claude_md):
        print("\n✗ CLAUDE.md not found. This is required for governance validation.")
        sys.exit(1)

    print(f"\nCLAUDE.md: {os.path.getsize(claude_md)} bytes")

    # Confirm
    answer = input("\nSubmit for review? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)

    # Submit
    result = submit(project_dir, manifest)
    if result:
        # Update submission config
        config_path = os.path.join(project_dir, ".forge", "submission-config.json")
        with open(config_path, "w") as f:
            json.dump({
                "submitted": True,
                "submission_id": result.get("submission_id"),
                "submitted_at": result.get("submitted_at"),
            }, f, indent=2)


if __name__ == "__main__":
    main()
