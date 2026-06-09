# Registration order = display order in admin (follow 1 → 2 → … → 8 to create warehouse card)

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.shortcuts import redirect, render
from django.urls import path
from django.contrib import messages
from django.utils.safestring import mark_safe
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
    ClerkInterviewTracking,
    ClerkDetail,
    Region,
    WarehouseMetric,
    DashboardTheme,
    ExecutiveOverviewKpiCard,
    MeetingPoint,
    Recommendation,
    PortfolioRaidItem,
    ProjectProcessStep,
    ProjectRegisterRemark,
    WorkspaceDepartment,
    WorkspaceProjectCategory,
    WorkspaceStrategicAlignment,
    TransformationWorkspaceProject,
    TransformationWorkspaceRaid,
    WeeklyProjectTrackerRow,
    PotentialChallenge,
    ProgressStatus,
)


# ─── 1. Status (For Warehouse and Phases) ───
@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ("name", "color_hex", "is_warehouse_status", "is_phase_status", "display_order")
    list_editable = ("color_hex", "is_warehouse_status", "is_phase_status", "display_order")
    list_filter = ("is_warehouse_status", "is_phase_status")


# ─── 2. Business Units ───
@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)


# ─── 3. Business Systems ───
@admin.register(BusinessSystem)
class BusinessSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "business_unit", "display_order")
    list_editable = ("display_order",)
    list_filter = ("business_unit",)


# ─── 4. Activities ───
@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    list_editable = ("display_order",)


# ─── 5. Warehouses ───
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "phase1_pct", "phase2_pct", "display_order")
    list_editable = ("display_order", "phase1_pct", "phase2_pct")
    list_filter = ("status",)


# ─── 6. Warehouse Business System Link (Business | System | Status table in card) ───
@admin.register(WarehouseBusinessSystem)
class WarehouseBusinessSystemAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "business_unit", "system", "system_name_override", "system_status", "display_order")
    list_editable = ("system_name_override", "system_status", "display_order")
    list_filter = ("warehouse", "business_unit", "system_status")


# ─── 7. Warehouse Employee Summary ───
@admin.register(WarehouseEmployeeSummary)
class WarehouseEmployeeSummaryAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "allocated_count", "pending_or_edit_count", "phase_label", "phase_status_label")
    list_editable = ("allocated_count", "pending_or_edit_count", "phase_label", "phase_status_label")


# ─── 8. Phase Status (Phase Status table in card) ───
@admin.register(WarehousePhaseStatus)
class WarehousePhaseStatusAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "business_unit", "activity", "status", "start_date", "end_date")
    list_editable = ("status", "start_date", "end_date")
    list_filter = ("warehouse", "business_unit", "activity", "status")


# ─── Phase Section (Title + Points) ───
class PhasePointInline(admin.TabularInline):
    model = PhasePoint
    extra = 1


@admin.register(PhaseSection)
class PhaseSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "days_number", "days_label", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    inlines = [PhasePointInline]
    fieldsets = (
        (None, {"fields": ("title", "display_order", "is_active")}),
        ("Ribbon (30, 60, 90 DAYS)", {"fields": ("days_number", "days_label")}),
    )


# ─── Clerk Interview Tracking (Project Overview table) ───
@admin.register(ClerkInterviewTracking)
class ClerkInterviewTrackingAdmin(admin.ModelAdmin):
    list_display = (
        "wh", "clerk_name", "nationality", "optimization_status",
        "system_used", "business", "remark", "display_order",
    )
    list_editable = ("display_order",)
    list_filter = ("wh", "business", "optimization_status")
    search_fields = ("wh", "clerk_name", "nationality", "business", "remark")
    change_list_template = "admin/dashboard/clerkinterviewtracking/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_clerkinterviewtracking_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import ClerkInterviewTrackingExcelUploadForm
        from .clerk_interview_import import import_clerk_interview_from_excel

        if request.method == "POST":
            form = ClerkInterviewTrackingExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "Sheet1"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"Deleted {deleted} old rows.")
                created_count, err_list = import_clerk_interview_from_excel(excel_file, sheet_name=sheet_name)
                if created_count > 0:
                    messages.success(
                        request,
                        f"Successfully imported {created_count} rows.",
                    )
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... and {len(err_list) - 10} more messages.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_clerkinterviewtracking_changelist")
        else:
            form = ClerkInterviewTrackingExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import Clerk Interview Tracking from Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/clerkinterviewtracking/import_excel.html", context)


