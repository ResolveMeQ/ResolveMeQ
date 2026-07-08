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
            {
                "name": "Employee onboarding",
                "trigger_category": "onboarding",
                "steps": [
                    {
                        "title": "Provision accounts",
                        "description": "Create email, SSO, and core system accounts for the new hire.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Assign hardware",
                        "description": "Prepare and assign a laptop and any other required equipment.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Coordinate facilities & desk setup",
                        "description": "Confirm desk/workspace and building access are ready for day one.",
                        "assignee_team": "Facilities",
                    },
                    {
                        "title": "Schedule orientation & training",
                        "description": "Book onboarding sessions and share the first-week schedule.",
                        "assignee_team": "HR",
                    },
                    {
                        "title": "Confirm new hire is set up",
                        "description": "Check in with the new hire that accounts, hardware, and access all work.",
                        "assignee_team": "IT Support",
                    },
                ],
            },
            {
                "name": "Employee offboarding",
                "trigger_category": "offboarding",
                "steps": [
                    {
                        "title": "Revoke system access",
                        "description": "Disable SSO, email, and any other system access for the departing employee.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Collect company equipment",
                        "description": "Arrange return/collection of laptop and any other company property.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Disable accounts",
                        "description": "Deactivate remaining accounts and transfer or archive their data as needed.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Confirm exit checklist complete",
                        "description": "Verify access is fully revoked and equipment is accounted for before closing out.",
                        "assignee_team": "HR",
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
