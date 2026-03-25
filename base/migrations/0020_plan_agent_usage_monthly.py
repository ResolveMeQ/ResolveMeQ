# Generated manually — agent operation quotas per plan

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_plan_agent_limits(apps, schema_editor):
    Plan = apps.get_model('base', 'Plan')
    slug_limits = {
        'trial': 200,
        'starter': 2000,
        'pro': 10000,
        'enterprise': None,
    }
    for p in Plan.objects.all():
        if p.slug in slug_limits:
            p.max_agent_operations_per_month = slug_limits[p.slug]
        else:
            p.max_agent_operations_per_month = 500
        p.save(update_fields=['max_agent_operations_per_month'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0019_user_google_sub'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='max_agent_operations_per_month',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Maximum AI agent operations (analyze, chat turn, etc.) per billing period. Null means unlimited (e.g. Enterprise).',
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='AgentUsageMonthly',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('period_start', models.DateTimeField()),
                ('period_end', models.DateTimeField()),
                ('operations_used', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='agent_usage_periods',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='billing account',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Agent usage (period)',
                'verbose_name_plural': 'Agent usage (periods)',
            },
        ),
        migrations.AddConstraint(
            model_name='agentusagemonthly',
            constraint=models.UniqueConstraint(fields=('user', 'period_start'), name='unique_agent_usage_user_period'),
        ),
        migrations.RunPython(seed_plan_agent_limits, noop),
    ]
