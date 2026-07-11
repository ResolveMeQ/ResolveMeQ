from django.db import migrations, models


class Migration(migrations.Migration):
    # NOTE: verify no duplicate gateway_payment_id rows exist in prod before deploying,
    # since the prior check-then-create logic in payment_sync.py was not race-safe.

    dependencies = [
        ("base", "0035_teamworkspaceadmin_scoped_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="gateway_payment_id",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
