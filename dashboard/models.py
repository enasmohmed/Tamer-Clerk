
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── Dashboard Theme Settings (Editable from Admin) ───
THEME_CATEGORY_CHOICES = [
    ("tabs", "Tabs Colors"),
    ("table", "Data Table Colors"),
    ("phases", "Phases Section Colors"),
    ("cards", "Warehouse Cards Colors"),
    ("general", "General Colors"),
]

# Default theme colors with their keys, default values, descriptions, and categories
# Harmonious Green + Teal palette (No orange, No purple)
DEFAULT_THEME_COLORS = [
    # Tabs Colors
    ("tab_active_bg", "#1a5f2a", "Active tab background color", "tabs"),
    ("tab_active_text", "#ffffff", "Active tab text color", "tabs"),
    ("tab_inactive_bg", "#ffffff", "Inactive tab background color", "tabs"),
    ("tab_inactive_text", "#1a5f2a", "Inactive tab text color", "tabs"),
    ("tab_border_color", "#1a5f2a", "Tab border color", "tabs"),
    ("tab_hover_bg", "#d1fae5", "Tab hover background color (Mint)", "tabs"),
    
    # Data Table Colors (Green gradient header)
    ("table_header_bg", "#1a5f2a", "Table header background (gradient start)", "table"),
    ("table_header_bg_end", "#15803d", "Table header background (gradient end)", "table"),
    ("table_header_text", "#ffffff", "Table header text color", "table"),
    ("table_row_hover", "#f1f5f9", "Table row hover background", "table"),
    ("table_border", "#e2e8f0", "Table border color", "table"),
    ("table_emp_no_color", "#0d9488", "Employee number text color (Teal)", "table"),
    ("table_business_badge_bg", "#ccfbf1", "Business badge background (Light Teal)", "table"),
    ("table_business_badge_text", "#0d9488", "Business badge text color (Teal)", "table"),
    ("table_business2_badge_bg", "#d1fae5", "Business 2 badge background (Mint)", "table"),
    ("table_business2_badge_text", "#15803d", "Business 2 badge text color (Forest Green)", "table"),
    ("table_title_icon_bg", "#0d9488", "Table title icon background (gradient start - Teal)", "table"),
    ("table_title_icon_bg_end", "#14b8a6", "Table title icon background (gradient end - Teal Light)", "table"),
    ("table_stat_badge_bg", "#d1fae5", "Stats badge background (Mint)", "table"),
    ("table_stat_badge_text", "#15803d", "Stats badge text color (Forest Green)", "table"),
    
    # Phases Section Colors (Teal icons)
    ("phase_icon_bg", "#0d9488", "Phase icon background (gradient start - Teal)", "phases"),
    ("phase_icon_bg_end", "#14b8a6", "Phase icon background (gradient end - Teal Light)", "phases"),
    ("phase_icon_text", "#ffffff", "Phase icon text color", "phases"),
    ("phase_card_bg", "#ffffff", "Phase card background", "phases"),
    ("phase_card_border", "#e2e8f0", "Phase card border color", "phases"),
    ("phase_count_badge_bg", "#ccfbf1", "Phase count badge background (Light Teal)", "phases"),
    ("phase_count_badge_text", "#0d9488", "Phase count badge text color (Teal)", "phases"),
    ("phase_bullet_color", "#0d9488", "Phase bullet point color (Teal)", "phases"),
    ("phase_point_bg", "#f1f5f9", "Phase point background", "phases"),
    
    # Warehouse Cards Colors (All green shades)
    ("card_bg", "#ffffff", "Warehouse card background", "cards"),
    ("card_border", "#e2e8f0", "Warehouse card border", "cards"),
    ("card_header_bg", "#f8fafc", "Card header background", "cards"),
    ("card_table_header_bg", "#1a5f2a", "Card table header background (Emerald)", "cards"),
    ("status_active_color", "#15803d", "Active status color (Forest Green)", "cards"),
    ("status_pending_color", "#0d9488", "Pending status color (Teal)", "cards"),
    ("status_completed_color", "#15803d", "Completed status color (Forest Green)", "cards"),
    ("donut_chart_color", "#1a5f2a", "Donut chart main color (Emerald)", "cards"),
    ("donut_chart_pending", "#0d9488", "Donut chart pending color (Teal)", "cards"),
    ("progress_bar_color", "#1a5f2a", "Progress bar fill color (Emerald)", "cards"),
    
    # General Colors (Harmonious Green + Teal)
    ("primary_color", "#1a5f2a", "Primary brand color (Emerald)", "general"),
    ("secondary_color", "#0d9488", "Secondary accent color (Teal)", "general"),
    ("success_color", "#15803d", "Success color (Forest Green)", "general"),
    ("warning_color", "#0d9488", "Warning/Pending color (Teal)", "general"),
    ("danger_color", "#dc2626", "Danger color (Red)", "general"),
    ("text_primary", "#1e293b", "Primary text color", "general"),
    ("text_secondary", "#475569", "Secondary text color", "general"),
    ("text_muted", "#64748b", "Muted text color", "general"),
    ("bg_light", "#f1f5f9", "Light background color", "general"),
    ("border_color", "#e2e8f0", "Default border color", "general"),
]


