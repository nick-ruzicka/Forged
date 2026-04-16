"""
Tier 2 sandbox image builder.

`build_image(tool_id, app_html, slug)` writes a tiny nginx:alpine Dockerfile
alongside the app's `index.html`, runs `docker build`, records the resulting
image tag on the tool row, and cleans up the build context.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from api import db


_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _REPO_ROOT / "logs"
_LOG_PATH = _LOG_DIR / "sandbox.log"

_DOCKERFILE = """FROM nginx:alpine
COPY index.html /usr/share/nginx/html/
EXPOSE 80
"""


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("forge.sandbox")
    if not logger.handlers:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(_LOG_PATH)
        fmt = logging.Formatter("%(asctime)sZ %(levelname)s [%(name)s] %(message)s")
        fmt.converter = lambda *a: datetime.utcnow().timetuple()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def build_image(tool_id: int, app_html: str, slug: str) -> dict:
    """
    Build `forge-app-{slug}:latest` from the given HTML. Returns
    {success, image_tag, build_output}. Always cleans up the temp context.
    """
    log = _get_logger()
    image_tag = f"forge-app-{slug}:latest"
    build_dir = Path(f"/tmp/forge-build/{slug}")
    output_parts: list[str] = []

    log.info("build start tool_id=%s slug=%s image_tag=%s", tool_id, slug, image_tag)

    try:
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
        build_dir.mkdir(parents=True, exist_ok=True)

        (build_dir / "index.html").write_text(app_html or "", encoding="utf-8")
        (build_dir / "Dockerfile").write_text(_DOCKERFILE, encoding="utf-8")
        log.info("build context written path=%s bytes=%d", build_dir, len(app_html or ""))

        env = os.environ.copy()
        proc = subprocess.run(
            ["docker", "build", "-t", image_tag, str(build_dir)],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        output_parts.append(proc.stdout or "")
        output_parts.append(proc.stderr or "")
        build_output = "\n".join(p for p in output_parts if p).strip()

        if proc.returncode != 0:
            log.error("build failed tool_id=%s rc=%s output=%s", tool_id, proc.returncode, build_output[-500:])
            return {"success": False, "image_tag": None, "build_output": build_output}

        db.update_tool(tool_id, image_tag=image_tag)
        log.info("build ok tool_id=%s image_tag=%s", tool_id, image_tag)
        return {"success": True, "image_tag": image_tag, "build_output": build_output}

    except subprocess.TimeoutExpired as exc:
        log.error("build timeout tool_id=%s slug=%s", tool_id, slug)
        return {
            "success": False,
            "image_tag": None,
            "build_output": f"timeout after {exc.timeout}s",
        }
    except Exception as exc:
        log.exception("build error tool_id=%s slug=%s", tool_id, slug)
        return {"success": False, "image_tag": None, "build_output": f"error: {exc}"}
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
