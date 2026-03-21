# Generated manually for billing gateway integration

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0011_contactrequest_newslettersubscription'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanGatewayProduct',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('gateway', models.CharField(choices=[('dodo', 'Dodo Payments')], max_length=32)),
                ('interval', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')], max_length=16)),
                ('external_product_id', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gateway_products', to='base.plan')),
            ],
            options={
                'verbose_name': 'Plan gateway product',
                'verbose_name_plural': 'Plan gateway products',
            },
        ),
        migrations.AddConstraint(
            model_name='plangatewayproduct',
            constraint=models.UniqueConstraint(fields=('plan', 'gateway', 'interval'), name='uniq_base_plangatewayproduct_plan_gateway_interval'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='gateway',
            field=models.CharField(blank=True, default='', help_text='Active payment provider code (e.g. dodo); empty if not linked', max_length=32),
        ),
        migrations.AddField(
            model_name='subscription',
            name='gateway_customer_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='subscription',
            name='gateway_subscription_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