class DashboardTheme(models.Model):
    """Key/value for dashboard colors and settings."""
    key = models.CharField(max_length=100, unique=True, help_text="Color key (e.g. tab_active_bg)")
    value = models.CharField(max_length=200, blank=True, help_text="Color value (e.g. #4C8FD6)")
    description = models.CharField(max_length=255, blank=True, help_text="Description of what this color controls")
    category = models.CharField(
        max_length=20,
        choices=THEME_CATEGORY_CHOICES,
        default="general",
        help_text="Color category for organization"
    )

    class Meta:
        verbose_name = "Dashboard Theme Color"
        verbose_name_plural = "Dashboard Theme Colors"
        ordering = ["category", "key"]

    def __str__(self):
        return f"{self.key} = {self.value or '(empty)'}"
    
    @classmethod
    def initialize_defaults(cls, reset_all=False):
        """
        Create default theme colors if they don't exist.
        If reset_all=True, also update existing colors to their default values.
        """
        created_count = 0
        updated_count = 0
        for key, value, description, category in DEFAULT_THEME_COLORS:
            if reset_all:
                # Update or create - will reset existing values to defaults
                obj, created = cls.objects.update_or_create(
                    key=key,
                    defaults={
                        "value": value,
                        "description": description,
                        "category": category,
                    }
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                obj, created = cls.objects.get_or_create(
                    key=key,
                    defaults={
                        "value": value,
                        "description": description,
                        "category": category,
                    }
                )
                if created:
                    created_count += 1
        return created_count, updated_count


# ─── 1. Status (For Warehouse and Phases) ───
class Status(models.Model):
    """General status with color (for warehouse or phase activity)."""
    name = models.CharField(max_length=80)
    color_hex = models.CharField(max_length=20, default="#6c757d", help_text="e.g. #2e7d32 for green")
    is_warehouse_status = models.BooleanField(default=True, help_text="Used as warehouse status")
    is_phase_status = models.BooleanField(default=False, help_text="Used as phase status (Completed, Pending, ...)")
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Display order: smaller appears first (0, 1, 2...)")

    class Meta:
        verbose_name = "1. Status"
        verbose_name_plural = "1. Statuses"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── 2. Business Unit (Pharma, FMCG, Retail) ───
class BusinessUnit(models.Model):
    name = models.CharField(max_length=80)
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Display order: smaller appears first")

    class Meta:
        verbose_name = "2. Business Unit"
        verbose_name_plural = "2. Business Units"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── 3. Business System (LogFire, SAP, WMS-X, ...) ───
class BusinessSystem(models.Model):
    name = models.CharField(max_length=120)
    business_unit = models.ForeignKey(
        BusinessUnit, on_delete=models.CASCADE, related_name="systems", null=True, blank=True
    )
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Display order: smaller appears first")

    class Meta:
        verbose_name = "3. Business System"
        verbose_name_plural = "3. Business Systems"
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name}" + (f" ({self.business_unit.name})" if self.business_unit else "")


