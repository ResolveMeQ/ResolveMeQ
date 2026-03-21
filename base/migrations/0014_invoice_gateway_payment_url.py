# Generated for Invoice gateway fields (payment sync + PDF URL)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0013_billing_webhook_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='gateway_payment_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoice_url',
            field=models.URLField(blank=True, max_length=512, null=True),
        ),
    ]
