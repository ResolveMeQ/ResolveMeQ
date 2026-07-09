"""
Install a curated playbook SKU bundle (template + KB + resolution template + automation rule).

Usage:
  python manage.py install_playbook_bundle employee-onboarding
  python manage.py install_playbook_bundle employee-onboarding --dry-run
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from knowledge_base.models import KnowledgeBaseArticle
from tickets.models import ResolutionTemplate
from workflows.playbooks.employee_onboarding import (
    ONBOARDING_KB_ARTICLE_TITLES,
    ONBOARDING_RESOLUTION_TEMPLATE,
    SKU_ID,
)


class Command(BaseCommand):
    help = "Install a sellable playbook bundle (onboarding pack v1)"

    def add_arguments(self, parser):
        parser.add_argument(
            "sku_id",
            nargs="?",
            default=SKU_ID,
            help=f"Playbook SKU id (default: {SKU_ID})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned actions without writing",
        )

    def handle(self, *args, **options):
        sku = (options.get("sku_id") or SKU_ID).strip().lower()
        if sku != SKU_ID:
            raise CommandError(f"Unknown playbook SKU: {sku}")

        dry = options["dry_run"]
        if dry:
            self.stdout.write(
                f"Would install {SKU_ID}: workflow template, KB article(s), "
                f"resolution template, automation rule"
            )
            return

        call_command("seed_onboarding_playbook")
        call_command("seed_automation_rules")

        kb_created = 0
        for title in ONBOARDING_KB_ARTICLE_TITLES:
            _, created = KnowledgeBaseArticle.objects.get_or_create(
                title=title,
                team=None,
                defaults={
                    "content": (
                        "## Overview\n\n"
                        "New hires receive equipment and accounts. This checklist ensures nothing is missed.\n\n"
                        "See the full Employee Onboarding Pack in ResolveMeQ for workflow steps and automation."
                    ),
                    "tags": ["onboarding", "new_employee", "checklist"],
                    "is_published": True,
                },
            )
            if created:
                kb_created += 1

        rt_data = dict(ONBOARDING_RESOLUTION_TEMPLATE)
        rt_name = rt_data.pop("name")
        _, rt_created = ResolutionTemplate.objects.update_or_create(
            name=rt_name,
            defaults={**rt_data, "is_active": True, "is_ai_generated": False},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Installed {SKU_ID}: template + rules; KB articles created={kb_created}; "
                f"resolution template {'created' if rt_created else 'updated'}"
            )
        )
