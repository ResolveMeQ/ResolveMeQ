"""
Seed default global automation rules (replaces hardcoded category→workflow triggers).

Usage: python manage.py seed_automation_rules
"""
from django.core.management.base import BaseCommand

from automation.models import Rule
from automation.validation import normalize_actions, normalize_conditions


DEFAULT_RULES = [
    {
        "name": "Auto-start onboarding workflow",
        "description": (
            "Platform starter (read-only). When a ticket category is onboarding, starts the "
            "Employee onboarding playbook. Copy to your workspace to customize."
        ),
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "onboarding"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "onboarding"}],
        "priority": 10,
    },
    {
        "name": "Auto-start provisioning workflow",
        "description": (
            "Platform starter (read-only). Starts equipment & software provisioning for "
            "provisioning tickets. Copy to your workspace to customize."
        ),
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "provisioning"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "provisioning"}],
        "priority": 20,
    },
    {
        "name": "Auto-start offboarding workflow",
        "description": (
            "Platform starter (read-only). Starts employee offboarding for offboarding tickets. "
            "Copy to your workspace to customize."
        ),
        "trigger": "ticket.created",
        "conditions": [{"field": "category", "op": "equals", "value": "offboarding"}],
        "actions": [{"type": "start_workflow", "template_trigger_category": "offboarding"}],
        "priority": 30,
    },
]


class Command(BaseCommand):
    help = "Install or upgrade global automation rules (category→workflow via rules engine)"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for data in DEFAULT_RULES:
            conditions = normalize_conditions(data["conditions"])
            actions = normalize_actions(data["actions"])
            rule, was_created = Rule.objects.update_or_create(
                name=data["name"],
                team=None,
                defaults={
                    "description": data.get("description", ""),
                    "trigger": data["trigger"],
                    "conditions": conditions,
                    "actions": actions,
                    "priority": data.get("priority", 100),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Automation rules: {created} created, {updated} updated."))
