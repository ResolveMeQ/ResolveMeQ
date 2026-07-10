from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0034_teamworkspaceadmin"),
    ]

    operations = [
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_manage_playbooks",
            field=models.BooleanField(default=True, help_text="Workflow templates and automation rules"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_manage_members",
            field=models.BooleanField(default=True, help_text="Invite/remove members and set ops roles"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_manage_integrations",
            field=models.BooleanField(default=False, help_text="Connect and disconnect integrations"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_manage_webhooks",
            field=models.BooleanField(default=False, help_text="Outbound webhook endpoints"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_manage_partner_api",
            field=models.BooleanField(default=False, help_text="Partner API keys"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="can_view_audit_log",
            field=models.BooleanField(default=False, help_text="Compliance audit log view and export"),
        ),
        migrations.AddField(
            model_name="teamworkspaceadmin",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
