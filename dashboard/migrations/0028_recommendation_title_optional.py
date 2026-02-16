# Make Recommendation title optional (blank=True)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0027_recommendation_user_name_business'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recommendation',
            name='title',
            field=models.CharField(blank=True, help_text='Recommendation title (optional)', max_length=200),
        ),
    ]
