# Generated manually – add Company field between person_name and date

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0020_projecttrackeritem'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecttrackeritem',
            name='company',
            field=models.CharField(blank=True, help_text='Company name', max_length=200),
        ),
    ]
