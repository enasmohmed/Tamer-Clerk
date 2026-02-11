# Migration: جعل Allocated count و Pending or edit count اختياريين (يمكن تركهما فارغين)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0010_warehouse_and_theme_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='warehouseemployeesummary',
            name='allocated_count',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='اختياري — اتركيه فارغاً إن لم تحتاجيه',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='warehouseemployeesummary',
            name='pending_or_edit_count',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='اختياري — رقم يظهر بجانب أيقونة القلم إن وُجد',
                null=True,
            ),
        ),
    ]
