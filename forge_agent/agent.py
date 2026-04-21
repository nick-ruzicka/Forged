"""
Forge Agent v0.2.0 — security-hardened local daemon.

Lets Forge's frontend start Docker containers and install apps
without a terminal. Token-authenticated, origin-pinned, rate-limited,
audit-logged, command-allowlisted.

Listens on localhost:4242. Never exposes to the network.
"""
import collections
import http.server
import json
import logging
import os
import pathlib
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

# ── config ─────────────────────────────────────────────────────
PORT = 4242
VERSION = "0.2.0"
FORGE_DIR = pathlib.Path.home() / ".forge"
TOKEN_FILE = FORGE_DIR / "agent-token"
AUDIT_LOG = FORGE_DIR / "audit.log"
LOG_FILE = FORGE_DIR / "agent.log"
ALLOWED_ORIGIN = os.environ.get("FORGE_ORIGIN", "http://localhost:8090")
ALLOWED_ORIGINS = {ALLOWED_ORIGIN, "http://localhost:3000", "http://localhost:3002"}
MAX_STARTS_PER_HOUR = 10

# ── setup ──────────────────────────────────────────────────────
FORGE_DIR.mkdir(exist_ok=True)
(FORGE_DIR / "envs").mkdir(exist_ok=True)
(FORGE_DIR / "downloads").mkdir(exist_ok=True)

if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_hex(32))
TOKEN = TOKEN_FILE.read_text().strip()

# ── loggers ────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOG_FILE), level=logging.INFO,
    format="%(asctime)s [agent] %(message)s",
)
logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))

audit = logging.getLogger("audit")
audit.setLevel(logging.INFO)
_ah = logging.FileHandler(str(AUDIT_LOG))
_ah.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
audit.addHandler(_ah)

# ── rate limiter ───────────────────────────────────────────────
_rate_buckets = collections.defaultdict(list)


def _check_rate(action):
    now = time.time()
    b = _rate_buckets[action]
    b[:] = [t for t in b if now - t < 3600]
    if len(b) >= MAX_STARTS_PER_HOUR:
        return False
    b.append(now)
    return True


# ── Claude exec ────────────────────────────────────────────────
CLAUDE_RUNS_DIR = FORGE_DIR / "claude-runs"
CLAUDE_RUNS_DIR.mkdir(exist_ok=True)
MAX_CLAUDE_EXEC_PER_HOUR = 20
ALLOWED_PROJECT_DIRS = [
    str(pathlib.Path.home() / "projects" / "forge"),
    str(pathlib.Path.home() / "projects" / "chariot-signal-engine"),
    str(pathlib.Path.home() / "projects" / "job-search"),
]

# Track running processes
_running_runs: dict = {}  # run_id -> Popen

# Check claude CLI exists — detect install method
_CLAUDE_AVAILABLE = False
_CLAUDE_CMD = "claude"  # default
try:
    _r = subprocess.run(["which", "claude"], capture_output=True, text=True, timeout=5)
    if _r.returncode == 0:
        _CLAUDE_AVAILABLE = True
        _CLAUDE_CMD = _r.stdout.strip()  # full path like /opt/homebrew/bin/claude
        logging.info("claude CLI found: %s", _CLAUDE_CMD)
    else:
        # Try npx claude
        _r2 = subprocess.run(["npx", "claude", "--version"], capture_output=True, text=True, timeout=10)
        if _r2.returncode == 0:
            _CLAUDE_AVAILABLE = True
            _CLAUDE_CMD = "npx claude"
            logging.info("claude CLI found via npx: %s", _r2.stdout.strip())
        else:
            logging.warning("claude CLI not found in PATH or via npx")
except Exception:
    logging.warning("Could not check for claude CLI")

# Prompt red flag patterns
_PROMPT_RED_FLAGS = [
    (re.compile(r"rm\s+-rf\s+/", re.IGNORECASE), "rm -rf / detected"),
    (re.compile(r"curl\s+.*\|\s*(?:sh|bash)", re.IGNORECASE), "curl | sh pipe detected"),
    (re.compile(r"subprocess\.run.*shell\s*=\s*True", re.IGNORECASE), "subprocess shell=True in prompt"),
    (re.compile(r"\$ANTHROPIC_API_KEY.*https?://", re.IGNORECASE), "API key exfiltration pattern"),
    (re.compile(r"\$(?:AWS_|GITHUB_TOKEN|OPENAI_API).*https?://", re.IGNORECASE), "credential exfiltration pattern"),
    (re.compile(r"eval\s*\(\s*fetch", re.IGNORECASE), "eval(fetch) pattern"),
]


def _scan_prompt(prompt: str) -> list:
    """Scan prompt text for red-flag patterns. Returns list of flagged patterns."""
    flags = []
    for pattern, desc in _PROMPT_RED_FLAGS:
        if pattern.search(prompt):
            flags.append(desc)
    return flags


def _validate_project_dir(raw: str) -> str:
    """Validate and resolve a project directory. Returns resolved path or raises."""
    expanded = str(pathlib.Path(raw).expanduser().resolve())
    if not any(expanded.startswith(allowed) for allowed in ALLOWED_PROJECT_DIRS):
        raise ValueError(f"Project dir not in allowlist: {expanded}")
    if not pathlib.Path(expanded).is_dir():
        raise ValueError(f"Project dir does not exist: {expanded}")
    return expanded


# ── Installed apps registry + passive monitor ──────────────────
INSTALLED_FILE = FORGE_DIR / "installed.json"
USAGE_FILE = FORGE_DIR / "usage.jsonl"
_app_state_cache: dict = {}  # slug -> bool (running)
_app_session_starts: dict = {}  # slug -> timestamp
_app_launch_source: dict = {}  # slug -> source ('forge' | 'external')
_pending_launches: dict = {}  # slug -> expires_at (time.time() + 5)
_running_cache = {"data": [], "ts": 0}  # 15s cache
MONITOR_INTERVAL = 30


