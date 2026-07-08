from django.urls import path

from . import template_views, views

urlpatterns = [
    path("", views.workflow_list_create, name="workflow-list-create"),
    path("templates/", views.workflow_templates, name="workflow-templates"),
    path("templates/manage/", template_views.template_manage_list_create, name="workflow-template-manage"),
    path("templates/<int:template_id>/", template_views.template_detail, name="workflow-template-detail"),
    path("<uuid:workflow_id>/steps/<int:step_id>/claim/", views.claim_step, name="workflow-step-claim"),
    path("<uuid:workflow_id>/steps/<int:step_id>/complete/", views.complete_step, name="workflow-step-complete"),
]
