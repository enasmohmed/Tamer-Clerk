# Potential Challenges table: Date, Challenges, Status, Progress %, Solutions

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0028_recommendation_title_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='PotentialChallenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.CharField(blank=True, help_text='Date', max_length=100)),
                ('challenges', models.TextField(blank=True, help_text='Challenges')),
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
                ('solutions', models.TextField(blank=True, help_text='Solutions')),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Row order in table')),
            ],
            options={
                'verbose_name': 'Potential Challenge',
                'verbose_name_plural': 'Potential Challenges',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
