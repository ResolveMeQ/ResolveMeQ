# Allow blank location/city on Profile so Settings can save without "field may not be blank"

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_teaminvitation_unique_pending_invitation_per_team_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='location',
            field=models.CharField(blank=True, default='', help_text='The location of the user, e.g., country or city', max_length=300, verbose_name='Location'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='city',
            field=models.CharField(blank=True, default='', help_text='The city where the user resides', max_length=300, verbose_name='City'),
        ),
    ]
