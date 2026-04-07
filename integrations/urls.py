from django.urls import path
from .views import (
    slack_oauth_start,
    slack_oauth_redirect,
    slack_integration_status,
    slack_events,
    slack_slash_command,
    SlackInteractiveActionView,
    slack_modal_submission,
)

urlpatterns = [
    path("slack/status/", slack_integration_status, name="slack_integration_status"),
    path("slack/oauth/start/", slack_oauth_start, name="slack_oauth_start"),
    path("slack/oauth/redirect/", slack_oauth_redirect, name="slack_oauth_redirect"),
    path("slack/events/", slack_events, name="slack_events"),
    path("slack/commands/", slack_slash_command, name="slack_slash_command"),
    path("slack/actions/", SlackInteractiveActionView.as_view(), name="slack_interactive_action"),
    path("slack/modal/", slack_modal_submission, name="slack_modal_submission"),
]
