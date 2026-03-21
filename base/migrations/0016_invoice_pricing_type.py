# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0015_alter_billingwebhookdelivery_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='pricing_type',
            field=models.CharField(default='subscription', max_length=32),
        ),
    ]
