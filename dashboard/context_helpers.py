# context_helpers.py — Functions to merge model data (theme, regions, warehouses) into dashboard context


def get_dashboard_theme_dict():
    """Returns a key -> value dictionary from DashboardTheme for template use (dashboard colors)."""
    try:
        from .models import DashboardTheme, DEFAULT_THEME_COLORS

        qs = DashboardTheme.objects.all()
        theme_dict = {t.key: t.value or "" for t in qs}

        # Fill in defaults for any missing keys
        for key, value, description, category in DEFAULT_THEME_COLORS:
            if key not in theme_dict or not theme_dict[key]:
                theme_dict[key] = value

        return theme_dict
    except Exception:
        # Return defaults if database error
        from .models import DEFAULT_THEME_COLORS

        return {key: value for key, value, desc, cat in DEFAULT_THEME_COLORS}


def get_regions_table_from_db():
    """Returns a list of dictionaries from Region model for returns_region_table."""
    try:
        from .models import Region

        rows = Region.objects.all()
        return [
            {
                "region": r.name,
                "skus": r.skus,
                "available": r.available,
                "utilization_pct": r.utilization_pct,
            }
            for r in rows
        ]
    except Exception:
        return []


def get_warehouse_metrics_table_from_db():
    """Returns a list of dictionaries from WarehouseMetric model for inventory_warehouse_table."""
    try:
        from .models import WarehouseMetric

        rows = WarehouseMetric.objects.all()
        return [
            {
                "warehouse": r.name or (r.warehouse.name if r.warehouse else ""),
                "skus": r.skus,
                "available_space": r.available_space,
                "utilization_pct": r.utilization_pct,
            }
            for r in rows
        ]
    except Exception:
        return []


def get_phases_sections_list():
    """
    Returns a list of Phase sections for Plan (30/60/90 DAYS) ribbons.
    Uses days_number and days_label from the model when set; else falls back to parsing title.
    """
    try:
        from .models import PhaseSection

        sections = PhaseSection.objects.filter(is_active=True).prefetch_related(
            "points"
        )
        result = []
        for s in sections:
            if s.days_number is not None:
                display_number = str(s.days_number)
                display_label = (s.days_label or "DAYS").strip() or "DAYS"
            else:
                title = (s.title or "").strip()
                parts = title.split(None, 1)
                if parts and parts[0].isdigit():
                    display_number = parts[0]
                    display_label = parts[1].strip() if len(parts) > 1 else "DAYS"
                else:
                    display_number = ""
                    display_label = title or "DAYS"
            result.append({
                "id": s.id,
                "title": s.title,
                "display_number": display_number,
                "display_label": display_label,
                "points": [p.text for p in s.points.all()],
            })
        return result
    except Exception:
        return []


