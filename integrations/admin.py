from django.contrib import admin

from integrations.models import SlackToken


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
