# Add user_name and business to Recommendation for grouped cards

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0026_clerkinterviewtracking_optimization_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='recommendation',
            name='user_name',
            field=models.CharField(blank=True, help_text='User who created this (e.g. Allaa, Hisham)', max_length=120),
        ),
        migrations.AddField(
            model_name='recommendation',
            name='business',
            field=models.CharField(blank=True, help_text='Business type (e.g. 3PL FMCG, 3PL Healthcare)', max_length=120),
        ),
        migrations.AlterModelOptions(
            name='recommendation',
            options={'ordering': ['business', 'user_name', 'display_order', 'id'], 'verbose_name': 'Recommendation', 'verbose_name_plural': 'Recommendations'},
        ),
    ]
