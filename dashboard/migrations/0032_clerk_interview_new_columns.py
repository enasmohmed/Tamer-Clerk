# Clerk Interview Tracking: new columns WH, NATIONALITY, Optimization Status, Strength, Remark

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0031_alter_projecttrackeritem_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='wh',
            field=models.CharField(blank=True, help_text='WH', max_length=120),
        ),
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='nationality',
            field=models.CharField(blank=True, help_text='NATIONALITY', max_length=120),
        ),
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='optimization_status',
            field=models.CharField(blank=True, help_text='Optimization Status', max_length=200),
        ),
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='strength',
            field=models.CharField(blank=True, help_text='Strength', max_length=200),
        ),
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='remark',
            field=models.TextField(blank=True, help_text='Remark'),
        ),
    ]
