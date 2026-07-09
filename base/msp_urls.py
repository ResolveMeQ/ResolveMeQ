from django.urls import path

from . import msp_views

urlpatterns = [
    path("status/", msp_views.msp_status, name="msp-status"),
    path("enable/", msp_views.msp_enable, name="msp-enable"),
    path("dashboard/", msp_views.msp_dashboard, name="msp-dashboard"),
    path("clients/", msp_views.msp_create_client, name="msp-create-client"),
    path("clients/<uuid:client_id>/usage/", msp_views.msp_client_usage, name="msp-client-usage"),
]