def _load_installed() -> list:
    if not INSTALLED_FILE.exists():
        return []
    try:
        return json.loads(INSTALLED_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_installed(apps: list):
    INSTALLED_FILE.write_text(json.dumps(apps, indent=2))


def _register_app(entry: dict):
    """Add an app to the installed registry if not already present."""
    apps = _load_installed()
    slug = entry.get("slug", "")
    if not slug:
        return
    # Update existing or append
    for i, a in enumerate(apps):
        if a.get("slug") == slug:
            apps[i] = {**a, **entry, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            _save_installed(apps)
            return
    entry["installed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    apps.append(entry)
    _save_installed(apps)


def _is_process_running(process_name: str) -> tuple:
    """Check if a process is running. Returns (running: bool, pid: int|None)."""
    try:
        r = subprocess.run(["pgrep", "-f", process_name],
                           capture_output=True, text=True, timeout=1)
        if r.returncode == 0 and r.stdout.strip():
            pid = int(r.stdout.strip().split()[0])
            return True, pid
        return False, None
    except subprocess.TimeoutExpired:
        return False, None
    except Exception:
        return False, None


def _log_session(slug: str, started_at: str, ended_at: str, duration_sec: int):
    """Append a usage session to the JSONL log."""
    source = _app_launch_source.pop(slug, "external")
    entry = {
        "slug": slug,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": duration_sec,
        "source": source,
    }
    with open(USAGE_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    audit.info("SESSION %s duration=%ds source=%s", slug, duration_sec, source)


def _monitor_loop():
    """Background thread: passively monitors installed apps every 30s.

    PRIVACY SCOPE: Only checks processes whose names are explicitly
    registered in ~/.forge/installed.json. Never enumerates all processes.
    Logs only: slug, start time, end time, duration. Never window titles,
    URLs, file names, command-line args, or any other user activity.
    """
    logging.info("Usage monitor started (interval=%ds)", MONITOR_INTERVAL)
    while True:
        try:
            installed = _load_installed()
            for app in installed:
                slug = app.get("slug", "")
                pname = app.get("process_name", "")
                if not slug or not pname:
                    continue
                running, pid = _is_process_running(pname)
                was_running = _app_state_cache.get(slug, False)

                if running and not was_running:
                    # Session started — check if launched from Forge
                    now_ts = time.time()
                    _app_session_starts[slug] = now_ts
                    if slug in _pending_launches and _pending_launches[slug] > now_ts:
                        _app_launch_source[slug] = "forge"
                        del _pending_launches[slug]
                    else:
                        _app_launch_source[slug] = "external"
                        _pending_launches.pop(slug, None)
                    logging.info("SESSION_START %s pid=%s source=%s", slug, pid, _app_launch_source[slug])
                elif not running and was_running:
                    # Session ended
                    start_ts = _app_session_starts.pop(slug, time.time())
                    duration = int(time.time() - start_ts)
                    if duration > 5:  # ignore sub-5s flickers
                        _log_session(
                            slug,
                            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_ts)),
                            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            duration,
                        )
                _app_state_cache[slug] = running
        except Exception as e:
            logging.error("monitor error: %s", e)
        time.sleep(MONITOR_INTERVAL)


# Start the monitor thread
import threading as _threading
_monitor_thread = _threading.Thread(target=_monitor_loop, daemon=True)
_monitor_thread.start()


# ── Docker safety ──────────────────────────────────────────────
ALLOWED_DOCKER_SUBCMDS = {"run", "stop", "rm", "inspect", "pull", "images", "ps", "network"}
MANAGED_CONTAINERS = set()
_IMAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-/]*(?::[a-zA-Z0-9._\-]+)?$")


def _safe_docker(args):
    if not args or args[0] not in ALLOWED_DOCKER_SUBCMDS:
        raise ValueError(f"Docker subcommand not allowed: {args[0] if args else 'none'}")
    cmd = ["docker"] + [str(a) for a in args]
    audit.info("EXEC %s", cmd)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def _validate_image(image):
    if not image or not _IMAGE_RE.match(image):
        raise ValueError(f"Invalid image name: {image}")
    if ".." in image or image.startswith("/"):
        raise ValueError(f"Invalid image path: {image}")
    return image


def _ensure_network():
    r = subprocess.run(["docker", "network", "inspect", "forge-isolated"], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["docker", "network", "create", "--driver=bridge", "forge-isolated"],
                       capture_output=True)


# ── brew/pip safety ────────────────────────────────────────────
_FORMULA_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-/]+$")
_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-]+$")

# ── git_clone safety ───────────────────────────────────────────
ALLOWED_GIT_HOSTS = frozenset({"github.com", "gitlab.com", "bitbucket.org"})
_GIT_REPO_RE = re.compile(
    r"^https://(github\.com|gitlab\.com|bitbucket\.org)/"
    r"[A-Za-z0-9][A-Za-z0-9._\-]{0,38}/"
    r"[A-Za-z0-9][A-Za-z0-9._\-]{0,99}(\.git)?/?$"
)
# npx commands are high-risk (arbitrary package execution) — restrict to known
# post-install patterns used by installable apps (headless browser setup, etc.).
_ALLOWED_NPX_CMDS = frozenset({
    "playwright install",
    "playwright install chromium",
    "playwright install firefox",
    "playwright install webkit",
    "playwright install chromium --with-deps",
    "puppeteer browsers install chrome",
})
_FORGE_APPS_DIR = pathlib.Path.home() / "forge-apps"


