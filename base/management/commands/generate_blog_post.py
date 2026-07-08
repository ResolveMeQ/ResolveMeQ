from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate one AI marketing blog post (same logic as the daily Celery task)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create another AI post even if one already exists for today.",
        )

    def handle(self, *args, **options):
        from base.blog_generation import generate_daily_blog_post

        post = generate_daily_blog_post(force=options["force"])
        if post is None:
            self.stdout.write(self.style.WARNING("Skipped: AI blog post already exists for today."))
            return
        self.stdout.write(self.style.SUCCESS(f"Created blog post #{post.pk} slug={post.slug}"))
