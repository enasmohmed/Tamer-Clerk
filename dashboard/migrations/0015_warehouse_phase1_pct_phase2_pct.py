# Migration: إضافة Phase 1 و Phase 2 مع نسبة الإنجاز (0–100) للمستودع

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0014_warehousebusinesssystem_system_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='phase1_pct',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='نسبة إنجاز Phase 1 (0–100). اتركه فارغاً إن لم تستخدمه.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='warehouse',
            name='phase2_pct',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='نسبة إنجاز Phase 2 (0–100). اتركه فارغاً إن لم تستخدمه.',
                null=True,
            ),
        ),
    ]