# ─── 4. Activity (Inbound, Outbound, Pending, Allocated, Not Started) ───
class Activity(models.Model):
    name = models.CharField(max_length=80)
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Display order: smaller appears first")

    class Meta:
        verbose_name = "4. Activity"
        verbose_name_plural = "4. Activities"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── 5. Warehouse (Jeddah, Riyadh, Dammam, Abha) ───
class Warehouse(models.Model):
    name = models.CharField(max_length=120)
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, blank=True, related_name="warehouses"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Card display order: 1 appears first, 2 second, etc."
    )
    phase1_pct = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Phase 1 completion percentage (0-100). Leave blank if not used.",
    )
    phase2_pct = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Phase 2 completion percentage (0-100). Leave blank if not used.",
    )

    class Meta:
        verbose_name = "5. Warehouse"
        verbose_name_plural = "5. Warehouses"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── System Status Choices (Next to System in card) ───
SYSTEM_STATUS_PENDING_PH1 = "pending_ph1"
SYSTEM_STATUS_PH1_COMPLETED = "ph1_completed"
SYSTEM_STATUS_PENDING_PH2 = "pending_ph2"
SYSTEM_STATUS_PH2_COMPLETED = "ph2_completed"
SYSTEM_STATUS_CHOICES = [
    ("", "—"),
    (SYSTEM_STATUS_PENDING_PH1, "Pending PH1"),
    (SYSTEM_STATUS_PH1_COMPLETED, "PH1 completed"),
    (SYSTEM_STATUS_PENDING_PH2, "Pending PH2"),
    (SYSTEM_STATUS_PH2_COMPLETED, "PH2 completed"),
]

# ─── Warehouse Business System Link (Business | System | Status table in warehouse card) ───
class WarehouseBusinessSystem(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="business_systems")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.CASCADE, related_name="warehouse_links")
    system = models.ForeignKey(
        BusinessSystem, on_delete=models.CASCADE, related_name="warehouse_links", null=True, blank=True
    )
    system_name_override = models.CharField(max_length=120, blank=True, help_text="If left blank, system name will be used")
    system_status = models.CharField(
        max_length=20,
        choices=SYSTEM_STATUS_CHOICES,
        blank=True,
        help_text="System status: Pending PH1 / PH1 completed / Pending PH2 / PH2 completed",
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "6. Warehouse Business System"
        verbose_name_plural = "6. Warehouse Business Systems"
        ordering = ["warehouse", "display_order"]
        unique_together = [["warehouse", "business_unit"]]

    def __str__(self):
        sys_name = self.system_name_override or (self.system.name if self.system else "")
        return f"{self.warehouse.name} — {self.business_unit.name}: {sys_name}"


# ─── Phase Status for each (Warehouse + Business Unit + Activity) with optional dates ───
class WarehousePhaseStatus(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="phase_statuses")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.CASCADE, related_name="phase_statuses")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="phase_statuses")
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, blank=True, related_name="phase_statuses"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "8. Warehouse Phase Status"
        verbose_name_plural = "8. Warehouse Phase Statuses"
        ordering = ["warehouse", "display_order", "business_unit", "activity"]

    def __str__(self):
        return f"{self.warehouse.name} / {self.business_unit.name} / {self.activity.name}"


# ─── Phase Section (Title + Points) for section below cards ───
class PhaseSection(models.Model):
    """Section in Phases below warehouse cards (e.g. 30 DAYS, 60 DAYS, 90 DAYS)."""
    title = models.CharField(
        max_length=200,
        blank=True,
        null = True,
        help_text="Optional phase title (e.g. Phase 1 details). Used as fallback if Days number is empty.",
    )
    days_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number on the ribbon (e.g. 30, 60, 90). Enter from Admin.",
    )
    days_label = models.CharField(
        max_length=50,
        default="DAYS",
        blank=True,
        help_text="Label next to the number (e.g. DAYS).",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Section display order: smaller appears first."
    )
    is_active = models.BooleanField(default=True, help_text="If disabled, won't appear in the interface.")

    class Meta:
        verbose_name = "Phase Section"
        verbose_name_plural = "Phase Sections"
        ordering = ["display_order", "id"]

    def __str__(self):
        if self.days_number is not None:
            return f"{self.days_number} {self.days_label or 'DAYS'}"
        return self.title or "Phase Section"


