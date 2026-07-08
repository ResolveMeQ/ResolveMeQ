"""
Management command to seed global workflow templates.
Usage: python manage.py populate_workflow_templates
"""
from django.core.management.base import BaseCommand

from workflows.models import WorkflowTemplate


class Command(BaseCommand):
    help = "Seed the database with global (team=None) workflow templates"

    def handle(self, *args, **options):
        templates = [
            {
                "name": "Equipment & software provisioning",
                "trigger_category": "provisioning",
                "steps": [
                    {
                        "title": "Confirm request details",
                        "description": "Verify exactly what's needed (device/software, quantity, urgency) with the requester.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Provision account/license access",
                        "description": "Grant the software license or system access the request needs.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Order or assign hardware",
                        "description": "Assign from existing stock or place an order if nothing is available.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Ship or deliver to requester",
                        "description": "Hand off in person or ship, and share tracking/pickup details.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Confirm receipt & close out",
                        "description": "Requester confirms everything arrived and works before this is marked done.",
                        "assignee_team": "IT Support",
                    },
                ],
            },
        ]

        created_count = 0
        for data in templates:
            _, created = WorkflowTemplate.objects.get_or_create(
                name=data["name"],
                team=None,
                defaults={"trigger_category": data["trigger_category"], "steps": data["steps"]},
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} new workflow template(s)."))
