"""
Forge Celery application.

- Broker & result backend: REDIS_URL (defaults to redis://localhost:6379/0).
- Auto-discovers tasks from the `agents` package (agents/tasks.py).
- Beat schedule runs the self-healer every 6 hours.

Start workers via scripts/start_worker.sh.
Start Beat via scripts/start_beat.sh.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "forge",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=60 * 60 * 24,
    beat_schedule={
        "self-healer-every-6-hours": {
            "task": "agents.tasks.self_heal",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "hibernate-idle-containers": {
            "task": "forge_sandbox.tasks.hibernate_idle",
            "schedule": crontab(minute="*/5"),
        },
    },
)

celery_app.autodiscover_tasks(["agents", "forge_sandbox"])