# ─── Clerk Details (Employee Interview Profiles) - Clerk_details.xlsx, sheet interview ───
@admin.register(ClerkDetail)
class ClerkDetailAdmin(admin.ModelAdmin):
    list_display = (
        "dept_name_en", "department", "company", "business", "account",
        "mobile", "interview_date", "system_badge", "display_order",
    )
    list_editable = ("display_order",)
    list_filter = ("department", "company", "business")
    search_fields = ("dept_name_en", "department", "company", "business", "account", "work_details")
    change_list_template = "admin/dashboard/clerkdetail/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_clerkdetail_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import ClerkDetailsExcelUploadForm
        from .clerk_details_import import import_clerk_details_from_excel

        if request.method == "POST":
            form = ClerkDetailsExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "interview"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"Deleted {deleted} old rows.")
                created_count, err_list = import_clerk_details_from_excel(excel_file, sheet_name=sheet_name)
                if created_count > 0:
                    messages.success(
                        request,
                        f"Successfully imported {created_count} rows.",
                    )
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... and {len(err_list) - 10} more messages.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_clerkdetail_changelist")
        else:
            form = ClerkDetailsExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import Clerk Details from Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/clerkdetail/import_excel.html", context)


# ─── Additional Models (Region / Warehouse tables in dashboard, Theme, Meeting Points) ───
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
    list_display = ("key", "value", "color_preview", "description", "category")
    list_editable = ("value",)
    list_filter = ("category",)
    search_fields = ("key", "description")
    ordering = ("category", "key")
    change_list_template = "admin/dashboard/dashboardtheme/change_list.html"
    
    def color_preview(self, obj):
        if obj.value and obj.value.startswith("#"):
            return f'<div style="width:30px;height:20px;background:{obj.value};border:1px solid #ccc;border-radius:3px;"></div>'
        return "—"
    color_preview.short_description = "Preview"
    color_preview.allow_tags = True
    
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "initialize-defaults/",
                self.admin_site.admin_view(self.initialize_defaults_view),
                name="dashboard_dashboardtheme_initialize",
            ),
            path(
                "reset-defaults/",
                self.admin_site.admin_view(self.reset_defaults_view),
                name="dashboard_dashboardtheme_reset",
            ),
        ]
        return custom + urls
    
    def initialize_defaults_view(self, request):
        from .models import DashboardTheme
        created_count, updated_count = DashboardTheme.initialize_defaults(reset_all=False)
        if created_count > 0:
            messages.success(request, f"Added {created_count} new theme colors.")
        else:
            messages.info(request, "All theme colors already exist. Use 'Reset to Defaults' to update them.")
        return redirect("admin:dashboard_dashboardtheme_changelist")
    
    def reset_defaults_view(self, request):
        from .models import DashboardTheme
        created_count, updated_count = DashboardTheme.initialize_defaults(reset_all=True)
        messages.success(request, f"Reset complete! Created: {created_count}, Updated: {updated_count} colors to new Green+Teal palette.")
        return redirect("admin:dashboard_dashboardtheme_changelist")


@admin.register(ExecutiveOverviewKpiCard)
class ExecutiveOverviewKpiCardAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "value_text", "accent", "is_active", "display_order")
    list_editable = ("value_text", "accent", "is_active", "display_order")
    search_fields = ("title", "key")
    ordering = ("display_order", "id")


@admin.register(MeetingPoint)
class MeetingPointAdmin(admin.ModelAdmin):
    list_display = ("description", "is_done", "created_at", "target_date")
    list_editable = ("is_done", "target_date",)
    list_filter = ("is_done", "created_at", "target_date")
    search_fields = ("description",)
    ordering = ("-created_at", "target_date", "assigned_to")
    fields = ("description", "is_done", "created_at", "target_date", "assigned_to")


