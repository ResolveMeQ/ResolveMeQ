# In-app notifications for the header bell dropdown

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0009_profile_location_city_blank'),
    ]

    operations = [
        migrations.CreateModel(
            name='InAppNotification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('type', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('error', 'Error')], default='info', max_length=20)),
                ('title', models.CharField(max_length=255, verbose_name='title')),
                ('message', models.TextField(blank=True, verbose_name='message')),
                ('link', models.CharField(blank=True, help_text='Optional URL or path to open on click', max_length=500, verbose_name='link')),
                ('is_read', models.BooleanField(default=False, verbose_name='read')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='in_app_notifications', to=settings.AUTH_USER_MODEL, verbose_name='user')),
            ],
            options={
                'verbose_name': 'In-app notification',
                'verbose_name_plural': 'In-app notifications',
                'ordering': ['-created_at'],
            },
        ),
    ]
