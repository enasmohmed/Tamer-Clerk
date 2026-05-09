# Generated manually for Transformation Workspace KPIs + RAID

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0042_projecttrackeritem_test_deadline_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="planned_hours",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Planned effort (hours). Used for CPI when Actual hours is set.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="actual_hours",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Actual effort spent (hours). CPI ≈ Planned / Actual when both set.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="last_status_update",
            field=models.DateField(
                blank=True,
                help_text="Last PMO/status update (used in PMO Score — Updates component).",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="PortfolioRaidItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("risk", "Risk"), ("assumption", "Assumption"), ("issue", "Issue"), ("dependency", "Dependency")], default="issue", max_length=20)),
                ("title", models.CharField(max_length=300)),
                ("status", models.CharField(choices=[("open", "Open"), ("pending", "Pending"), ("closed", "Closed")], default="open", max_length=20)),
                ("severity", models.CharField(choices=[("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low")], default="medium", max_length=20)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="raid_items",
                        to="dashboard.projecttrackeritem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Portfolio RAID Item",
                "verbose_name_plural": "Portfolio RAID Items",
                "ordering": ["project", "display_order", "id"],
            },
        ),
    ]
