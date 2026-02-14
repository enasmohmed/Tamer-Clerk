# Rename date -> start_date, add end_date (after Launch)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0021_projecttrackeritem_company'),
    ]

    operations = [
        migrations.RenameField(
            model_name='projecttrackeritem',
            old_name='date',
            new_name='start_date',
        ),
        migrations.AddField(
            model_name='projecttrackeritem',
            name='end_date',
            field=models.DateField(blank=True, help_text='Project end date (optional)', null=True),
        ),
    ]
