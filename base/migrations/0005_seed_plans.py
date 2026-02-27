# Data migration: seed default billing plans

from django.db import migrations


def seed_plans(apps, schema_editor):
    Plan = apps.get_model('base', 'Plan')
    if Plan.objects.exists():
        return
    Plan.objects.bulk_create([
        Plan(
            name='Starter',
            slug='starter',
            max_teams=5,
            max_members=10,
            price_monthly=19,
            price_yearly=190,
            is_active=True,
        ),
        Plan(
            name='Pro',
            slug='pro',
            max_teams=20,
            max_members=50,
            price_monthly=49,
            price_yearly=490,
            is_active=True,
        ),
        Plan(
            name='Enterprise',
            slug='enterprise',
            max_teams=999,
            max_members=999,
            price_monthly=99,
            price_yearly=990,
            is_active=True,
        ),
    ])


def reverse_seed(apps, schema_editor):
    Plan = apps.get_model('base', 'Plan')
    Plan.objects.filter(slug__in=['starter', 'pro', 'enterprise']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_plan_subscription_invoice'),
    ]

    operations = [
        migrations.RunPython(seed_plans, reverse_seed),
    ]
