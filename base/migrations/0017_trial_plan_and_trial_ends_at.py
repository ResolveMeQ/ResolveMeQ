# Generated manually - Free trial support

from django.db import migrations, models


def add_trial_plan(apps, schema_editor):
    Plan = apps.get_model('base', 'Plan')
    if Plan.objects.filter(slug='trial').exists():
        return
    Plan.objects.create(
        name='Trial',
        slug='trial',
        is_trial=True,
        max_teams=2,
        max_members=5,
        price_monthly=0,
        price_yearly=0,
        is_active=True,
    )


def remove_trial_plan(apps, schema_editor):
    Plan = apps.get_model('base', 'Plan')
    Plan.objects.filter(slug='trial').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0016_invoice_pricing_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='is_trial',
            field=models.BooleanField(default=False, help_text='Free trial plan. No payment required.'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='trial_ends_at',
            field=models.DateTimeField(blank=True, help_text='When the free trial expires. Trial plan only.', null=True),
        ),
        migrations.RunPython(add_trial_plan, remove_trial_plan),
    ]
