# Generated manually for team owner and invitations

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_seed_plans'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                help_text='User who owns this team and can invite/remove members',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='owned_teams',
                to=settings.AUTH_USER_MODEL,
                verbose_name='team owner',
            ),
        ),
        migrations.CreateModel(
            name='TeamInvitation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, verbose_name='invitee email')),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')],
                    default='pending',
                    max_length=20,
                    verbose_name='status',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('invited_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_team_invitations',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='invited by',
                )),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invitations',
                    to='base.team',
                    verbose_name='team',
                )),
            ],
            options={
                'verbose_name': 'Team invitation',
                'verbose_name_plural': 'Team invitations',
                'ordering': ['-created_at'],
            },
        ),
    ]
