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
from . import okta_views
from . import google_views
from . import microsoft_views
from . import jira_views

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
    path("okta/status/", okta_views.okta_integration_status, name="okta_integration_status"),
    path("okta/oauth/start/", okta_views.okta_oauth_start, name="okta_oauth_start"),
    path("okta/oauth/redirect/", okta_views.okta_oauth_redirect, name="okta_oauth_redirect"),
    path("okta/disconnect/", okta_views.okta_disconnect, name="okta_disconnect"),
    path("google/status/", google_views.google_workspace_status, name="google_workspace_status"),
    path("google/oauth/start/", google_views.google_workspace_oauth_start, name="google_workspace_oauth_start"),
    path("google/oauth/redirect/", google_views.google_workspace_oauth_redirect, name="google_workspace_oauth_redirect"),
    path("google/disconnect/", google_views.google_workspace_disconnect, name="google_workspace_disconnect"),
    path("microsoft/status/", microsoft_views.microsoft365_status, name="microsoft365_status"),
    path("microsoft/oauth/start/", microsoft_views.microsoft365_oauth_start, name="microsoft365_oauth_start"),
    path("microsoft/oauth/redirect/", microsoft_views.microsoft365_oauth_redirect, name="microsoft365_oauth_redirect"),
    path("microsoft/disconnect/", microsoft_views.microsoft365_disconnect, name="microsoft365_disconnect"),
    path("jira/status/", jira_views.jira_integration_status, name="jira_integration_status"),
    path("jira/configure/", jira_views.jira_configure, name="jira_configure"),
    path("jira/update/", jira_views.jira_update, name="jira_update"),
    path("jira/disconnect/", jira_views.jira_disconnect, name="jira_disconnect"),
]
