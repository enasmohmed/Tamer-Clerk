from django.db import migrations, models


def import_remarks_from_legacy_text(apps, schema_editor):
    ProjectTrackerItem = apps.get_model("dashboard", "ProjectTrackerItem")
    ProjectRegisterRemark = apps.get_model("dashboard", "ProjectRegisterRemark")

    for obj in ProjectTrackerItem.objects.all().iterator():
        raw = (obj.remarks or "").strip()
        if not raw:
            continue

        kept_lines = []
        order = 0
        risk_from_line = ""

        for line in raw.split("\n"):
            s = line.strip()
            low = s.lower()
            if low.startswith("remark:"):
                text = s.split(":", 1)[1].strip() if ":" in s else ""
                if text:
                    ProjectRegisterRemark.objects.create(
                        project_id=obj.pk,
                        text=text,
                        display_order=order,
                    )
                    order += 1
                continue
            if low.startswith("risk level:"):
                rl = s.split(":", 1)[1].strip() if ":" in s else ""
                if rl in ("Low", "Medium", "High"):
                    risk_from_line = rl
                continue
            kept_lines.append(line)

        update_fields = []
        new_remarks = "\n".join(kept_lines).strip()
        if new_remarks != raw:
            obj.remarks = new_remarks
            update_fields.append("remarks")
        if risk_from_line and not (obj.register_risk_level or "").strip():
            obj.register_risk_level = risk_from_line
            update_fields.append("register_risk_level")
        if update_fields:
            obj.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0053_projecttrackeritem_progress_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="register_risk_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("Low", "Low"),
                    ("Medium", "Medium"),
                    ("High", "High"),
                ],
                default="",
                help_text="Risk level from Project Register form (Low / Medium / High).",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ProjectRegisterRemark",
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
                ("text", models.TextField(help_text="نص الملاحظة")),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="register_remarks",
                        to="dashboard.projecttrackeritem",
                    ),
                ),
            ],
            options={
                "verbose_name": "Project register remark",
                "verbose_name_plural": "Project register remarks",
                "ordering": ["project", "display_order", "id"],
            },
        ),
        migrations.RunPython(import_remarks_from_legacy_text, noop_reverse),
    ]
