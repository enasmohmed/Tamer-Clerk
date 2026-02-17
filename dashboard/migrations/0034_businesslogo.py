# Business logo per business name (Key Recommendations card header)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0033_remove_clerk_legacy_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessLogo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business', models.CharField(help_text='Business name (must match exactly the Business used in Recommendations, e.g. 3PL FMCG)', max_length=120, unique=True)),
                ('logo', models.ImageField(help_text='Company/business logo. Shown in the card header for this business.', upload_to='business_logos/')),
            ],
            options={
                'verbose_name': 'Business Logo',
                'verbose_name_plural': 'Business Logos',
                'ordering': ['business'],
            },
        ),
    ]