class PhasePoint(models.Model):
    """Bullet point inside a Phase section."""
    section = models.ForeignKey(
        PhaseSection, on_delete=models.CASCADE, related_name="points", help_text="The phase this point belongs to."
    )
    text = models.CharField(max_length=255, help_text="Brief text for the point.")
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Point display order within the section."
    )

    class Meta:
        verbose_name = "Phase Point"
        verbose_name_plural = "Phase Points"
        ordering = ["section", "display_order", "id"]

    def __str__(self):
        return self.text[:80]


# ─── Warehouse Employee Summary (Allocated count, edit count, or text like Phase 1 Completed) ───
class WarehouseEmployeeSummary(models.Model):
    warehouse = models.OneToOneField(
        Warehouse, on_delete=models.CASCADE, related_name="employee_summary"
    )
    allocated_count = models.PositiveIntegerField(null=True, blank=True, help_text="Optional — leave blank if not needed")
    pending_or_edit_count = models.PositiveIntegerField(null=True, blank=True, help_text="Optional — number shown next to pen icon if exists")
    phase_label = models.CharField(max_length=120, blank=True, help_text="e.g. Phase 1")
    phase_status_label = models.CharField(max_length=120, blank=True, help_text="e.g. Completed")

    class Meta:
        verbose_name = "7. Warehouse Employee Summary"
        verbose_name_plural = "7. Warehouse Employee Summaries"

    def __str__(self):
        return f"{self.warehouse.name}: {self.allocated_count if self.allocated_count is not None else '—'} allocated"


# ─── Dashboard Tab → Returns Section: Region Table (Region | SKUs | Available | Utilization %) ───
class Region(models.Model):
    """Returns table data in dashboard. Columns: Region, SKUs, Available, Utilization %."""
    name = models.CharField(max_length=120)
    skus = models.CharField(max_length=80, blank=True)
    available = models.CharField(max_length=80, blank=True)
    utilization_pct = models.CharField(max_length=80, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Region"
        verbose_name_plural = "Regions"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── Dashboard Tab → Inventory Section: Warehouse Table (Warehouse | SKUs | Available Space | Utilization %) ───
class WarehouseMetric(models.Model):
    """Warehouse/Inventory table data in dashboard. Columns: Warehouse, SKUs, Available Space, Utilization %."""
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="metrics", null=True, blank=True
    )
    name = models.CharField(max_length=120, help_text="Display name if not linked to warehouse")
    skus = models.CharField(max_length=80, blank=True)
    available_space = models.CharField(max_length=80, blank=True)
    utilization_pct = models.CharField(max_length=80, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Warehouse Metric"
        verbose_name_plural = "Warehouse Metrics"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name or (self.warehouse.name if self.warehouse else "—")


# ─── Clerk Interview Tracking (Project Overview table) ───
class ClerkInterviewTracking(models.Model):
    """Clerk Interview Tracking: WH, Clerk Name, NATIONALITY, Report Used, Optimization Status, Strength, System Used, Business, Remark. Excel: CP_project.xlsx, Sheet1."""
    wh = models.CharField(max_length=120, blank=True, help_text="WH")
    clerk_name = models.CharField(max_length=200, blank=True, help_text="Clerk Name")
    nationality = models.CharField(max_length=120, blank=True, help_text="NATIONALITY")
    report_used = models.CharField(max_length=200, blank=True, help_text="Report Used")
    optimization_status = models.CharField(max_length=200, blank=True, help_text="Optimization Status")
    strength = models.CharField(max_length=200, blank=True, help_text="Strength")
    system_used = models.CharField(max_length=200, blank=True, help_text="System Used")
    business = models.CharField(max_length=200, blank=True, help_text="Business")
    remark = models.TextField(blank=True, help_text="Remark")
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Row order in table")

    class Meta:
        verbose_name = "Clerk Interview Tracking"
        verbose_name_plural = "Clerk Interview Tracking"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.clerk_name or '—'} ({self.wh or '—'})"


