from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0060_hide_cpi_open_risks_kpi_cards"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectprocessstep",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Not Started"),
                    ("in_progress", "In Progress"),
                    ("done", "Completed"),
                ],
                default="pending",
                help_text="Task completion status for Cards View progress metrics.",
                max_length=20,
            ),
        ),
    ]
