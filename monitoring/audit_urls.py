from django.urls import path

from . import audit_views

urlpatterns = [
    path("events/", audit_views.audit_events, name="audit-events"),
    path("export/", audit_views.audit_export, name="audit-export"),
]
