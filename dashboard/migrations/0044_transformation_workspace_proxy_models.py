from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0043_portfolio_raid_transformation_workspace"),
    ]

    operations = [
        migrations.CreateModel(
            name="TransformationWorkspaceProject",
            fields=[],
            options={
                "verbose_name": "Project — TW (KPI cards + register)",
                "verbose_name_plural": (
                    "01 — Transformation Workspace — Projects / المشاريع "
                    "(داتا الكاردات العلوية + جدول السجل)"
                ),
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("dashboard.ProjectTrackerItem",),
        ),
        migrations.CreateModel(
            name="TransformationWorkspaceRaid",
            fields=[],
            options={
                "verbose_name": "RAID row — TW (Open RAID KPI)",
                "verbose_name_plural": (
                    "02 — Transformation Workspace — RAID / عناصر RAID "
                    "(كارد Open RAID Items)"
                ),
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("dashboard.PortfolioRaidItem",),
        ),
    ]
