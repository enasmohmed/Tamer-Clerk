from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0054_project_register_remarks"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectsTabTaskStore",
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
                        help_text="e.g. log-068",
                        max_length=80,
                        unique=True,
                    ),
                ),
                ("tasks", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Projects tab task store",
                "verbose_name_plural": "Projects tab task stores",
            },
        ),
    ]
