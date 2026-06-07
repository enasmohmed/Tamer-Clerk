from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0056_projectstabcardproject"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectsTabProjectMetaStore",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "project_key",
                    models.CharField(
                        help_text="e.g. log-065",
                        max_length=80,
                        unique=True,
                    ),
                ),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Cards view project meta",
                "verbose_name_plural": "Cards view project meta",
            },
        ),
    ]