class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file.name} ({self.uploaded_at:%Y-%m-%d %H:%M})"




class UploadMonth(models.Model):
    month = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.month



class MeetingPoint(models.Model):
    description = models.TextField()
    is_done = models.BooleanField(default=False)
    created_at = models.DateField(default=timezone.now)
    target_date = models.DateField(null=True, blank=True)
    assigned_to = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.description[:50]


# ─── Recommendations for Recommendation Overview Tab ───
ICON_CHOICES = [
    ("check-circle", "Check Circle (Completed)"),
    ("scanner", "RF Scanner"),
    ("people", "People/Team"),
    ("document", "Document"),
    ("box", "Box/Package"),
    ("chart", "Chart/Analytics"),
    ("settings", "Settings"),
    ("lightbulb", "Lightbulb/Idea"),
    ("clock", "Clock/Time"),
    ("arrow-up", "Arrow Up/Improvement"),
    ("custom", "Custom Image"),
]


class Recommendation(models.Model):
    """Key recommendation displayed in Recommendation Overview tab. Grouped by business + user_name into cards."""
    user_name = models.CharField(max_length=120, blank=True, help_text="User who created this (e.g. Allaa, Hisham)")
    business = models.CharField(max_length=120, blank=True, help_text="Business type (e.g. 3PL FMCG, 3PL Healthcare)")
    title = models.CharField(max_length=200, blank=True, help_text="Recommendation title (optional)")
    description = models.TextField(help_text="Detailed recommendation description")
    icon_type = models.CharField(
        max_length=20,
        choices=ICON_CHOICES,
        default="check-circle",
        help_text="Icon type displayed next to the recommendation"
    )
    custom_icon = models.ImageField(
        upload_to="recommendation_icons/",
        null=True,
        blank=True,
        help_text="Custom icon image (only if you chose Custom Image)"
    )
    icon_bg_color = models.CharField(
        max_length=20,
        default="#f5f5f0",
        help_text="Icon background color (e.g. #f5f5f0)"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Recommendation display order: smaller appears first"
    )
    is_active = models.BooleanField(default=True, help_text="If disabled, won't appear in the interface")

    class Meta:
        verbose_name = "Recommendation"
        verbose_name_plural = "Recommendations"
        ordering = ["business", "user_name", "display_order", "id"]

    def __str__(self):
        return self.title[:80]


# ─── Project Tracker (تاب Project Tracker: شهر، شخص، تاريخ، ثلاث مراحل) ───
PROJECT_TRACKER_STATUS_CHOICES = [
    ("", "Not started"),
    ("done", "Done"),
    ("working_on_it", "Working on it"),
    ("stuck", "Stuck"),
]

PROJECT_TYPE_CHOICES = [
    ("idea", "Idea"),
    ("automation", "Automation"),
]


class ProjectTrackerItem(models.Model):
    """
    عنصر في تاب Project Tracker: وصف المشروع، الشخص، التاريخ، وحالة كل مرحلة
    (Brainstorming, Execution, Launch). كل الداتا تدخل من الأدمن والفلترة بالشهر والتاريخ والحالة.
    """
    description = models.CharField(
        max_length=300,
        help_text="Project task description (e.g. Finalize kickoff materials)"
    )
    person_name = models.CharField(
        max_length=120,
        help_text="Employee name (person responsible)"
    )
    project_type = models.CharField(
        max_length=20,
        choices=PROJECT_TYPE_CHOICES,
        default="idea",
        help_text="Project Type: Idea or Automation",
    )
    company = models.CharField(
        max_length=200,
        blank=True,
        help_text="Company name"
    )
    start_date = models.DateField(
        help_text="Project start date (used for month grouping and ordering)"
    )
    brainstorming_status = models.CharField(
        max_length=20,
        choices=PROJECT_TRACKER_STATUS_CHOICES,
        blank=True,
        default="",
        help_text="Brainstorming phase: Done / Working on it / Stuck"
    )
    execution_status = models.CharField(
        max_length=20,
        choices=PROJECT_TRACKER_STATUS_CHOICES,
        blank=True,
        default="",
        help_text="Execution phase: Done / Working on it / Stuck"
    )
    launch_status = models.CharField(
        max_length=20,
        choices=PROJECT_TRACKER_STATUS_CHOICES,
        blank=True,
        default="",
        help_text="Launch phase: Done / Working on it / Stuck"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Project end date (optional)"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Order within the same day (smaller = first)"
    )

    class Meta:
        verbose_name = "Project Tracker Item"
        verbose_name_plural = "Project Tracker Items"
        ordering = ["-start_date", "display_order", "id"]

    def __str__(self):
        return f"{self.description[:50]} ({self.start_date})"


