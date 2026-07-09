from django.urls import path
from .views import (
    slack_oauth_start,
    slack_oauth_redirect,
    slack_integration_status,
    slack_disconnect,
    slack_events,
    slack_slash_command,
    SlackInteractiveActionView,
    slack_modal_submission,
)
from .teams_views import (
    teams_link_start,
    teams_integration_status,
    teams_disconnect,
    teams_messages,
)
from . import webhook_views

urlpatterns = [
    path("slack/status/", slack_integration_status, name="slack_integration_status"),
    path("slack/disconnect/", slack_disconnect, name="slack_disconnect"),
    path("slack/oauth/start/", slack_oauth_start, name="slack_oauth_start"),
    path("slack/oauth/redirect/", slack_oauth_redirect, name="slack_oauth_redirect"),
    path("slack/events/", slack_events, name="slack_events"),
    path("slack/commands/", slack_slash_command, name="slack_slash_command"),
    path("slack/actions/", SlackInteractiveActionView.as_view(), name="slack_interactive_action"),
    path("slack/modal/", slack_modal_submission, name="slack_modal_submission"),
    path("teams/status/", teams_integration_status, name="teams_integration_status"),
    path("teams/disconnect/", teams_disconnect, name="teams_disconnect"),
    path("teams/link/start/", teams_link_start, name="teams_link_start"),
    path("teams/messages/", teams_messages, name="teams_messages"),
    path("webhooks/metadata/", webhook_views.webhook_metadata, name="webhook_metadata"),
    path("webhooks/", webhook_views.webhook_list_create, name="webhook_list_create"),
    path("webhooks/deliveries/", webhook_views.webhook_deliveries, name="webhook_deliveries"),
    path("webhooks/<int:endpoint_id>/", webhook_views.webhook_detail, name="webhook_detail"),
    path("webhooks/<int:endpoint_id>/test/", webhook_views.webhook_test, name="webhook_test"),
]
