from django.contrib import admin

from .models import Rule, RuleExecutionLog


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger", "cron_expression", "team", "is_active", "priority", "updated_at")
    list_filter = ("trigger", "is_active", "team")
    search_fields = ("name", "description")


@admin.register(RuleExecutionLog)
class RuleExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("trigger", "rule", "status", "ticket", "executed_at")
    list_filter = ("trigger", "status")
    readonly_fields = ("executed_at",)
