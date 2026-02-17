# Progress Status table: Clerk, Account, Remark, Status (Quick_wins.xlsx, Sheet1)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0035_delete_businesslogo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProgressStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clerk', models.CharField(blank=True, help_text='Clerk', max_length=200)),
                ('account', models.CharField(blank=True, help_text='Account', max_length=200)),
                ('remark', models.TextField(blank=True, help_text='Remark')),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('in_progress', 'In Progress'), ('not_started', 'Not Started')], default='not_started', help_text='Completed / In Progress / Not Started', max_length=20)),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='Row order in table')),
            ],
            options={
                'verbose_name': 'Progress Status',
                'verbose_name_plural': 'Progress Status',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
