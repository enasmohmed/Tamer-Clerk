# Generated manually — portfolio activity for Active Alerts

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0051_projecttrackeritem_pmo_register_published"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspacePortfolioActivity",
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
                ("message", models.CharField(max_length=420)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_activities",
                        to="dashboard.projecttrackeritem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Portfolio activity (TW alerts)",
                "verbose_name_plural": "Portfolio activities (TW alerts)",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
