from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0061_projectprocessstep_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectprocessstep",
            name="business_benefits",
            field=models.TextField(
                blank=True,
                help_text="Business benefits expected from completing this task.",
            ),
        ),
    ]
