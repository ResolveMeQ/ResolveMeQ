from django.contrib import admin
from .models import AgentConfidenceLog, Ticket, ResolutionTemplate
from integrations.views import notify_user_ticket_resolved
import csv
from django.http import HttpResponse

@admin.action(description="Mark selected tickets as resolved")
def mark_as_resolved(modeladmin, request, queryset):
    for ticket in queryset:
        queryset.filter(pk=ticket.pk).update(status="resolved")
        if ticket.user:
            notify_user_ticket_resolved(ticket)

@admin.action(description="Respond via Slack bot")
def respond_via_bot(modeladmin, request, queryset):
    from integrations import slack_installation as slack_inst

    for ticket in queryset:
        inst = slack_inst.get_installation_for_ticket(ticket)
        ch = slack_inst.slack_dm_channel_for_user(ticket.user)
        if not inst or not ch:
            continue
        slack_inst.slack_api_post(
            inst,
            "chat.postMessage",
            {
                "channel": ch,
                "text": (
                    f"IT has responded to your ticket: {ticket.issue_type}\n"
                    f"Status: {ticket.status}\nDescription: {ticket.description}"
                ),
            },
        )

@admin.action(description="Export selected tickets as CSV")
def export_tickets_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tickets.csv"'
    writer = csv.writer(response)
    writer.writerow(['Ticket ID', 'User', 'Issue Type', 'Status', 'Description', 'Screenshot', 'Created At', 'Updated At'])
    for ticket in queryset:
        writer.writerow([
            ticket.ticket_id,
            ticket.user.name if ticket.user else "",
            ticket.issue_type,
            ticket.status,
            ticket.description,
            ticket.screenshot,
            ticket.created_at,
            ticket.updated_at,
        ])
    return response

@admin.register(AgentConfidenceLog)
class AgentConfidenceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "source", "confidence", "recommended_action", "created_at")
    list_filter = ("source",)
    search_fields = ("ticket__ticket_id", "recommended_action")
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_id", "user", "issue_type", "category", "status", "assigned_to", "description", "tags", "created_at", "updated_at"
    )
    list_filter = ("status", "assigned_to", "category")
    search_fields = (
        "user__user_id",
        "user__name",
        "user__email",
        "assigned_to__user_id",
        "assigned_to__name",
        "assigned_to__email",
        "issue_type",
        "description",
        "category",
        "tags",
    )
    actions = [mark_as_resolved, respond_via_bot, export_tickets_csv]
    autocomplete_fields = ["user", "assigned_to"]


@admin.action(description="Activate selected templates")
def activate_templates(modeladmin, request, queryset):
    """Bulk activate resolution templates."""
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"{updated} templates activated successfully.")


@admin.action(description="Deactivate selected templates")
def deactivate_templates(modeladmin, request, queryset):
    """Bulk deactivate resolution templates."""
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} templates deactivated successfully.")


@admin.action(description="Mark as AI-generated")
def mark_as_ai_generated(modeladmin, request, queryset):
    """Mark templates as AI-generated."""
    updated = queryset.update(is_ai_generated=True)
    modeladmin.message_user(request, f"{updated} templates marked as AI-generated.")


@admin.action(description="Export templates as CSV")
def export_templates_csv(modeladmin, request, queryset):
    """Export selected templates to CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="resolution_templates.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Name', 'Category', 'Issue Types', 'Tags', 'Estimated Time (min)',
        'Use Count', 'Success Count', 'Success Rate %', 'Is Active', 'Is AI Generated'
    ])
    for template in queryset:
        writer.writerow([
            str(template.id),
            template.name,
            template.category,
            ', '.join(template.issue_types) if template.issue_types else '',
            ', '.join(template.tags) if template.tags else '',
            template.estimated_time,
            template.use_count,
            template.success_count,
            f"{template.success_rate:.1f}",
            template.is_active,
            template.is_ai_generated,
        ])
    return response


@admin.register(ResolutionTemplate)
class ResolutionTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Resolution Templates."""
    list_display = [
        'name', 'category', 'display_issue_types', 'estimated_time', 
        'use_count', 'success_rate_display', 'is_active', 'is_ai_generated'
    ]
    list_filter = ['category', 'is_active', 'is_ai_generated', 'created_at']
    search_fields = ['name', 'description', 'tags']
    readonly_fields = ['id', 'use_count', 'success_count', 'success_rate_display', 'created_at', 'updated_at']
    ordering = ['-success_count', '-use_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category')
        }),
        ('Classification', {
            'fields': ('issue_types', 'tags')
        }),
        ('Resolution Steps', {
            'fields': ('steps', 'estimated_time'),
            'description': 'JSON array of steps with step_number, title, description, estimated_minutes'
        }),
        ('Usage Statistics', {
            'fields': ('use_count', 'success_count', 'success_rate_display'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_ai_generated')
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [activate_templates, deactivate_templates, mark_as_ai_generated, export_templates_csv]
    
    def display_issue_types(self, obj):
        """Display issue types as comma-separated string."""
        if obj.issue_types:
            return ', '.join(obj.issue_types[:3]) + ('...' if len(obj.issue_types) > 3 else '')
        return '-'
    display_issue_types.short_description = 'Issue Types'
    
    def success_rate_display(self, obj):
        """Display success rate with color coding."""
        rate = obj.success_rate
        if rate >= 80:
            color = 'green'
        elif rate >= 60:
            color = 'orange'
        else:
            color = 'red'
        return f'<span style="color: {color}; font-weight: bold;">{rate:.1f}%</span>'
    success_rate_display.short_description = 'Success Rate'
    success_rate_display.allow_tags = True

