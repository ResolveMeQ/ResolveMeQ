import logging
import os
import sys

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _email_dispatch_uses_celery() -> bool:
    """
    Queue outbound mail via Celery when workers are expected.

    If EMAIL_USE_CELERY is unset, default to synchronous delivery while
    ``runserver`` is used so verification/password emails are not dropped
    when no worker is running (tasks would sit in Redis).
    """
    explicit = os.getenv("EMAIL_USE_CELERY", "").strip().lower()
    if explicit in ("0", "false", "no"):
        return False
    if explicit in ("1", "true", "yes"):
        return True
    return "runserver" not in sys.argv


def dispatch_send_email_with_template(
    data: dict, template_name: str, context: dict, recipient: list
) -> None:
    if _email_dispatch_uses_celery():
        send_email_with_template.delay(data, template_name, context, recipient)
    else:
        logger.info("Sending email synchronously (no Celery queue for this process)")
        send_email_with_template(data, template_name, context, recipient)


@shared_task
def send_email_with_template(data: dict, template_name: str, context: dict, recipient: list):
    template_name = f'emails/{template_name}'
    try:
        email_body = render_to_string(template_name, context)

        email = EmailMessage(
            subject=data['subject'],
            body=email_body,
            from_email=settings.EMAIL_HOST_USER,
            to=recipient,
        )
        email.content_subtype = 'html'
        email.send()
        logger.info('Email sent')
    except Exception as e:
        logger.error(f'Email sending failed: {str(e)}', exc_info=True)
        print("❌ EMAIL FAILED:", str(e))