# ─── Recommendations ───
@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("title", "business", "user_name", "icon_type", "display_order", "is_active")
    list_editable = ("icon_type", "display_order", "is_active")
    list_filter = ("is_active", "icon_type", "business")
    search_fields = ("title", "description", "business", "user_name")
    ordering = ("business", "user_name", "display_order", "id")
    fieldsets = (
        (None, {
            "fields": ("business", "user_name", "title", "description"),
            "description": "Business + User name group this recommendation into a card (e.g. 3PL FMCG, Allaa)."
        }),
        ("Icon Settings", {
            "fields": ("icon_type", "custom_icon", "icon_bg_color"),
        }),
        ("Settings", {
            "fields": ("display_order", "is_active")
        }),
    )


# ─── Weekly Project Tracker (Progress Overview tab) ───
@admin.register(WeeklyProjectTrackerRow)
class WeeklyProjectTrackerRowAdmin(admin.ModelAdmin):
    list_display = ("week", "task_short", "status", "progress_pct", "impact_short", "display_order")
    list_editable = ("display_order",)
    list_filter = ("status",)
    search_fields = ("week", "task", "impact")
    change_list_template = "admin/dashboard/weeklyprojecttrackerrow/change_list.html"

    def task_short(self, obj):
        return (obj.task[:60] + "…") if obj.task and len(obj.task) > 60 else (obj.task or "—")

    task_short.short_description = "Task"

    def impact_short(self, obj):
        return (obj.impact[:40] + "…") if obj.impact and len(obj.impact) > 40 else (obj.impact or "—")

    impact_short.short_description = "Impact"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_weeklyprojecttrackerrow_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import WeeklyProjectTrackerExcelUploadForm
        from .weekly_tracker_import import import_weekly_tracker_from_excel

        if request.method == "POST":
            form = WeeklyProjectTrackerExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "Weekly Tracker"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"Deleted {deleted} old rows.")
                created_count, err_list = import_weekly_tracker_from_excel(
                    excel_file, sheet_name=sheet_name
                )
                if created_count > 0:
                    messages.success(
                        request,
                        f"Successfully imported {created_count} rows.",
                    )
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... and {len(err_list) - 10} more messages.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_weeklyprojecttrackerrow_changelist")
        else:
            form = WeeklyProjectTrackerExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import Weekly Project Tracker from Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/weeklyprojecttrackerrow/import_excel.html", context)


# ─── Progress Status (PROGRESS STATUS table: Clerk, Account, Remark, Status) ───
@admin.register(ProgressStatus)
class ProgressStatusAdmin(admin.ModelAdmin):
    list_display = ("clerk", "account", "remark_short", "status", "display_order")
    list_editable = ("display_order",)
    list_filter = ("status",)
    search_fields = ("clerk", "account", "remark")
    change_list_template = "admin/dashboard/progressstatus/change_list.html"

    def remark_short(self, obj):
        return (obj.remark[:50] + "…") if obj.remark and len(obj.remark) > 50 else (obj.remark or "—")
    remark_short.short_description = "Remark"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_progressstatus_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import ProgressStatusExcelUploadForm
        from .progress_status_import import import_progress_status_from_excel

        if request.method == "POST":
            form = ProgressStatusExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "Sheet1"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"Deleted {deleted} old rows.")
                created_count, err_list = import_progress_status_from_excel(
                    excel_file, sheet_name=sheet_name
                )
                if created_count > 0:
                    messages.success(request, f"Successfully imported {created_count} rows.")
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... and {len(err_list) - 10} more messages.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_progressstatus_changelist")
        else:
            form = ProgressStatusExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import Progress Status from Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/progressstatus/import_excel.html", context)


