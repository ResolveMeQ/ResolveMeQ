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


class TeamsInstallation(models.Model):
    """
    Microsoft Teams tenant/team installation (Bot Framework conversation reference).

    Unlike Slack (one workspace = one OAuth install), a single AAD `tenant_id` can contain
    several Teams "teams", each potentially linked to a different ResolveMeQ Team -- so
    uniqueness is on (tenant_id, teams_team_id), not tenant_id alone. `teams_team_id` is
    null until the bot is actually added to a team/channel (captured from a
    conversationUpdate activity); `resolvemeq_team` is null until a link code is consumed
    (see TeamsLinkCode) -- these two can happen in either order.
    """

    tenant_id = models.CharField(max_length=64, db_index=True, help_text="AAD tenant id")
    teams_team_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        help_text="Teams team (group) id; set once the bot is added to a team",
    )
    conversation_id = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="Default channel conversation id, used for escalation-channel posts",
    )
    service_url = models.URLField(
        max_length=512,
        blank=True,
        default="",
        help_text="serviceUrl to use for outbound Bot Framework calls to this tenant/team",
    )
    resolvemeq_team = models.ForeignKey(
        "base.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams_installations",
    )
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams_app_installs",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "teams_team_id"],
                condition=models.Q(teams_team_id__isnull=False),
                name="integrations_teamsinstallation_unique_tenant_team",
            ),
        ]
        indexes = [
            models.Index(fields=["resolvemeq_team", "is_active"]),
        ]

    def __str__(self):
        return f"Teams {self.tenant_id}/{self.teams_team_id or '?'}" + (
            f" → {self.resolvemeq_team.name}" if self.resolvemeq_team_id else " (unlinked)"
        )


class TeamsLinkCode(models.Model):
    """
    Short-lived code shown in Settings; consumed by a `link <code>` message sent to the bot
    in Teams. DB-backed (not a signed token like Slack's OAuth `state`) because the gap
    between generating the code and typing it into Teams can be minutes, across two
    different UIs -- a row lets the UI show live status and lets us enforce one-time use.
    """

    code = models.CharField(max_length=12, unique=True, db_index=True)
    resolvemeq_team = models.ForeignKey(
        "base.Team", on_delete=models.CASCADE, related_name="teams_link_codes"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by_installation = models.ForeignKey(
        TeamsInstallation, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["resolvemeq_team", "consumed_at"]),
        ]

    def __str__(self):
        state = "consumed" if self.consumed_at else "pending"
        return f"TeamsLinkCode {self.code} ({state})"


class WebhookEndpoint(models.Model):
    """Team-scoped outbound webhook URL with HMAC signing secret."""

    resolvemeq_team = models.ForeignKey(
        "base.Team",
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
    )
    name = models.CharField(max_length=120, blank=True, default="")
    url = models.URLField(max_length=512)
    secret = models.CharField(max_length=128)
    events = models.JSONField(
        default=list,
        blank=True,
        help_text="Empty list = all events; else subset of ticket.* / workflow.* events.",
    )
    is_active = models.BooleanField(default=True)
    failure_count = models.PositiveIntegerField(default=0)
    circuit_open_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_endpoints_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["resolvemeq_team", "is_active"]),
        ]

    def __str__(self):
        label = self.name or self.url
        return f"Webhook {label} ({self.resolvemeq_team_id})"


class WebhookDelivery(models.Model):
    """Outbound webhook attempt log (retries + admin visibility)."""

    delivery_id = models.UUIDField(unique=True, db_index=True)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    event_type = models.CharField(max_length=64, db_index=True)
    team_id = models.UUIDField(null=True, blank=True, db_index=True)
    url = models.URLField(max_length=512)
    secret = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
    )
    attempts = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["endpoint", "created_at"]),
            models.Index(fields=["team_id", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"WebhookDelivery {self.delivery_id} ({self.status})"
