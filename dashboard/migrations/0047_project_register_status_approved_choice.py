# Add "Approved" to register_status choices; backfill from legacy is_approved flag

from django.db import migrations, models


def backfill_approved_status(apps, schema_editor):
    ProjectTrackerItem = apps.get_model("dashboard", "ProjectTrackerItem")
    ProjectTrackerItem.objects.filter(is_approved=True, register_status="").update(
        register_status="approved"
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0046_alter_projecttrackeritem_cost_reduction_pct_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projecttrackeritem",
            name="register_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("on_track", "On Track"),
                    ("at_risk", "At Risk"),
                    ("delayed", "Delayed"),
                    ("blocked", "Blocked"),
                    ("approved", "Approved"),
                ],
                default="",
                help_text="حالة المشروع في السجل (يشمل Approved كخيار في القائمة)",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_approved_status, noop_reverse),
    ]
