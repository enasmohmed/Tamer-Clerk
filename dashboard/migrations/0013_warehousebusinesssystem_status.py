# Migration: إضافة عمود الحالة (Status) لجدول System داخل كارد المستودع

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0012_alter_activity_options_alter_businesssystem_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehousebusinesssystem',
            name='status',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='warehouse_business_systems',
                to='dashboard.status',
            ),
        ),
    ]
