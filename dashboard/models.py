
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── ثيم وألوان الداشبورد (قابلة للتعديل من الأدمن) ───
class DashboardTheme(models.Model):
    """مفتاح/قيمة لألوان وإعدادات الداشبورد بالكامل."""
    key = models.CharField(max_length=100, unique=True, help_text="مثال: primary_color, tab_active_bg")
    value = models.CharField(max_length=200, blank=True, help_text="قيمة مثل #4C8FD6 أو 12px")
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Dashboard Theme"
        verbose_name_plural = "Dashboard Themes"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value or '(empty)'}"


# ─── 1. الحالات (للمستودع وللمراحل) ───
class Status(models.Model):
    """حالة عامة مع لون (للمستودع أو لمرحلة النشاط)."""
    name = models.CharField(max_length=80)
    color_hex = models.CharField(max_length=20, default="#6c757d", help_text="مثل #2e7d32 للأخضر")
    is_warehouse_status = models.BooleanField(default=True, help_text="يُستخدم كحالة للمستودع")
    is_phase_status = models.BooleanField(default=False, help_text="يُستخدم كحالة للمرحلة (Completed, Pending, ...)")
    display_order = models.PositiveSmallIntegerField(default=0, help_text="رقم الترتيب: الأصغر يظهر أولاً (0، 1، 2...)")

    class Meta:
        verbose_name = "1. Status (الحالات)"
        verbose_name_plural = "1. Statuses (الحالات)"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── وحدة الأعمال (Pharma, FMCG, Retail) ───
class BusinessUnit(models.Model):
    name = models.CharField(max_length=80)
    display_order = models.PositiveSmallIntegerField(default=0, help_text="رقم الترتيب: الأصغر يظهر أولاً")

    class Meta:
        verbose_name = "2. Business Unit (وحدة الأعمال)"
        verbose_name_plural = "2. Business Units (وحدات الأعمال)"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── 3. النظام المرتبط بوحدة الأعمال (LogFire, SAP, WMS-X, ...) ───
class BusinessSystem(models.Model):
    name = models.CharField(max_length=120)
    business_unit = models.ForeignKey(
        BusinessUnit, on_delete=models.CASCADE, related_name="systems", null=True, blank=True
    )
    display_order = models.PositiveSmallIntegerField(default=0, help_text="رقم الترتيب: الأصغر يظهر أولاً")

    class Meta:
        verbose_name = "3. Business System (النظام)"
        verbose_name_plural = "3. Business Systems (الأنظمة)"
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name}" + (f" ({self.business_unit.name})" if self.business_unit else "")


# ─── 4. النشاط (Inbound, Outbound, Pending, Allocated, Not Started) ───
class Activity(models.Model):
    name = models.CharField(max_length=80)
    display_order = models.PositiveSmallIntegerField(default=0, help_text="رقم الترتيب: الأصغر يظهر أولاً")

    class Meta:
        verbose_name = "4. Activity (النشاط)"
        verbose_name_plural = "4. Activities (النشاطات)"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── 5. المستودع (Jeddah, Riyadh, Dammam, Abha) ───
class Warehouse(models.Model):
    name = models.CharField(max_length=120)
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, blank=True, related_name="warehouses"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="ترتيب ظهور الكارد في الصفحة: 1 يظهر أولاً، 2 ثانياً، وهكذا."
    )
    phase1_pct = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="نسبة إنجاز Phase 1 (0–100). اتركه فارغاً إن لم تستخدمه.",
    )
    phase2_pct = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="نسبة إنجاز Phase 2 (0–100). اتركه فارغاً إن لم تستخدمه.",
    )

    class Meta:
        verbose_name = "5. Warehouse (المستودع)"
        verbose_name_plural = "5. Warehouses (المستودعات)"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


# ─── خيارات حالة النظام (جنب System في الكارد) ───
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

