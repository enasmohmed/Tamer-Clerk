# context_helpers.py — دوال لدمج بيانات الموديلز (ثيم، مناطق، مستودعات) في سياق الداشبورد


def get_dashboard_theme_dict():
    """يرجع قاموساً key -> value من DashboardTheme للاستخدام في التمبلت (ألوان الداشبورد)."""
    try:
        from .models import DashboardTheme
        qs = DashboardTheme.objects.all()
        return {t.key: t.value or "" for t in qs}
    except Exception:
        return {}


def get_regions_table_from_db():
    """يرجع قائمة قواميس من موديل Region لجدول returns_region_table."""
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
    """يرجع قائمة قواميس من موديل WarehouseMetric لجدول inventory_warehouse_table."""
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


def get_warehouse_overview_list():
    """
    يرجع قائمة مستودعات مع business_systems و employee_summary و phase_statuses
    لعرض كروت المستودعات (مثل صورة التابات الأولى).
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

        # ألوان حالة النظام: Pending = برتقالي، Completed = أخضر
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
                # النسبة للشارت الدائري: (Pending or edit count / Allocated count) * 100 — يظهر الشارت لو Allocated معرّف
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
            # لون شارة المستودع: لو اللون فارغ أو رصاصي نستخدم لون حسب الاسم (Active → أخضر، Partial → برتقالي)
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
    """يرجع قائمة صفوف الجدول تحت كاردز Warehouses Overview (WH | Emp No | Full Name | Business | Business 2)."""
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