# ─── Weekly Project Tracker (تاب Progress Overview: جدول تحت Key Recommendations) ───
WEEKLY_TRACKER_STATUS_CHOICES = [
    ("completed", "Completed"),
    ("in_progress", "In Progress"),
    ("not_started", "Not Started"),
]


class WeeklyProjectTrackerRow(models.Model):
    """
    صف في جدول Weekly Project Tracker داخل تاب Progress Overview (تحت Key Recommendations).
    يستورد من Excel: Weekly_Project_Tracker.xlsx، شيت "Weekly Tracker"
    الأعمدة: Week | Task | Status | Progress % | Impact
    """
    week = models.CharField(
        max_length=100,
        help_text="Week label e.g. Week 1 - Feb"
    )
    task = models.TextField(
        help_text="Task or description"
    )
    status = models.CharField(
        max_length=20,
        choices=WEEKLY_TRACKER_STATUS_CHOICES,
        default="not_started",
        help_text="Completed / In Progress / Not Started"
    )
    progress_pct = models.PositiveSmallIntegerField(
        default=0,
        blank=True,
        help_text="Progress percentage (0-100)"
    )
    impact = models.TextField(
        blank=True,
        help_text="Impact description"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Row order in table (smaller = first)"
    )

    class Meta:
        verbose_name = "Weekly Project Tracker Row"
        verbose_name_plural = "Weekly Project Tracker Rows"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.week} — {self.task[:50] if self.task else '—'}"


# ─── Potential Challenges (جدول Potential Challenges: Date | Challenges | Status | Progress % | Solutions) ───
class PotentialChallenge(models.Model):
    """Potential Challenges table: Date, Challenges, Status, Progress %, Solutions. Import from Excel."""
    date = models.CharField(max_length=100, blank=True, help_text="Date")
    challenges = models.TextField(blank=True, help_text="Challenges")
    status = models.CharField(
        max_length=20,
        choices=WEEKLY_TRACKER_STATUS_CHOICES,
        default="not_started",
        help_text="Completed / In Progress / Not Started",
    )
    progress_pct = models.PositiveSmallIntegerField(default=0, blank=True, help_text="Progress percentage (0-100)")
    solutions = models.TextField(blank=True, help_text="Solutions")
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Row order in table")

    class Meta:
        verbose_name = "Potential Challenge"
        verbose_name_plural = "Potential Challenges"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.date} — {self.challenges[:50] if self.challenges else '—'}"


# ─── Progress Status (جدول PROGRESS STATUS: Clerk | Account | Remark | Status) ───
class ProgressStatus(models.Model):
    """Progress Status table: Clerk, Account, Remark, Status. Excel: Quick_wins.xlsx, Sheet1."""
    clerk = models.CharField(max_length=200, blank=True, help_text="Clerk")
    account = models.CharField(max_length=200, blank=True, help_text="Account")
    remark = models.TextField(blank=True, help_text="Remark")
    status = models.CharField(
        max_length=20,
        choices=WEEKLY_TRACKER_STATUS_CHOICES,
        default="not_started",
        help_text="Completed / In Progress / Not Started",
    )
    display_order = models.PositiveSmallIntegerField(default=0, help_text="Row order in table")

    class Meta:
        verbose_name = "Progress Status"
        verbose_name_plural = "Progress Status"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.clerk or '—'} — {self.account or '—'}"
