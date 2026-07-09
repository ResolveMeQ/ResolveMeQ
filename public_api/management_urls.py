from django.urls import path

from . import key_views

urlpatterns = [
    path("keys/metadata/", key_views.partner_key_metadata, name="partner-key-metadata"),
    path("keys/", key_views.partner_key_list_create, name="partner-key-list-create"),
    path("keys/<uuid:key_id>/", key_views.partner_key_revoke, name="partner-key-revoke"),
]
