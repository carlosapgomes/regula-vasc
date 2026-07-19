"""django-q2 task entry points for pipeline execution."""

from __future__ import annotations

import uuid

from django_q.tasks import async_task


def enqueue_pipeline(case_id: uuid.UUID) -> None:
    """Enqueue the pipeline task via django-q2.

    Routes to cluster "llm" so pipeline processing is isolated.
    Called synchronously from views; the actual work runs in a worker.
    """
    async_task(
        "apps.pipeline.tasks.execute_pipeline",
        str(case_id),
        q_options={"cluster": "llm", "task_name": f"llm:{case_id}"},
    )


def execute_pipeline(case_id_str: str) -> None:
    """Entry point for django-q2 worker.

    Loads the case and runs the full pipeline orchestrator.
    """
    from apps.pipeline.orchestrator import run_pipeline

    run_pipeline(uuid.UUID(case_id_str))