# ─── Potential Challenges ───
@admin.register(PotentialChallenge)
class PotentialChallengeAdmin(admin.ModelAdmin):
    list_display = ("date", "challenges_short", "status", "progress_pct", "solutions_short", "display_order")
    list_editable = ("display_order",)
    list_filter = ("status",)
    search_fields = ("date", "challenges", "solutions")
    change_list_template = "admin/dashboard/potentialchallenge/change_list.html"

    def challenges_short(self, obj):
        return (obj.challenges[:50] + "…") if obj.challenges and len(obj.challenges) > 50 else (obj.challenges or "—")

    def solutions_short(self, obj):
        return (obj.solutions[:40] + "…") if obj.solutions and len(obj.solutions) > 40 else (obj.solutions or "—")

    challenges_short.short_description = "Challenges"
    solutions_short.short_description = "Solutions"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="dashboard_potentialchallenge_import_excel",
            ),
        ]
        return custom + urls

    def import_excel_view(self, request):
        from .forms import PotentialChallengesExcelUploadForm
        from .potential_challenges_import import import_potential_challenges_from_excel

        if request.method == "POST":
            form = PotentialChallengesExcelUploadForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                sheet_name = (form.cleaned_data.get("sheet_name") or "").strip() or "Potential_Challenges"
                clear_before = form.cleaned_data.get("clear_before_import")
                if clear_before:
                    deleted, _ = self.model.objects.all().delete()
                    messages.info(request, f"Deleted {deleted} old rows.")
                created_count, err_list = import_potential_challenges_from_excel(
                    excel_file, sheet_name=sheet_name
                )
                if created_count > 0:
                    messages.success(request, f"Successfully imported {created_count} rows.")
                if err_list:
                    for err in err_list[:10]:
                        messages.warning(request, err)
                    if len(err_list) > 10:
                        messages.warning(request, f"... and {len(err_list) - 10} more messages.")
                if created_count > 0 or not err_list:
                    return redirect("admin:dashboard_potentialchallenge_changelist")
        else:
            form = PotentialChallengesExcelUploadForm()
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import Potential Challenges from Excel",
            "opts": self.model._meta,
        }
        return render(request, "admin/dashboard/potentialchallenge/import_excel.html", context)


# ─── Transformation Workspace — لوحة منفصلة (كاردات أول التاب + السجل + RAID) ───
# أي موديل جديد يخص هذه الشاشة يُسجَّل هنا مع بادئة "03 — …" في verbose_name_plural.
# النماذج الفعلية في قاعدة البيانات هي ProjectTrackerItem و PortfolioRaidItem؛
# الـ proxy للعرض فقط في الأدمن بأسماء توضيحية.


@admin.register(WorkspaceDepartment)
class WorkspaceDepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    ordering = ("display_order", "name")


@admin.register(WorkspaceProjectCategory)
class WorkspaceProjectCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    ordering = ("display_order", "name")


@admin.register(WorkspaceStrategicAlignment)
class WorkspaceStrategicAlignmentAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    ordering = ("display_order", "name")


class ProjectProcessStepInline(admin.TabularInline):
    model = ProjectProcessStep
    extra = 0
    fields = ("description", "step_deadline", "owner_name", "status", "business_benefits", "display_order")


class PortfolioRaidItemInline(admin.TabularInline):
    model = PortfolioRaidItem
    extra = 1
    fields = ("category", "title", "status", "severity", "owner_name", "display_order")


class ProjectRegisterRemarkInline(admin.TabularInline):
    model = ProjectRegisterRemark
    extra = 1
    fields = ("text", "display_order")


