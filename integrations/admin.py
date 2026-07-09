from django.contrib import admin

from integrations.models import SlackToken, WebhookDelivery, WebhookEndpoint


@admin.register(SlackToken)
class SlackTokenAdmin(admin.ModelAdmin):
    list_display = (
        "team_id",
        "resolvemeq_team",
        "installed_by",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("team_id", "bot_user_id", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "installed_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "url", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "created_by")


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("delivery_id", "event_type", "status", "response_code", "attempts", "created_at")
    list_filter = ("status", "event_type")
    search_fields = ("delivery_id", "url", "error_message")
    readonly_fields = ("delivery_id", "payload", "created_at", "delivered_at")
