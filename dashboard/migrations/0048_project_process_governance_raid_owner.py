# Project Process steps, Governance fields, RAID owner + status Mitigated

import django.utils.timezone
import django.db.models.deletion
from django.db import migrations, models


def migrate_raid_pending_to_mitigated(apps, schema_editor):
    PortfolioRaidItem = apps.get_model("dashboard", "PortfolioRaidItem")
    PortfolioRaidItem.objects.filter(status="pending").update(status="mitigated")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0047_project_register_status_approved_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="created_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                help_text="وقت إنشاء السجل — للترتيب من الأحدث للأقدم",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_approval_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("in_review", "In review"),
                ],
                default="",
                help_text="Governance — Approval status",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_assumptions_constraints",
            field=models.TextField(blank=True, help_text="Governance — Assumptions & constraints"),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_operational_impact",
            field=models.TextField(blank=True, help_text="Operational impact summary"),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_reviewed_by",
            field=models.CharField(blank=True, help_text="Governance — Reviewed by", max_length=120),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_stakeholders",
            field=models.TextField(blank=True, help_text="Stakeholders list"),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="gov_submitted_by",
            field=models.CharField(blank=True, help_text="Governance — Submitted by", max_length=120),
        ),
        migrations.AlterField(
            model_name="projecttrackeritem",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                help_text="وقت إنشاء السجل — للترتيب من الأحدث للأقدم",
            ),
        ),
        migrations.CreateModel(
            name="ProjectProcessStep",
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
                ("description", models.TextField(blank=True, help_text="الخطوة / ماذا سيتم إنجازه")),
                ("step_deadline", models.DateField(blank=True, null=True)),
                (
                    "owner_name",
                    models.CharField(
                        blank=True,
                        help_text="المسؤول عن الخطوة",
                        max_length=120,
                    ),
                ),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_steps",
                        to="dashboard.projecttrackeritem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project Process Step",
                "verbose_name_plural": "Project Process Steps",
                "ordering": ["project", "display_order", "id"],
            },
        ),
        migrations.AddField(
            model_name="portfolioraiditem",
            name="owner_name",
            field=models.CharField(
                blank=True,
                help_text="RAID item owner / accountable person",
                max_length=120,
            ),
        ),
        migrations.RunPython(migrate_raid_pending_to_mitigated, noop),
        migrations.AlterField(
            model_name="portfolioraiditem",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("mitigated", "Mitigated"),
                    ("closed", "Closed"),
                ],
                default="open",
                max_length=20,
            ),
        ),
    ]