@admin.register(TransformationWorkspaceProject)
class TransformationWorkspaceProjectAdmin(admin.ModelAdmin):
    """بيانات المشاريع التي تغذّي الكاردات العلوية (Active / Delayed / SPI / CPI / PMO) وجدول السجل."""

    change_list_template = "admin/dashboard/transformation_workspace/project_changelist.html"
    readonly_fields = ("is_approved",)

    fieldsets = (
        (
            "01 — Project identity",
            {
                "fields": (
                    "description",
                    "project_code",
                    "project_lead",
                    "person_name",
                    "company",
                    "department_ref",
                    "department",
                    "register_priority",
                    "register_status",
                    "is_approved",
                    "register_category",
                    "project_type",
                    "start_date",
                    "end_date",
                    "display_order",
                )
            },
        ),
        (
            "02 — Business case & impact",
            {
                "fields": (
                    "objective_sow",
                    "business_benefits",
                    "strategic_alignment_ref",
                    "kpi_success_criteria",
                    "cost_reduction_pct",
                    "headcount_impact",
                    "sla_improvement",
                    "scope_in",
                    "scope_out",
                    "scope_deliverables",
                    "scope_dependencies",
                )
            },
        ),
        (
            "03 — Governance & approvals",
            {
                "fields": (
                    "pmo_register_published",
                    "gov_submitted_by",
                    "gov_reviewed_by",
                    "gov_approval_status",
                    "gov_stakeholders",
                    "gov_operational_impact",
                    "gov_assumptions_constraints",
                )
            },
        ),
        (
            "Phases (KPI progress)",
            {
                "fields": (
                    "brainstorming_status",
                    "execution_status",
                    "test_deadline_status",
                    "launch_status",
                    "planned_hours",
                    "actual_hours",
                    "last_status_update",
                )
            },
        ),
        ("Notes", {"fields": ("register_risk_level", "remarks")}),
    )

    list_display = (
        "description",
        "project_code",
        "project_lead",
        "person_name",
        "department_ref",
        "register_priority",
        "register_status",
        "is_approved",
        "pmo_register_published",
        "project_type",
        "start_date",
        "brainstorming_badge",
        "launch_badge",
        "test_deadline_status",
        "end_date",
        "planned_hours",
        "actual_hours",
        "last_status_update",
        "display_order",
    )
    list_editable = (
        "register_priority",
        "register_status",
        "pmo_register_published",
        "test_deadline_status",
        "end_date",
        "planned_hours",
        "actual_hours",
        "last_status_update",
        "display_order",
    )
    list_filter = (
        "pmo_register_published",
        "project_type",
        "brainstorming_status",
        "execution_status",
        "launch_status",
        "test_deadline_status",
        "start_date",
    )
    date_hierarchy = "start_date"
    search_fields = ("description", "person_name", "company", "department")
    ordering = ("-created_at", "-id")
    list_per_page = 25
    inlines = [ProjectProcessStepInline, PortfolioRaidItemInline, ProjectRegisterRemarkInline]

    def brainstorming_badge(self, obj):
        return obj.get_brainstorming_status_display() or "—"

    brainstorming_badge.short_description = "Brainstorming"

    def execution_badge(self, obj):
        return obj.get_execution_status_display() or "—"

    execution_badge.short_description = "Development"

    def launch_badge(self, obj):
        return obj.get_launch_status_display() or "—"

    launch_badge.short_description = "Launch"

    def test_deadline_badge(self, obj):
        return obj.get_test_deadline_status_display() or "—"

    test_deadline_badge.short_description = "Test"

    def save_model(self, request, obj, form, change):
        # Projects maintained in Admin are portfolio source-of-truth — show in register & KPIs.
        obj.pmo_register_published = True
        super().save_model(request, obj, form, change)


@admin.register(TransformationWorkspaceRaid)
class TransformationWorkspaceRaidAdmin(admin.ModelAdmin):
    """عناصر RAID المفتوحة/المعلقة تُحسب في كارد Open RAID Items (ومع Critical في التذييل)."""

    change_list_template = "admin/dashboard/transformation_workspace/raid_changelist.html"

    list_display = ("title", "project", "category", "status", "severity", "owner_name", "display_order")
    list_editable = ("display_order",)
    list_filter = ("category", "status", "severity")
    search_fields = ("title", "project__description")
    ordering = ("project", "display_order", "id")


# ─── سجل التعديلات (مين دخل إيه ومتى من الأدمن) ───
@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("action_time", "user", "content_type", "object_repr_short", "action_flag_badge", "change_message")
    list_filter = ("action_flag", "content_type", "action_time")
    search_fields = ("user__username", "object_repr", "change_message")
    date_hierarchy = "action_time"
    ordering = ("-action_time",)
    list_per_page = 50
    readonly_fields = ("action_time", "user", "content_type", "object_id", "object_repr", "action_flag", "change_message")

    def object_repr_short(self, obj):
        return (obj.object_repr[:60] + "…") if obj.object_repr and len(obj.object_repr) > 60 else (obj.object_repr or "—")

    object_repr_short.short_description = "العنصر"

    def action_flag_badge(self, obj):
        if obj.action_flag == 1:
            return "إضافة"
        if obj.action_flag == 2:
            return "تعديل"
        if obj.action_flag == 3:
            return "حذف"
        return "—"

    action_flag_badge.short_description = "الإجراء"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
