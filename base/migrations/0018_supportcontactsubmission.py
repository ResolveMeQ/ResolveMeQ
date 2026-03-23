# Generated manually for SupportContactSubmission

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0017_trial_plan_and_trial_ends_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportContactSubmission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, verbose_name='submitter email')),
                ('subject', models.CharField(blank=True, max_length=200, verbose_name='subject')),
                ('message', models.TextField(verbose_name='message')),
                ('page_context', models.CharField(blank=True, default='billing', max_length=64, verbose_name='page')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP address')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='support_contact_submissions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Support contact submission',
                'verbose_name_plural': 'Support contact submissions',
                'ordering': ['-created_at'],
            },
        ),
    ]
