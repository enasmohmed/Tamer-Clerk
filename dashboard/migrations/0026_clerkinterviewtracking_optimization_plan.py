# Add Optimization Plan to Clerk Interview Tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0025_delete_whdatarow'),
    ]

    operations = [
        migrations.AddField(
            model_name='clerkinterviewtracking',
            name='optimization_plan',
            field=models.CharField(blank=True, help_text='Optimization Plan (optional, from Excel)', max_length=300),
        ),
    ]
