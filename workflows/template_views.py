from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import Team
from tickets.scoping import active_team_id_for_user

from .models import WorkflowTemplate
from .template_scoping import user_can_edit_template, user_can_manage_templates
from .template_validation import normalize_template_steps


def _template_to_dict(template, *, can_edit: bool) -> dict:
    steps = template.steps or []
    return {
        "id": template.id,
        "name": template.name,
        "trigger_category": template.trigger_category or "",
        "team_id": str(template.team_id) if template.team_id else None,
        "is_global": template.team_id is None,
        "steps": steps,
        "step_count": len(steps),
        "can_edit": can_edit,
        "created_at": template.created_at,
    }


def _templates_queryset_for_user(user):
    tid = active_team_id_for_user(user)
    if tid:
        return WorkflowTemplate.objects.filter(Q(team__isnull=True) | Q(team_id=tid))
    return WorkflowTemplate.objects.filter(team__isnull=True)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def template_manage_list_create(request):
    """
    GET: templates visible to the caller with can_edit flags.
    POST: create a team-scoped template (team owner) or global (staff only).
    """
    can_manage = user_can_manage_templates(request.user)
    tid = active_team_id_for_user(request.user)

    if request.method == "GET":
        qs = _templates_queryset_for_user(request.user).order_by("name")
        return Response({
            "can_manage": can_manage,
            "templates": [
                _template_to_dict(t, can_edit=user_can_edit_template(request.user, t))
                for t in qs
            ],
        })

    if not can_manage:
        return Response({"error": "Only the workspace owner can create workflow templates."}, status=403)

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required."}, status=400)

    try:
        steps = normalize_template_steps(request.data.get("steps"))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    trigger_category = (request.data.get("trigger_category") or "").strip()
    team = None
    if getattr(request.user, "is_staff", False) and request.data.get("is_global"):
        team = None
    else:
        team = Team.objects.filter(pk=tid).first() if tid else None
        if not team:
            return Response({"error": "Select an active workspace before creating a template."}, status=400)

    template = WorkflowTemplate.objects.create(
        name=name[:200],
        trigger_category=trigger_category[:30],
        team=team,
        steps=steps,
    )
    return Response(
        {"template": _template_to_dict(template, can_edit=user_can_edit_template(request.user, template))},
        status=201,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def template_detail(request, template_id):
    template = get_object_or_404(WorkflowTemplate, pk=template_id)
    visible = _templates_queryset_for_user(request.user).filter(pk=template.pk).exists()
    if not visible:
        return Response({"error": "Template not found."}, status=404)

    if request.method == "GET":
        return Response({
            "template": _template_to_dict(template, can_edit=user_can_edit_template(request.user, template)),
        })

    if not user_can_edit_template(request.user, template):
        return Response({"error": "You do not have permission to edit this template."}, status=403)

    if request.method == "DELETE":
        template.delete()
        return Response({"deleted": True})

    updates = {}
    if "name" in request.data:
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "name cannot be empty."}, status=400)
        updates["name"] = name[:200]
    if "trigger_category" in request.data:
        updates["trigger_category"] = (request.data.get("trigger_category") or "").strip()[:30]
    if "steps" in request.data:
        try:
            updates["steps"] = normalize_template_steps(request.data.get("steps"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

    if updates:
        for field, value in updates.items():
            setattr(template, field, value)
        template.save(update_fields=list(updates.keys()))

    return Response({
        "template": _template_to_dict(template, can_edit=True),
    })