# ─── ربط المستودع بوحدة أعمال + نظام (جدول Business | System | الحالة داخل كارد المستودع) ───
class WarehouseBusinessSystem(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="business_systems")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.CASCADE, related_name="warehouse_links")
    system = models.ForeignKey(
        BusinessSystem, on_delete=models.CASCADE, related_name="warehouse_links", null=True, blank=True
    )
    system_name_override = models.CharField(max_length=120, blank=True, help_text="إن تركت فارغاً يُستخدم اسم النظام")
    system_status = models.CharField(
        max_length=20,
        choices=SYSTEM_STATUS_CHOICES,
        blank=True,
        help_text="حالة النظام: Pending PH1 / PH1 completed / Pending PH2 / PH2 completed",
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "6. Warehouse Business System (ربط المستودع بالأنظمة)"
        verbose_name_plural = "6. Warehouse Business Systems"
        ordering = ["warehouse", "display_order"]
        unique_together = [["warehouse", "business_unit"]]

    def __str__(self):
        sys_name = self.system_name_override or (self.system.name if self.system else "")
        return f"{self.warehouse.name} — {self.business_unit.name}: {sys_name}"


# ─── حالة مرحلة لكل (مستودع + وحدة أعمال + نشاط) مع تواريخ اختيارية ───
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
        verbose_name = "8. Warehouse Phase Status (حالة المرحلة)"
        verbose_name_plural = "8. Warehouse Phase Statuses"
        ordering = ["warehouse", "display_order", "business_unit", "activity"]

    def __str__(self):
        return f"{self.warehouse.name} / {self.business_unit.name} / {self.activity.name}"


# ─── سكشن Phases (عنوان + نقاط) للجزء تحت الكاردز ───
class PhaseSection(models.Model):
    """قسم في سكشن Phases أسفل كروت المستودعات (مثل Accordion item)."""
    title = models.CharField(max_length=200, help_text="عنوان المرحلة أو السؤال (مثال: Phase 1 details).")
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="ترتيب ظهور السكشن: الأصغر يظهر أولاً."
    )
    is_active = models.BooleanField(default=True, help_text="لو مقفولة مش هتظهر في الواجهة.")

    class Meta:
        verbose_name = "Phase Section (قسم مرحلة)"
        verbose_name_plural = "Phase Sections (أقسام مراحل)"
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.title


class PhasePoint(models.Model):
    """نقطة (Bullet) داخل سكشن Phase واحد."""
    section = models.ForeignKey(
        PhaseSection, on_delete=models.CASCADE, related_name="points", help_text="المرحلة المرتبطة بالنقطة."
    )
    text = models.CharField(max_length=255, help_text="النص المختصر للنقطة.")
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="ترتيب ظهور النقطة داخل السكشن."
    )

    class Meta:
        verbose_name = "Phase Point (نقطة مرحلة)"
        verbose_name_plural = "Phase Points (نقاط مراحل)"
        ordering = ["section", "display_order", "id"]

    def __str__(self):
        return self.text[:80]


# ─── ملخص الموظفين للمستودع (عدد المعينين، رقم قلم، أو نص مثل Phase 1 Completed) ───
class WarehouseEmployeeSummary(models.Model):
    warehouse = models.OneToOneField(
        Warehouse, on_delete=models.CASCADE, related_name="employee_summary"
    )
    allocated_count = models.PositiveIntegerField(null=True, blank=True, help_text="اختياري — اتركيه فارغاً إن لم تحتاجيه")
    pending_or_edit_count = models.PositiveIntegerField(null=True, blank=True, help_text="اختياري — رقم يظهر بجانب أيقونة القلم إن وُجد")
    phase_label = models.CharField(max_length=120, blank=True, help_text="مثل Phase 1")
    phase_status_label = models.CharField(max_length=120, blank=True, help_text="مثل Completed")

    class Meta:
        verbose_name = "7. Warehouse Employee Summary (ملخص الموظفين)"
        verbose_name_plural = "7. Warehouse Employee Summaries"

    def __str__(self):
        return f"{self.warehouse.name}: {self.allocated_count if self.allocated_count is not None else '—'} allocated"


# ─── تبع تاب Dashboard → قسم Returns: جدول Region (Region | SKUs | Available | Utilization %) ───
class Region(models.Model):
    """بيانات جدول Returns في الداشبورد (container-fluid-dashboard). الأعمدة: Region, SKUs, Available, Utilization %."""
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


