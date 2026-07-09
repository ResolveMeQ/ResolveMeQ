from celery import shared_task

from integrations.connectors.base import should_retry
from integrations.connectors.webhook import deliver_webhook_now


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deliver_webhook_task(self, delivery_id):
    ok = deliver_webhook_now(delivery_id)
    if ok:
        return {"delivery_id": delivery_id, "status": "success"}

    from integrations.models import WebhookDelivery

    delivery = WebhookDelivery.objects.filter(pk=delivery_id).first()
    if delivery and delivery.attempts < 4 and should_retry(delivery.response_code):
        raise self.retry(exc=Exception(delivery.error_message or "webhook failed"))
    return {"delivery_id": delivery_id, "status": "failed"}
