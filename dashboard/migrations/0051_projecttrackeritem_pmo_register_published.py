# Generated manually for PMO portal register visibility

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0050_alter_projecttrackeritem_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="projecttrackeritem",
            name="pmo_register_published",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="يظهر في Project Register والمقاييس بعد موافقة المدير. التيم: False حتى الموافقة.",
            ),
        ),
    ]
