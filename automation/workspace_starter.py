"""Editable starter automation rules for new workspaces."""

from __future__ import annotations

from automation.models import Rule
from automation.validation import normalize_actions, normalize_conditions

WORKSPACE_STARTER_RULES = [
    {
        "name": "Onboarding tickets → Employee onboarding playbook",
        "description": (
            "Starts your onboarding workflow when a ticket is created with category "
            "'onboarding'. Edit this rule or pause it anytime."
        ),
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "onboarding"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "onboarding"}],
        "priority": 10,
    },
    {
        "name": "Provisioning tickets → Equipment provisioning playbook",
        "description": "Starts the equipment & software provisioning workflow for provisioning tickets.",
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "provisioning"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "provisioning"}],
        "priority": 20,
    },
    {
        "name": "Offboarding tickets → Employee offboarding playbook",
        "description": "Starts the offboarding workflow when HR opens a departure ticket.",
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "offboarding"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "offboarding"}],
        "priority": 30,
    },
]


def seed_starter_rules_for_team(team) -> int:
    """Create editable workspace rules if this team has none yet. Returns count created."""
    if not team or Rule.objects.filter(team=team).exists():
        return 0
    created = 0
    for data in WORKSPACE_STARTER_RULES:
        conditions = normalize_conditions(data["conditions"])
        actions = normalize_actions(data["actions"])
        Rule.objects.create(
            name=data["name"][:200],
            description=data.get("description", ""),
            team=team,
            trigger=data["trigger"],
            conditions=conditions,
            actions=actions,
            priority=data.get("priority", 100),
            is_active=True,
        )
        created += 1
    return created
