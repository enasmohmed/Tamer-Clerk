# Clerk Interview Tracking table for Project Overview

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0023_weeklyprojecttrackerrow'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClerkInterviewTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('no', models.CharField(blank=True, help_text='NO', max_length=50)),
                ('dept_name_en', models.CharField(blank=True, help_text='DEPT_NAME_EN', max_length=200)),
                ('date', models.DateField(blank=True, help_text='Date', null=True)),
                ('clerk_name', models.CharField(blank=True, help_text='Clerk Name', max_length=200)),
                ('mobile', models.CharField(blank=True, help_text='Mobile', max_length=50)),
                ('company', models.CharField(blank=True, help_text='Company', max_length=200)),
                ('business', models.CharField(blank=True, help_text='Business', max_length=200)),
                ('account', models.CharField(blank=True, help_text='Account', max_length=200)),
                ('system_used', models.CharField(blank=True, help_text='System Used', max_length=200)),
                ('report_used', models.CharField(blank=True, help_text='Report Used', max_length=200)),
                ('details', models.TextField(blank=True, help_text='Details')),
                ('wh_visit_reasons', models.CharField(blank=True, help_text='WH Visit Reasons', max_length=300)),
                ('physical_dependency', models.CharField(blank=True, help_text='Physical Dependency', max_length=200)),
                ('automation_potential', models.CharField(blank=True, help_text='Automation Potential', max_length=200)),
                ('ct_suitability', models.CharField(blank=True, help_text='CT Suitability', max_length=200)),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Row order in table')),
            ],
            options={
                'verbose_name': 'Clerk Interview Tracking',
                'verbose_name_plural': 'Clerk Interview Tracking',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
