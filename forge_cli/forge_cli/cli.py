"""
Forge CLI — deploy any HTML app to Forge in one command.
Stdlib only: argparse + urllib + webbrowser + zipfile + json + mimetypes.
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import sys
import uuid
import webbrowser
import zipfile
from urllib import error as urlerror
from urllib import request as urlrequest

from forge_cli import __version__

DEFAULT_HOST = "http://localhost:8090"
CONFIG_DIR = os.path.expanduser("~/.forge")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
EXCLUDE_FILES = {".DS_Store"}


# -------------------- Config --------------------

def _load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _resolve_host(arg_host: str | None) -> str:
    if arg_host:
        return arg_host.rstrip("/")
    cfg = _load_config()
    host = cfg.get("host") or os.environ.get("FORGE_HOST") or DEFAULT_HOST
    return host.rstrip("/")


# -------------------- Multipart encoder (stdlib) --------------------

def _encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """fields: {name: str_value}; files: {name: (filename, bytes, content_type)}.
    Returns (body, content_type_header)."""
    boundary = "----ForgeBoundary" + uuid.uuid4().hex
    buf = io.BytesIO()
    crlf = b"\r\n"

    for name, value in fields.items():
        if value is None:
            continue
        buf.write(b"--" + boundary.encode() + crlf)
        buf.write(f'Content-Disposition: form-data; name="{name}"'.encode() + crlf + crlf)
        buf.write(str(value).encode("utf-8") + crlf)

    for name, (filename, data, ctype) in files.items():
        ctype = ctype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        buf.write(b"--" + boundary.encode() + crlf)
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode()
            + crlf
        )
        buf.write(f"Content-Type: {ctype}".encode() + crlf + crlf)
        buf.write(data + crlf)

    buf.write(b"--" + boundary.encode() + b"--" + crlf)
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


# -------------------- HTTP helpers --------------------

def _http_get(url: str, timeout: int = 30) -> tuple[int, dict]:
    req = urlrequest.Request(url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return resp.status, {"_raw": body[:500].decode("utf-8", errors="replace")}
    except urlerror.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"error": str(e)}
        return e.code, payload
    except urlerror.URLError as e:
        return 0, {"error": "connection_failed", "detail": str(e)}


def _http_post_multipart(url: str, fields: dict, files: dict, timeout: int = 60) -> tuple[int, dict]:
    body, ctype = _encode_multipart(fields, files)
    req = urlrequest.Request(url, data=body, method="POST")
    req.add_header("Content-Type", ctype)
    req.add_header("Content-Length", str(len(body)))
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return resp.status, {"_raw": raw[:500].decode("utf-8", errors="replace")}
    except urlerror.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = {"error": str(e)}
        return e.code, payload
    except urlerror.URLError as e:
        return 0, {"error": "connection_failed", "detail": str(e)}


# -------------------- Path helpers --------------------

def _title_case_from_dirname(path: str) -> str:
    base = os.path.basename(os.path.abspath(path))
    cleaned = base.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return "Forge App"
    return " ".join(w.capitalize() for w in cleaned.split())


def _find_index_html(path: str) -> str | None:
    direct = os.path.join(path, "index.html")
    if os.path.isfile(direct):
        return direct
    return None


def _zip_directory(path: str) -> bytes:
    buf = io.BytesIO()
    abs_root = os.path.abspath(path)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(abs_root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fname in filenames:
                if fname in EXCLUDE_FILES:
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, abs_root)
                try:
                    zf.write(full, rel)
                except OSError:
                    continue
    return buf.getvalue()


# -------------------- Commands --------------------

def cmd_deploy(args) -> int:
    path = os.path.abspath(args.path or ".")
    if not os.path.exists(path):
        print(f"error: path not found: {path}", file=sys.stderr)
        return 2

    name = args.name or _title_case_from_dirname(path)
    description = args.description or f"App deployed via forge CLI from {os.path.basename(path)}"
    category = args.category or "Other"
    host = _resolve_host(args.host)

    fields = {
        "name": name,
        "description": description,
        "category": category,
        "author_name": args.author_name or os.environ.get("USER", "cli"),
        "author_email": args.author_email or f"{os.environ.get('USER', 'cli')}@forge.local",
    }
    files: dict = {}

    if os.path.isfile(path):
        if not path.endswith(".html"):
            print(f"error: file must be .html (got {path})", file=sys.stderr)
            return 2
        with open(path, "rb") as f:
            html = f.read()
        fields["html"] = html.decode("utf-8", errors="replace")
        target = "single index.html"
    else:
        index = _find_index_html(path)
        contents = os.listdir(path)
        only_index = (
            index is not None
            and len([c for c in contents if not c.startswith(".") and c not in EXCLUDE_DIRS]) == 1
        )
        if only_index:
            with open(index, "rb") as f:
                html = f.read()
            fields["html"] = html.decode("utf-8", errors="replace")
            target = "single index.html"
        else:
            zdata = _zip_directory(path)
            files["file"] = (f"{name}.zip", zdata, "application/zip")
            target = f"directory ({len(zdata)} bytes zipped)"

    print(f"Deploying {name} to Forge...")
    print(f"  source: {target}")
    print(f"  host:   {host}")

    url = f"{host}/api/submit/app"
    status, payload = _http_post_multipart(url, fields, files)
    if status not in (200, 201):
        print(f"error: deploy failed ({status}): {payload}", file=sys.stderr)
        return 1

    slug = payload.get("slug")
    app_url = payload.get("url") or (f"/apps/{slug}" if slug else "")
    full_url = f"{host}{app_url}" if app_url.startswith("/") else app_url
    print(f"Live at: {full_url}")
    if payload.get("status"):
        print(f"  status: {payload['status']}")
    if payload.get("id"):
        print(f"  tool_id: {payload['id']}")
    return 0


def cmd_status(args) -> int:
    host = _resolve_host(args.host)
    status, payload = _http_get(f"{host}/api/health")
    if status == 0:
        print(f"forge: unreachable at {host} ({payload.get('detail')})", file=sys.stderr)
        return 1
    if status != 200:
        print(f"forge: {host} returned {status}: {payload}", file=sys.stderr)
        return 1
    print(f"forge: {host}")
    for k, v in payload.items():
        print(f"  {k}: {v}")
    return 0


def cmd_list(args) -> int:
    host = _resolve_host(args.host)
    status, payload = _http_get(f"{host}/api/tools?app_type=app&limit=100")
    if status != 200:
        print(f"error: list failed ({status}): {payload}", file=sys.stderr)
        return 1
    tools = payload.get("tools") or []
    apps = [t for t in tools if (t.get("app_type") or "prompt") == "app"]
    if not apps:
        print("No live apps yet. Try: forge deploy")
        return 0

    rows = [("SLUG", "NAME", "AUTHOR", "RUNS", "URL")]
    for t in apps:
        slug = t.get("slug") or ""
        rows.append((
            slug,
            (t.get("name") or "")[:32],
            (t.get("author_name") or "")[:20],
            str(t.get("run_count") or 0),
            f"{host}/apps/{slug}",
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for i, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row))
        print(line)
        if i == 0:
            print("  ".join("-" * w for w in widths))
    return 0


def cmd_open(args) -> int:
    host = _resolve_host(args.host)
    url = f"{host}/apps/{args.slug}"
    print(f"Opening {url}")
    webbrowser.open(url)
    return 0


def cmd_login(args) -> int:
    host = (args.host_arg or DEFAULT_HOST).rstrip("/")
    cfg = _load_config()
    cfg["host"] = host
    _save_config(cfg)
    print(f"Saved host: {host} → {CONFIG_PATH}")
    return 0


# -------------------- Parser --------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Deploy any HTML app to Forge in one command.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    p_deploy = sub.add_parser("deploy", help="Deploy an HTML app or directory to Forge")
    p_deploy.add_argument("path", nargs="?", default=".", help="Path to file or directory (default: .)")
    p_deploy.add_argument("--name", help="Tool name (default: derived from directory)")
    p_deploy.add_argument("--description", help="Tool description")
    p_deploy.add_argument("--category", help="Tool category (default: Other)")
    p_deploy.add_argument("--host", help="Forge host (default: from ~/.forge/config.json or http://localhost:8090)")
    p_deploy.add_argument("--author-name", dest="author_name", help="Author name")
    p_deploy.add_argument("--author-email", dest="author_email", help="Author email")
    p_deploy.set_defaults(func=cmd_deploy)

    p_status = sub.add_parser("status", help="Check Forge server health")
    p_status.add_argument("--host", help="Forge host")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List live apps on Forge")
    p_list.add_argument("--host", help="Forge host")
    p_list.set_defaults(func=cmd_list)

    p_open = sub.add_parser("open", help="Open a deployed app in your browser")
    p_open.add_argument("slug", help="App slug")
    p_open.add_argument("--host", help="Forge host")
    p_open.set_defaults(func=cmd_open)

    p_login = sub.add_parser("login", help="Save default Forge host to ~/.forge/config.json")
    p_login.add_argument("host_arg", nargs="?", default=DEFAULT_HOST, help="Host URL")
    p_login.set_defaults(func=cmd_login)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
