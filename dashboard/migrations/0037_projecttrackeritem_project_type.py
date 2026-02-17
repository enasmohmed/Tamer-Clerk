# Add Project Type (Idea / Automation) to Project Tracker Item

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0036_progressstatus'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecttrackeritem',
            name='project_type',
            field=models.CharField(
                choices=[('idea', 'Idea'), ('automation', 'Automation')],
                default='idea',
                help_text='Project Type: Idea or Automation',
                max_length=20,
            ),
        ),
    ]
