from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0055_projectstabtaskstore"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectsTabCardProject",
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
                ("project_key", models.CharField(max_length=80, unique=True)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Cards view project",
                "verbose_name_plural": "Cards view projects",
                "ordering": ["-created_at"],
            },
        ),
    ]