def get_warehouse_overview_list():
    """
    Returns a list of warehouses with business_systems, employee_summary, and phase_statuses
    to display warehouse cards (like the first tabs image).
    """
    try:
        from .models import (
            Warehouse,
            WarehouseBusinessSystem,
            WarehouseEmployeeSummary,
            WarehousePhaseStatus,
        )

        warehouses = Warehouse.objects.all()
        result = []
        from .models import SYSTEM_STATUS_CHOICES

        # System status colors: Pending = orange, Completed = green
        _system_status_colors = {
            "pending_ph1": "#f57c00",
            "ph1_completed": "#2e7d32",
            "pending_ph2": "#f57c00",
            "ph2_completed": "#2e7d32",
        }
        _choice_labels = {
            value: label for value, label in SYSTEM_STATUS_CHOICES if value
        }

        for wh in warehouses:
            biz_systems = []
            for wbs in wh.business_systems.select_related(
                "business_unit", "system"
            ).all():
                val = wbs.system_status or ""
                biz_systems.append(
                    {
                        "business": wbs.business_unit.name,
                        "system": wbs.system_name_override
                        or (wbs.system.name if wbs.system else ""),
                        "status_name": _choice_labels.get(val, ""),
                        "status_color": _system_status_colors.get(val, "#6c757d"),
                    }
                )
            try:
                emp = wh.employee_summary
                # Chart percentage: (Pending or edit count / Allocated count) * 100 — chart shows if Allocated is defined
                chart_pct = None
                if emp.allocated_count is not None:
                    if emp.allocated_count > 0:
                        pending = emp.pending_or_edit_count or 0
                        chart_pct = round((pending / emp.allocated_count) * 100)
                        chart_pct = min(100, max(0, chart_pct))
                    else:
                        chart_pct = 0
                emp_summary = {
                    "allocated_count": emp.allocated_count,
                    "pending_or_edit_count": emp.pending_or_edit_count,
                    "phase_label": emp.phase_label,
                    "phase_status_label": emp.phase_status_label,
                    "employee_chart_pct": chart_pct,
                }
            except WarehouseEmployeeSummary.DoesNotExist:
                emp_summary = {
                    "allocated_count": None,
                    "pending_or_edit_count": None,
                    "phase_label": "",
                    "phase_status_label": "",
                    "employee_chart_pct": None,
                }
            phase_rows = []
            for ps in wh.phase_statuses.select_related(
                "business_unit", "activity", "status"
            ).all():
                phase_rows.append(
                    {
                        "business": ps.business_unit.name,
                        "activity": ps.activity.name,
                        "status_name": ps.status.name if ps.status else "",
                        "status_color": ps.status.color_hex if ps.status else "#6c757d",
                        "start_date": ps.start_date,
                        "end_date": ps.end_date,
                    }
                )
            # Warehouse badge color: if empty or gray, use color based on name (Active → green, Partial → orange)
            status_color = "#6c757d"
            if wh.status:
                hex_val = (wh.status.color_hex or "").strip()
                if hex_val and hex_val.lower() not in ("#6c757d", ""):
                    status_color = hex_val
                else:
                    name_lower = (wh.status.name or "").strip().lower()
                    if "active" in name_lower:
                        status_color = "#2e7d32"
                    elif "partial" in name_lower:
                        status_color = "#f57c00"
                    else:
                        status_color = "#2e7d32"
            result.append(
                {
                    "warehouse": wh,
                    "status_name": wh.status.name if wh.status else "",
                    "status_color": status_color,
                    "business_systems": biz_systems,
                    "employee_summary": emp_summary,
                    "phase_statuses": phase_rows,
                    "phase1_pct": wh.phase1_pct,
                    "phase2_pct": wh.phase2_pct,
                }
            )
        return result
    except Exception:
        return []


