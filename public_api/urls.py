from django.urls import path

from . import views

urlpatterns = [
    path("", views.public_api_info, name="public-api-info"),
    path("tickets/", views.public_ticket_list, name="public-ticket-list"),
    path("tickets/create/", views.public_ticket_create, name="public-ticket-create"),
    path("tickets/<int:ticket_id>/", views.public_ticket_detail, name="public-ticket-detail"),
    path("tickets/<int:ticket_id>/update/", views.public_ticket_update, name="public-ticket-update"),
    path("workflows/", views.public_workflow_list, name="public-workflow-list"),
    path("workflows/start/", views.public_workflow_start, name="public-workflow-start"),
    path("workflows/<uuid:workflow_id>/", views.public_workflow_detail, name="public-workflow-detail"),
    path("rules/", views.public_rule_list, name="public-rule-list"),
]
