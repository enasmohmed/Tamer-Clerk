# Generated manually for warehouse, theme, region, and related models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0009_alter_meetingpoint_assigned_to'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardTheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(help_text='مثال: primary_color, tab_active_bg', max_length=100, unique=True)),
                ('value', models.CharField(blank=True, help_text='قيمة مثل #4C8FD6 أو 12px', max_length=200)),
                ('description', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'verbose_name': 'Dashboard Theme',
                'verbose_name_plural': 'Dashboard Themes',
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('color_hex', models.CharField(default='#6c757d', help_text='مثل #2e7d32 للأخضر', max_length=20)),
                ('is_warehouse_status', models.BooleanField(default=True, help_text='يُستخدم كحالة للمستودع')),
                ('is_phase_status', models.BooleanField(default=False, help_text='يُستخدم كحالة للمرحلة (Completed, Pending, ...)')),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Status',
                'verbose_name_plural': 'Statuses',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='BusinessUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Business Unit',
                'verbose_name_plural': 'Business Units',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Activity',
                'verbose_name_plural': 'Activities',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('status', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='warehouses', to='dashboard.status')),
            ],
            options={
                'verbose_name': 'Warehouse',
                'verbose_name_plural': 'Warehouses',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='BusinessSystem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('business_unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='systems', to='dashboard.businessunit')),
            ],
            options={
                'verbose_name': 'Business System',
                'verbose_name_plural': 'Business Systems',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('skus', models.CharField(blank=True, max_length=80)),
                ('available', models.CharField(blank=True, max_length=80)),
                ('utilization_pct', models.CharField(blank=True, max_length=80)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Region',
                'verbose_name_plural': 'Regions',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='WarehouseBusinessSystem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system_name_override', models.CharField(blank=True, help_text='إن تركت فارغاً يُستخدم اسم النظام', max_length=120)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('business_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='warehouse_links', to='dashboard.businessunit')),
                ('system', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='warehouse_links', to='dashboard.businesssystem')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='business_systems', to='dashboard.warehouse')),
            ],
            options={
                'verbose_name': 'Warehouse Business System',
                'verbose_name_plural': 'Warehouse Business Systems',
                'ordering': ['warehouse', 'display_order'],
                'unique_together': {('warehouse', 'business_unit')},
            },
        ),
        migrations.CreateModel(
            name='WarehousePhaseStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phase_statuses', to='dashboard.activity')),
                ('business_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phase_statuses', to='dashboard.businessunit')),
                ('status', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='phase_statuses', to='dashboard.status')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='phase_statuses', to='dashboard.warehouse')),
            ],
            options={
                'verbose_name': 'Warehouse Phase Status',
                'verbose_name_plural': 'Warehouse Phase Statuses',
                'ordering': ['warehouse', 'display_order', 'business_unit', 'activity'],
            },
        ),
        migrations.CreateModel(
            name='WarehouseEmployeeSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allocated_count', models.PositiveIntegerField(default=0)),
                ('pending_or_edit_count', models.PositiveIntegerField(default=0, help_text='رقم يظهر بجانب أيقونة القلم إن وُجد')),
                ('phase_label', models.CharField(blank=True, help_text='مثل Phase 1', max_length=120)),
                ('phase_status_label', models.CharField(blank=True, help_text='مثل Completed', max_length=120)),
                ('warehouse', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employee_summary', to='dashboard.warehouse')),
            ],
            options={
                'verbose_name': 'Warehouse Employee Summary',
                'verbose_name_plural': 'Warehouse Employee Summaries',
            },
        ),
        migrations.CreateModel(
            name='WarehouseMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='اسم العرض إن لم يُربط بمستودع', max_length=120)),
                ('skus', models.CharField(blank=True, max_length=80)),
                ('available_space', models.CharField(blank=True, max_length=80)),
                ('utilization_pct', models.CharField(blank=True, max_length=80)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('warehouse', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='dashboard.warehouse')),
            ],
            options={
                'verbose_name': 'Warehouse Metric',
                'verbose_name_plural': 'Warehouse Metrics',
                'ordering': ['display_order', 'name'],
            },
        ),
    ]
