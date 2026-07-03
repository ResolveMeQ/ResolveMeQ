from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0014_teams_integration'),
        ('base', '0029_subscription_trial_past_due_notification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='supportcontactsubmission',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True,
                help_text='Mirrors the linked ticket assignee when set.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_support_contact_submissions',
                to='base.user',
            ),
        ),
        migrations.AddField(
            model_name='supportcontactsubmission',
            name='status',
            field=models.CharField(
                choices=[
                    ('open', 'Open'),
                    ('in_progress', 'In progress'),
                    ('resolved', 'Resolved'),
                    ('closed', 'Closed'),
                ],
                default='open',
                max_length=20,
                verbose_name='status',
            ),
        ),
        migrations.AddField(
            model_name='supportcontactsubmission',
            name='ticket',
            field=models.ForeignKey(
                blank=True,
                help_text='Escalated ticket created from this enquiry (portal billing form).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='support_contact_submissions',
                to='tickets.ticket',
            ),
        ),
    ]
