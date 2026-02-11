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
    Returns a list of Phase sections (title + points) to display in Accordion below warehouse cards.
    Each element is:
      {
        "id": section.id,
        "title": section.title,
        "points": ["Point 1", "Point 2", ...],
      }
    """
    try:
        from .models import PhaseSection

        sections = PhaseSection.objects.filter(is_active=True).prefetch_related("points")
        return [
            {
                "id": s.id,
                "title": s.title,
                "points": [p.text for p in s.points.all()],
            }
            for s in sections
        ]
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
        _choice_labels = {value: label for value, label in SYSTEM_STATUS_CHOICES if value}

        for wh in warehouses:
            biz_systems = []
            for wbs in wh.business_systems.select_related("business_unit", "system").all():
                val = wbs.system_status or ""
                biz_systems.append({
                    "business": wbs.business_unit.name,
                    "system": wbs.system_name_override or (wbs.system.name if wbs.system else ""),
                    "status_name": _choice_labels.get(val, ""),
                    "status_color": _system_status_colors.get(val, "#6c757d"),
                })
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
            for ps in wh.phase_statuses.select_related("business_unit", "activity", "status").all():
                phase_rows.append({
                    "business": ps.business_unit.name,
                    "activity": ps.activity.name,
                    "status_name": ps.status.name if ps.status else "",
                    "status_color": ps.status.color_hex if ps.status else "#6c757d",
                    "start_date": ps.start_date,
                    "end_date": ps.end_date,
                })
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
            result.append({
                "warehouse": wh,
                "status_name": wh.status.name if wh.status else "",
                "status_color": status_color,
                "business_systems": biz_systems,
                "employee_summary": emp_summary,
                "phase_statuses": phase_rows,
                "phase1_pct": wh.phase1_pct,
                "phase2_pct": wh.phase2_pct,
            })
        return result
    except Exception:
        return []


def get_wh_data_rows_list():
    """Returns a list of table rows below Warehouses Overview cards (WH | Emp No | Full Name | Business | Business 2)."""
    try:
        from .models import WHDataRow
        rows = WHDataRow.objects.select_related("business", "business_2").all()
        return [
            {
                "wh": r.wh,
                "emp_no": r.emp_no,
                "full_name": r.full_name,
                "business": r.business.name if r.business else "—",
                "business_2": r.business_2.name if r.business_2 else "—",
            }
            for r in rows
        ]
    except Exception:
        return []


def get_recommendations_list():
    """Returns a list of active recommendations for Recommendation Overview tab."""
    try:
        from .models import Recommendation
        recs = Recommendation.objects.filter(is_active=True).order_by("display_order", "id")
        result = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "icon_type": r.icon_type,
                "custom_icon": r.custom_icon.url if r.custom_icon else None,
                "icon_bg_color": r.icon_bg_color or "#f5f5f0",
                "display_order": r.display_order,
            }
            for r in recs
        ]
        print(f"[Recommendations] Found {len(result)} active recommendations")  # For debugging
        return result
    except Exception as e:
        print(f"[Recommendations] Error: {e}")  # For debugging
        return []
