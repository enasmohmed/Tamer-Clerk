from django.db import migrations


def hide_cpi_and_open_risks(apps, schema_editor):
    ExecutiveOverviewKpiCard = apps.get_model("dashboard", "ExecutiveOverviewKpiCard")
    ExecutiveOverviewKpiCard.objects.filter(key__in=["cpi", "open_risks"]).update(
        is_active=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0059_executive_overview_time_saved_kpi"),
    ]

    operations = [
        migrations.RunPython(hide_cpi_and_open_risks, migrations.RunPython.noop),
    ]
