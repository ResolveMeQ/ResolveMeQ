from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge_base", "0003_kbattachment"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbquestion",
            name="duplicate_note",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="kbquestion",
            name="duplicate_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="duplicates",
                to="knowledge_base.kbquestion",
            ),
        ),
    ]
