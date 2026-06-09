from django.db import migrations


def hide_time_saved_kpi(apps, schema_editor):
    ExecutiveOverviewKpiCard = apps.get_model("dashboard", "ExecutiveOverviewKpiCard")
    ExecutiveOverviewKpiCard.objects.filter(key="time_saved").update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0063_projecttrackeritem_business_benefits"),
    ]

    operations = [
        migrations.RunPython(hide_time_saved_kpi, migrations.RunPython.noop),
    ]
