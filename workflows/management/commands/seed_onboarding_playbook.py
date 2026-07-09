"""
Upgrade the global Employee onboarding template to the P1-7 SKU (roles, SLA, branching, KB links).

Usage:
  python manage.py seed_onboarding_playbook
  python manage.py seed_onboarding_playbook --dry-run
"""
from django.core.management.base import BaseCommand

from workflows.models import WorkflowTemplate
from workflows.playbooks.employee_onboarding import (
    ONBOARDING_TEMPLATE_NAME,
    ONBOARDING_TEMPLATE_STEPS,
)
from workflows.template_validation import normalize_template_steps


class Command(BaseCommand):
    help = "Install or upgrade the global Employee onboarding playbook SKU template"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to the database",
        )

    def handle(self, *args, **options):
        steps = normalize_template_steps(ONBOARDING_TEMPLATE_STEPS)
        defaults = {
            "trigger_category": "onboarding",
            "steps": steps,
        }

        if options["dry_run"]:
            existing = WorkflowTemplate.objects.filter(
                name=ONBOARDING_TEMPLATE_NAME,
                team__isnull=True,
            ).first()
            action = "update" if existing else "create"
            self.stdout.write(f"Would {action} global template '{ONBOARDING_TEMPLATE_NAME}' ({len(steps)} steps)")
            return

        template, created = WorkflowTemplate.objects.update_or_create(
            name=ONBOARDING_TEMPLATE_NAME,
            team=None,
            defaults=defaults,
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} onboarding playbook template (id={template.id}, {len(steps)} steps, SLA {sum(s['due_days'] for s in steps)} days)"
            )
        )
