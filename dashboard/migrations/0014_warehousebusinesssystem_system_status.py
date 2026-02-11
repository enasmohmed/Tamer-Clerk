# Migration: استبدال status (FK) بحالة نظام اختيار من متعدد: Pending PH1, PH1 completed, Pending PH2, PH2 completed

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0013_warehousebusinesssystem_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehousebusinesssystem',
            name='system_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("pending_ph1", "Pending PH1"),
                    ("ph1_completed", "PH1 completed"),
                    ("pending_ph2", "Pending PH2"),
                    ("ph2_completed", "PH2 completed"),
                ],
                help_text="حالة النظام: Pending PH1 / PH1 completed / Pending PH2 / PH2 completed",
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name='warehousebusinesssystem',
            name='status',
        ),
    ]
