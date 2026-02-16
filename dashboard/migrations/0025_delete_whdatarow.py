# Remove WHDataRow (Employee Data Table: WH, Emp No, Full Name, Business, Business 2)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0024_clerkinterviewtracking'),
    ]

    operations = [
        migrations.DeleteModel(name='WHDataRow'),
    ]
