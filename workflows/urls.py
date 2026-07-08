from django.urls import path

from . import views

urlpatterns = [
    path("", views.workflow_list_create, name="workflow-list-create"),
    path("templates/", views.workflow_templates, name="workflow-templates"),
    path("<uuid:workflow_id>/steps/<int:step_id>/claim/", views.claim_step, name="workflow-step-claim"),
    path("<uuid:workflow_id>/steps/<int:step_id>/complete/", views.complete_step, name="workflow-step-complete"),
]
