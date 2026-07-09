from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .kb_links import resolve_kb_articles_by_titles
from .models import WorkflowTemplate
from .playbook_metrics import compute_onboarding_playbook_metrics
from .playbooks.employee_onboarding import (
    ONBOARDING_AUTOMATION_RULE,
    ONBOARDING_KB_ARTICLE_TITLES,
    ONBOARDING_TEMPLATE_NAME,
    ONBOARDING_TEMPLATE_STEPS,
    SKU_ID,
    SKU_NAME,
    SKU_TAGLINE,
)
from .scoping import workflows_queryset_for_user


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_onboarding_playbook(request):
    """
    Sellable onboarding SKU bundle: global template, linked KB articles, auto-start rule, metrics.
    """
    template = WorkflowTemplate.objects.filter(
        name=ONBOARDING_TEMPLATE_NAME,
        team__isnull=True,
        trigger_category="onboarding",
    ).first()

    wf_qs = workflows_queryset_for_user(request.user)
    metrics = compute_onboarding_playbook_metrics(wf_qs)

    kb_articles = resolve_kb_articles_by_titles(ONBOARDING_KB_ARTICLE_TITLES)

    steps = template.steps if template else ONBOARDING_TEMPLATE_STEPS
    step_previews = []
    for idx, step in enumerate(steps):
        titles = step.get("kb_links") or []
        step_previews.append({
            "order": idx + 1,
            "title": step.get("title", ""),
            "assignee_role": step.get("assignee_role", ""),
            "step_type": step.get("step_type", "manual"),
            "due_days": step.get("due_days", 2),
            "kb_articles": resolve_kb_articles_by_titles(titles),
            "has_branching": bool(step.get("skip_when")),
        })

    sla_days = sum(int(s.get("due_days") or 2) for s in steps)

    return Response({
        "playbook": {
            "id": SKU_ID,
            "name": SKU_NAME,
            "tagline": SKU_TAGLINE,
            "trigger_category": "onboarding",
            "remote_trigger_category": "remote_onboarding",
            "template_id": template.id if template else None,
            "template_installed": template is not None,
            "step_count": len(steps),
            "workflow_sla_days": sla_days,
            "steps": step_previews,
            "kb_articles": kb_articles,
            "automation_rule": ONBOARDING_AUTOMATION_RULE,
            "metrics": metrics,
            "demo_minutes": 10,
        },
    })
