from django.contrib import admin

from integrations.models import SlackToken, WebhookDelivery, WebhookEndpoint, OktaInstallation, ConnectorCheckLog


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


@admin.register(OktaInstallation)
class OktaInstallationAdmin(admin.ModelAdmin):
    list_display = ("okta_domain", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("okta_domain", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "installed_by")


@admin.register(ConnectorCheckLog)
class ConnectorCheckLogAdmin(admin.ModelAdmin):
    list_display = ("connector", "check_type", "status", "workflow_step", "team", "ran_at")
    list_filter = ("connector", "status", "check_type")
    search_fields = ("message",)
    readonly_fields = ("ran_at", "detail")
