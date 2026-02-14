# Generated manually for Project Tracker tab

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0019_alter_activity_options_alter_businesssystem_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectTrackerItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(help_text='Project task description (e.g. Finalize kickoff materials)', max_length=300)),
                ('person_name', models.CharField(help_text='Name of the person responsible', max_length=120)),
                ('date', models.DateField(help_text='Project date (used for month grouping and ordering)')),
                ('brainstorming_status', models.CharField(blank=True, choices=[('', 'Not started'), ('done', 'Done'), ('working_on_it', 'Working on it'), ('stuck', 'Stuck')], default='', help_text='Brainstorming phase: Done / Working on it / Stuck', max_length=20)),
                ('execution_status', models.CharField(blank=True, choices=[('', 'Not started'), ('done', 'Done'), ('working_on_it', 'Working on it'), ('stuck', 'Stuck')], default='', help_text='Execution phase: Done / Working on it / Stuck', max_length=20)),
                ('launch_status', models.CharField(blank=True, choices=[('', 'Not started'), ('done', 'Done'), ('working_on_it', 'Working on it'), ('stuck', 'Stuck')], default='', help_text='Launch phase: Done / Working on it / Stuck', max_length=20)),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Order within the same day (smaller = first)')),
            ],
            options={
                'verbose_name': 'Project Tracker Item',
                'verbose_name_plural': 'Project Tracker Items',
                'ordering': ['-date', 'display_order', 'id'],
            },
        ),
    ]
