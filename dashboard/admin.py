# ترتيب التسجيل = ترتيب الظهور في الأدمن (اتبعي 1 → 2 → … → 8 لإنشاء كارد المستودع)

from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django.contrib import messages
from .models import (
    Status,
    BusinessUnit,
    BusinessSystem,
    Activity,
    Warehouse,
    WarehouseBusinessSystem,
    WarehouseEmployeeSummary,
    WarehousePhaseStatus,
    PhaseSection,
    PhasePoint,
    WHDataRow,
    Region,
    WarehouseMetric,
    DashboardTheme,
    MeetingPoint,
)


# ─── 1. الحالات (للمستودع وللمراحل) ───
@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color_hex", "is_warehouse_status", "is_phase_status", "display_order")
    list_editable = ("color_hex", "is_warehouse_status", "is_phase_status", "display_order")
    list_filter = ("is_warehouse_status", "is_phase_status")


# ─── 2. وحدات الأعمال ───
@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)


# ─── 3. أنظمة الأعمال ───
@admin.register(BusinessSystem)
class BusinessSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "business_unit", "display_order")
    list_editable = ("display_order",)
    list_filter = ("business_unit",)


# ─── 4. النشاطات ───
@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)


# ─── 5. المستودعات ───
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "phase1_pct", "phase2_pct", "display_order")
    list_editable = ("display_order", "phase1_pct", "phase2_pct")
    list_filter = ("status",)


# ─── 6. ربط المستودع بوحدة أعمال + نظام (جدول Business | System | الحالة داخل الكارد) ───
@admin.register(WarehouseBusinessSystem)
class WarehouseBusinessSystemAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "business_unit", "system", "system_name_override", "system_status", "display_order")
    list_editable = ("system_name_override", "system_status", "display_order")
    list_filter = ("warehouse", "business_unit", "system_status")


# ─── 7. ملخص الموظفين للمستودع ───
@admin.register(WarehouseEmployeeSummary)
class WarehouseEmployeeSummaryAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "allocated_count", "pending_or_edit_count", "phase_label", "phase_status_label")
    list_editable = ("allocated_count", "pending_or_edit_count", "phase_label", "phase_status_label")


# ─── 8. حالة المرحلة (جدول Phase Status داخل الكارد) ───
@admin.register(WarehousePhaseStatus)
class WarehousePhaseStatusAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "business_unit", "activity", "status", "start_date", "end_date")
    list_editable = ("status", "start_date", "end_date")
    list_filter = ("warehouse", "business_unit", "activity", "status")


# ─── 8-bis. سكشن Phases (عنوان + نقاط) ───
class PhasePointInline(admin.TabularInline):
    model = PhasePoint
    extra = 1


@admin.register(PhaseSection)
class PhaseSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    inlines = [PhasePointInline]


# ─── جدول تحت كاردز Warehouses Overview (WH | Emp No | Full Name | Business | Business 2) ───
@admin.register(WHDataRow)
class WHDataRowAdmin(admin.ModelAdmin):
    list_display = ("wh", "emp_no", "full_name", "business", "business_2", "display_order")
    list_editable = ("display_order",)
    list_filter = ("business", "business_2")
    search_fields = ("wh", "emp_no", "full_name")
    change_list_template = "admin/dashboard/whdatarow/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_whdatarow_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import WHDataRowExcelUploadForm
        from .wh_data_import import import_wh_data_rows_from_excel

        if request.method == "POST":
            form = WHDataRowExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "part_2"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"تم حذف {deleted} صف قديم.")
                created_count, err_list = import_wh_data_rows_from_excel(excel_file, sheet_name=sheet_name)
                if created_count > 0:
                    messages.success(
                        request,
                        f"تم استيراد {created_count} صف بنجاح.",
                    )
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... و {len(err_list) - 10} رسالة أخرى.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_whdatarow_changelist")
        else:
            form = WHDataRowExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "استيراد WH Data Rows من Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/whdatarow/import_excel.html", context)


# ─── نماذج إضافية (جداول Region / Warehouse في الداشبورد، الثيم، نقاط الاجتماع) ───
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "skus", "available", "utilization_pct", "display_order")
    list_editable = ("skus", "available", "utilization_pct", "display_order")


@admin.register(WarehouseMetric)
class WarehouseMetricAdmin(admin.ModelAdmin):
    list_display = ("name", "warehouse", "skus", "available_space", "utilization_pct", "display_order")
    list_editable = ("skus", "available_space", "utilization_pct", "display_order")
    list_filter = ("warehouse",)


@admin.register(DashboardTheme)
class DashboardThemeAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description")
    list_editable = ("value", "description")
    search_fields = ("key", "description")


@admin.register(MeetingPoint)
class MeetingPointAdmin(admin.ModelAdmin):
    list_display = ("description", "is_done", "created_at", "target_date")
    list_editable = ("is_done", "target_date",)
    list_filter = ("is_done", "created_at", "target_date")
    search_fields = ("description",)
    ordering = ("-created_at", "target_date", "assigned_to")
    fields = ("description", "is_done", "created_at", "target_date", "assigned_to")
