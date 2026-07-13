from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tickets"

    def ready(self):
        import tickets.signals  # noqa

        try:
            from resolvemeq.media_dirs import ensure_media_subdirectories

            ensure_media_subdirectories()
        except Exception as exc:
            # Do not block startup; entrypoint should fix Docker volumes. Log for local dev.
            import logging

            logging.getLogger(__name__).debug("Media subdir ensure skipped: %s", exc)
