# Weekly Project Tracker table for Progress Overview tab

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0022_projecttrackeritem_start_date_end_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyProjectTrackerRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week', models.CharField(help_text='Week label e.g. Week 1 - Feb', max_length=100)),
                ('task', models.TextField(help_text='Task or description')),
                ('status', models.CharField(
                    choices=[
                        ('completed', 'Completed'),
                        ('in_progress', 'In Progress'),
                        ('not_started', 'Not Started'),
                    ],
                    default='not_started',
                    help_text='Completed / In Progress / Not Started',
                    max_length=20,
                )),
                ('progress_pct', models.PositiveSmallIntegerField(blank=True, default=0, help_text='Progress percentage (0-100)')),
                ('impact', models.TextField(blank=True, help_text='Impact description')),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Row order in table (smaller = first)')),
            ],
            options={
                'verbose_name': 'Weekly Project Tracker Row',
                'verbose_name_plural': 'Weekly Project Tracker Rows',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
