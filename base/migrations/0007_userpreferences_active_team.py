# Generated manually: active team for usage/billing context

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0006_team_owner_teaminvitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreferences',
            name='active_team',
            field=models.ForeignKey(
                blank=True,
                help_text='Team context for usage and billing; user must be a member',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users_with_active',
                to='base.team',
                verbose_name='active team',
            ),
        ),
    ]
