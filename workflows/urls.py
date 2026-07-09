from django.urls import path

from . import playbook_views, template_views, views

urlpatterns = [
    path("", views.workflow_list_create, name="workflow-list-create"),
    path("playbooks/employee-onboarding/", playbook_views.employee_onboarding_playbook, name="workflow-playbook-onboarding"),
    path("templates/", views.workflow_templates, name="workflow-templates"),
    path("templates/manage/", template_views.template_manage_list_create, name="workflow-template-manage"),
    path("templates/<int:template_id>/", template_views.template_detail, name="workflow-template-detail"),
    path("assignee-roles/", views.assignee_roles, name="workflow-assignee-roles"),
    path("<uuid:workflow_id>/steps/<int:step_id>/claim/", views.claim_step, name="workflow-step-claim"),
    path("<uuid:workflow_id>/steps/<int:step_id>/complete/", views.complete_step, name="workflow-step-complete"),
    path("<uuid:workflow_id>/steps/<int:step_id>/auto-check/", views.rerun_auto_check, name="workflow-step-auto-check"),
]
