from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0048_project_process_governance_raid_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExecutiveOverviewKpiCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(help_text="Unique key (e.g. total_projects, on_track, spi)", max_length=80, unique=True)),
                ("title", models.CharField(help_text="Card title (upper label)", max_length=120)),
                ("value_text", models.CharField(default="—", help_text="Displayed value", max_length=40)),
                ("subtitle", models.CharField(blank=True, help_text="Small line under value", max_length=140)),
                ("footer", models.CharField(blank=True, help_text="Footer hint under the card", max_length=160)),
                ("accent", models.CharField(choices=[("cyan", "Cyan"), ("green", "Green"), ("amber", "Amber"), ("purple", "Purple"), ("red", "Red")], default="cyan", max_length=12)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Executive KPI Card",
                "verbose_name_plural": "00 — Executive Overview — KPI Cards / كروت المؤشرات",
                "ordering": ["display_order", "id"],
            },
        ),
    ]

