"""
Tier 2 sandbox lifecycle manager.

Responsibilities:
  - ensure_running(tool_id): idempotent start; builds the image on first run,
    boots an nginx:alpine container with resource caps, polls until healthy.
  - hibernate(tool_id): stop + mark stopped. Silent on error.
  - hibernate_idle_containers(): crontab target for idle-sweep.
  - pre_warm(tool_id): start a container for a stopped hot tool.
  - get_status(): admin status blob (running, stopped, memory use).
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from api import db
from forge_sandbox import builder as _builder


_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _REPO_ROOT / "logs"
_LOG_PATH = _LOG_DIR / "sandbox.log"

_READY_TIMEOUT_SEC = 10.0
_READY_POLL_INTERVAL = 0.2
_MEMORY_LIMIT = "256m"
_CPU_LIMIT = "0.5"
_IDLE_AFTER_SECONDS = 10 * 60


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("forge.sandbox.manager")
    if not logger.handlers:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_PATH)
        fmt = logging.Formatter("%(asctime)sZ %(levelname)s [%(name)s] %(message)s")
        fmt.converter = lambda *a: datetime.utcnow().timetuple()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class SandboxError(Exception):
    pass


class SandboxManager:
    """Thin wrapper around the docker CLI. Subprocess-only — avoids docker-py."""

    def __init__(self) -> None:
        self.log = _get_logger()

    # -------------------- Public API --------------------

    def ensure_running(self, tool_id: int) -> int:
        tool = db.get_tool(tool_id)
        if not tool:
            raise SandboxError(f"tool {tool_id} not found")
        slug = tool.get("slug") or f"tool-{tool_id}"
        container_name = f"forge-{slug}"

        if tool.get("container_status") == "running" and tool.get("container_id"):
            if self._container_is_running(container_name):
                port = tool.get("container_port")
                if port:
                    db.update_tool(tool_id, last_request_at=datetime.utcnow())
                    self.log.info("ensure_running reuse tool_id=%s port=%s", tool_id, port)
                    return int(port)

        image_tag = tool.get("image_tag")
        if not image_tag:
            self.log.info("ensure_running building image tool_id=%s slug=%s", tool_id, slug)
            result = _builder.build_image(tool_id, tool.get("app_html") or "", slug)
            if not result.get("success"):
                raise SandboxError(f"image build failed: {result.get('build_output', '')[-400:]}")
            image_tag = result["image_tag"]

        self._remove_container_if_exists(container_name)
        container_id, port = self._run_container(container_name, image_tag)
        self._wait_healthy(port)

        db.update_tool(
            tool_id,
            container_id=container_id,
            container_status="running",
            container_port=port,
            last_request_at=datetime.utcnow(),
        )
        self.log.info(
            "ensure_running started tool_id=%s slug=%s port=%s container=%s",
            tool_id, slug, port, container_id[:12],
        )
        return port

    def hibernate(self, tool_id: int) -> None:
        tool = db.get_tool(tool_id)
        if not tool:
            return
        slug = tool.get("slug") or f"tool-{tool_id}"
        container_name = f"forge-{slug}"
        if tool.get("container_id"):
            try:
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except Exception:
                pass
        db.update_tool(
            tool_id,
            container_status="stopped",
            container_port=None,
        )
        self.log.info("hibernate tool_id=%s slug=%s", tool_id, slug)

    def hibernate_idle_containers(self) -> int:
        with db.get_db() as cur:
            cur.execute(
                """
                SELECT id FROM tools
                WHERE container_status = 'running'
                  AND last_request_at < NOW() - (INTERVAL '1 second' * %s)
                """,
                (_IDLE_AFTER_SECONDS,),
            )
            rows = cur.fetchall()
        count = 0
        for row in rows:
            try:
                self.hibernate(row["id"])
                count += 1
            except Exception:
                self.log.exception("hibernate_idle failed tool_id=%s", row.get("id"))
        self.log.info("hibernate_idle count=%d", count)
        return count

    def pre_warm(self, tool_id: int) -> Optional[int]:
        tool = db.get_tool(tool_id)
        if not tool:
            return None
        if not tool.get("image_tag"):
            return None
        if tool.get("container_status") != "stopped":
            return None
        port = self.ensure_running(tool_id)
        slug = tool.get("slug") or f"tool-{tool_id}"
        self.log.info("pre-warmed %s port=%s", slug, port)
        return port

    def get_status(self) -> dict:
        with db.get_db() as cur:
            cur.execute(
                """
                SELECT id, slug, container_status, container_port, last_request_at
                FROM tools
                WHERE container_mode = TRUE
                """
            )
            rows = cur.fetchall()

        running = []
        stopped = []
        for r in rows:
            status = r.get("container_status")
            slug = r.get("slug")
            if status == "running":
                lr = r.get("last_request_at")
                running.append({
                    "slug": slug,
                    "port": r.get("container_port"),
                    "last_request_at": lr.isoformat() if hasattr(lr, "isoformat") else lr,
                })
            else:
                stopped.append({"slug": slug})

        memory_used = self._aggregate_memory_usage()
        return {
            "running": running,
            "stopped": stopped,
            "total_containers": len(running),
            "memory_used": memory_used,
        }

    # -------------------- Internals --------------------

    def _container_is_running(self, name: str) -> bool:
        try:
            proc = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return False
        if proc.returncode != 0:
            return False
        return (proc.stdout or "").strip().lower() == "true"

    def _remove_container_if_exists(self, name: str) -> None:
        try:
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            pass

    def _run_container(self, name: str, image_tag: str) -> tuple[str, int]:
        """Start a container with a Docker-assigned host port, then read it back.

        Using `-p 127.0.0.1::80` (empty host port) lets the kernel pick a free
        port atomically. We then query `docker port` to learn which one. This
        eliminates the TOCTOU race that an in-Python port scan had.
        """
        proc = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", name,
                "-p", "127.0.0.1::80",
                "--memory", _MEMORY_LIMIT,
                "--cpus", _CPU_LIMIT,
                "--network", "bridge",
                image_tag,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise SandboxError(
                f"docker run failed rc={proc.returncode}: {(proc.stderr or proc.stdout or '').strip()[-400:]}"
            )
        container_id = (proc.stdout or "").strip()

        port_proc = subprocess.run(
            ["docker", "port", name, "80/tcp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if port_proc.returncode != 0 or not port_proc.stdout.strip():
            # Tear the container down so we don't leak it.
            self._remove_container_if_exists(name)
            raise SandboxError(
                f"could not read assigned port for {name}: {port_proc.stderr.strip()[:200]}"
            )
        # Output looks like "127.0.0.1:32768\n" (possibly multiple lines).
        first_line = port_proc.stdout.strip().splitlines()[0]
        try:
            port = int(first_line.rsplit(":", 1)[-1])
        except ValueError:
            self._remove_container_if_exists(name)
            raise SandboxError(f"could not parse docker port output: {first_line!r}")

        return container_id, port

    def _wait_healthy(self, port: int) -> None:
        import requests  # local import keeps module import cheap
        deadline = time.monotonic() + _READY_TIMEOUT_SEC
        url = f"http://127.0.0.1:{port}/"
        last_err: Optional[str] = None
        while time.monotonic() < deadline:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    return
                last_err = f"status {resp.status_code}"
            except Exception as exc:
                last_err = str(exc)
            time.sleep(_READY_POLL_INTERVAL)
        raise SandboxError(f"container never became healthy on port {port}: {last_err}")

    def _aggregate_memory_usage(self) -> str:
        try:
            proc = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return "unknown"
        if proc.returncode != 0:
            return "unknown"
        total_mb = 0.0
        matched = 0
        for line in (proc.stdout or "").splitlines():
            if not line.startswith("forge-"):
                continue
            matched += 1
            try:
                _, usage = line.split("|", 1)
                used = usage.split("/")[0].strip()
                total_mb += _parse_mem(used)
            except Exception:
                continue
        if matched == 0:
            return "0MiB"
        return f"{total_mb:.1f}MiB"


def _parse_mem(value: str) -> float:
    value = value.strip()
    try:
        if value.endswith("GiB") or value.endswith("GB"):
            return float(value.rstrip("GiBB").strip()) * 1024.0
        if value.endswith("MiB") or value.endswith("MB"):
            return float(value.rstrip("MiBB").strip())
        if value.endswith("KiB") or value.endswith("KB"):
            return float(value.rstrip("KiBB").strip()) / 1024.0
        if value.endswith("B"):
            return float(value.rstrip("B").strip()) / (1024.0 * 1024.0)
    except ValueError:
        return 0.0
    return 0.0
