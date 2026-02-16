# Remove legacy columns from ClerkInterviewTracking (NO, DEPT_NAME_EN, Date, Mobile, Company, Account, Details, etc.)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0032_clerk_interview_new_columns'),
    ]

    operations = [
        migrations.RemoveField(model_name='clerkinterviewtracking', name='no'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='dept_name_en'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='date'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='mobile'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='company'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='account'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='details'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='wh_visit_reasons'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='physical_dependency'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='automation_potential'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='ct_suitability'),
        migrations.RemoveField(model_name='clerkinterviewtracking', name='optimization_plan'),
    ]
