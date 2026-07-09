"""Connector-driven auto-complete for workflow auto_check steps (P3-3)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def try_auto_complete_connector_step(workflow, step) -> bool:
    """
    Run connector auto_check when a step becomes active.
    Returns True if the step was marked done automatically.
    """
    if step.step_type != "auto_check" or step.status != "active":
        return False

    from django.utils import timezone

    from .auto_checks import run_auto_check

    passed, message = run_auto_check(step, workflow)
    if not passed:
        logger.info(
            "Connector auto_check did not pass for workflow=%s step=%s: %s",
            workflow.id,
            step.id,
            message,
        )
        return False

    step.status = "done"
    step.completed_at = timezone.now()
    step.save(update_fields=["status", "completed_at"])
    try:
        from automation.hooks import on_workflow_step_completed

        on_workflow_step_completed(workflow, step)
    except Exception as exc:
        logger.warning("Workflow step completed hook failed: %s", exc)
    return True


def count_connector_auto_steps(steps: list) -> int:
    """Count template steps that auto-complete via connector checks."""
    count = 0
    for step in steps or []:
        if (step.get("step_type") or "manual") == "auto_check":
            count += 1
    return count
