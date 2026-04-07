from django.conf import settings
from django.db import models


class SlackToken(models.Model):
    """
    Slack workspace installation (OAuth bot token).
    `team_id` is Slack's workspace identifier (team.id from OAuth / API payloads).
    `resolvemeq_team` is the ResolveMeQ Team this workspace is linked to after install.
    """

    access_token = models.TextField(help_text="Slack bot token (xoxb-...)")
    team_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        db_index=True,
        help_text="Slack workspace ID (T...)",
    )
    bot_user_id = models.CharField(max_length=32, blank=True, null=True)
    resolvemeq_team = models.ForeignKey(
        "base.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slack_installations",
    )
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slack_app_installs",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team_id"],
                condition=models.Q(team_id__isnull=False),
                name="integrations_slacktoken_unique_slack_team_id",
            ),
        ]
        indexes = [
            models.Index(fields=["resolvemeq_team", "is_active"]),
        ]

    def __str__(self):
        return f"Slack {self.team_id or '?'}" + (
            f" → {self.resolvemeq_team.name}" if self.resolvemeq_team_id else " (unlinked)"
        )
