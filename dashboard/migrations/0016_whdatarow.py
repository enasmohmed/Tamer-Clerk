# Migration: جدول WH Data Row (تحت كاردز Warehouses Overview)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0015_warehouse_phase1_pct_phase2_pct'),
    ]

    operations = [
        migrations.CreateModel(
            name='WHDataRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wh', models.CharField(help_text='WH (اسم)', max_length=120)),
                ('emp_no', models.CharField(help_text='Emp No (أرقام)', max_length=50)),
                ('full_name', models.CharField(help_text='Full Name', max_length=200)),
                ('display_order', models.PositiveSmallIntegerField(default=0, help_text='ترتيب الصف في الجدول')),
                ('business', models.ForeignKey(help_text='Business (وحدة أعمال)', on_delete=django.db.models.deletion.CASCADE, related_name='wh_data_rows_business', to='dashboard.businessunit')),
                ('business_2', models.ForeignKey(blank=True, help_text='Business 2 (وحدة أعمال ثانية، اختياري)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wh_data_rows_business_2', to='dashboard.businessunit')),
            ],
            options={
                'verbose_name': 'WH Data Row (صف جدول تحت الكاردز)',
                'verbose_name_plural': 'WH Data Rows (جدول تحت الكاردز)',
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
