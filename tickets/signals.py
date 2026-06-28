import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from celery.exceptions import OperationalError

from .models import Ticket
from .tasks import process_ticket_with_agent, process_ticket_with_agent_sync
from base.agent_usage import get_billing_user_for_ticket

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket)
def ticket_created(sender, instance, created, **kwargs):
    """
    Signal handler for when a ticket is created.
    Queues the ticket for processing by the AI agent using Celery, with a synchronous
    fallback if Celery itself is unavailable -- previously this just logged and gave up,
    so a new ticket would silently never get analyzed if the broker was down at creation
    time (unlike the manual "process with agent" trigger, which already degrades gracefully).
    """
    # Skip agent processing during tests if disabled
    if getattr(settings, 'TEST_DISABLE_AGENT', False):
        return

    if created and not instance.agent_processed:
        try:
            process_ticket_with_agent.delay(instance.ticket_id)
        except OperationalError as e:
            logger.warning(
                f"Celery unavailable for ticket {instance.ticket_id}, processing synchronously: {e}"
            )
            try:
                billing_user = get_billing_user_for_ticket(instance)
                process_ticket_with_agent_sync(instance, billing_user)
            except Exception as sync_error:
                logger.error(
                    f"Synchronous fallback failed for ticket {instance.ticket_id}: {sync_error}"
                )
