from django.contrib import admin

from integrations.models import SlackToken, WebhookDelivery, WebhookEndpoint, OktaInstallation, ConnectorCheckLog, ConnectorActionLog, GoogleWorkspaceInstallation, Microsoft365Installation, JiraInstallation


def _masked(value) -> str:
    """Never render a real credential in the admin -- masked placeholder only."""
    return "•" * 12 if value else "—"


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
    readonly_fields = ("created_at", "updated_at", "access_token_display")
    exclude = ("access_token",)

    @admin.display(description="Access token")
    def access_token_display(self, obj):
        return _masked(obj.access_token)


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "url", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "created_by")
    readonly_fields = ("secret_display",)
    exclude = ("secret",)

    @admin.display(description="Signing secret")
    def secret_display(self, obj):
        return _masked(obj.secret)


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("delivery_id", "event_type", "status", "response_code", "attempts", "created_at")
    list_filter = ("status", "event_type")
    search_fields = ("delivery_id", "url", "error_message")
    readonly_fields = ("delivery_id", "payload", "created_at", "delivered_at", "secret_display")
    exclude = ("secret",)

    @admin.display(description="Signing secret")
    def secret_display(self, obj):
        return _masked(obj.secret)


@admin.register(OktaInstallation)
class OktaInstallationAdmin(admin.ModelAdmin):
    list_display = ("okta_domain", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("okta_domain", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "installed_by")
    readonly_fields = ("access_token_display", "refresh_token_display")
    exclude = ("access_token", "refresh_token")

    @admin.display(description="Access token")
    def access_token_display(self, obj):
        return _masked(obj.access_token)

    @admin.display(description="Refresh token")
    def refresh_token_display(self, obj):
        return _masked(obj.refresh_token)


@admin.register(ConnectorCheckLog)
class ConnectorCheckLogAdmin(admin.ModelAdmin):
    list_display = ("connector", "check_type", "status", "workflow_step", "team", "ran_at")
    list_filter = ("connector", "status", "check_type")
    search_fields = ("message",)
    readonly_fields = ("ran_at", "detail")


@admin.register(ConnectorActionLog)
class ConnectorActionLogAdmin(admin.ModelAdmin):
    list_display = ("connector", "action_type", "status", "executed_by", "workflow_step", "team", "ran_at")
    list_filter = ("connector", "status", "action_type")
    search_fields = ("message",)
    readonly_fields = ("ran_at", "detail")


@admin.register(GoogleWorkspaceInstallation)
class GoogleWorkspaceInstallationAdmin(admin.ModelAdmin):
    list_display = ("admin_email", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    raw_id_fields = ("resolvemeq_team", "installed_by")
    readonly_fields = ("access_token_display", "refresh_token_display")
    exclude = ("access_token", "refresh_token")

    @admin.display(description="Access token")
    def access_token_display(self, obj):
        return _masked(obj.access_token)

    @admin.display(description="Refresh token")
    def refresh_token_display(self, obj):
        return _masked(obj.refresh_token)


@admin.register(Microsoft365Installation)
class Microsoft365InstallationAdmin(admin.ModelAdmin):
    list_display = ("tenant_id", "resolvemeq_team", "is_active", "failure_count", "updated_at")
    list_filter = ("is_active",)
    raw_id_fields = ("resolvemeq_team", "installed_by")
    readonly_fields = ("access_token_display", "refresh_token_display")
    exclude = ("access_token", "refresh_token")

    @admin.display(description="Access token")
    def access_token_display(self, obj):
        return _masked(obj.access_token)

    @admin.display(description="Refresh token")
    def refresh_token_display(self, obj):
        return _masked(obj.refresh_token)


@admin.register(JiraInstallation)
class JiraInstallationAdmin(admin.ModelAdmin):
    list_display = ("site_url", "project_key", "resolvemeq_team", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("site_url", "project_key", "resolvemeq_team__name")
    raw_id_fields = ("resolvemeq_team", "installed_by")
    readonly_fields = ("api_token_display",)
    exclude = ("api_token",)

    @admin.display(description="API token")
    def api_token_display(self, obj):
        return _masked(obj.api_token)