def _validate_git_dest(raw: str) -> str:
    """Expand a dest path and ensure it lives under ~/forge-apps/ (preferred)
    or directly under $HOME. Rejects system dirs, home-root itself, and any
    traversal outside those roots. Returns the resolved absolute path."""
    if not raw or not isinstance(raw, str):
        raise ValueError("dest is required")
    expanded = pathlib.Path(raw).expanduser()
    # Resolve without requiring existence (clone target must not exist yet).
    try:
        expanded = expanded.resolve(strict=False)
    except Exception:
        raise ValueError(f"cannot resolve dest: {raw}")
    home = pathlib.Path.home().resolve()
    forge_apps = _FORGE_APPS_DIR.resolve()
    # Home itself is off-limits — clones must go into a subdir.
    if expanded == home:
        raise ValueError("dest cannot be the home directory")
    # Must be under ~/forge-apps/ OR under $HOME.
    s = str(expanded)
    if not (s.startswith(str(forge_apps) + os.sep) or s.startswith(str(home) + os.sep)):
        raise ValueError(f"dest must be under ~/ or ~/forge-apps/: {s}")
    # Never write to system/bin/etc/var paths even if they appear nested in home.
    forbidden_roots = ("/etc", "/System", "/usr", "/bin", "/sbin", "/var",
                       "/private/etc", "/private/var", "/Library/System")
    for f in forbidden_roots:
        if s == f or s.startswith(f + os.sep):
            raise ValueError(f"dest in system dir: {s}")
    return s


# ── handler ────────────────────────────────────────────────────

