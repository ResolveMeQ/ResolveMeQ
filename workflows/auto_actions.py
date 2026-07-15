"""
Run workflow template auto_action steps against external connectors.

Unlike auto_checks.py (read-only, safe to run any time), these are WRITE actions
against Okta/Google Workspace/Microsoft 365 (deactivate user, reset password,
remove from group, revoke license) -- they must never fire automatically.
run_auto_action is only ever called from workflows.views.execute_auto_action,
which requires an explicit staff confirmation on each call (see that view).
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from .auto_checks import resolve_check_email

logger = logging.getLogger(__name__)


def get_auto_action_config(workflow, step) -> Optional[dict]:
    template = workflow.template
    if not template:
        return None
    steps = template.steps or []
    idx = step.order_index
    if idx < 0 or idx >= len(steps):
        return None
    cfg = steps[idx].get("auto_action")
    return cfg if isinstance(cfg, dict) else None


def _log_action(
    *,
    team_id,
    workflow,
    step,
    connector: str,
    action_type: str,
    status: str,
    message: str,
    detail: Optional[dict] = None,
    executed_by=None,
):
    from integrations.models import ConnectorActionLog

    return ConnectorActionLog.objects.create(
        team_id=team_id,
        workflow=workflow,
        workflow_step=step,
        connector=connector,
        action_type=action_type,
        status=status,
        message=message[:2000],
        detail=detail or {},
        executed_by=executed_by,
    )


def latest_action_result(step) -> Optional[dict]:
    from integrations.models import ConnectorActionLog

    log = (
        ConnectorActionLog.objects.filter(workflow_step=step)
        .order_by("-ran_at")
        .first()
    )
    if not log:
        return None
    return {
        "status": log.status,
        "message": log.message,
        "connector": log.connector,
        "action_type": log.action_type,
        "ran_at": log.ran_at,
        "executed_by": log.executed_by_id and (
            log.executed_by.get_full_name() or log.executed_by.email or log.executed_by.username
        ),
    }


def run_auto_action(step, workflow, *, user) -> Tuple[bool, str, Optional[str]]:
    """
    Execute the connector write action for an active auto_action step.
    Returns (passed, message, generated_secret). generated_secret (e.g. a one-time
    temp password for a reset_password action) is returned to the caller only --
    it is never written to ConnectorActionLog.detail or any other persisted record.
    """
    if step.step_type != "auto_action":
        return False, "Step is not an auto_action step.", None

    cfg = get_auto_action_config(workflow, step)
    if not cfg:
        _log_action(
            team_id=workflow.team_id,
            workflow=workflow,
            step=step,
            connector="unknown",
            action_type="unknown",
            status="error",
            message="Missing auto_action config on template step.",
            executed_by=user,
        )
        return False, "Missing auto_action configuration.", None

    connector = (cfg.get("connector") or "").strip().lower()
    action_type = (cfg.get("action") or "").strip()
    email_from = (cfg.get("email_from") or "ticket_reporter").strip()
    team_id = workflow.team_id

    email = resolve_check_email(workflow, email_from)
    if not email:
        _log_action(
            team_id=team_id,
            workflow=workflow,
            step=step,
            connector=connector,
            action_type=action_type,
            status="error",
            message="Could not resolve email for auto_action.",
            detail={"email_from": email_from},
            executed_by=user,
        )
        return False, "Could not resolve user email for action.", None

    if connector == "okta":
        from integrations.connectors.okta import get_active_installation, run_okta_action

        installation = get_active_installation(team_id)
        if not installation:
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="okta", action_type=action_type,
                status="skipped", message="Connect Okta in Settings → Integrations to run this action.",
                executed_by=user,
            )
            return False, "Connect Okta in Settings → Integrations to run this action.", None
        try:
            passed, msg, detail = run_okta_action(
                installation, action_type, email=email, group_id=(cfg.get("group_id") or ""),
            )
        except Exception as exc:
            logger.warning("Okta auto_action failed: %s", exc)
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="okta", action_type=action_type,
                status="error", message=str(exc), detail={"email": email}, executed_by=user,
            )
            return False, str(exc), None
        secret = (detail or {}).pop("temp_password", None)
        _log_action(
            team_id=team_id, workflow=workflow, step=step, connector="okta", action_type=action_type,
            status="success" if passed else "failed", message=msg, detail=detail, executed_by=user,
        )
        return passed, msg, secret

    if connector == "google_workspace":
        from integrations.connectors.google_workspace import get_active_installation, run_google_action

        installation = get_active_installation(team_id)
        if not installation:
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="google_workspace", action_type=action_type,
                status="skipped", message="Connect Google Workspace in Settings → Integrations to run this action.",
                executed_by=user,
            )
            return False, "Connect Google Workspace in Settings → Integrations to run this action.", None
        try:
            passed, msg, detail = run_google_action(
                installation, action_type, email=email,
                group_id=(cfg.get("group_id") or ""), sku_id=(cfg.get("sku_id") or ""),
            )
        except Exception as exc:
            logger.warning("Google auto_action failed: %s", exc)
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="google_workspace", action_type=action_type,
                status="error", message=str(exc), detail={"email": email}, executed_by=user,
            )
            return False, str(exc), None
        secret = (detail or {}).pop("temp_password", None)
        _log_action(
            team_id=team_id, workflow=workflow, step=step, connector="google_workspace", action_type=action_type,
            status="success" if passed else "failed", message=msg, detail=detail, executed_by=user,
        )
        return passed, msg, secret

    if connector == "microsoft365":
        from integrations.connectors.microsoft365 import get_active_installation, run_microsoft_action

        installation = get_active_installation(team_id)
        if not installation:
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="microsoft365", action_type=action_type,
                status="skipped", message="Connect Microsoft 365 in Settings → Integrations to run this action.",
                executed_by=user,
            )
            return False, "Connect Microsoft 365 in Settings → Integrations to run this action.", None
        try:
            passed, msg, detail = run_microsoft_action(
                installation, action_type, email=email,
                group_id=(cfg.get("group_id") or ""), sku_id=(cfg.get("sku_id") or ""),
            )
        except Exception as exc:
            logger.warning("Microsoft auto_action failed: %s", exc)
            _log_action(
                team_id=team_id, workflow=workflow, step=step, connector="microsoft365", action_type=action_type,
                status="error", message=str(exc), detail={"email": email}, executed_by=user,
            )
            return False, str(exc), None
        secret = (detail or {}).pop("temp_password", None)
        _log_action(
            team_id=team_id, workflow=workflow, step=step, connector="microsoft365", action_type=action_type,
            status="success" if passed else "failed", message=msg, detail=detail, executed_by=user,
        )
        return passed, msg, secret

    _log_action(
        team_id=team_id, workflow=workflow, step=step, connector=connector or "unknown", action_type=action_type,
        status="error", message=f"Unsupported connector: {connector}", executed_by=user,
    )
    return False, f"Unsupported connector: {connector}", None
