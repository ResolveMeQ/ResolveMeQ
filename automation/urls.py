from django.urls import path

from . import views

urlpatterns = [
    path("metadata/", views.automation_metadata, name="automation-metadata"),
    path("rules/", views.rule_list_create, name="automation-rules"),
    path("rules/<int:rule_id>/", views.rule_detail, name="automation-rule-detail"),
    path("rules/<int:rule_id>/dry-run/", views.rule_dry_run, name="automation-rule-dry-run"),
    path("logs/", views.rule_execution_logs, name="automation-logs"),
]
