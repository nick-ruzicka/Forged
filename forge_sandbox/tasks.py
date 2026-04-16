"""
Celery wrapper for sandbox lifecycle jobs.

Registered via autodiscovery (see celery_app.py). The beat schedule entry
"hibernate-idle-containers" calls this every 5 minutes.
"""
from __future__ import annotations

from celery_app import celery_app


@celery_app.task(name="forge_sandbox.tasks.hibernate_idle")
def hibernate_idle() -> dict:
    try:
        from forge_sandbox.manager import SandboxManager
        return {"hibernated": SandboxManager().hibernate_idle_containers()}
    except Exception as e:
        return {"error": str(e)}
