from django.db import migrations


def add_time_saved_kpi(apps, schema_editor):
    ExecutiveOverviewKpiCard = apps.get_model("dashboard", "ExecutiveOverviewKpiCard")
    seeds = [
        {
            "key": "time_saved",
            "title": "TIME SAVED",
            "value_text": "—",
            "subtitle": "Estimated time preserved",
            "footer": "Sum of project time-saving estimates",
            "accent": "purple",
            "display_order": 45,
        },
    ]
    for row in seeds:
        ExecutiveOverviewKpiCard.objects.get_or_create(
            key=row["key"],
            defaults={**row, "is_active": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0058_projecttrackeritem_automation_fields"),
    ]

    operations = [
        migrations.RunPython(add_time_saved_kpi, migrations.RunPython.noop),
    ]