class AgentHandler(http.server.BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json({"status": "ok", "version": VERSION,
                        "managed_containers": len(MANAGED_CONTAINERS),
                        "claude_available": _CLAUDE_AVAILABLE,
                        "running_claude_runs": len(_running_runs)})
            return
        if parsed.path == "/status":
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or [""])[0]
            cname = f"forge-{name}"
            if not name or cname not in MANAGED_CONTAINERS:
                self._json({"running": False, "managed": False})
                return
            r = _safe_docker(["inspect", "--format", "{{.State.Running}}", cname])
            self._json({"running": r.stdout.strip() == "true", "managed": True})
            return
        if parsed.path == "/running":
            self._handle_running()
            return
        if parsed.path == "/updates":
            self._handle_updates()
            return
        if parsed.path == "/privacy":
            self._handle_privacy()
            return
        if parsed.path == "/usage":
            qs = parse_qs(parsed.query)
            slug = (qs.get("slug") or [""])[0]
            self._handle_usage(slug)
            return
        if parsed.path.startswith("/claude-exec/log/"):
            run_id = parsed.path.split("/")[-1]
            self._handle_claude_log(run_id)
            return
        if parsed.path == "/claude-exec/runs":
            self._handle_claude_list()
            return
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        if not self._check_token():
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            self._json({"error": "invalid JSON"}, 400)
            return
        if self.path == "/run":
            self._handle_run(body)
        elif self.path == "/install":
            self._handle_install(body)
        elif self.path == "/launch":
            self._handle_launch(body)
        elif self.path == "/uninstall":
            self._handle_uninstall(body)
        elif self.path == "/stop":
            self._handle_stop(body)
        elif self.path == "/claude-exec":
            self._handle_claude_exec(body)
        elif self.path == "/open-terminal":
            self._handle_open_terminal(body)
        else:
            self._json({"error": "not_found"}, 404)

    # ── /run (Docker containers) ──────────────────────────────

    def _handle_run(self, body):
        if not _check_rate("run"):
            self._json({"error": "Rate limit: max 10 starts/hour"}, 429)
            return
        try:
            image = _validate_image(body.get("image", ""))
            port = int(body.get("port", 0))
            slug = re.sub(r"[^a-z0-9\-]", "", str(body.get("name", "app"))[:50])
            if not (1024 <= port <= 65535):
                raise ValueError("Port must be 1024-65535")
        except (ValueError, TypeError) as e:
            self._json({"error": str(e)}, 400)
            return

        cname = f"forge-{slug}"

        # Already running?
        r = _safe_docker(["inspect", "--format", "{{.State.Running}}", cname])
        if r.stdout.strip() == "true":
            self._json({"success": True, "message": "already running", "container_id": cname})
            return

        _ensure_network()
        _safe_docker(["rm", "-f", cname])
        MANAGED_CONTAINERS.discard(cname)

        # Preflight CVE scan (non-blocking if Trivy not installed)
        try:
            from forge_agent.preflight import check_docker_image
            scan = check_docker_image(image)
            audit.info("PREFLIGHT %s critical=%s high=%s", image,
                       scan.get("critical", 0), scan.get("high", 0))
            if not scan.get("safe", True):
                self._json({
                    "success": False, "blocked": True, "reason": "security_scan",
                    "message": f"Blocked: {scan.get('critical', 0)} critical CVEs",
                    "findings": scan.get("findings", [])[:5],
                }, 403)
                return
        except ImportError:
            pass
        except Exception as exc:
            audit.warning("preflight error: %s", exc)

        # SSE stream: pull then run
        self._sse_start()

        # Check if cached
        check = subprocess.run(["docker", "image", "inspect", image],
                               capture_output=True, text=True)
        if check.returncode == 0:
            self._sse_event("cached", {"message": f"Image {image} cached locally"})
        else:
            self._sse_event("pulling", {"message": f"Downloading {image}..."})
            pull = subprocess.Popen(["docker", "pull", image],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
            layers = 0
            for line in pull.stdout:
                line = line.strip()
                if not line:
                    continue
                if "Pull complete" in line or "Download complete" in line:
                    layers += 1
                    self._sse_event("layer", {"message": line, "layers_done": layers})
                elif "Already exists" in line:
                    layers += 1
                    self._sse_event("cached_layer", {"message": line, "layers_done": layers})
                else:
                    self._sse_event("progress", {"message": line})
            pull.wait()
            if pull.returncode != 0:
                self._sse_event("error", {"success": False, "message": "Pull failed"})
                self._sse_end()
                return
            self._sse_event("pulled", {"message": f"Image ready ({layers} layers)"})

        self._sse_event("starting", {"message": "Starting container..."})
        token = secrets.token_hex(16)
        r = _safe_docker([
            "run", "-d", "--name", cname,
            "-p", f"{port}:{port}",
            "--memory=512m", "--cpus=1",
            "-e", f"FORGE_CONTAINER_TOKEN={token}",
            image,
        ])
        success = r.returncode == 0
        if success:
            MANAGED_CONTAINERS.add(cname)
            self._sse_event("started", {"success": True,
                                        "container_id": r.stdout.strip()[:64],
                                        "message": "Container running"})
        else:
            err = r.stderr.strip()[:200]
            if "Cannot connect to the Docker daemon" in err:
                err = "Docker not running. Start Docker Desktop first."
            self._sse_event("error", {"success": False, "message": err})
        self._sse_end()

    # ── /install (brew, pip, dmg) ─────────────────────────────

    def _handle_install(self, body):
        if not _check_rate("install"):
            self._json({"error": "Rate limit: max 10 installs/hour"}, 429)
            return

        install_type = body.get("type", "")
        name = str(body.get("name", "app"))[:50]

        self._sse_start()

        slug = body.get("slug", re.sub(r"[^a-z0-9\-]", "", name.lower()))
        process_name = body.get("process_name", name)

        if install_type == "brew":
            formula = body.get("formula", "")
            cask = body.get("cask", True)
            tap = body.get("tap", "")
            extra_formulas = body.get("extra_formulas", [])
            if not _FORMULA_RE.match(formula):
                self._sse_event("error", {"success": False, "message": f"Invalid formula: {formula}"})
                self._sse_end()
                return
            # Run brew tap first if specified
            if tap and _FORMULA_RE.match(tap):
                audit.info("BREW_TAP %s", tap)
                self._sse_event("progress", {"message": f"Tapping {tap}..."})
                tap_proc = subprocess.run(["brew", "tap", tap],
                                          capture_output=True, text=True, timeout=60)
                if tap_proc.returncode != 0:
                    err = tap_proc.stderr.strip() or tap_proc.stdout.strip()
                    # "already tapped" is fine
                    if "already tapped" not in err.lower():
                        self._sse_event("error", {"success": False,
                                                  "message": f"brew tap failed: {err[:200]}"})
                        self._sse_end()
                        return
                self._sse_event("progress", {"message": f"Tapped {tap}"})
            # Main install
            cmd = ["brew", "install"]
            if cask:
                cmd.append("--cask")
            cmd.append(formula)
            audit.info("BREW_INSTALL %s", formula)
            self._stream_process(cmd, name, registry_entry={
                "slug": slug, "name": name, "process_name": process_name,
                "install_type": "brew", "formula": formula,
            })
            # Install extra formulas (e.g. backend companion packages)
            for extra in extra_formulas:
                if isinstance(extra, str) and _FORMULA_RE.match(extra):
                    audit.info("BREW_INSTALL_EXTRA %s", extra)
                    self._sse_event("progress", {"message": f"Installing {extra}..."})
                    self._stream_process(["brew", "install", extra], extra)

        elif install_type == "pip":
            package = body.get("package", "")
            if not _PACKAGE_RE.match(package):
                self._sse_event("error", {"success": False, "message": f"Invalid package: {package}"})
                self._sse_end()
                return
            audit.info("PIP_INSTALL %s", package)
            self._stream_process(["pip3", "install", package], name, registry_entry={
                "slug": slug, "name": name, "process_name": process_name,
                "install_type": "pip", "package": package,
            })

        elif install_type == "dmg":
            url = body.get("url", "")
            filename = re.sub(r"[^a-zA-Z0-9._\-]", "", str(body.get("filename", "app.dmg"))[:100])
            if not url.startswith("https://"):
                self._sse_event("error", {"success": False, "message": "Only HTTPS URLs allowed"})
                self._sse_end()
                return
            if any(x in url for x in ["localhost", "127.0.0.1", "192.168.", "10.0."]):
                self._sse_event("error", {"success": False, "message": "Private URLs not allowed"})
                self._sse_end()
                return
            download_path = FORGE_DIR / "downloads" / filename
            audit.info("DMG_DOWNLOAD %s -> %s", url, download_path)
            self._sse_event("progress", {"message": f"Downloading {filename}..."})
            self._stream_process(
                ["curl", "-L", "--max-filesize", "500000000",
                 "--progress-bar", "-o", str(download_path), url],
                name,
            )
            # If download succeeded, open the DMG and register
            if download_path.exists():
                subprocess.run(["open", str(download_path)], capture_output=True)
                _register_app({
                    "slug": slug, "name": name, "process_name": process_name,
                    "install_type": "dmg", "url": url,
                })
                self._sse_event("installed", {
                    "success": True,
                    "message": "Download complete — installer opened. Follow on-screen instructions.",
                })
            self._sse_end()
            return

        elif install_type == "command":
            # Restricted command execution — only allows known safe install patterns
            command = body.get("command", "")
            if not command:
                self._sse_event("error", {"success": False, "message": "No command provided"})
                self._sse_end()
                return

            # Allowlist: only permit known install tools, no shell metacharacters
            ALLOWED_PREFIXES = ("brew install", "npm install", "pip install", "pipx install",
                                "cargo install", "go install", "npx", "pip3 install")
            BLOCKED_CHARS = set(";|&`$(){}\\'\"\n")
            cmd_clean = command.strip()
            is_allowed = any(cmd_clean.startswith(p) for p in ALLOWED_PREFIXES)
            has_blocked = bool(BLOCKED_CHARS & set(cmd_clean))

            if not is_allowed or has_blocked:
                audit.warning("BLOCKED_INSTALL_CMD %s", cmd_clean[:200])
                self._sse_event("error", {"success": False,
                                          "message": "Command not in allowlist. Only brew/npm/pip/cargo/go install commands are permitted."})
                self._sse_end()
                return

            audit.info("ALLOWED_INSTALL %s", cmd_clean[:200])
            # Split into args list — no shell=True
            cmd_parts = cmd_clean.split()
            self._stream_process(cmd_parts, name, registry_entry={
                "slug": slug, "name": name, "process_name": slug,
                "install_type": "command", "command": cmd_clean,
            })
            return

        elif install_type == "git_clone":
            self._handle_git_clone_install(body, slug, name, process_name)
            return

        else:
            self._sse_event("error", {"success": False, "message": f"Unknown type: {install_type}"})
            self._sse_end()

    def _handle_git_clone_install(self, body, slug, name, process_name):
        """Structured `git clone` + post-install steps.

        Body shape:
          {
            "type": "git_clone",
            "repo": "https://github.com/owner/repo.git",
            "dest": "~/forge-apps/<slug>",
            "post_install": [
              {"type": "npm_install", "cwd": "~/forge-apps/<slug>"},
              {"type": "pip_install", "cwd": "...", "requirements": "requirements.txt"},
              {"type": "cargo_install", "cwd": "..."},
              {"type": "go_install", "cwd": "..."},
              {"type": "npx", "cwd": "...", "cmd": "playwright install chromium"}
            ]
          }

        Validations (all fail-fast, all pre-disk):
          * repo host ∈ ALLOWED_GIT_HOSTS
          * dest under ~/ or ~/forge-apps/, never a system dir, never home itself
          * each post_install step uses an allowlisted sub-tool
          * npx `cmd` exact-matches _ALLOWED_NPX_CMDS
        """
        repo = (body.get("repo") or "").strip()
        dest_raw = (body.get("dest") or "").strip()
        post_install = body.get("post_install") or []

        # 1. repo URL
        if not _GIT_REPO_RE.match(repo):
            try:
                host = urlparse(repo).hostname or "(none)"
            except Exception:
                host = "(none)"
            msg = (f"repo host not allowlisted: {host}"
                   if host not in ALLOWED_GIT_HOSTS
                   else f"invalid repo URL: {repo[:120]}")
            audit.warning("BLOCKED_GIT_CLONE %s", msg)
            self._sse_event("error", {"success": False, "message": msg})
            self._sse_end()
            return

        # 2. dest path
        try:
            dest_abs = _validate_git_dest(dest_raw)
        except ValueError as e:
            audit.warning("BLOCKED_GIT_CLONE_DEST %s", e)
            self._sse_event("error", {"success": False, "message": f"invalid dest: {e}"})
            self._sse_end()
            return

        # 3. post_install steps (validate BEFORE touching disk)
        if not isinstance(post_install, list):
            self._sse_event("error", {"success": False,
                                      "message": "post_install must be a list"})
            self._sse_end()
            return

        validated = []  # list[(cmd_args, cwd_abs, label)]
        for idx, step in enumerate(post_install):
            if not isinstance(step, dict):
                self._sse_event("error", {"success": False,
                                          "message": f"post_install[{idx}] must be an object"})
                self._sse_end()
                return
            step_type = step.get("type", "")
            cwd_raw = (step.get("cwd") or dest_abs).strip()
            try:
                cwd_abs = _validate_git_dest(cwd_raw)
            except ValueError as e:
                self._sse_event("error", {"success": False,
                                          "message": f"invalid cwd for step {idx} ({step_type}): {e}"})
                self._sse_end()
                return

            if step_type == "npm_install":
                validated.append((["npm", "install"], cwd_abs, "npm install"))
            elif step_type == "pip_install":
                req = (step.get("requirements") or "requirements.txt").strip()
                if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._/\-]{0,100}$", req):
                    self._sse_event("error", {"success": False,
                                              "message": f"invalid requirements path: {req[:100]}"})
                    self._sse_end()
                    return
                validated.append((["pip3", "install", "-r", req], cwd_abs, f"pip3 install -r {req}"))
            elif step_type == "cargo_install":
                validated.append((["cargo", "install", "--path", "."], cwd_abs, "cargo install --path ."))
            elif step_type == "go_install":
                validated.append((["go", "install", "./..."], cwd_abs, "go install ./..."))
            elif step_type == "npx":
                cmd_str = (step.get("cmd") or "").strip()
                if cmd_str not in _ALLOWED_NPX_CMDS:
                    audit.warning("BLOCKED_NPX %s", cmd_str[:200])
                    self._sse_event("error", {"success": False,
                                              "message": f"npx cmd not allowlisted: {cmd_str[:120]}"})
                    self._sse_end()
                    return
                validated.append((["npx"] + cmd_str.split(), cwd_abs, f"npx {cmd_str}"))
            else:
                self._sse_event("error", {"success": False,
                                          "message": f"post_install type not allowed: {step_type}"})
                self._sse_end()
                return

        # 4. destination must not exist (avoid overwriting user work)
        if pathlib.Path(dest_abs).exists():
            self._sse_event("error", {"success": False,
                                      "message": f"dest already exists: {dest_abs}. "
                                                 f"Remove it first or pick a different dest."})
            self._sse_end()
            return

        # 5. ensure parent dir exists (mkdir ~/forge-apps/ on first use)
        try:
            pathlib.Path(dest_abs).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._sse_event("error", {"success": False,
                                      "message": f"cannot create parent dir: {str(e)[:120]}"})
            self._sse_end()
            return

        audit.info("GIT_CLONE repo=%s dest=%s steps=%d", repo, dest_abs, len(validated))

        # 6. clone
        self._sse_event("progress", {"message": f"Cloning {repo} → {dest_abs}..."})
        clone_rc = self._run_step(["git", "clone", "--depth", "1", repo, dest_abs], cwd=None)
        if clone_rc != 0:
            self._sse_event("error", {"success": False,
                                      "message": f"git clone failed (exit {clone_rc})"})
            self._sse_end()
            return

        # 7. run each post_install step in order
        for cmd, cwd_abs, label in validated:
            self._sse_event("progress", {"message": f"Running: {label} (in {cwd_abs})"})
            rc = self._run_step(cmd, cwd=cwd_abs)
            if rc != 0:
                self._sse_event("error", {"success": False,
                                          "message": f"{label} failed (exit {rc})"})
                self._sse_end()
                return

        # 8. success — register and close stream
        _register_app({
            "slug": slug, "name": name, "process_name": process_name,
            "install_type": "git_clone", "repo": repo, "install_path": dest_abs,
        })
        self._sse_event("installed", {"success": True,
                                      "message": f"{name} installed to {dest_abs}"})
        self._sse_end()

    def _run_step(self, cmd, cwd=None):
        """Run one step: stream stdout/stderr as SSE progress lines, return exit code.
        Does NOT emit installed/error/end — the caller owns lifecycle events."""
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, cwd=cwd)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._sse_event("progress", {"message": line})
            proc.wait()
            return proc.returncode
        except FileNotFoundError as e:
            self._sse_event("progress", {"message": f"command not found: {str(e)[:120]}"})
            return 127
        except Exception as e:
            self._sse_event("progress", {"message": f"exec error: {str(e)[:200]}"})
            return 1

    def _stream_process(self, cmd, name, registry_entry=None):
        """Run a command, stream stdout/stderr via SSE, emit installed/error at end.
        If registry_entry is provided, append to installed.json on success."""
        self._sse_event("installing", {"message": f"Running: {' '.join(cmd)}"})
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._sse_event("progress", {"message": line})
            proc.wait()
            if proc.returncode == 0:
                if registry_entry:
                    _register_app(registry_entry)
                self._sse_event("installed", {"success": True, "message": f"{name} installed successfully"})
            else:
                self._sse_event("error", {"success": False,
                                          "message": f"Install failed (exit {proc.returncode})"})
        except Exception as exc:
            self._sse_event("error", {"success": False, "message": str(exc)[:200]})
        self._sse_end()

    # ── /launch ───────────────────────────────────────────────

    def _handle_launch(self, body):
        """Launch or reveal a locally installed app (macOS)."""
        app_slug = body.get("app_slug", "")
        app_name = body.get("app_name", "")
        action = body.get("action", "launch")  # "launch" or "reveal"
        if not app_name and not app_slug:
            self._json({"error": "app_name or app_slug required"}, 400)
            return
        # For reveal, look up install_path from installed.json
        if action == "reveal":
            installed = _load_installed()
            app_entry = next((a for a in installed if a.get("slug") == app_slug), None)
            install_path = app_entry.get("install_path", "") if app_entry else ""
            if not install_path:
                install_path = f"/Applications/{app_name}.app"
            try:
                r = subprocess.run(["open", "-R", install_path],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    self._json({"success": True, "message": f"Revealed {install_path}"})
                else:
                    self._json({"success": False, "message": r.stderr.strip()[:200]}, 400)
            except subprocess.TimeoutExpired:
                self._json({"success": False, "message": "Reveal timed out"}, 500)
            return
        # Original launch logic
        if not app_name:
            self._json({"error": "app_name required"}, 400)
            return
        if not re.match(r"^[a-zA-Z0-9 .\-]+$", app_name):
            self._json({"error": "Invalid app name"}, 400)
            return
        audit.info("LAUNCH %s (%s)", app_name, app_slug)
        if app_slug:
            _pending_launches[app_slug] = time.time() + 45
        try:
            r = subprocess.run(["open", "-a", app_name],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                self._json({"success": True, "message": f"Launched {app_name}"})
            else:
                self._json({"success": False,
                            "message": r.stderr.strip()[:200] or f"Could not launch {app_name}"}, 400)
        except subprocess.TimeoutExpired:
            self._json({"success": False, "message": "Launch timed out"}, 500)

    # ── /running ──────────────────────────────────────────────

    def _handle_running(self):
        """Return running status of all installed apps. Cached 15s."""
        now = time.time()
        if now - _running_cache["ts"] < 15 and _running_cache["data"]:
            self._json({"apps": _running_cache["data"]})
            return
        installed = _load_installed()
        results = []
        for app in installed:
            slug = app.get("slug", "")
            pname = app.get("process_name", "")
            if not slug or not pname:
                continue
            running, pid = _is_process_running(pname)
            entry = {
                "slug": slug,
                "name": app.get("name", slug),
                "running": running,
                "pid": pid,
            }
            # Calculate uptime if we have a session start
            if running and slug in _app_session_starts:
                entry["uptime_sec"] = int(now - _app_session_starts[slug])
            results.append(entry)
        _running_cache["data"] = results
        _running_cache["ts"] = now
        self._json({"apps": results})

    # ── /updates ──────────────────────────────────────────────

    def _handle_updates(self):
        """Check for available updates for installed apps."""
        installed = _load_installed()
        updates = []
        # Check brew outdated (casks)
        brew_apps = [a for a in installed if a.get("install_type") == "brew"]
        if brew_apps:
            try:
                r = subprocess.run(["brew", "outdated", "--cask", "--greedy"],
                                   capture_output=True, text=True, timeout=30)
                outdated_lines = r.stdout.strip().lower().split("\n") if r.stdout.strip() else []
                for app in brew_apps:
                    formula = app.get("formula", "").lower()
                    for line in outdated_lines:
                        if formula and formula in line:
                            updates.append({
                                "slug": app.get("slug"),
                                "name": app.get("name"),
                                "type": "brew",
                                "detail": line.strip(),
                            })
            except (subprocess.TimeoutExpired, Exception) as e:
                logging.warning("brew outdated check failed: %s", e)
        self._json({"updates": updates, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    # ── /privacy ──────────────────────────────────────────────

    def _handle_privacy(self):
        """Return exactly what forge-agent monitors and how."""
        installed = _load_installed()
        monitored = [{"slug": a.get("slug"), "process_name": a.get("process_name")}
                     for a in installed if a.get("process_name")]
        self._json({
            "scope": "Only apps explicitly registered in ~/.forge/installed.json",
            "method": "pgrep -f <process_name> every 30 seconds",
            "data_collected": [
                "slug (app identifier)",
                "session start time",
                "session end time",
                "session duration in seconds",
            ],
            "data_not_collected": [
                "window titles",
                "URLs visited",
                "file names or paths",
                "command-line arguments",
                "keystrokes or clipboard",
                "screen contents",
                "any data from non-Forge apps",
            ],
            "storage": str(USAGE_FILE),
            "currently_monitoring": monitored,
            "monitor_interval_sec": MONITOR_INTERVAL,
        })

    def _handle_usage(self, slug):
        """Return usage stats for a slug from usage.jsonl, aggregated over 7 days."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        day_buckets = {}
        for i in range(7):
            d = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
            day_buckets[d] = {"date": d, "duration_sec": 0, "count": 0}

        last_opened = None
        try:
            with open(USAGE_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if slug and entry.get("slug") != slug:
                        continue
                    started = entry.get("started_at", "")
                    try:
                        dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    if dt >= cutoff:
                        day_key = dt.strftime("%Y-%m-%d")
                        if day_key in day_buckets:
                            day_buckets[day_key]["duration_sec"] += entry.get("duration_sec", 0)
                            day_buckets[day_key]["count"] += 1
                    if last_opened is None or started > last_opened:
                        last_opened = started
        except FileNotFoundError:
            pass

        sessions_7d = list(day_buckets.values())
        total_sec = sum(d["duration_sec"] for d in sessions_7d)
        session_count = sum(d["count"] for d in sessions_7d)
        self._json({
            "slug": slug,
            "sessions_7d": sessions_7d,
            "total_sec_7d": total_sec,
            "session_count_7d": session_count,
            "last_opened": last_opened,
        })

    # ── /uninstall ────────────────────────────────────────────

    def _handle_uninstall(self, body):
        """Remove an app from the installed registry and purge usage data."""
        slug = body.get("slug", "")
        if not slug:
            self._json({"error": "slug required"}, 400)
            return
        apps = _load_installed()
        before = len(apps)
        apps = [a for a in apps if a.get("slug") != slug]
        if len(apps) == before:
            self._json({"error": "App not found in registry"}, 404)
            return
        _save_installed(apps)
        # Clear from state caches
        _app_state_cache.pop(slug, None)
        _app_session_starts.pop(slug, None)
        # Purge usage log entries for this slug
        if USAGE_FILE.exists():
            try:
                lines = USAGE_FILE.read_text().strip().split("\n")
                kept = [l for l in lines if l and json.loads(l).get("slug") != slug]
                USAGE_FILE.write_text("\n".join(kept) + "\n" if kept else "")
            except Exception as e:
                logging.warning("Failed to purge usage for %s: %s", slug, e)
        audit.info("UNINSTALL %s", slug)
        self._json({"success": True, "message": f"Removed {slug} from registry"})

    # ── /open-terminal ─────────────────────────────────────────

    def _handle_open_terminal(self, body):
        """Open Terminal.app with a command pre-filled and executed."""
        command = body.get("command", "")
        cwd = body.get("cwd", os.path.expanduser("~"))
        launch_claude = body.get("then_launch_claude", False)

        # If requested, append Claude launch command
        if launch_claude and _CLAUDE_AVAILABLE:
            command = f"{command} && {_CLAUDE_CMD}" if command else _CLAUDE_CMD

        if not command:
            self._json({"error": "command required"}, 400)
            return

        audit.info("OPEN_TERMINAL cmd=%s cwd=%s", command[:200], cwd)

        import platform
        if platform.system() != "Darwin":
            self._json({"error": "open-terminal only supported on macOS"}, 400)
            return

        try:
            # Use Terminal.app — works on every Mac, no dependencies
            # Block dangerous shell patterns (allow && for chained commands)
            BLOCKED_PATTERNS = ['`', '$(', '${', '>>', '>', '<', 'rm -rf', 'curl|', 'wget|']
            for pat in BLOCKED_PATTERNS:
                if pat in command:
                    self._json({"error": f"Command contains blocked pattern: {pat}"}, 400)
                    return
            # Length limit
            if len(command) > 500:
                self._json({"error": "Command too long (max 500 chars)"}, 400)
                return
            # Detect best terminal: Ghostty (great TUI) > iTerm2 > Terminal.app
            ghostty = os.path.exists("/Applications/Ghostty.app")
            iterm = os.path.exists("/Applications/iTerm.app")

            if ghostty:
                # Ghostty: -e flag runs command directly, no permissions needed
                full_cmd = f"cd {cwd} && {command}"
                subprocess.Popen(["ghostty", "-e", "/bin/zsh", "-c", full_cmd])
                self._json({"success": True, "terminal": "Ghostty", "command": command})
            elif iterm:
                safe_cmd = command.replace('\\', '\\\\').replace('"', '\\"')
                safe_cwd = cwd.replace('\\', '\\\\').replace('"', '\\"')
                script = (
                    f'tell application "iTerm2"\n'
                    f'  create window with default profile command "cd \\"{safe_cwd}\\" && {safe_cmd}"\n'
                    f'end tell'
                )
                subprocess.Popen(["osascript", "-e", script])
                self._json({"success": True, "terminal": "iTerm2", "command": command})
            else:
                # Terminal.app fallback
                safe_cmd = command.replace('\\', '\\\\').replace('"', '\\"')
                safe_cwd = cwd.replace('\\', '\\\\').replace('"', '\\"')
                script = (
                    f'tell application "Terminal"\n'
                    f'  activate\n'
                    f'  do script "cd \\"{safe_cwd}\\" && {safe_cmd}"\n'
                    f'end tell'
                )
                subprocess.Popen(["osascript", "-e", script])
                self._json({"success": True, "terminal": "Terminal.app", "command": command,
                            "note": "For best Claude Code experience, install Ghostty: https://ghostty.org"})
        except Exception as exc:
            self._json({"error": f"Failed to open terminal: {exc}"}, 500)

    # ── /claude-exec ────────────────────────────────────────────

    def _handle_claude_exec(self, body):
        """Run a Claude Code prompt headlessly in a project directory."""
        if not _CLAUDE_AVAILABLE:
            self._json({"error": "claude CLI not found in PATH"}, 503)
            return
        if not _check_rate("claude-exec"):
            self._json({"error": "Rate limit: max 20 claude-exec/hour"}, 429)
            return

        prompt = body.get("prompt", "")
        project_dir = body.get("project_dir", "~/projects/forge")

        # Validate prompt
        if not isinstance(prompt, str) or not prompt.strip():
            self._json({"error": "prompt required"}, 400)
            return
        if len(prompt) > 50000:
            self._json({"error": "prompt too long (max 50000 chars)"}, 400)
            return

        # Scan for red flags
        flags = _scan_prompt(prompt)
        if flags:
            audit.warning("CLAUDE_EXEC_BLOCKED flags=%s prompt=%s", flags, prompt[:200])
            self._json({"error": "prompt_blocked", "flags": flags,
                         "message": f"Prompt blocked by security scan: {', '.join(flags)}"}, 403)
            return

        # Validate project dir
        try:
            resolved_dir = _validate_project_dir(project_dir)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
            return

        # Generate run ID + log file
        run_id = secrets.token_hex(8)
        log_path = CLAUDE_RUNS_DIR / f"{run_id}.log"

        audit.info("CLAUDE_EXEC run_id=%s dir=%s prompt=%s", run_id, resolved_dir, prompt[:200])

        # Write prompt to log
        with open(log_path, "w") as f:
            f.write(f"PROMPT: {prompt}\n")
            f.write(f"DIR: {resolved_dir}\n")
            f.write(f"STARTED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("---\n")

        # Spawn claude subprocess
        try:
            proc = subprocess.Popen(
                ["claude", "-p", prompt, "--allowedTools", "Read,Grep,Glob,WebSearch"],
                cwd=resolved_dir,
                stdout=open(log_path, "a"),
                stderr=subprocess.STDOUT,
                text=True,
            )
            _running_runs[run_id] = proc
            logging.info("claude-exec started: run_id=%s pid=%s", run_id, proc.pid)
        except Exception as exc:
            with open(log_path, "a") as f:
                f.write(f"\nERROR: {exc}\n")
            self._json({"error": f"Failed to start claude: {exc}"}, 500)
            return

        self._json({
            "run_id": run_id,
            "log_url": f"/claude-exec/log/{run_id}",
            "pid": proc.pid,
            "status": "running",
        })

    def _handle_claude_log(self, run_id):
        """Return the log file for a claude-exec run."""
        if not re.match(r"^[a-f0-9]{16}$", run_id):
            self._json({"error": "invalid run_id"}, 400)
            return
        log_path = CLAUDE_RUNS_DIR / f"{run_id}.log"
        if not log_path.exists():
            self._json({"error": "run not found"}, 404)
            return

        # Determine status
        status = "complete"
        exit_code = None
        if run_id in _running_runs:
            proc = _running_runs[run_id]
            poll = proc.poll()
            if poll is None:
                status = "running"
            else:
                exit_code = poll
                status = "complete" if poll == 0 else "error"
                del _running_runs[run_id]

        content = log_path.read_text()
        body = json.dumps({
            "run_id": run_id,
            "status": status,
            "exit_code": exit_code,
            "log": content,
        }).encode()

        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Run-Status", status)
        if exit_code is not None:
            self.send_header("X-Exit-Code", str(exit_code))
        self.end_headers()
        self.wfile.write(body)

    def _handle_claude_list(self):
        """List recent claude-exec runs."""
        runs = []
        for f in sorted(CLAUDE_RUNS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            run_id = f.stem
            try:
                first_lines = f.read_text()[:300]
                prompt_line = ""
                for line in first_lines.split("\n"):
                    if line.startswith("PROMPT: "):
                        prompt_line = line[8:][:100]
                        break
            except Exception:
                prompt_line = ""

            status = "complete"
            if run_id in _running_runs:
                poll = _running_runs[run_id].poll()
                status = "running" if poll is None else ("complete" if poll == 0 else "error")

            runs.append({
                "run_id": run_id,
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime)),
                "status": status,
                "prompt_preview": prompt_line,
            })
        self._json({"runs": runs, "count": len(runs)})

    # ── /stop ─────────────────────────────────────────────────

    def _handle_stop(self, body):
        name = re.sub(r"[^a-z0-9\-]", "", str(body.get("name", ""))[:50])
        cname = f"forge-{name}"
        if cname not in MANAGED_CONTAINERS:
            self._json({"error": "Not managed by forge-agent"}, 403)
            return
        r = _safe_docker(["stop", cname])
        MANAGED_CONTAINERS.discard(cname)
        self._json({"success": r.returncode == 0})

    # ── auth + CORS ───────────────────────────────────────────

    def _check_token(self):
        token = self.headers.get("X-Forge-Token", "")
        if not secrets.compare_digest(token, TOKEN):
            audit.warning("BAD_TOKEN from %s", self.client_address)
            self._json({"error": "Unauthorized"}, 401)
            return False
        return True

    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        allowed = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGIN
        self.send_header("Access-Control-Allow-Origin", allowed)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Forge-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    # ── response helpers ──────────────────────────────────────

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse_start(self):
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

    def _sse_event(self, event_type, data):
        payload = json.dumps({"type": event_type, **data})
        try:
            self.wfile.write(f"event: {event_type}\ndata: {payload}\n\n".encode())
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def _sse_end(self):
        try:
            self.wfile.write(b"event: done\ndata: {}\n\n")
            self.wfile.flush()
        except BrokenPipeError:
            pass

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Forge Agent v{VERSION}")
    print(f"Port: {PORT}")
    print(f"Token: {TOKEN[:8]}…")
    print(f"Audit: {AUDIT_LOG}")
    print(f"CORS: {ALLOWED_ORIGIN}")
    try:
        from socketserver import ThreadingMixIn
        class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        ThreadedHTTPServer(("localhost", PORT), AgentHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
