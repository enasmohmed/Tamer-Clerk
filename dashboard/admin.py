# ترتيب التسجيل = ترتيب الظهور في الأدمن (اتبعي 1 → 2 → … → 8 لإنشاء كارد المستودع)

from django.contrib import admin
from .models import (
    Status,
    BusinessUnit,
    BusinessSystem,
    Activity,
    Warehouse,
    WarehouseBusinessSystem,
    WarehouseEmployeeSummary,
    WarehousePhaseStatus,
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


# ─── جدول تحت كاردز Warehouses Overview (WH | Emp No | Full Name | Business | Business 2) ───
@admin.register(WHDataRow)
class WHDataRowAdmin(admin.ModelAdmin):
    list_display = ("wh", "emp_no", "full_name", "business", "business_2", "display_order")
    list_editable = ("display_order",)
    list_filter = ("business", "business_2")
    search_fields = ("wh", "emp_no", "full_name")


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
