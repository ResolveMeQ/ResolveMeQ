from django.urls import path, include
from .views import (
    ticket_analytics,
    process_with_agent,
    task_status,
    ticket_agent_status,
    create_ticket,
    clarify_ticket,
    feedback_ticket,
    ticket_history,
    list_tickets,
    get_ticket,
    update_ticket,
    delete_ticket,
    search_tickets,
    upload_attachment,
    add_comment,
    escalate_ticket,
    assign_ticket,
    update_ticket_status,
    agent_dashboard,
    bulk_update_tickets,
    suggest_kb_articles,
    add_internal_note,
    audit_log,
    ai_suggestions,
    agent_analytics,
    enhanced_kb_search,
    agent_recommendations,
    rollback_action,
    action_history,
    submit_resolution_feedback,
    resolution_analytics,
)

# Enhanced views for improved UX/UI
from .enhanced_views import (
    paginated_action_history,
    dashboard_summary,
    filtered_recommendations,
    batch_process_tickets,
    batch_status,
    validate_action,
)

# Resolution Template views (P2)
from .template_views import (
    list_resolution_templates,
    get_resolution_template,
    create_resolution_template,
    update_resolution_template,
    delete_resolution_template,
    apply_template_to_ticket,
    get_templates_for_ticket,
)

# AI Insights views (P3)
from .ai_insights_views import (
    get_confidence_explanation,
    get_similar_tickets,
)

urlpatterns = [
    # Add ticket-related endpoints here
    path("analytics/", ticket_analytics, name="ticket-analytics"),
    path("<int:ticket_id>/process/", process_with_agent, name="process-with-agent"),
    path("tasks/<str:task_id>/status/", task_status, name="task-status"),
    path("<int:ticket_id>/agent-status/", ticket_agent_status, name="ticket-agent-status"),
    path("", create_ticket, name="create-ticket"),
    path("list/", list_tickets, name="list-tickets"),
    path("<int:ticket_id>/", get_ticket, name="get-ticket"),
    path("<int:ticket_id>/update/", update_ticket, name="update-ticket"),
    path("<int:ticket_id>/delete/", delete_ticket, name="delete-ticket"),
    path("<int:ticket_id>/clarify/", clarify_ticket, name="clarify-ticket"),
    path("<int:ticket_id>/feedback/", feedback_ticket, name="feedback-ticket"),
    path("<int:ticket_id>/history/", ticket_history, name="ticket-history"),
    path("search/", search_tickets, name="search-tickets"),
    path("<int:ticket_id>/upload/", upload_attachment, name="upload-attachment"),
    path("<int:ticket_id>/comment/", add_comment, name="add-comment"),
    path("<int:ticket_id>/escalate/", escalate_ticket, name="escalate-ticket"),
    path("<int:ticket_id>/assign/", assign_ticket, name="assign-ticket"),
    path("<int:ticket_id>/status/", update_ticket_status, name="update-ticket-status"),
    path("dashboard/", agent_dashboard, name="agent-dashboard"),
    path("bulk-update/", bulk_update_tickets, name="bulk-update-tickets"),
    path("<int:ticket_id>/kb-suggestions/", suggest_kb_articles, name="suggest-kb-articles"),
    path("<int:ticket_id>/internal-note/", add_internal_note, name="add-internal-note"),
    path("<int:ticket_id>/audit-log/", audit_log, name="audit-log"),
    path("<int:ticket_id>/ai-suggestions/", ai_suggestions, name="ai-suggestions"),
    # AI Agent endpoints
    path("agent/analytics/", agent_analytics, name="agent-analytics"),
    path("agent/kb-search/", enhanced_kb_search, name="enhanced-kb-search"),
    path("agent/recommendations/", agent_recommendations, name="agent-recommendations"),
    
    # Enhanced UX/UI endpoints (Quick Wins)
    path("agent/dashboard-summary/", dashboard_summary, name="dashboard-summary"),
    path("agent/recommendations/filtered/", filtered_recommendations, name="filtered-recommendations"),
    path("<int:ticket_id>/action-history-paginated/", paginated_action_history, name="paginated-action-history"),
    
    # Batch Operations (P0)
    path("agent/batch-process/", batch_process_tickets, name="batch-process"),
    path("agent/batch/<str:batch_id>/status/", batch_status, name="batch-status"),
    path("<int:ticket_id>/actions/validate/", validate_action, name="validate-action"),
    
    # Rollback and feedback endpoints
    path("actions/<uuid:action_history_id>/rollback/", rollback_action, name="rollback-action"),
    path("<int:ticket_id>/action-history/", action_history, name="action-history"),
    path("<int:ticket_id>/resolution-feedback/", submit_resolution_feedback, name="submit-resolution-feedback"),
    path("resolution-analytics/", resolution_analytics, name="resolution-analytics"),
    
    # Resolution Templates (P2)
    path("agent/templates/", list_resolution_templates, name="list-resolution-templates"),
    path("agent/templates/create/", create_resolution_template, name="create-resolution-template"),
    path("agent/templates/<uuid:template_id>/", get_resolution_template, name="get-resolution-template"),
    path("agent/templates/<uuid:template_id>/update/", update_resolution_template, name="update-resolution-template"),
    path("agent/templates/<uuid:template_id>/delete/", delete_resolution_template, name="delete-resolution-template"),
    path("<int:ticket_id>/apply-template/", apply_template_to_ticket, name="apply-template"),
    path("<int:ticket_id>/recommended-templates/", get_templates_for_ticket, name="get-templates-for-ticket"),
    
    # AI Insights & Transparency (P3)
    path("<int:ticket_id>/confidence-explanation/", get_confidence_explanation, name="confidence-explanation"),
    path("<int:ticket_id>/similar/", get_similar_tickets, name="similar-tickets"),
    
    # Chat conversation endpoints
    path("", include('tickets.chat_urls')),
]
