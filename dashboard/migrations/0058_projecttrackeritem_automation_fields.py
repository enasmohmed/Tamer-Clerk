from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0057_projectstabprojectmetastore"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="estimated_time_saving",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Estimated time saving from automation (numeric value).",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="estimated_time_saving_unit",
            field=models.CharField(
                blank=True,
                choices=[("hours", "Hours"), ("minutes", "Minutes")],
                default="hours",
                help_text="Unit for estimated time saving (hours or minutes).",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="projecttrackeritem",
            name="resources_before_automation",
            field=models.TextField(
                blank=True,
                help_text="People / roles involved before automation.",
            ),
        ),
    ]
