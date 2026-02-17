# Remove BusinessLogo: card header logo uses Recommendation.custom_icon instead

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0034_businesslogo'),
    ]

    operations = [
        migrations.DeleteModel(name='BusinessLogo'),
    ]
