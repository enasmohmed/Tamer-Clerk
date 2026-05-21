from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0052_workspaceportfolioactivity"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="progress_pct",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="% complete (0–100) from Project Register; overrides phase-derived estimate when set.",
                null=True,
            ),
        ),
    ]
