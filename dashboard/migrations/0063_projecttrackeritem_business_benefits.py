from django.db import migrations, models


def merge_legacy_automation_fields(apps, schema_editor):
    ProjectTrackerItem = apps.get_model("dashboard", "ProjectTrackerItem")
    for obj in ProjectTrackerItem.objects.all():
        if (obj.business_benefits or "").strip():
            continue
        parts = []
        if obj.estimated_time_saving is not None:
            unit = (obj.estimated_time_saving_unit or "hours").strip() or "hours"
            parts.append(f"Estimated time saving: {obj.estimated_time_saving} {unit}")
        if (obj.resources_before_automation or "").strip():
            parts.append((obj.resources_before_automation or "").strip())
        if parts:
            obj.business_benefits = "\n".join(parts)
            obj.save(update_fields=["business_benefits"])


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0062_projectprocessstep_business_benefits"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="business_benefits",
            field=models.TextField(
                blank=True,
                help_text="Expected business benefits from the project or automation.",
            ),
        ),
        migrations.RunPython(merge_legacy_automation_fields, migrations.RunPython.noop),
    ]