# ─── تبع تاب Dashboard → قسم Inventory: جدول Warehouse (Warehouse | SKUs | Available Space | Utilization %) ───
class WarehouseMetric(models.Model):
    """بيانات جدول Warehouse/Inventory في الداشبورد (container-fluid-dashboard). الأعمدة: Warehouse, SKUs, Available Space, Utilization %."""
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="metrics", null=True, blank=True
    )
    name = models.CharField(max_length=120, help_text="اسم العرض إن لم يُربط بمستودع")
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


# ─── جدول تحت كاردز Warehouses Overview: WH | Emp No | Full Name | Business | Business 2 ───
class WHDataRow(models.Model):
    """صف في الجدول تحت كاردز المستودعات: WH (اسم)، Emp No (أرقام)، Full Name، Business، Business 2."""
    wh = models.CharField(max_length=120, help_text="WH (اسم)")
    emp_no = models.CharField(max_length=50, help_text="Emp No (أرقام)")
    full_name = models.CharField(max_length=200, help_text="Full Name")
    business = models.ForeignKey(
        BusinessUnit,
        on_delete=models.CASCADE,
        related_name="wh_data_rows_business",
        help_text="Business (وحدة أعمال)",
    )
    business_2 = models.ForeignKey(
        BusinessUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wh_data_rows_business_2",
        help_text="Business 2 (وحدة أعمال ثانية، اختياري)",
    )
    display_order = models.PositiveSmallIntegerField(default=0, help_text="ترتيب الصف في الجدول")

    class Meta:
        verbose_name = "WH Data Row (صف جدول تحت الكاردز)"
        verbose_name_plural = "WH Data Rows (جدول تحت الكاردز)"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.wh} — {self.full_name} ({self.emp_no})"


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
    description = models.TextField()  # لازم يكون TextField أو CharField
    is_done = models.BooleanField(default=False)
    created_at = models.DateField(default=timezone.now)
    target_date = models.DateField(null=True, blank=True)
    assigned_to = models.CharField(max_length=255, blank=True, null=True)

    # def save(self, *args, **kwargs):
    #     # لو مفيش تاريخ هدف، حطيه بعد 7 أيام من الإنشاء
    #     if not self.target_date and not self.pk:
    #         from datetime import date
    #         self.target_date = date.today() + timedelta(days=7)
    #     super().save(*args, **kwargs)

    def __str__(self):
        return self.description[:50]


# ─── التوصيات (Recommendations) لتاب Recommendation Overview ───
ICON_CHOICES = [
    ("check-circle", "✓ Check Circle (توصية منجزة)"),
    ("scanner", "📟 RF Scanner"),
    ("people", "👥 People/Team"),
    ("document", "📄 Document"),
    ("box", "📦 Box/Package"),
    ("chart", "📊 Chart/Analytics"),
    ("settings", "⚙️ Settings"),
    ("lightbulb", "💡 Lightbulb/Idea"),
    ("clock", "⏰ Clock/Time"),
    ("arrow-up", "⬆️ Arrow Up/Improvement"),
    ("custom", "🖼️ Custom Image"),
]


class Recommendation(models.Model):
    """توصية رئيسية تظهر في تاب Recommendation Overview."""
    title = models.CharField(max_length=200, help_text="عنوان التوصية (مثال: Enhance Packing List Sheet)")
    description = models.TextField(help_text="وصف التوصية بالتفصيل")
    icon_type = models.CharField(
        max_length=20,
        choices=ICON_CHOICES,
        default="check-circle",
        help_text="نوع الأيقونة المعروضة بجانب التوصية"
    )
    custom_icon = models.ImageField(
        upload_to="recommendation_icons/",
        null=True,
        blank=True,
        help_text="صورة مخصصة للأيقونة (فقط لو اخترت Custom Image)"
    )
    icon_bg_color = models.CharField(
        max_length=20,
        default="#f5f5f0",
        help_text="لون خلفية الأيقونة (مثل #f5f5f0)"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="ترتيب ظهور التوصية: الأصغر يظهر أولاً"
    )
    is_active = models.BooleanField(default=True, help_text="لو مقفولة مش هتظهر في الواجهة")

    class Meta:
        verbose_name = "Recommendation (توصية)"
        verbose_name_plural = "Recommendations (التوصيات)"
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.title[:80]
