# Generated by Django 5.2.2 on 2025-06-13 21:59

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('ticket_id', models.AutoField(primary_key=True, serialize=False)),
                ('issue_type', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=50)),
                ('description', models.TextField(blank=True, null=True)),
                ('screenshot', models.URLField(blank=True, null=True)),
                ('category', models.CharField(choices=[('wifi', 'Wi-Fi'), ('laptop', 'Laptop'), ('vpn', 'VPN'), ('printer', 'Printer'), ('email', 'Email'), ('software', 'Software'), ('hardware', 'Hardware'), ('network', 'Network'), ('account', 'Account'), ('access', 'Access'), ('phone', 'Phone'), ('server', 'Server'), ('security', 'Security'), ('cloud', 'Cloud'), ('storage', 'Storage'), ('other', 'Other')], default='other', max_length=30)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent_response', models.JSONField(blank=True, help_text='Response from the AI agent analyzing this ticket', null=True)),
                ('agent_processed', models.BooleanField(default=False, help_text='Whether the AI agent has processed this ticket')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tickets', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TicketInteraction',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('interaction_type', models.CharField(choices=[('clarification', 'Clarification'), ('feedback', 'Feedback'), ('agent_response', 'Agent Response'), ('user_message', 'User Message')], max_length=50)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tickets.ticket')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
