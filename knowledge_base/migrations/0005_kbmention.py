from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge_base", "0004_kbquestion_duplicate_link"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KBMention",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "target_type",
                    models.CharField(
                        choices=[("question", "Question"), ("answer", "Answer"), ("comment", "Comment")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("target_id", models.PositiveIntegerField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "mentioned_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_mentions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="kb_mentions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["target_type", "target_id"], name="knowledge_ba_target__7f1c2e_idx"),
                    models.Index(fields=["mentioned_user", "created_at"], name="knowledge_ba_mention__6a1f3c_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="kbmention",
            constraint=models.UniqueConstraint(
                fields=("target_type", "target_id", "mentioned_user"),
                name="uniq_kbmention_target_user",
            ),
        ),
    ]

