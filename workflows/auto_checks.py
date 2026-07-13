"""Run workflow template auto_check steps against external connectors."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_EMAIL_SOURCES = frozenset({"ticket_reporter"})


def get_auto_check_config(workflow, step) -> Optional[dict]:
    template = workflow.template
    if not template:
        return None
    steps = template.steps or []
    idx = step.order_index
    if idx < 0 or idx >= len(steps):
        return None
    cfg = steps[idx].get("auto_check")
    return cfg if isinstance(cfg, dict) else None


def resolve_check_email(workflow, email_from: str) -> Optional[str]:
    source = (email_from or "ticket_reporter").strip()
    if source != "ticket_reporter":
        return None
    if not workflow.ticket_id:
        return None
    user = workflow.ticket.user
    return (user.email or "").strip() or None


def _log_check(
    *,
    team_id,
    workflow,
    step,
    connector: str,
    check_type: str,
    status: str,
    message: str,
    detail: Optional[dict] = None,
):
    from integrations.models import ConnectorCheckLog

    return ConnectorCheckLog.objects.create(
        team_id=team_id,
        workflow=workflow,
        workflow_step=step,
        connector=connector,
        check_type=check_type,
        status=status,
        message=message[:2000],
        detail=detail or {},
    )


def latest_check_result(step) -> Optional[dict]:
    from integrations.models import ConnectorCheckLog

    log = (
        ConnectorCheckLog.objects.filter(workflow_step=step)
        .order_by("-ran_at")
        .first()
    )
    if not log:
        return None
    return {
        "status": log.status,
        "message": log.message,
        "connector": log.connector,
        "check_type": log.check_type,
        "ran_at": log.ran_at,
    }


def run_auto_check(step, workflow) -> Tuple[bool, str]:
    """
    Execute connector check for an active auto_check step.
    Returns (passed, message).
    """
    if step.step_type != "auto_check":
        return False, "Step is not an auto_check step."

    cfg = get_auto_check_config(workflow, step)
    if not cfg:
        _log_check(
            team_id=workflow.team_id,
            workflow=workflow,
            step=step,
            connector="unknown",
            check_type="unknown",
            status="error",
            message="Missing auto_check config on template step.",
        )
        return False, "Missing auto_check configuration."

    connector = (cfg.get("connector") or "").strip().lower()
    check_type = (cfg.get("check") or "").strip()
    email_from = (cfg.get("email_from") or "ticket_reporter").strip()
    team_id = workflow.team_id

    email = resolve_check_email(workflow, email_from)
    if not email:
        _log_check(
            team_id=team_id,
            workflow=workflow,
            step=step,
            connector=connector,
            check_type=check_type,
            status="error",
            message="Could not resolve email for auto_check.",
            detail={"email_from": email_from},
        )
        return False, "Could not resolve user email for check."

    if connector == "okta":
        from integrations.connectors.okta import get_active_installation, run_okta_check

        installation = get_active_installation(team_id)
        if not installation:
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="okta",
                check_type=check_type,
                status="skipped",
                message="Connect Okta in Settings → Integrations to run this check.",
            )
            return False, "Connect Okta in Settings → Integrations to run this check."

        try:
            passed, msg, detail = run_okta_check(
                installation,
                check_type,
                email=email,
                group_id=(cfg.get("group_id") or ""),
            )
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="okta",
                check_type=check_type,
                status="success" if passed else "failed",
                message=msg,
                detail=detail,
            )
            return passed, msg
        except Exception as exc:
            logger.warning("Okta auto_check failed: %s", exc)
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="okta",
                check_type=check_type,
                status="error",
                message=str(exc),
                detail={"email": email},
            )
            return False, str(exc)

    if connector == "google_workspace":
        from integrations.connectors.google_workspace import get_active_installation, run_google_check

        installation = get_active_installation(team_id)
        if not installation:
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="google_workspace",
                check_type=check_type,
                status="skipped",
                message="Connect Google Workspace in Settings → Integrations to run this check.",
            )
            return False, "Connect Google Workspace in Settings → Integrations to run this check."
        try:
            passed, msg, detail = run_google_check(
                installation,
                check_type,
                email=email,
                sku_id=(cfg.get("sku_id") or ""),
            )
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="google_workspace",
                check_type=check_type,
                status="success" if passed else "failed",
                message=msg,
                detail=detail,
            )
            return passed, msg
        except Exception as exc:
            logger.warning("Google auto_check failed: %s", exc)
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="google_workspace",
                check_type=check_type,
                status="error",
                message=str(exc),
                detail={"email": email},
            )
            return False, str(exc)

    if connector == "microsoft365":
        from integrations.connectors.microsoft365 import get_active_installation, run_microsoft_check

        installation = get_active_installation(team_id)
        if not installation:
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="microsoft365",
                check_type=check_type,
                status="skipped",
                message="Connect Microsoft 365 in Settings → Integrations to run this check.",
            )
            return False, "Connect Microsoft 365 in Settings → Integrations to run this check."
        try:
            passed, msg, detail = run_microsoft_check(
                installation,
                check_type,
                email=email,
                sku_id=(cfg.get("sku_id") or ""),
            )
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="microsoft365",
                check_type=check_type,
                status="success" if passed else "failed",
                message=msg,
                detail=detail,
            )
            return passed, msg
        except Exception as exc:
            logger.warning("Microsoft auto_check failed: %s", exc)
            _log_check(
                team_id=team_id,
                workflow=workflow,
                step=step,
                connector="microsoft365",
                check_type=check_type,
                status="error",
                message=str(exc),
                detail={"email": email},
            )
            return False, str(exc)

    _log_check(
        team_id=team_id,
        workflow=workflow,
        step=step,
        connector=connector or "unknown",
        check_type=check_type,
        status="error",
        message=f"Unsupported connector: {connector}",
    )
    return False, f"Unsupported connector: {connector}"