def get_clerk_interview_list():
    """Returns a list of Clerk Interview Tracking rows for Project Overview table. Columns: WH, Clerk Name, NATIONALITY, Report Used, Optimization Status, Strength, System Used, Business, Remark."""
    try:
        from .models import ClerkInterviewTracking

        rows = ClerkInterviewTracking.objects.all()
        return [
            {
                "wh": r.wh or "—",
                "clerk_name": r.clerk_name or "—",
                "nationality": r.nationality or "—",
                "optimization_status": r.optimization_status or "—",
                "system_used": r.system_used or "—",
                "business": r.business or "—",
                "remark": r.remark or "—",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_clerk_details_list():
    """Returns list of Clerk Detail (interview profile) rows for Clerk details tab. Sidebar uses dept_name_en."""
    try:
        from .models import ClerkDetail

        rows = ClerkDetail.objects.all()
        return [
            {
                "id": r.id,
                "dept_name_en": r.dept_name_en or "—",
                "department": r.department or "—",
                "company": r.company or "—",
                "business": r.business or "—",
                "account": r.account or "—",
                "mobile": r.mobile or "—",
                "interview_date": r.interview_date or "—",
                "work_details": r.work_details or "",
                "reports_used": r.reports_used or "",
                "system_badge": r.system_badge or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_weekly_project_tracker_list():
    """Returns list of Weekly Project Tracker rows for Progress Overview tab."""
    try:
        from .models import WeeklyProjectTrackerRow

        rows = WeeklyProjectTrackerRow.objects.all()
        return [
            {
                "week": r.week,
                "task": r.task,
                "status": r.status,
                "status_display": r.get_status_display(),
                "progress_pct": r.progress_pct,
                "impact": r.impact or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_progress_status_list():
    """Returns list of Progress Status rows (Clerk, Account, Remark, Status)."""
    try:
        from .models import ProgressStatus

        rows = ProgressStatus.objects.all()
        return [
            {
                "clerk": r.clerk or "—",
                "account": r.account or "—",
                "remark": r.remark or "—",
                "status": r.status,
                "status_display": r.get_status_display(),
            }
            for r in rows
        ]
    except Exception:
        return []


def get_potential_challenges_list():
    """Returns list of Potential Challenges rows (Date, Challenges, Status, Progress %, Solutions)."""
    try:
        from .models import PotentialChallenge

        rows = PotentialChallenge.objects.all()
        return [
            {
                "date": r.date or "—",
                "challenges": r.challenges or "—",
                "status": r.status,
                "status_display": r.get_status_display(),
                "progress_pct": r.progress_pct,
                "solutions": r.solutions or "—",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_recommendations_list():
    """
    Returns a list of "cards" for Recommendation Overview tab.
    Each card has business, user_name, logo_url (from first item's Custom icon if set), and items.
    Cards are grouped by (business, user_name); two cards per row in the UI.
    """
    try:
        from .models import Recommendation
        from itertools import groupby

        recs = Recommendation.objects.filter(is_active=True).order_by(
            "business", "user_name", "display_order", "id"
        )

        cards = []
        for (business, user_name), group in groupby(
            recs, key=lambda r: (r.business or "", r.user_name or "")
        ):
            items = [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description,
                    "icon_type": r.icon_type,
                    "custom_icon": r.custom_icon.url if r.custom_icon else None,
                    "icon_bg_color": r.icon_bg_color or "#f5f5f0",
                    "display_order": r.display_order,
                }
                for r in group
            ]
            if items:
                # Card header logo: first item's Custom icon (company logo) if set
                logo_url = next((i["custom_icon"] for i in items if i.get("custom_icon")), None)
                cards.append({
                    "business": business or "—",
                    "user_name": user_name or "",
                    "logo_url": logo_url,
                    "items": items,
                })
        return cards
    except Exception as e:
        print(f"[Recommendations] Error: {e}")
        return []


def get_project_tracker_list(project_type=None):
    """
    يعرض كل الأشهر اللي فيها داتا من الأدمن فقط (حتى لو سنة فاتت).
    الترتيب: من الأحدث (فوق) للأقدم (تحت).
    project_type: اختياري — "idea" أو "automation" لفلترة النتائج لكل الأشهر.
    """
    from datetime import date
    from calendar import month_abbr

    try:
        from .models import ProjectTrackerItem

        today = date.today()
        this_year, this_month = today.year, today.month

        def item_to_dict(obj):
            return {
                "id": obj.id,
                "description": obj.description,
                "person_name": obj.person_name,
                "project_type": getattr(obj, "project_type", "") or "",
                "project_type_display": obj.get_project_type_display() if getattr(obj, "project_type", None) else "",
                "company": getattr(obj, "company", "") or "",
                "start_date": obj.start_date,
                "start_date_display": obj.start_date.strftime("%b %d"),
                "end_date": obj.end_date,
                "end_date_display": obj.end_date.strftime("%b %d") if obj.end_date else "",
                "brainstorming_status": obj.brainstorming_status or "",
                "execution_status": obj.execution_status or "",
                "launch_status": obj.launch_status or "",
                "brainstorming_display": obj.get_brainstorming_status_display() or "",
                "execution_display": obj.get_execution_status_display() or "",
                "launch_display": obj.get_launch_status_display() or "",
            }

        base_qs = ProjectTrackerItem.objects.all()
        if project_type and project_type in ("idea", "automation"):
            base_qs = base_qs.filter(project_type=project_type)

        def phase_progress(items, phase_key):
            total = len(items)
            if total == 0:
                return {
                    "done": 0,
                    "working_on_it": 0,
                    "stuck": 0,
                    "empty": 0,
                    "total": 0,
                    "done_pct": 0,
                    "working_on_it_pct": 0,
                    "stuck_pct": 0,
                    "empty_pct": 100,
                }
            done = sum(1 for i in items if i.get(phase_key) == "done")
            working = sum(1 for i in items if i.get(phase_key) == "working_on_it")
            stuck = sum(1 for i in items if i.get(phase_key) == "stuck")
            empty = total - done - working - stuck
            done_pct = round(100 * done / total) if total else 0
            working_pct = round(100 * working / total) if total else 0
            stuck_pct = round(100 * stuck / total) if total else 0
            empty_pct = 100 - done_pct - working_pct - stuck_pct
            if empty_pct < 0:
                empty_pct = 0
            return {
                "done": done,
                "working_on_it": working,
                "stuck": stuck,
                "empty": empty,
                "total": total,
                "done_pct": done_pct,
                "working_on_it_pct": working_pct,
                "stuck_pct": stuck_pct,
                "empty_pct": empty_pct,
            }

        # كل الأشهر المميزة اللي فيها عناصر (من الأدمن)، من الأحدث للأقدم
        distinct_months = list(base_qs.dates("start_date", "month", order="DESC"))
        month_sections = []
        for month_date in distinct_months:
            y, m = month_date.year, month_date.month
            qs = (
                base_qs.filter(start_date__year=y, start_date__month=m)
                .order_by("-start_date", "display_order", "id")
            )
            items = [item_to_dict(o) for o in qs]
            progress = {
                "brainstorming": phase_progress(items, "brainstorming_status"),
                "execution": phase_progress(items, "execution_status"),
                "launch": phase_progress(items, "launch_status"),
            }
            if y == this_year and m == this_month:
                label = "This month"
                css_class = "this-month"
            elif (y == this_year and m == this_month - 1) or (
                y == this_year - 1 and this_month == 1 and m == 12
            ):
                label = "Last month"
                css_class = "last-month"
            else:
                label = f"{month_abbr[m]} {y}"
                css_class = "month-other"
            month_sections.append({
                "label": label,
                "items": items,
                "progress": progress,
                "css_class": css_class,
            })

        this_month = month_sections[0]["items"] if month_sections else []
        last_month = month_sections[1]["items"] if len(month_sections) > 1 else []
        _empty = phase_progress([], "")
        this_month_progress = (
            month_sections[0]["progress"]
            if month_sections
            else {"brainstorming": _empty, "execution": _empty, "launch": _empty}
        )
        last_month_progress = (
            month_sections[1]["progress"]
            if len(month_sections) > 1
            else this_month_progress
        )

        return {
            "month_sections": month_sections,
            "this_month": this_month,
            "last_month": last_month,
            "this_month_progress": this_month_progress,
            "last_month_progress": last_month_progress,
            "current_project_type": project_type or "",
        }
    except Exception as e:
        import traceback

        traceback.print_exc()

        def _empty_progress():
            return {
                "done": 0,
                "working_on_it": 0,
                "stuck": 0,
                "empty": 0,
                "total": 0,
                "done_pct": 0,
                "working_on_it_pct": 0,
                "stuck_pct": 0,
                "empty_pct": 100,
            }

        _empty = _empty_progress()
        return {
            "month_sections": [],
            "this_month": [],
            "last_month": [],
            "this_month_progress": {
                "brainstorming": _empty,
                "execution": _empty,
                "launch": _empty,
            },
            "last_month_progress": {
                "brainstorming": _empty,
                "execution": _empty,
                "launch": _empty,
            },
            "current_project_type": "",
        }
