from django.conf import settings
from django.core.management.base import BaseCommand

from base.blog_seed_data import STATIC_BLOG_POSTS, import_static_blog_posts


class Command(BaseCommand):
    help = (
        "One-time import of the 5 legacy static marketing blog posts into BlogPost. "
        "Safe to re-run: skips existing slugs unless --force."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing posts when slug already exists.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created or updated without writing to the database.",
        )

    def handle(self, *args, **options):
        author = getattr(settings, "BLOG_AUTHOR_NAME", None) or "Nyuydine Bill"
        created, updated, skipped = import_static_blog_posts(
            force=options["force"],
            dry_run=options["dry_run"],
            author_name=author,
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would create {created}, update {updated}, skip {skipped} "
                    f"(of {len(STATIC_BLOG_POSTS)} static posts)."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Blog seed complete: created {created}, updated {updated}, skipped {skipped}."
            )
        )
