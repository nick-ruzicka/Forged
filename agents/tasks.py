"""
Celery task definitions for the agent pipeline.

- run_pipeline_task(tool_id): runs the 6-agent review pipeline for a tool.
- self_heal(): periodic task (every 6h via Beat) that improves underperforming tools.

Both tasks delegate to existing modules in the agents/ package so the Celery layer
stays thin; retries are handled at the task boundary.
"""
from celery_app import celery_app


@celery_app.task(
    bind=True,
    name="agents.tasks.run_pipeline_task",
    max_retries=3,
    default_retry_delay=30,
)
def run_pipeline_task(self, tool_id: int):
    """Execute the 6-agent review pipeline for a submitted tool."""
    from agents import pipeline

    try:
        return pipeline.run_pipeline(int(tool_id))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="agents.tasks.self_heal",
    max_retries=2,
    default_retry_delay=60,
)
def self_heal(self):
    """Scan for underperforming approved tools and propose improved versions."""
    from agents.self_healer import SelfHealerAgent

    try:
        return SelfHealerAgent().heal_underperforming_tools()
    except Exception as exc:
        raise self.retry(exc=exc)
