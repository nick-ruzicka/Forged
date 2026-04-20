"""
Auto-generate a forge.config.yml schema from a GitHub repository.

Fetches README + config files from a public GitHub repo, sends them to
Claude to produce a config schema, then validates the result against
the schema spec.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

import anthropic

from api.config_schema import validate


# Config file patterns to look for in the repo tree
_CONFIG_PATTERNS = [
    re.compile(r"\.example\.(ya?ml)$"),
    re.compile(r"\.sample\.(ya?ml)$"),
    re.compile(r"^\.env\.(example|sample)$"),
    re.compile(r"^config/"),
    re.compile(r"^CLAUDE\.md$", re.IGNORECASE),
    re.compile(r"^AGENTS\.md$", re.IGNORECASE),
    re.compile(r"^package\.json$"),
    re.compile(r"^pyproject\.toml$"),
    re.compile(r"^go\.mod$"),
]

_MAX_CONTENT_CHARS = 30_000
_SCHEMA_SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "specs", "config_schema.md",
)


def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Handles:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/branch/...
      - https://github.com/owner/repo.git
    """
    url = url.strip().rstrip("/")
    m = re.match(
        r"https?://github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+?)(?:\.git)?(?:/.*)?$",
        url,
    )
    if not m:
        raise ValueError(f"Could not parse GitHub URL: {url}")
    return m.group(1), m.group(2)


def _github_get(url: str) -> bytes:
    """Fetch a URL, adding a GitHub token header if available."""
    headers = {"User-Agent": "forge-schema-autogen/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise ValueError(f"GitHub API error {e.code} for {url}: {e.reason}") from e


def _fetch_repo_tree(owner: str, repo: str) -> list[dict[str, Any]]:
    """Return the full recursive tree listing for the default branch."""
    # Try main first, fall back to master
    for branch in ("main", "master"):
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            data = json.loads(_github_get(url))
            return data.get("tree", [])
        except ValueError:
            continue
    raise ValueError(f"Could not fetch repo tree for {owner}/{repo} (tried main, master)")


def _fetch_raw(owner: str, repo: str, path: str) -> str:
    """Fetch raw file content from GitHub."""
    # Try main, then master
    for branch in ("main", "master"):
        try:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            return _github_get(url).decode("utf-8", errors="replace")
        except ValueError:
            continue
    raise ValueError(f"Could not fetch {path} from {owner}/{repo}")


def _matches_config_pattern(path: str) -> bool:
    """Check if a file path matches any config pattern."""
    basename = path.rsplit("/", 1)[-1] if "/" in path else path
    for pat in _CONFIG_PATTERNS:
        if pat.search(path) or pat.search(basename):
            return True
    return False


def _load_schema_spec() -> str:
    """Load the config schema spec from docs/specs/config_schema.md."""
    try:
        with open(_SCHEMA_SPEC_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(
            f"Schema spec not found at {_SCHEMA_SPEC_PATH}. "
            "Ensure docs/specs/config_schema.md exists."
        )


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    # Remove ```yaml ... ``` or ``` ... ```
    if text.startswith("```"):
        # Remove opening fence line
        first_nl = text.index("\n") if "\n" in text else len(text)
        text = text[first_nl + 1:]
    if text.endswith("```"):
        text = text[: -3]
    return text.strip()


def generate_config_schema(github_url: str) -> str:
    """Fetch README + config files from a GitHub repo,
    send to Claude API to generate a forge.config.yml schema,
    validate the result, and return the YAML string.

    Raises ValueError if generation fails or output is invalid.
    """
    owner, repo = _parse_github_url(github_url)

    # 1. Fetch README (required)
    try:
        readme = _fetch_raw(owner, repo, "README.md")
    except ValueError:
        raise ValueError(f"README.md not found in {owner}/{repo}. Cannot generate schema without it.")

    # 2. Fetch repo tree and find config files
    tree = _fetch_repo_tree(owner, repo)
    config_paths = [
        entry["path"]
        for entry in tree
        if entry.get("type") == "blob" and _matches_config_pattern(entry["path"])
    ]

    # 3. Fetch config file contents, respecting total char limit
    config_contents: list[str] = []
    total_chars = len(readme)
    for path in config_paths:
        if total_chars >= _MAX_CONTENT_CHARS:
            break
        try:
            content = _fetch_raw(owner, repo, path)
            # Truncate individual files that are too large
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            entry_text = f"--- {path} ---\n{content}\n"
            total_chars += len(entry_text)
            config_contents.append(entry_text)
        except ValueError:
            continue  # Skip files we can't fetch

    # Truncate readme if needed
    remaining = _MAX_CONTENT_CHARS - sum(len(c) for c in config_contents)
    if len(readme) > remaining:
        readme = readme[:remaining] + "\n... (truncated)"

    # 4. Load schema spec
    schema_spec = _load_schema_spec()

    # 5. Build prompt
    config_files_text = "\n".join(config_contents) if config_contents else "(no config files found)"

    prompt = f"""Generate a forge.config.yml for this app.

<schema_spec>
{schema_spec}
</schema_spec>

<readme>
{readme}
</readme>

<config_files>
{config_files_text}
</config_files>

Output ONLY valid YAML matching the schema spec. No markdown fences, no explanation.
Identify every config file the user needs to create or edit.
For each required value, create a field with a clear prompt.
Use source: forge.user.name / forge.user.email where appropriate.
Include a verification command if the README mentions one (e.g., npm run doctor, pytest, etc).
The app slug should be "{repo}"."""

    # 6. Call Claude API
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        raise ValueError(f"Claude API error: {e}") from e

    # 7. Extract response text
    raw_yaml = ""
    for block in response.content:
        if block.type == "text":
            raw_yaml += block.text

    if not raw_yaml.strip():
        raise ValueError("Claude returned an empty response")

    # 8. Strip markdown fences if present
    schema_yaml = _strip_markdown_fences(raw_yaml)

    # 9. Validate
    try:
        validate(schema_yaml)
    except ValueError as e:
        raise ValueError(f"Generated schema failed validation: {e}\n\nRaw output:\n{schema_yaml}")

    return schema_yaml
