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
            {
                "name": "Software license renewal",
                "trigger_category": "license_renewal",
                "steps": [
                    {
                        "title": "Confirm renewal terms",
                        "description": "Verify seat count, term length, and pricing with the vendor.",
                        "assignee_team": "IT Support",
                        "auto_assign": "started_by",
                    },
                    {
                        "title": "Get budget approval",
                        "description": "Confirm the renewal cost is approved before purchasing.",
                        "assignee_team": "Finance",
                    },
                    {
                        "title": "Renew or purchase license",
                        "description": "Complete the renewal or purchase with the vendor.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Notify affected users",
                        "description": "Let current users know the renewal is complete and note any changes.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Confirm access still works",
                        "description": "Spot-check that existing users can still log in without interruption.",
                        "assignee_team": "IT Support",
                    },
                ],
            },
            {
                "name": "Office / desk move",
                "trigger_category": "office_move",
                "steps": [
                    {
                        "title": "Confirm new location/desk",
                        "description": "Verify the new desk, room, or building with facilities.",
                        "assignee_team": "Facilities",
                    },
                    {
                        "title": "Update network/phone port",
                        "description": "Ensure the new location has working network and phone connections.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Move equipment",
                        "description": "Relocate the desk, monitor, and any other hardware.",
                        "assignee_team": "Facilities",
                    },
                    {
                        "title": "Test connectivity",
                        "description": "Confirm network, phone, and any peripherals work at the new location.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Confirm employee is settled in",
                        "description": "Check in that everything works and nothing was left behind.",
                        "assignee_team": "IT Support",
                    },
                ],
            },
            {
                "name": "Contractor access setup",
                "trigger_category": "contractor_access",
                "steps": [
                    {
                        "title": "Verify signed contractor agreement on file",
                        "description": "Confirm the agreement/NDA is signed before granting any access.",
                        "assignee_team": "HR",
                    },
                    {
                        "title": "Provision limited-scope accounts",
                        "description": "Create accounts scoped to only what the contractor needs.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Assign temporary equipment",
                        "description": "Assign a loaner device if the contractor needs one.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Set access-expiration reminder",
                        "description": "Log the contract end date so access gets revoked on time.",
                        "assignee_team": "IT Support",
                        "auto_complete": True,
                    },
                    {
                        "title": "Confirm contractor can work",
                        "description": "Verify the contractor can log in and access what they need.",
                        "assignee_team": "IT Support",
                    },
                ],
            },
            {
                "name": "Hardware retirement & disposal",
                "trigger_category": "hardware_retirement",
                "steps": [
                    {
                        "title": "Confirm device data wiped",
                        "description": "Verify all data has been securely wiped before disposal.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Deregister from device management",
                        "description": "Remove the device from MDM/asset tracking.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Physically collect device",
                        "description": "Arrange pickup or drop-off of the retired device.",
                        "assignee_team": "IT Support",
                    },
                    {
                        "title": "Dispose or recycle per policy",
                        "description": "Follow the company's e-waste/recycling policy for disposal.",
                        "assignee_team": "Facilities",
                    },
                    {
                        "title": "Confirm retirement logged",
                        "description": "Record the device as retired in the asset register.",
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
