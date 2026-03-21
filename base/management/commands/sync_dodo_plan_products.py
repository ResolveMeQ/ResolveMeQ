from django.core.management.base import BaseCommand, CommandError

from base.billing.exceptions import BillingConfigurationError
from base.billing.services import sync_dodo_products_for_plan
from base.models import Plan


class Command(BaseCommand):
    help = (
        'Create Dodo Payments subscription products via API for local Plans and '
        'store PlanGatewayProduct mappings. Skips intervals with price 0 or existing rows. '
        'Use --recreate if checkout fails with "Product ... does not exist" (wrong test/live '
        'mode or stale IDs vs current DODO_PAYMENTS_API_KEY).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--plan-slug',
            type=str,
            help='Only sync the plan with this slug (must be active).',
        )
        parser.add_argument(
            '--recreate',
            action='store_true',
            help=(
                'Remove existing Dodo mappings for each matching plan, then create new products '
                'in the current Dodo environment (orphans old product IDs in Dodo).'
            ),
        )

    def handle(self, *args, **options):
        qs = Plan.objects.filter(is_active=True).order_by('slug')
        slug = options.get('plan_slug')
        if slug:
            qs = qs.filter(slug=slug)
        if not qs.exists():
            raise CommandError('No matching active plans found.')

        recreate = bool(options.get('recreate'))
        try:
            for plan in qs:
                rows = sync_dodo_products_for_plan(plan, recreate=recreate)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{plan.slug}: {len(rows)} gateway mapping(s) '
                        f'({", ".join(f"{r.interval}={r.external_product_id}" for r in rows) or "none"})'
                    )
                )
        except BillingConfigurationError as e:
            raise CommandError(str(e)) from e
