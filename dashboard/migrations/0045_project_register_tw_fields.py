# Project Register — Transformation Workspace structured fields + lookups

from django.db import migrations, models
import django.db.models.deletion


def seed_tw_lookups(apps, schema_editor):
    WD = apps.get_model("dashboard", "WorkspaceDepartment")
    WC = apps.get_model("dashboard", "WorkspaceProjectCategory")
    WS = apps.get_model("dashboard", "WorkspaceStrategicAlignment")
    for i, name in enumerate(
        ["Logistics", "IT", "HR", "Finance", "Operations", "Retail", "PMO", "Digital"]
    ):
        WD.objects.get_or_create(name=name, defaults={"display_order": i, "is_active": True})
    for i, name in enumerate(["Idea", "Automation", "Digital", "Infrastructure", "Operations"]):
        WC.objects.get_or_create(name=name, defaults={"display_order": i, "is_active": True})
    for i, name in enumerate(
        [
            "Cost Optimization",
            "Automation",
            "Customer Satisfaction",
            "Compliance",
            "Productivity",
            "Digital Transformation",
            "Revenue Growth",
        ]
    ):
        WS.objects.get_or_create(name=name, defaults={"display_order": i, "is_active": True})


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0044_transformation_workspace_proxy_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceDepartment",
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
                ("name", models.CharField(max_length=200, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "TW Lookup — Department",
                "verbose_name_plural": "03 — TW Lookups — Departments",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="WorkspaceProjectCategory",
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
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "TW Lookup — Category",
                "verbose_name_plural": "04 — TW Lookups — Project categories",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="WorkspaceStrategicAlignment",
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
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "TW Lookup — Strategic alignment",
                "verbose_name_plural": "05 — TW Lookups — Strategic alignment",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.RunPython(seed_tw_lookups, reverse_seed),
        migrations.AlterField(
            model_name="projecttrackeritem",
            name="person_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Secondary contact / Project 2",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="cost_reduction_pct",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Cost reduction %",
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="department_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracker_projects",
                to="dashboard.workspacedepartment",
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="headcount_impact",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="is_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="kpi_success_criteria",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="objective_sow",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="project_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="project_lead",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="register_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracker_projects",
                to="dashboard.workspaceprojectcategory",
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="register_priority",
            field=models.CharField(
                blank=True,
                choices=[
                    ("critical", "Critical"),
                    ("high", "High"),
                    ("medium", "Medium"),
                    ("low", "Low"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="register_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("on_track", "On Track"),
                    ("at_risk", "At Risk"),
                    ("delayed", "Delayed"),
                    ("blocked", "Blocked"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="scope_deliverables",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="scope_dependencies",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="scope_in",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="scope_out",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="sla_improvement",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="strategic_alignment_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracker_projects",
                to="dashboard.workspacestrategicalignment",
            ),
        ),
    ]
