from django.contrib import admin

from .models import ComplianceAuditEvent


@admin.register(ComplianceAuditEvent)
class ComplianceAuditEventAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "event_type",
        "actor_email",
        "resource_type",
        "resource_id",
        "team",
    ]
    list_filter = ["event_type", "resource_type", "created_at"]
    search_fields = ["summary", "actor_email", "resource_id"]
    readonly_fields = [
        "id",
        "team",
        "actor",
        "actor_email",
        "event_type",
        "resource_type",
        "resource_id",
        "summary",
        "metadata",
        "ip_address",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
