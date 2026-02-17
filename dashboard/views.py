# views.py
import datetime
import shutil
import os
import re
from io import BytesIO
from collections import OrderedDict

import pandas as pd
import numpy as np
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from .forms import ExcelUploadForm
from django.core.cache import cache

from django.views.decorators.cache import cache_control
import json, traceback, os
from datetime import date
from django.db.models import Q
from django.template.loader import render_to_string
from calendar import month_abbr, month_name
import calendar as calendar_module

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.text import slugify

from .models import MeetingPoint
from . import context_helpers


def make_json_serializable(df):

    def convert_value(x):
        if isinstance(x, (pd.Timestamp, pd.Timedelta)):
            return x.isoformat()
        elif isinstance(x, (datetime.datetime, datetime.date, datetime.time)):
            return x.isoformat()
        elif isinstance(x, (np.int64, np.int32)):
            return int(x)
        elif isinstance(x, (np.float64, np.float32)):
            return float(x)
        elif isinstance(x, (np.ndarray, list, dict)):
            return str(x)
        else:
            return x

    return df.applymap(convert_value)


def _sanitize_for_json(obj):
    """Convert numpy/pandas types to native Python for JsonResponse."""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, np.ndarray):
        return [_sanitize_for_json(v) for v in obj.tolist()]
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        try:
            v = float(obj)
            if np.isnan(v) or np.isinf(v):
                return None
            return v
        except (ValueError, TypeError):
            return None
    if isinstance(obj, (pd.Timestamp, pd.Timedelta, datetime.datetime, datetime.date)):
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)
    if isinstance(obj, (int, float)) and (obj != obj or abs(obj) == float("inf")):
        return None  # NaN or Inf
    try:
        if pd.isna(obj) and not isinstance(obj, (dict, list, tuple)):
            return None
    except (ValueError, TypeError):
        pass
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _get_excel_path_for_request(request):
    """يرجع مسار ملف الإكسل المرفوع من الجلسة أو المجلد الافتراضي."""
    if not request:
        return None
    folder = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
    if not os.path.isdir(folder):
        return None
    path = request.session.get("uploaded_excel_path")
    if path and os.path.isfile(path):
        return path
    for name in ["latest.xlsm", "latest.xlsx", "all sheet.xlsm", "all sheet.xlsx", "all_sheet.xlsm", "all_sheet.xlsx"]:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            return p
    return None


# اسم ملف الداشبورد الثابت (شيت تاني للتاب Dashboard فقط)
DASHBOARD_EXCEL_FILENAME = "Aramco_Tamer3PL_KPI_Dashboard.xlsx"

# داتا Inbound الافتراضية (للكروت والشارت) — نفس فكرة chart_data في rejection
INBOUND_DEFAULT_KPI = {
    "number_of_vehicles": 12,
    "number_of_shipments": 287,
    "number_of_pallets": 1105,
    "total_quantity": 65400,
    "total_quantity_display": "65.4k",
}
# الداتا اللي بتظهر على شارت Pending Shipments (label, value, pct, color)
INBOUND_DEFAULT_PENDING_SHIPMENTS = [
    {"label": "In Transit", "value": "1%", "pct": 1, "color": "#87CEEB"},
    {"label": "Receiving Complete", "value": "96%", "pct": 96, "color": "#2E7D32"},
    {"label": "Verified", "value": "3%", "pct": 3, "color": "#1565C0"},
]

# داتا الشارتات الافتراضية للداشبورد (نفس فكرة chart_data في rejection — لو مفيش إكسل نستخدمها)
DASHBOARD_DEFAULT_CHART_DATA = {
    "outbound_chart_data": {
        "categories": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "series": [40, 55, 48, 62, 58, 70],
    },
    "returns_chart_data": {
        "categories": ["Mar", "Apr", "May", "Jun", "Jul", "Aug"],
        "series": [280, 320, 300, 350, 380, 400],
    },
    "inventory_capacity_data": {"used": 78, "available": 22},
}


def _read_dashboard_charts_from_excel(excel_path):
    """
    يقرأ داتا الشارتات (Outbound, Returns, Inventory) من ملف الداشبورد لو الشيتات موجودة.
    ترجع ديكت باللي اتقرا فقط (لو مفيش داتا للشارت ترجع None للكاي) — عشان نعمل الشارتات دينامك.
    """
    result = {}
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return result
    sheet_names = [str(s).strip() for s in xls.sheet_names]

    # Outbound: من شيت Outbound_Data أو Outbound — تجميع حسب شهر لو فيه عمود شهر/تاريخ
    for out_name in ["Outbound_Data", "Outbound Data", "Outbound"]:
        if not any(out_name.lower().replace(" ", "") in s.lower().replace(" ", "") for s in sheet_names):
            continue
        sheet_name = next((s for s in sheet_names if out_name.lower() in s.lower()), None)
        if not sheet_name:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
            if df.empty or len(df) < 2:
                break
            df.columns = [str(c).strip() for c in df.columns]
            cols_lower = {c.lower(): c for c in df.columns}
            month_col = None
            for c in cols_lower:
                if "month" in c or "date" in c:
                    month_col = cols_lower[c]
                    break
            if month_col:
                df["_m"] = pd.to_datetime(df[month_col], errors="coerce").dt.strftime("%b")
                by_month = df.groupby("_m").size().reindex(
                    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                ).dropna()
                if not by_month.empty:
                    result["outbound_chart_data"] = {
                        "categories": by_month.index.tolist(),
                        "series": by_month.values.tolist(),
                    }
            break
        except Exception:
            break

    # Returns: من شيت Return أو Rejection
    for ret_name in ["Return", "Rejection", "Returns"]:
        sheet_name = next((s for s in sheet_names if ret_name.lower() in s.lower()), None)
        if not sheet_name:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
            if df.empty or len(df) < 2:
                break
            df.columns = [str(c).strip() for c in df.columns]
            month_col = next((c for c in df.columns if "month" in c.lower()), None)
            val_col = next(
                (c for c in df.columns if "order" in c.lower() or "booking" in c.lower() or "count" in c.lower()),
                df.columns[1] if len(df.columns) > 1 else None,
            )
            if month_col and val_col:
                summary = df[[month_col, val_col]].dropna()
                if not summary.empty:
                    try:
                        summary[val_col] = pd.to_numeric(summary[val_col].astype(str).str.replace("%", "", regex=False), errors="coerce")
                        summary = summary.dropna(subset=[val_col])
                        categories = summary[month_col].astype(str).tolist()
                        series = summary[val_col].astype(int).tolist()
                        if categories and series:
                            result["returns_chart_data"] = {"categories": categories, "series": series}
                    except Exception:
                        pass
            break
        except Exception:
            break

    # Inventory capacity: من شيت Inventory أو Capacity
    for inv_name in ["Inventory", "Capacity", "Warehouse"]:
        sheet_name = next((s for s in sheet_names if inv_name.lower() in s.lower()), None)
        if not sheet_name:
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
            if df.empty:
                break
            df.columns = [str(c).strip() for c in df.columns]
            used_col = next((c for c in df.columns if "used" in c.lower() or "utilization" in c.lower()), None)
            if used_col:
                vals = pd.to_numeric(df[used_col], errors="coerce").dropna()
                if len(vals) > 0:
                    used = int(min(100, max(0, vals.mean())))
                    result["inventory_capacity_data"] = {"used": used, "available": 100 - used}
            break
        except Exception:
            break

    return result


def _get_dashboard_excel_path(request):
    """
    يرجّع مسار ملف إكسل الداشبورد (Aramco_Tamer3PL_KPI_Dashboard.xlsx) إن وُجد.
    مصدر الداتا لتاب Dashboard فقط؛ باقي التابات من الملف الرئيسي (all_sheet / latest).
    """
    if not request:
        return None
    folder = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
    path = request.session.get("dashboard_excel_path")
    if path and os.path.isfile(path):
        return path
    p = os.path.join(folder, DASHBOARD_EXCEL_FILENAME)
    if os.path.isfile(p):
        try:
            request.session["dashboard_excel_path"] = p
            request.session.save()
        except Exception:
            pass
        return p
    return None


def _is_dashboard_excel_filename(name):
    """يعرف إذا الملف المرفوع هو ملف الداشبورد (شيت تاني)."""
    if not name:
        return False
    n = (name or "").strip().lower()
    return "kpi_dashboard" in n or "aramco_tamer3pl" in n


def _read_inbound_data_from_excel(excel_path):
    """
    يقرأ بيانات Inbound (KPI + Pending Shipments) من ملف الإكسل.
    الشيت: "Inbound" أو أول شيت اسمه يحتوي "inbound".
    أعمدة الـ KPI (حسب الطلب):
    - Vehicle_ID: كل يوم بيومه نشيل المتكرر (unique per day) ثم نجمع عدد المركبات لكل الأيام → Number of Vehicles
    - Shipment_ID: نفس المنطق يوم بيوم unique ثم جمع → Number of Shipments
    - Nbr_LPNs: مجموع كل القيم (27+18+13+...) → Number of Pallets (LPNs)
    - Total_Qty: مجموع كل القيم → Total Quantity
    عمود التاريخ: أي عمود اسمه يحتوي date/receipt/shipment date (للتجميع يوم بيوم).
    إن لم يوجد عمود تاريخ، نعتبر كل البيانات يوم واحد.
    Pending Shipments: إن وُجدت أعمدة Label/Status, Value, Pct, Color في نفس الشيت أو شيت آخر نستخدمها.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        if "inbound" in name.lower():
            sheet_name = name
            break
    if not sheet_name:
        sheet_name = xls.sheet_names[0] if xls.sheet_names else None
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    # تطبيع أسماء الأعمدة: strip + lower للبحث
    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    # عمود التاريخ (للتجميع يوم بيوم)
    date_col = None
    for c in df.columns:
        cl = c.lower()
        if "date" in cl or "receipt" in cl or ("shipment" in cl and "date" in cl) or cl == "day":
            date_col = c
            break
    if not date_col and df.columns.size > 0:
        for c in df.columns:
            try:
                pd.to_datetime(df[c].dropna().head(20), errors="coerce")
                date_col = c
                break
            except Exception:
                continue

    vehicle_col = _col("Vehicle_ID", "Vehicle ID", "Vehicle_ID")
    shipment_col = _col("Shipment_ID", "Shipment ID", "Shipment_ID")
    lpn_col = _col("Nbr_LPNs", "Nbr LPNs", "LPNs")
    qty_col = _col("Total_Qty", "Total_Qty", "Total Qty", "Total_Qty")

    def _to_int(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    n_vehicles = 0
    n_shipments = 0
    n_pallets = 0
    n_qty = 0

    if date_col and (vehicle_col or shipment_col):
        # تجميع يوم بيوم
        df_date = df.copy()
        df_date["_date"] = pd.to_datetime(df_date[date_col], errors="coerce")
        df_date = df_date.dropna(subset=["_date"])
        df_date["_day"] = df_date["_date"].dt.normalize()

        if vehicle_col:
            # كل يوم: عدد الـ Vehicle_ID المميزة، ثم نجمع كل الأيام
            per_day_vehicles = df_date.groupby("_day")[vehicle_col].nunique()
            n_vehicles = int(per_day_vehicles.sum())
        if shipment_col:
            # كل يوم: عدد الـ Shipment_ID المميزة، ثم نجمع كل الأيام
            per_day_shipments = df_date.groupby("_day")[shipment_col].nunique()
            n_shipments = int(per_day_shipments.sum())
    else:
        # بدون تاريخ: نعتبر كل الصفوف يوم واحد (unique للمركبات والشحنات)
        if vehicle_col:
            n_vehicles = int(df[vehicle_col].nunique())
        if shipment_col:
            n_shipments = int(df[shipment_col].nunique())

    if lpn_col:
        n_pallets = _to_int(df[lpn_col].sum()) or 0
    if qty_col:
        n_qty = _to_int(df[qty_col].sum()) or 0

    # قيم افتراضية لو مفيش أعمدة مناسبة
    if not vehicle_col:
        n_vehicles = 12
    if not shipment_col:
        n_shipments = 287
    if not lpn_col:
        n_pallets = 1105
    if not qty_col:
        n_qty = 65400

    if n_qty >= 1000:
        qty_display = f"{n_qty / 1000:.1f}k".rstrip("0").rstrip(".")
        if not qty_display.endswith("k"):
            qty_display += "k"
    else:
        qty_display = str(n_qty)

    inbound_kpi = {
        "number_of_vehicles": n_vehicles,
        "number_of_shipments": n_shipments,
        "number_of_pallets": n_pallets,
        "total_quantity": n_qty,
        "total_quantity_display": qty_display,
    }

    # Pending Shipments: من عمود Status في نفس شيت Inbound — In Transit, Receiving Complete, Verified
    # يوم بيوم نجمع عدد الشحنات لكل حالة ثم نجمع التوتال، ثم النسبة = (عدد الحالة / التوتال) * 100
    pending = []
    status_col = _col("Status", "status")
    STATUS_LABELS = (
        ("in transit", "In Transit", "#87CEEB"),
        ("receiving complete", "Receiving Complete", "#2E7D32"),
        ("verified", "Verified", "#1565C0"),
    )
    if status_col:
        df_status = df.copy()
        # تطبيع Status: حروف صغيرة + إزالة مسافات زائدة لتحمل اختلافات الكتابة
        s = df_status[status_col].fillna("").astype(str).str.strip().str.lower()
        df_status["_status_norm"] = s.str.replace(r"\s+", " ", regex=True)
        if date_col:
            df_status["_date"] = pd.to_datetime(df_status[date_col], errors="coerce")
            df_status = df_status.dropna(subset=["_date"])
            df_status["_day"] = df_status["_date"].dt.normalize()
            # كل يوم: عدد الصفوف (شحنات) لكل حالة، ثم جمع كل الأيام
            count_in_transit = 0
            count_receiving_complete = 0
            count_verified = 0
            for _day, grp in df_status.groupby("_day"):
                count_in_transit += (grp["_status_norm"] == "in transit").sum()
                count_receiving_complete += (grp["_status_norm"] == "receiving complete").sum()
                count_verified += (grp["_status_norm"] == "verified").sum()
        else:
            count_in_transit = (df_status["_status_norm"] == "in transit").sum()
            count_receiving_complete = (df_status["_status_norm"] == "receiving complete").sum()
            count_verified = (df_status["_status_norm"] == "verified").sum()
        total_pending = count_in_transit + count_receiving_complete + count_verified
        if total_pending > 0:
            for key, label, color in STATUS_LABELS:
                if key == "in transit":
                    c = count_in_transit
                elif key == "receiving complete":
                    c = count_receiving_complete
                else:
                    c = count_verified
                pct = round((c / total_pending) * 100)
                pending.append({
                    "label": label,
                    "value": f"{pct}%",
                    "pct": pct,
                    "color": color,
                })
    if not pending:
        pending = [
            {"label": "In Transit", "value": "1%", "pct": 1, "color": "#87CEEB"},
            {"label": "Receiving Complete", "value": "96%", "pct": 96, "color": "#2E7D32"},
            {"label": "Verified", "value": "3%", "pct": 3, "color": "#1565C0"},
        ]

    return {"inbound_kpi": inbound_kpi, "pending_shipments": pending}


def _read_outbound_data_from_excel(excel_path):
    """
    يقرأ بيانات Outbound من شيت Outbound_Data في ملف الداشبورد.
    - عمود Status: نفلتر "Released" → released_orders، "Picked" → picked_orders
    - عمود Order_ID: نحذف المتكرر (unique) ونحسب عدد الطلبات لكل حالة
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        if "outbound_data" in name.lower().replace(" ", "").replace("_", ""):
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "outbound" in name.lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    status_col = _col("Status", "status")
    order_col = _col("Order_ID", "Order ID", "Order_ID", "OrderID")
    if not status_col or not order_col:
        return None

    # تطبيع Status للمقارنة
    s = df[status_col].fillna("").astype(str).str.strip().str.lower()
    df["_status_norm"] = s.str.replace(r"\s+", " ", regex=True)

    released_mask = df["_status_norm"] == "released"
    picked_mask = df["_status_norm"] == "picked"

    released_orders = 0
    picked_orders = 0
    if released_mask.any():
        released_orders = df.loc[released_mask, order_col].dropna().astype(str).str.strip().nunique()
    if picked_mask.any():
        picked_orders = df.loc[picked_mask, order_col].dropna().astype(str).str.strip().nunique()

    return {
        "released_orders": int(released_orders),
        "picked_orders": int(picked_orders),
    }


def _read_pods_data_from_excel(excel_path):
    """
    يقرأ من شيت PODs_Data: عمود POD_Status (On Time, Pending, Late)،
    Delivery_Date للشهور، POD_ID للعدد. يرجّع داتا لشارت خط: كل شهر ونسبة كل حالة %.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        n = str(name).strip().lower().replace(" ", "").replace("_", "")
        if "podsdata" in n or "pods_data" in n or (n == "pods" and "data" in n):
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "pod" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    status_col = _col("POD_Status", "POD Status", "PODStatus")
    date_col = _col("Delivery_Date", "Delivery Date", "DeliveryDate", "Date")
    pod_id_col = _col("POD_ID", "POD ID", "PODID")
    if not status_col or not date_col:
        return None
    if not pod_id_col:
        pod_id_col = df.columns[0]

    s = df[status_col].fillna("").astype(str).str.strip().str.lower()
    df["_status_norm"] = s.str.replace(r"\s+", " ", regex=True)
    valid_statuses = {"on time", "pending", "late"}
    df = df[df["_status_norm"].isin(valid_statuses)].copy()
    if df.empty:
        return None

    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_month"] = df["_date"].dt.strftime("%b")
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months_in_data = df["_month"].unique().tolist()
    months_sorted = sorted(months_in_data, key=lambda m: month_order.index(m) if m in month_order else 99)

    series_on_time = []
    series_pending = []
    series_late = []
    for m in months_sorted:
        grp = df[df["_month"] == m]
        on_time = (grp["_status_norm"] == "on time").sum()
        pending = (grp["_status_norm"] == "pending").sum()
        late = (grp["_status_norm"] == "late").sum()
        total = on_time + pending + late
        if total == 0:
            series_on_time.append(0)
            series_pending.append(0)
            series_late.append(0)
        else:
            series_on_time.append(round(100.0 * on_time / total, 1))
            series_pending.append(round(100.0 * pending / total, 1))
            series_late.append(round(100.0 * late / total, 1))

    return {
        "categories": months_sorted,
        "series": [
            {"name": "On Time", "data": series_on_time},
            {"name": "Pending", "data": series_pending},
            {"name": "Late", "data": series_late},
        ],
    }


def _read_returns_data_from_excel(excel_path):
    """
    يقرأ من شيت Returns_Data: عمود Return_Status (فلترة مثل PODs: On Time, Pending, Late)،
    Request_Date للشهور، Return_ID لعدد الشحنات (unique). يرجّع returns_kpi و returns_chart_data.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        n = str(name).strip().lower().replace(" ", "").replace("_", "")
        if "returnsdata" in n or "returns_data" in n:
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "returns" in str(name).lower() and "data" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        for name in xls.sheet_names:
            if "return" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    status_col = _col("Return_Status", "Return Status", "ReturnStatus")
    date_col = _col("Request_Date", "Request Date", "RequestDate", "Date")
    return_id_col = _col("Return_ID", "Return ID", "ReturnID")
    nbr_skus_col = _col("Nbr_SKUs", "Nbr SKUs", "NbrSKUs")
    nbr_items_col = _col("Nbr_Items", "Nbr Items", "NbrItems")
    if not status_col or not date_col:
        return None
    if not return_id_col:
        return_id_col = df.columns[0]

    s = df[status_col].fillna("").astype(str).str.strip().str.lower()
    df["_status_norm"] = s.str.replace(r"\s+", " ", regex=True)
    valid_statuses = {"on time", "pending", "late"}
    df = df[df["_status_norm"].isin(valid_statuses)].copy()
    if df.empty:
        return None

    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_month"] = df["_date"].dt.strftime("%b")
    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    months_in_data = df["_month"].unique().tolist()
    months_sorted = sorted(months_in_data, key=lambda m: month_order.index(m) if m in month_order else 99)

    total_unique_returns = df[return_id_col].dropna().astype(str).str.strip().nunique()
    total_rows = len(df)

    total_skus_kpi = total_unique_returns
    total_lpns_kpi = total_rows
    if nbr_skus_col:
        total_skus_kpi = int(pd.to_numeric(df[nbr_skus_col], errors="coerce").fillna(0).sum())
    if nbr_items_col:
        total_lpns_kpi = int(pd.to_numeric(df[nbr_items_col], errors="coerce").fillna(0).sum())

    series_on_time = []
    series_pending = []
    series_late = []
    for m in months_sorted:
        grp = df[df["_month"] == m]
        on_time = (grp["_status_norm"] == "on time").sum()
        pending = (grp["_status_norm"] == "pending").sum()
        late = (grp["_status_norm"] == "late").sum()
        total = on_time + pending + late
        if total == 0:
            series_on_time.append(0)
            series_pending.append(0)
            series_late.append(0)
        else:
            series_on_time.append(round(100.0 * on_time / total, 1))
            series_pending.append(round(100.0 * pending / total, 1))
            series_late.append(round(100.0 * late / total, 1))

    return {
        "returns_kpi": {
            "total_skus": total_skus_kpi,
            "total_lpns": total_lpns_kpi,
        },
        "returns_chart_data": {
            "categories": months_sorted,
            "series": [
                {"name": "On Time", "data": series_on_time},
                {"name": "Pending", "data": series_pending},
                {"name": "Late", "data": series_late},
            ],
        },
    }


def _read_inventory_data_from_excel(excel_path):
    """
    يقرأ من شيت Inventory_Lots:
    - عمود LPNs: تجميع كل القيم (مجموع) = Total LPNs.
    - عمود Snapshot_Date: كل يوم بيومه (للاستخدام لاحقاً في شارت/تحليل).
    - عمود SKU: حذف المتكرر وعدّ القيم الفريدة فقط = Total SKUs.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        n = str(name).strip().lower().replace(" ", "").replace("_", "")
        if "inventorylots" in n or "inventory_lots" in n:
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "inventory" in str(name).lower() and "lot" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        for name in xls.sheet_names:
            if "inventory" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    lpns_col = _col("LPNs", "LPN")
    snapshot_date_col = _col("Snapshot_Date", "Snapshot Date", "SnapshotDate", "Date")
    sku_col = _col("SKU", "Sku")

    total_lpns = 0
    total_skus = 0

    if lpns_col:
        total_lpns = int(pd.to_numeric(df[lpns_col], errors="coerce").fillna(0).sum())

    if sku_col:
        sku_series = df[sku_col].dropna().astype(str).str.strip()
        sku_series = sku_series[sku_series != ""]
        total_skus = int(sku_series.nunique())

    return {
        "inventory_kpi": {
            "total_skus": total_skus,
            "total_lpns": total_lpns,
            "utilization_pct": "78",
        },
    }


def _read_inventory_snapshot_capacity_from_excel(excel_path):
    """
    يقرأ من شيت Inventory_Snapshot:
    - Used_Space_m3 → Used (مجموع ثم نسبة مئوية).
    - Available_Space_m3 → Available (مجموع ثم نسبة مئوية).
    يرجع inventory_capacity_data: { used: نسبة Used %, available: نسبة Available % }.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        n = str(name).strip().lower().replace(" ", "").replace("_", "")
        if "inventorysnapshot" in n or "inventory_snapshot" in n:
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "inventory" in str(name).lower() and "snapshot" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    used_col = _col("Used_Space_m3", "Used Space m3", "UsedSpace_m3")
    avail_col = _col("Available_Space_m3", "Available Space m3", "AvailableSpace_m3")
    if not used_col or not avail_col:
        return None

    total_used = pd.to_numeric(df[used_col], errors="coerce").fillna(0).sum()
    total_avail = pd.to_numeric(df[avail_col], errors="coerce").fillna(0).sum()
    total = total_used + total_avail
    if total <= 0:
        return {"inventory_capacity_data": {"used": 78, "available": 22}}

    used_pct = round(100.0 * total_used / total, 1)
    available_pct = round(100.0 - used_pct, 1)
    return {
        "inventory_capacity_data": {
            "used": used_pct,
            "available": available_pct,
        },
    }


def _read_inventory_warehouse_table_from_excel(excel_path):
    """
    يقرأ من شيت Inventory_Snapshot جدول الـ Warehouse:
    - Warehouse من عمود Warehouse
    - SKUs من عمود Total_SKUs
    - Available Space من عمود Available_Space_m3
    - Utilization % من عمود Utilization_%
    كل صف كما هو من الشيت بدون جمع.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None
    sheet_name = None
    for name in xls.sheet_names:
        n = str(name).strip().lower().replace(" ", "").replace("_", "")
        if "inventorysnapshot" in n or "inventory_snapshot" in n:
            sheet_name = name
            break
    if not sheet_name:
        for name in xls.sheet_names:
            if "inventory" in str(name).lower() and "snapshot" in str(name).lower():
                sheet_name = name
                break
    if not sheet_name:
        return None
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception:
        return None
    if df.empty or len(df) < 1:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = {c.lower(): c for c in df.columns if c}

    def _col(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lower:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lower[col]
            if k.lower() in cols_lower:
                return cols_lower[k.lower()]
        return None

    warehouse_col = _col("Warehouse")
    total_skus_col = _col("Total_SKUs", "Total SKUs", "TotalSKUs")
    avail_space_col = _col("Available_Space_m3", "Available Space m3", "AvailableSpace_m3")
    util_col = _col("Utilization_%", "Utilization %", "UtilizationPct", "Utilization")
    if not warehouse_col:
        return None

    def _val(col, r):
        if not col or col not in r.index:
            return ""
        v = r[col]
        if pd.isna(v):
            return ""
        if isinstance(v, (int, float)):
            return str(int(v)) if v == int(v) else str(v)
        return str(v).strip()

    def _util_pct(col, r):
        if not col or col not in r.index:
            return ""
        v = r[col]
        if pd.isna(v):
            return ""
        try:
            num = float(v)
            if 0 <= num <= 1:
                return f"{round(num * 100, 2)}%"
            return f"{round(num, 2)}%"
        except (TypeError, ValueError):
            s = str(v).strip()
            return f"{s}%" if s and not s.endswith("%") else s

    rows = []
    for _, r in df.iterrows():
        warehouse = "" if pd.isna(r[warehouse_col]) else str(r[warehouse_col]).strip()
        rows.append({
            "warehouse": warehouse,
            "skus": _val(total_skus_col, r),
            "available_space": _val(avail_space_col, r),
            "utilization_pct": _util_pct(util_col, r),
        })
    if not rows:
        return None
    return {"inventory_warehouse_table": rows}


def _read_returns_region_table_from_excel(excel_path):
    """
    يبني returns_region_table من Inventory_Lots + Inventory_Snapshot:
    - Region من عمود Warehouse في Inventory_Lots (فلترة بالـ Warehouse).
    - SKUs: عدد القيم الفريدة لعمود SKU لكل Warehouse بعد الفلترة بالتاريخ.
    - Available: مجموع LPNs لكل Warehouse بعد الفلترة بـ Snapshot_Date (آخر تاريخ).
    - Utilization %: (LPNs للمنطقة والتاريخ) / Capacity_m3 من Inventory_Snapshot لنفس المنطقة، كنسبة مئوية.
    """
    try:
        xls = pd.ExcelFile(excel_path, engine="openpyxl")
    except Exception:
        return None

    def _find_sheet(*names):
        for want in names:
            want_n = want.lower().replace(" ", "").replace("_", "")
            for s in xls.sheet_names:
                if want_n in str(s).lower().replace(" ", "").replace("_", ""):
                    return s
        return None

    lots_sheet = _find_sheet("Inventory_Lots", "Inventory Lots")
    snapshot_sheet = _find_sheet("Inventory_Snapshot", "Inventory Snapshot")
    if not lots_sheet:
        return None

    try:
        df_lots = pd.read_excel(excel_path, sheet_name=lots_sheet, engine="openpyxl", header=0)
    except Exception:
        return None
    if df_lots.empty:
        return None

    df_lots.columns = [str(c).strip() for c in df_lots.columns]
    cols_lots = {c.lower(): c for c in df_lots.columns if c}

    def _col_lots(*keys):
        for k in keys:
            k_norm = k.lower().replace(" ", "").replace("_", "")
            for col in cols_lots:
                if col.replace(" ", "").replace("_", "") == k_norm:
                    return cols_lots[col]
        return None

    wh_col = _col_lots("Warehouse")
    sku_col = _col_lots("SKU", "Sku")
    lpns_col = _col_lots("LPNs", "LPN")
    snap_col = _col_lots("Snapshot_Date", "Snapshot Date", "SnapshotDate", "Date")
    if not wh_col or not snap_col:
        return None
    if not lpns_col:
        lpns_col = df_lots.columns[1] if len(df_lots.columns) > 1 else None
    if not lpns_col:
        return None

    df_lots["_date"] = pd.to_datetime(df_lots[snap_col], errors="coerce")
    df_lots = df_lots.dropna(subset=["_date"])
    if df_lots.empty:
        return None

    latest_date = df_lots["_date"].max()
    df_filtered = df_lots[df_lots["_date"] == latest_date].copy()

    capacity_by_warehouse = {}
    if snapshot_sheet:
        try:
            df_snap = pd.read_excel(excel_path, sheet_name=snapshot_sheet, engine="openpyxl", header=0)
            if not df_snap.empty:
                df_snap.columns = [str(c).strip() for c in df_snap.columns]
                snap_cols = {c.lower(): c for c in df_snap.columns if c}
                snap_wh = next((snap_cols[c] for c in snap_cols if "warehouse" in c.replace(" ", "").replace("_", "")), None)
                cap_col = next((snap_cols[c] for c in snap_cols if "capacity_m3" in c.replace(" ", "").replace("_", "") or ("capacity" in c and "m3" in c)), None)
                if not cap_col:
                    used_c = next((snap_cols[c] for c in snap_cols if "used_space" in c.replace(" ", "").replace("_", "")), None)
                    avail_c = next((snap_cols[c] for c in snap_cols if "available_space" in c.replace(" ", "").replace("_", "")), None)
                    if used_c and avail_c:
                        df_snap["_cap"] = pd.to_numeric(df_snap[used_c], errors="coerce").fillna(0) + pd.to_numeric(df_snap[avail_c], errors="coerce").fillna(0)
                        cap_col = "_cap"
                if snap_wh and cap_col:
                    for _, r in df_snap.iterrows():
                        w = r.get(snap_wh)
                        if pd.isna(w):
                            continue
                        w = str(w).strip()
                        if not w:
                            continue
                        c = r.get(cap_col)
                        if cap_col == "_cap":
                            val = c
                        else:
                            val = pd.to_numeric(c, errors="coerce")
                        if pd.notna(val) and val > 0:
                            capacity_by_warehouse[w] = float(val)
        except Exception:
            pass

    df_filtered["_lpns_num"] = pd.to_numeric(df_filtered[lpns_col], errors="coerce").fillna(0)
    rows = []
    for wh, grp in df_filtered.groupby(wh_col, dropna=False):
        wh_name = "" if pd.isna(wh) else str(wh).strip()
        skus = grp[sku_col].dropna().astype(str).str.strip() if sku_col else pd.Series(dtype=object)
        skus = skus[skus != ""].nunique() if not skus.empty else 0
        available = int(grp["_lpns_num"].sum())
        cap = capacity_by_warehouse.get(wh_name) or capacity_by_warehouse.get(wh)
        if cap and cap > 0:
            util = round(100.0 * available / cap, 2)
            utilization_pct = f"{util}%"
        else:
            utilization_pct = "—"
        rows.append({
            "region": wh_name,
            "skus": str(int(skus)) if isinstance(skus, (int, float)) else str(skus),
            "available": str(available),
            "utilization_pct": utilization_pct,
        })

    if not rows:
        return None
    return {"returns_region_table": rows}


def get_dashboard_tab_context(request):
    """
    يبني سياق تاب الداشبورد (نفس بيانات Dashboard view).
    إذا وُجدت الفيو في تطبيق dashboard أو inbound يتم استخدامها، وإلا يُرجع سياق افتراضي.
    """
    try:
        for app_label in ["dashboard", "inbound"]:
            try:
                view_module = __import__(f"{app_label}.views", fromlist=["DashboardView"])
                ViewClass = getattr(view_module, "DashboardView", None)
                if ViewClass is not None:
                    view = ViewClass()
                    view.request = request
                    view.object = None
                    return view.get_context_data()
            except (ImportError, AttributeError):
                continue
    except Exception:
        pass
    # سياق افتراضي عند عدم وجود الموديلات/الفيو (مع داتا وهمية لـ Inbound)
    return {
        "title": "Dashboard",
        "breadcrumb": {"title": "Healthcare Dashboard", "parent": "Dashboard", "child": "Default"},
        "is_admin": False,
        "is_employee": False,
        "inbound_data": [],
        "transportation_outbound_data": [],
        "wh_outbound_data": [],
        "returns_data": [],
        "expiry_data": [],
        "damage_data": [],
        "inventory_data": [],
        "pallet_location_availability_data": [],
        "hse_data": [],
        "number_of_shipments": 0,
        "total_vehicles_daily": 0,
        "total_pallets": 0,
        "total_pending_shipments": 0,
        "total_number_of_shipments": 0,
        "total_quantity": 0,
        "total_number_of_line": 0,
        # Inbound KPI + داتا شارت Pending Shipments (من الديكت في الفيو)
        "inbound_kpi": INBOUND_DEFAULT_KPI.copy(),
        "pending_shipments": list(INBOUND_DEFAULT_PENDING_SHIPMENTS),
        "shipment_data": {"bulk": 0, "loose": 0, "cold": 0, "frozen": 0, "ambient": 0},
        "wh_total_released_order": 0,
        "wh_total_piked_order": 0,
        "wh_total_pending_pick_orders": 0,
        "wh_total_number_of_PODs_collected_on_time": 0,
        "wh_total_number_of_PODs_collected_Late": 0,
        "total_orders_items_returned": 0,
        "total_number_of_return_items_orders_updated_on_time": 0,
        "total_number_of_return_items_orders_updated_late": 0,
        "total_SKUs_expired": 0,
        "total_expired_SKUS_disposed": 0,
        "total_nearly_expired_1_to_3_months": 0,
        "total_nearly_expired_3_to_6_months": 0,
        "total_SKUs_expired_calculated": 0,
        "Total_QTYs_Damaged_by_WH": 0,
        "Total_Number_of_Damaged_during_receiving": 0,
        "Total_Araive_Damaged": 0,
        "Total_Locations_match": 0,
        "Total_Locations_not_match": 0,
        "last_shipment": None,
        "Total_Storage_Pallet": 0,
        "Total_Storage_pallet_empty": 0,
        "Total_Storage_Bin": 0,
        "Total_occupied_pallet_location": 0,
        "Total_Storage_Bin_empty": 0,
        "Total_occupied_Bin_location": 0,
        "Total_Incidents_on_the_side": 0,
        "total_no_of_employees": 0,
        "admin_data": [],
        "user_type": "Unknown",
        "years": [],
        "months": list(calendar_module.month_name)[1:],
        "days": list(range(1, 32)),
        "returns_region_table": [
            {"region": "Main warehouse", "skus": "2,538", "available": "1118", "utilization_pct": "71%"},
            {"region": "Dammam DC", "skus": "501", "available": "200", "utilization_pct": "—"},
            {"region": "Riyadh DC", "skus": "3,996", "available": "209", "utilization_pct": "—"},
            {"region": "Jeddah DC", "skus": "7,996", "available": "300", "utilization_pct": "—"},
        ],
    }


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(
    cache_control(no_cache=True, no_store=True, must_revalidate=True, max_age=0),
    name="dispatch",
)
class UploadExcelViewRoche(View):
    template_name = "index.html"
    excel_file_name = "all sheet.xlsm"
    correct_code = "1234"

    # تابات تحذف من الداشبورد (أضف أسماء الشيتات كما هي في الإكسل)
    EXCLUDE_TABS = []  # مثال: ["Sheet2", "تقارير قديمة", "Backup"]
    # أو: اعرض تابات معينة فقط (لو ضعت قائمة هنا، التابات الأخرى كلها تختفي)
    INCLUDE_ONLY_TABS = (
        None  # مثال: ["Overview", "Dock to stock", "Order General Information"]
    )
    # تابات افتراضية نعرضها بدون الاعتماد على شيت مباشر
    DASHBOARD_TAB_NAME = "Dashboard"
    # عرض تاب Warehouse فقط (كروت المستودعات من الأدمن) وإخفاء كل التابات الأخرى
    USE_WAREHOUSE_TAB_ONLY = True
    DEFAULT_EXCEL_FILENAMES = [
        "all sheet.xlsm",
        "all sheet.xlsx",
        "all_sheet.xlsm",
        "all_sheet.xlsx",
    ]

    MONTH_LOOKUP = {}
    MONTH_PREFIXES = set()
    for idx in range(1, 13):
        abbr = month_abbr[idx]
        full = month_name[idx]
        if abbr:
            MONTH_LOOKUP[abbr.lower()] = abbr
            MONTH_PREFIXES.add(abbr.lower())
        if full:
            MONTH_LOOKUP[full.lower()] = abbr
        MONTH_LOOKUP[str(idx)] = abbr
        MONTH_LOOKUP[f"{idx:02d}"] = abbr
    MONTH_LOOKUP["sept"] = "Sep"

    AGGREGATE_COLUMN_KEYWORDS = {
        "total",
        "grand total",
        "overall total",
        "sum",
        "ytd",
        "y.t.d.",
        "avg",
        "average",
        "target",
        "target (%)",
        "target %",
        "target%",
        "cumulative",
    }

    # اسم الملف الافتراضي إذا وُضع في excel_uploads بدون رفع (مثلاً all sheet.xlsm)
    def get_excel_path(self):
        folder_path = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
        os.makedirs(folder_path, exist_ok=True)
        priority_files = ["latest.xlsm", "latest.xlsx"] + self.DEFAULT_EXCEL_FILENAMES
        for name in priority_files:
            path = os.path.join(folder_path, name)
            if os.path.exists(path):
                return path
        return os.path.join(folder_path, "latest.xlsx")

    def get_uploaded_file_path(self, request):
        folder = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
        os.makedirs(folder, exist_ok=True)

        # أولوية: ملف الجلسة ثم latest.xlsm ثم latest.xlsx ثم all sheet
        if request:
            saved_path = request.session.get("uploaded_excel_path")
            if saved_path and os.path.exists(saved_path):
                return saved_path
        priority_files = ["latest.xlsm", "latest.xlsx"] + self.DEFAULT_EXCEL_FILENAMES
        for name in priority_files:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                if request:
                    try:
                        request.session["uploaded_excel_path"] = path
                        request.session.save()
                    except Exception:
                        pass
                return path
        return os.path.join(folder, "latest.xlsx")

    @staticmethod
    def safe_format_value(val):
        if pd.isna(val) or val is pd.NaT:
            return ""
        elif isinstance(val, pd.Timestamp):
            if val.tzinfo is not None:
                val = val.tz_convert(None)
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return val

    # ----------------------------------------------------
    # 🔧 Helper methods for month normalization & filtering
    # ----------------------------------------------------
    def normalize_month_label(self, month_value):
        if month_value is None:
            return None

        raw = str(month_value).strip()
        if not raw:
            return None

        lower = raw.lower()
        if lower in self.MONTH_LOOKUP:
            return self.MONTH_LOOKUP[lower]

        first_three = lower[:3]
        if first_three in self.MONTH_LOOKUP:
            return self.MONTH_LOOKUP[first_three]

        try:
            parsed = pd.to_datetime(raw, errors="coerce")
            if not pd.isna(parsed):
                return parsed.strftime("%b")
        except Exception:
            pass

        return raw[:3].capitalize()

    def _value_matches_month(self, value, month_lower):
        if value is None:
            return False
        normalized = self.normalize_month_label(value)
        return normalized is not None and normalized.lower() == month_lower

    def _column_matches_month(self, column, month_lower):
        if column is None:
            return False
        col_lower = str(column).strip().lower()
        if col_lower == month_lower:
            return True
        if col_lower.startswith(month_lower + " "):
            return True
        if col_lower.endswith(" " + month_lower):
            return True
        if col_lower.startswith(month_lower + "-") or col_lower.endswith(
            "-" + month_lower
        ):
            return True
        if col_lower.startswith(month_lower + "/") or col_lower.endswith(
            "/" + month_lower
        ):
            return True
        if col_lower.startswith(month_lower + "("):
            return True
        if col_lower.split(" ")[0] == month_lower:
            return True
        if col_lower.replace(".", "").startswith(month_lower):
            return True
        return False

    def _is_month_column(self, column):
        if column is None:
            return False
        col_lower = str(column).strip().lower()
        if col_lower in self.MONTH_LOOKUP:
            return True
        first_three = col_lower[:3]
        if first_three in self.MONTH_PREFIXES:
            return True
        col_split = col_lower.replace("/", " ").replace("-", " ").split()
        if col_split and col_split[0][:3] in self.MONTH_PREFIXES:
            return True
        return False

    def _is_aggregate_column(self, column):
        if column is None:
            return False
        col_lower = str(column).strip().lower()
        if col_lower in self.AGGREGATE_COLUMN_KEYWORDS:
            return True
        compact = col_lower.replace(" ", "")
        if compact in {"target%", "target(%)", "total%"}:
            return True
        if col_lower.isdigit():
            try:
                if int(col_lower) >= 1900:
                    return True
            except ValueError:
                pass
        return False

    def _append_missing_month_messages(self, tab_data, missing_months):
        if not missing_months:
            return

        message_table = {
            "title": "Missing Months",
            "columns": ["Message"],
            "data": [
                {"Message": f"No data available for month {month}."}
                for month in missing_months
            ],
        }

        if isinstance(tab_data.get("sub_tables"), list):
            tab_data["sub_tables"] = [
                sub
                for sub in tab_data["sub_tables"]
                if sub.get("title") != "Missing Months"
            ]
            tab_data["sub_tables"].append(message_table)
            return

        # في حال كان التاب عبارة عن جدول واحد فقط، نحوله إلى sub_tables
        columns = tab_data.pop("columns", None)
        data_rows = tab_data.pop("data", None)
        if columns is not None and data_rows is not None:
            existing_table = {
                "title": tab_data.get("name", "Data"),
                "columns": columns,
                "data": data_rows,
            }
            tab_data["sub_tables"] = [existing_table, message_table]
        else:
            tab_data["sub_tables"] = [message_table]

    def apply_month_filter_to_tab(
        self, tab_data, selected_month=None, selected_months=None
    ):
        if not tab_data:
            return None

        selected_months_norm = []
        if selected_months:
            if isinstance(selected_months, str):
                selected_months = [selected_months]
            seen = set()
            for month in selected_months:
                norm = self.normalize_month_label(month)
                if norm and norm.lower() not in seen:
                    seen.add(norm.lower())
                    selected_months_norm.append(norm)

        month_norm = self.normalize_month_label(selected_month)
        month_filters = []
        if selected_months_norm:
            month_filters = selected_months_norm
        elif month_norm:
            month_filters = [month_norm]
        else:
            tab_data.pop("selected_month", None)
            tab_data.pop("selected_months", None)
            return None

        month_filters_lower = [m.lower() for m in month_filters]
        matched_months = set()

        def matches_any_month(column):
            if not month_filters_lower:
                return False
            for month_lower in month_filters_lower:
                if self._column_matches_month(column, month_lower):
                    matched_months.add(month_lower)
                    return True
            return False

        def value_matches_month(value):
            if not month_filters_lower:
                return False
            normalized = self.normalize_month_label(value)
            if not normalized:
                return False
            val_lower = normalized.lower()
            if val_lower in month_filters_lower:
                matched_months.add(val_lower)
                return True
            return False

        def filter_columns(columns):
            filtered = []
            for col in columns:
                if self._is_month_column(col):
                    if matches_any_month(col):
                        filtered.append(col)
                elif self._is_aggregate_column(col) and not self._column_matches_month(
                    col,
                    month_filters_lower[0] if month_filters_lower else "",
                ):
                    continue
                else:
                    filtered.append(col)
            return filtered if filtered else columns

        def filter_rows(data_rows, columns):
            if not data_rows:
                return data_rows

            month_cols = [
                col
                for col in columns
                if str(col).strip().lower() in {"month", "month name", "monthname"}
            ]
            if not month_cols:
                return data_rows

            month_col = month_cols[0]
            scoped_rows = []
            for row in data_rows:
                value = None
                if isinstance(row, dict):
                    value = row.get(month_col)
                if value_matches_month(value):
                    scoped_rows.append(row)
            return scoped_rows if scoped_rows else data_rows

        if "sub_tables" in tab_data and isinstance(tab_data["sub_tables"], list):
            for sub in tab_data["sub_tables"]:
                if not isinstance(sub, dict):
                    continue
                # ✅ الحفاظ على chart_data في sub_table
                sub_chart_data = sub.get("chart_data", [])

                columns = sub.get("columns", [])
                if columns:
                    filtered_columns = filter_columns(columns)
                    if sub.get("data"):
                        new_data = []
                        for row in sub["data"]:
                            if isinstance(row, dict):
                                new_row = {
                                    col: row.get(col, "") for col in filtered_columns
                                }
                            else:
                                new_row = row
                            new_data.append(new_row)
                        sub["data"] = filter_rows(new_data, filtered_columns)
                    sub["columns"] = filtered_columns

                # ✅ إعادة إضافة chart_data إلى sub_table بعد التعديل (حتى لو كانت فارغة)
                sub["chart_data"] = sub_chart_data
        else:
            columns = tab_data.get("columns", [])
            data_rows = tab_data.get("data", [])
            if columns:
                filtered_columns = filter_columns(columns)
                if data_rows:
                    new_rows = []
                    for row in data_rows:
                        if isinstance(row, dict):
                            new_row = {
                                col: row.get(col, "") for col in filtered_columns
                            }
                        else:
                            new_row = row
                        new_rows.append(new_row)
                    tab_data["data"] = filter_rows(new_rows, filtered_columns)
                tab_data["columns"] = filtered_columns

        if "chart_data" in tab_data and isinstance(tab_data["chart_data"], list):
            for chart in tab_data["chart_data"]:
                if not isinstance(chart, dict):
                    continue
                points = chart.get("dataPoints")
                if not points:
                    continue
                filtered_points = []
                for point in points:
                    label_norm = self.normalize_month_label(point.get("label"))
                    if label_norm and label_norm.lower() in month_filters_lower:
                        matched_months.add(label_norm.lower())
                        filtered_points.append(point)
                if filtered_points:
                    chart["dataPoints"] = filtered_points

        if selected_months_norm:
            tab_data["selected_months"] = selected_months_norm
            return selected_months_norm[0]
        else:
            tab_data["selected_month"] = month_filters[0]
            return month_filters[0]

    @method_decorator(cache_control(max_age=3600, public=True), name="get")
    def get(self, request):
        # --------------------------
        # طلبات AJAX للتابات (حتى مع USE_WAREHOUSE_TAB_ONLY): إرجاع JSON وليس الصفحة الكاملة
        # --------------------------
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            selected_tab = (request.GET.get("tab") or "").strip().lower()
            if selected_tab == "meeting points":
                return self.meeting_points_tab(request)
            if getattr(self, "USE_WAREHOUSE_TAB_ONLY", False) and selected_tab == "warehouse":
                wh_result = self.warehouse_tab(request)
                return JsonResponse(wh_result, safe=False)
            if selected_tab == "recommendation":
                recommendations = context_helpers.get_recommendations_list()
                weekly_tracker_rows = context_helpers.get_weekly_project_tracker_list()
                progress_status_rows = context_helpers.get_progress_status_list()
                potential_challenges_rows = context_helpers.get_potential_challenges_list()
                recommendation_html = render_to_string(
                    "components/ui-kits/tab-bootstrap/components/recommendation-cards.html",
                    {
                        "recommendations": recommendations,
                        "weekly_tracker_rows": weekly_tracker_rows,
                        "progress_status_rows": progress_status_rows,
                        "potential_challenges_rows": potential_challenges_rows,
                        "dashboard_theme": context_helpers.get_dashboard_theme_dict(),
                    },
                    request=request,
                )
                return JsonResponse({"detail_html": recommendation_html}, safe=False)
            if selected_tab == "project tracker":
                project_type_filter = request.GET.get("project_type", "").strip().lower()
                if project_type_filter not in ("idea", "automation"):
                    project_type_filter = None
                project_tracker_items = context_helpers.get_project_tracker_list(project_type=project_type_filter)
                project_tracker_html = render_to_string(
                    "components/ui-kits/tab-bootstrap/components/project-tracker-cards.html",
                    {"project_tracker_items": project_tracker_items},
                    request=request,
                )
                return JsonResponse({"detail_html": project_tracker_html}, safe=False)

        # فلتر Meeting Points: طلب بـ status فقط (بدون tab) — نرجع JSON حتى بدون هيدر AJAX
        if request.GET.get("status") and not request.GET.get("tab"):
            status_filter = request.GET.get("status", "all")
            meeting_html = self.get_meeting_points_section_html(
                request, status_filter
            )
            meeting_points = MeetingPoint.objects.all()
            done_count = meeting_points.filter(is_done=True).count()
            total_count = meeting_points.count()
            return JsonResponse(
                {
                    "meeting_section_html": meeting_html,
                    "detail_html": meeting_html,
                    "done_count": done_count,
                    "total_count": total_count,
                },
                safe=False,
            )

        # --------------------------
        # وضع Warehouse فقط: لا نفتح الإكسل ولا نستدعي أي دوال ثقيلة — تحميل سريع
        # --------------------------
        if getattr(self, "USE_WAREHOUSE_TAB_ONLY", False):
            meeting_points = MeetingPoint.objects.all().order_by("is_done", "-created_at")
            render_context = {
                "data_is_uploaded": True,
                "months": [],
                "excel_tabs": [],
                "active_tab": "warehouse",
                "tab_summaries": [],
                "form": ExcelUploadForm(),
                "meeting_points": meeting_points,
                "done_count": meeting_points.filter(is_done=True).count(),
                "total_count": meeting_points.count(),
                "all_tab_data": {"detail_html": ""},
                "raw_tab_data": None,
                "warehouse_overview": context_helpers.get_warehouse_overview_list(),
                "clerk_interview_rows": context_helpers.get_clerk_interview_list(),
                "dashboard_theme": context_helpers.get_dashboard_theme_dict(),
                "phases_sections": context_helpers.get_phases_sections_list(),
                "recommendations": context_helpers.get_recommendations_list(),
                "weekly_tracker_rows": context_helpers.get_weekly_project_tracker_list(),
                "progress_status_rows": context_helpers.get_progress_status_list(),
                "potential_challenges_rows": context_helpers.get_potential_challenges_list(),
                "project_tracker_items": context_helpers.get_project_tracker_list(
                    project_type=request.GET.get("project_type") or None
                ),
            }
            return render(request, self.template_name, render_context)

        # --------------------------
        # مسار الإكسل (عند إيقاف USE_WAREHOUSE_TAB_ONLY)
        # --------------------------
        print("🟢 [GET] Loading dashboard with Excel tabs")
        cache.clear()
        excel_path = self.get_uploaded_file_path(request) or self.get_excel_path()
        data_is_uploaded = os.path.exists(excel_path)

        if not data_is_uploaded:
            form = ExcelUploadForm()
            return render(
                request, self.template_name, {"form": form, "data_is_uploaded": False}
            )

        # --------------------------
        # Read request parameters
        # --------------------------
        selected_tab = request.GET.get("tab", "").lower() or "all"
        selected_month = request.GET.get("month", "").strip()
        selected_quarter = request.GET.get("quarter", "").strip()
        action = request.GET.get("action", "").lower()
        status = request.GET.get("status")

        print(f"🔹 Selected tab: {selected_tab}")
        print(f"🔹 Selected month: {selected_month}")
        print(f"🔹 Selected quarter: {selected_quarter}")
        print(f"🔹 Action: {action}")

        print("🛰️ Quarter AJAX Triggered:", request.GET.get("quarter"))

        quarter_months = []
        quarter_error = None
        if selected_quarter:
            try:
                quarter_months = self._resolve_quarter_months(selected_quarter)
            except ValueError as exc:
                quarter_error = str(exc)

        effective_month = None if quarter_months else selected_month

        if action == "meeting_points_tab":
            return self.meeting_points_tab(request)

        # ✅ إذا كان الطلب AJAX وبه status فقط (بدون tab)، نعيد قسم Meeting Points فقط
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            and request.GET.get("status")
            and not request.GET.get("tab")
        ):
            status_filter = request.GET.get("status", "all")
            meeting_html = self.get_meeting_points_section_html(
                request, status_filter
            )
            meeting_points = MeetingPoint.objects.all()
            done_count = meeting_points.filter(is_done=True).count()
            total_count = meeting_points.count()
            return JsonResponse(
                {
                    "meeting_section_html": meeting_html,
                    "detail_html": meeting_html,
                    "done_count": done_count,
                    "total_count": total_count,
                },
                safe=False,
            )

        if action == "export_excel":
            if quarter_error:
                return HttpResponse(quarter_error, status=400)
            return self.export_dashboard_excel(
                request,
                selected_month=effective_month,
                selected_months=quarter_months or None,
            )

        # ====================== طلبات AJAX ======================
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            print("⚡ [AJAX Request] Received request")

            if quarter_error:
                return JsonResponse({"error": quarter_error})

            tab_filter_map = {
                "warehouse": lambda: self.warehouse_tab(request),
                "dashboard": lambda: self.dashboard_tab(request),
                "all": lambda: self.filter_all_tabs(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "return & refusal": lambda: self.filter_rejections_combined(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "rejections": lambda: self.filter_rejections_combined(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "inbound": lambda: self.filter_dock_to_stock_combined(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "outbound": lambda: self.filter_total_lead_time_performance(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "total lead time performance": lambda: self.filter_total_lead_time_performance(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "pods update": lambda: self.filter_pods_update(
                    request, effective_month
                ),
                "meeting points": lambda: self.meeting_points_tab(request),
                "project tracker": lambda: self.project_tracker_tab(request),
                "expiry": lambda: self.filter_expiry(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
                "Expiry": lambda: self.filter_expiry(
                    request,
                    effective_month,
                    selected_months=quarter_months or None,
                ),
            }

            # Iterate available tab filters
            for key, func in tab_filter_map.items():
                if key in selected_tab:
                    print(f"📂 Executing tab filter: {key}")
                    try:
                        result = func()

                        # Direct HttpResponse/JsonResponse
                        if isinstance(result, HttpResponse):
                            print(
                                "ℹ️ Filter returned HttpResponse/JsonResponse; returning as-is."
                            )
                            return result

                        # Dict/list response → JSON
                        if isinstance(result, (dict, list)):
                            return JsonResponse(result, safe=False)

                        # String response (likely HTML)
                        if isinstance(result, str):
                            return JsonResponse({"detail_html": result}, safe=False)

                        # Fallback conversion
                        return JsonResponse({"detail_html": str(result)}, safe=False)

                    except Exception as e:
                        import traceback

                        print("❌ Error while executing tab filter:", key)
                        traceback.print_exc()
                        return JsonResponse(
                            {"error": f"Error in '{key}': {str(e)}"},
                            status=200,
                        )

            # Warehouse tab (كروت المستودعات من الأدمن)
            if selected_tab == "warehouse":
                print("🔹 Loading Warehouse tab")
                wh_result = self.warehouse_tab(request)
                return JsonResponse(wh_result, safe=False)

            # All-in-One (never cached)
            if selected_tab == "all":
                print("🔹 Loading All-in-One tab")
                all_result = self.filter_all_tabs(
                    request=request,
                    selected_month=effective_month,
                    selected_months=quarter_months or None,
                )
                return JsonResponse(all_result, safe=False)

            # Remaining tabs
            if selected_tab in ["rejections", "return & refusal"]:
                return JsonResponse(
                    self.filter_rejections_combined(
                        request,
                        effective_month,
                        selected_months=quarter_months or None,
                    ),
                    safe=False,
                )
            # airport / seaport tabs تم إلغاؤها
            elif selected_tab in [
                "outbound",
                "total lead time performance",
                "total lead time preformance",
            ]:
                return JsonResponse(
                    self.filter_total_lead_time_performance(
                        request,
                        effective_month,
                        selected_months=quarter_months or None,
                    ),
                    safe=False,
                )
            elif selected_tab == "total lead time preformance -r":
                return JsonResponse(
                    self.filter_total_lead_time_roche(request, effective_month),
                    safe=False,
                )
            # data logger tab تم إلغاؤه
            elif "dock to stock - roche" in selected_tab:
                return JsonResponse(
                    self.filter_dock_to_stock_roche(request, effective_month),
                    safe=False,
                )
            elif (selected_tab or "").lower() == "inbound":
                return JsonResponse(
                    self.filter_dock_to_stock_combined(
                        request,
                        effective_month,
                        selected_months=quarter_months or None,
                    ),
                    safe=False,
                )
            elif selected_tab == "pods update":
                return JsonResponse(
                    self.filter_pods_update(request, effective_month), safe=True
                )
            elif "rejection" in selected_tab:
                return JsonResponse(
                    self.filter_rejection_data(request, effective_month), safe=False
                )
            elif "dock to stock" in selected_tab:
                return JsonResponse(
                    self.filter_dock_to_stock_combined(
                        request,
                        effective_month,
                        selected_months=quarter_months or None,
                    ),
                    safe=False,
                )
            elif "meeting points" in selected_tab:
                return self.meeting_points_tab(request)
            elif selected_tab:
                raw_data = self.render_raw_sheet(request, selected_tab)
                return JsonResponse(raw_data, safe=False)
            else:
                return JsonResponse({"error": "⚠️ Please select a tab first."})

        # ====================== الطلب العادي ======================
        try:
            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            all_sheets = [s.strip() for s in xls.sheet_names]

            MERGE_SHEETS = ["Urgent orders details", "Outbound details"]
            REJECTION_SHEETS = ["Rejection", "Rejection breakdown"]
            AIRPORT_SHEETS = ["Airport Clearance - Roche", "Airport Clearance - 3PL"]
            SEAPORT_SHEETS = ["Seaport clearance - 3pl", "Seaport clearance - Roche"]
            TOTAL_LEADTIME_SHEETS = [
                "Total lead time preformance",
                "Total lead time preformance -R",
            ]
            DOCK_TO_STOCK_SHEETS = ["Dock to stock", "Dock to stock - Roche"]
            # التابات اللي تحب تاخدها من الداشبورد: عدّل هنا (أسماء كما في الإكسل)
            EXCLUDE_SHEETS_BASE = ["Sheet2"]
            # لو حابب تحذف تابات إضافية: زود أسمائهم هنا (بالضبط كما في الإكسل)
            EXCLUDE_SHEETS_EXTRA = getattr(
                self.__class__, "EXCLUDE_TABS", []
            )  # أو عدّل EXCLUDE_TABS في أول الكلاس
            EXCLUDE_SHEETS = list(EXCLUDE_SHEETS_BASE) + list(EXCLUDE_SHEETS_EXTRA)

            include_only = getattr(self.__class__, "INCLUDE_ONLY_TABS", None)
            if include_only:
                # عرض التابات المذكورة فقط (الاسم كما في الإكسل)
                include_set = {s.strip() for s in include_only}
                filtered_tabs = [t for t in all_sheets if t in include_set]
            else:
                filtered_tabs = [
                    t
                    for t in all_sheets
                    if t not in MERGE_SHEETS
                    and t not in REJECTION_SHEETS
                    and t not in AIRPORT_SHEETS
                    and t not in SEAPORT_SHEETS
                    and t not in TOTAL_LEADTIME_SHEETS
                    and t not in DOCK_TO_STOCK_SHEETS
                    and t not in EXCLUDE_SHEETS
                ]

            virtual_tabs = [
                self.DASHBOARD_TAB_NAME,
                "Inbound",
                "Outbound",
                "Return & Refusal",
                "PODs update",
                "Expiry",
                "Meeting Points & Action",
            ]
            if include_only:
                include_set_v = {s.strip() for s in include_only}
                filtered_tabs += [v for v in virtual_tabs if v in include_set_v]
            else:
                filtered_tabs += virtual_tabs

            ordered_tabs = [
                self.DASHBOARD_TAB_NAME,
                "Inbound",
                "Outbound",
                "Return & Refusal",
                "PODs update",
                "Expiry",
                "Meeting Points & Action",
            ]

            filtered_tabs = [tab for tab in ordered_tabs if tab in filtered_tabs]
            excel_tabs = [{"original": name, "display": name} for name in filtered_tabs]

        except Exception as e:
            print(f"⚠️ [ERROR] تعذر قراءة الشيتات من الملف: {e}")
            excel_tabs = []

        # ======================================================
        # 🗓️ استخراج كل الشهور من جميع الشيتات الممكنة
        # ======================================================
        all_months = set()
        try:
            for sheet in xls.sheet_names:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet, engine="openpyxl")
                    df.columns = df.columns.str.strip().str.title()
                    possible_date_cols = [
                        c
                        for c in df.columns
                        if "date" in c.lower() or "month" in c.lower()
                    ]
                    if not possible_date_cols:
                        continue
                    col = possible_date_cols[0]
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                    df["MonthName"] = df[col].dt.strftime("%b")
                    all_months.update(df["MonthName"].dropna().unique().tolist())
                except Exception as inner_e:
                    continue

            all_months = sorted(
                all_months, key=lambda m: pd.to_datetime(m, format="%b")
            )
            print("📅 [INFO] الشهور المستخرجة من كل الشيتات:", all_months)
        except Exception as e:
            print("⚠️ [ERROR] أثناء استخراج الشهور:", e)
            all_months = []

        meeting_points = MeetingPoint.objects.all().order_by("is_done", "-created_at")
        done_count = meeting_points.filter(is_done=True).count()
        total_count = meeting_points.count()

        # وضع تاب Warehouse فقط: تاب واحد وعرض الكروت من الأدمن
        if getattr(self, "USE_WAREHOUSE_TAB_ONLY", False):
            excel_tabs = []
            selected_tab = "warehouse"
            data_is_uploaded = True
            warehouse_overview = context_helpers.get_warehouse_overview_list()
            clerk_interview_rows = context_helpers.get_clerk_interview_list()
            dashboard_theme = context_helpers.get_dashboard_theme_dict()
            phases_sections = context_helpers.get_phases_sections_list()
        else:
            data_is_uploaded = True
            warehouse_overview = []
            clerk_interview_rows = []
            dashboard_theme = context_helpers.get_dashboard_theme_dict()
            phases_sections = []

        all_tab_data = self.filter_all_tabs(
            request=request, selected_month=selected_month or None
        )

        render_context = {
            "data_is_uploaded": data_is_uploaded,
            "months": all_months,
            "excel_tabs": excel_tabs,
            "active_tab": selected_tab or "all",
            "tab_summaries": [],
            "form": ExcelUploadForm(),
            "meeting_points": meeting_points,
            "done_count": done_count,
            "total_count": total_count,
            "all_tab_data": all_tab_data,
            "raw_tab_data": None,
            "warehouse_overview": warehouse_overview,
            "clerk_interview_rows": clerk_interview_rows,
            "dashboard_theme": dashboard_theme,
            "recommendations": context_helpers.get_recommendations_list(),
            "weekly_tracker_rows": context_helpers.get_weekly_project_tracker_list(),
            "progress_status_rows": context_helpers.get_progress_status_list(),
            "potential_challenges_rows": context_helpers.get_potential_challenges_list(),
            "project_tracker_items": context_helpers.get_project_tracker_list(
                project_type=request.GET.get("project_type") or None
            ),
        }
        if (selected_tab or "").lower() == "dashboard":
            try:
                dashboard_ctx = self._get_dashboard_include_context(request)
                render_context.update(dashboard_ctx)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"⚠️ [Dashboard include context] {e}")

        return render(request, self.template_name, render_context)

    def post(self, request):
        print("📥 [DEBUG] تم استدعاء post()")  # ✅ بداية الدالة

        entered_code = request.POST.get("upload_code", "").strip()
        print(f"🔑 [DEBUG] الكود المدخل: {entered_code}")

        # ✅ التحقق من الكود
        if entered_code != self.correct_code:
            print("❌ [DEBUG] الكود غير صحيح!")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "❌ Invalid code. Please try again."}, status=403
                )
            messages.error(request, "❌ Invalid code. Please try again.")
            return redirect(request.path)

        # ✅ التحقق من الملف المرفوع
        form = ExcelUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            print("⚠️ [DEBUG] النموذج غير صالح أو لم يتم رفع ملف.")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "⚠️ Please select an Excel file."}, status=400
                )
            return render(
                request, self.template_name, {"form": form, "data_is_uploaded": False}
            )

        # ✅ حفظ الملف (يدعم .xlsx و .xlsm مثل all sheet.xlsm)
        excel_file = form.cleaned_data["excel_file"]
        folder_path = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
        os.makedirs(folder_path, exist_ok=True)
        file_name = getattr(excel_file, "name", "") or ""
        is_dashboard_file = _is_dashboard_excel_filename(file_name)

        if is_dashboard_file:
            # ✅ ملف الداشبورد (شيت تاني): Aramco_Tamer3PL_KPI_Dashboard.xlsx — للتاب Dashboard فقط
            file_path = os.path.join(folder_path, DASHBOARD_EXCEL_FILENAME)
            print(f"📊 [DEBUG] رفع ملف الداشبورد: {file_name} → {file_path}")
        else:
            # ✅ الملف الرئيسي (all_sheet / latest) — لباقي التابات
            ext = os.path.splitext(file_name)[1] or ".xlsx"
            if ext.lower() not in (".xlsx", ".xlsm"):
                ext = ".xlsx"
            file_path = os.path.join(folder_path, "latest" + ext)

        try:
            if not is_dashboard_file:
                # ✅ حذف أي ملف latest قديم (xlsx أو xlsm) لتفادي بقاء ملف بالامتداد الآخر
                for old_name in ("latest.xlsx", "latest.xlsm"):
                    old_path = os.path.join(folder_path, old_name)
                    if os.path.exists(old_path):
                        try:
                            os.chmod(old_path, 0o644)
                            os.remove(old_path)
                            print(f"🗑️ [DEBUG] تم حذف الملف القديم: {old_path}")
                        except Exception as e:
                            print(f"⚠️ [DEBUG] تحذير حذف {old_name}: {e}")
            if os.path.exists(file_path):
                try:
                    os.chmod(file_path, 0o644)
                    os.remove(file_path)
                    print(f"🗑️ [DEBUG] تم حذف الملف القديم: {file_path}")
                except PermissionError as pe:
                    print(
                        f"⚠️ [DEBUG] تحذير: لا يمكن حذف الملف القديم (PermissionError): {pe}"
                    )
                    temp_path = os.path.join(folder_path, "temp_upload.xlsx")
                    with open(temp_path, "wb+") as destination:
                        for chunk in excel_file.chunks():
                            destination.write(chunk)
                    try:
                        os.replace(temp_path, file_path)
                        print(f"✅ [DEBUG] تم استبدال الملف باستخدام os.replace")
                    except Exception as replace_error:
                        print(
                            f"⚠️ [DEBUG] تحذير: لا يمكن استبدال الملف: {replace_error}"
                        )
                        file_path = temp_path
                except Exception as delete_error:
                    print(f"⚠️ [DEBUG] تحذير: خطأ في حذف الملف القديم: {delete_error}")

            # ✅ حفظ الملف الجديد
            with open(file_path, "wb+") as destination:
                for chunk in excel_file.chunks():
                    destination.write(chunk)

            try:
                os.chmod(file_path, 0o644)
            except Exception as chmod_error:
                print(f"⚠️ [DEBUG] تحذير: لا يمكن تغيير صلاحيات الملف: {chmod_error}")

            print(f"✅ [DEBUG] تم حفظ الملف بنجاح في: {file_path}")

            # ✅ حفظ المسار في الجلسة حسب نوع الملف (داشبورد أو رئيسي)
            if is_dashboard_file:
                request.session["dashboard_excel_path"] = file_path
                print(f"💾 [DEBUG] تم حفظ مسار ملف الداشبورد في الجلسة: {file_path}")
            else:
                request.session["uploaded_excel_path"] = file_path
                print(f"💾 [DEBUG] تم حفظ مسار الملف الرئيسي في الجلسة: {file_path}")
            request.session.save()

            # ✅ مسح الكاش بعد رفع ملف جديد
            try:
                cache.clear()
                print(f"🗑️ [DEBUG] تم مسح الكاش")
            except Exception as cache_error:
                print(f"⚠️ [DEBUG] تحذير: لا يمكن مسح الكاش: {cache_error}")

            # ✅ إرجاع response
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": True, "message": "✅ File uploaded successfully!"}
                )
            messages.success(request, "✅ File uploaded successfully!")
            return redirect(request.path)
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            print(f"❌ [DEBUG] خطأ في حفظ الملف: {e}")
            print(f"❌ [DEBUG] Traceback:\n{error_trace}")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": f"❌ Error saving file: {str(e)}"}, status=500
                )
            messages.error(request, f"❌ Error saving file: {str(e)}")
            return redirect(request.path)

    def export_dashboard_excel(
        self, request, selected_month=None, selected_months=None
    ):
        """
        تصدير الملف الأصلي المرفوع (Roche KPI new.xlsx) فقط مع الحفاظ على الألوان والتنسيق
        """
        from openpyxl import load_workbook

        # 📂 البحث عن الملف الأصلي "Roche KPI new.xlsx" في مجلد media
        folder_path = os.path.join(settings.MEDIA_ROOT, "excel_uploads")
        original_excel_path = os.path.join(folder_path, "Roche KPI new.xlsx")

        # إذا لم يوجد، جرب البحث عن latest.xlsx كبديل
        if not os.path.exists(original_excel_path):
            latest_path = os.path.join(folder_path, "latest.xlsx")
            if os.path.exists(latest_path):
                original_excel_path = latest_path
                print(
                    f"📄 [EXPORT] تم العثور على latest.xlsx بدلاً من Roche KPI new.xlsx"
                )
            else:
                # جرب من الجلسة
                saved_path = request.session.get("uploaded_excel_path")
                if saved_path and os.path.exists(saved_path):
                    original_excel_path = saved_path
                    print(f"📄 [EXPORT] تم استخدام الملف من الجلسة: {saved_path}")
                else:
                    print(f"⚠️ [EXPORT] لم يتم العثور على الملف الأصلي")
                    return HttpResponse(
                        "❌ لم يتم العثور على الملف الأصلي (Roche KPI new.xlsx)",
                        status=404,
                    )

        try:
            print(f"📄 [EXPORT] جاري قراءة الملف الأصلي: {original_excel_path}")

            # قراءة الملف باستخدام openpyxl للحفاظ على التنسيق والألوان
            workbook = load_workbook(original_excel_path)

            # حفظ الملف في BytesIO مع الحفاظ على كل التنسيق
            output = BytesIO()
            workbook.save(output)
            output.seek(0)

            print(f"✅ [EXPORT] تم نسخ الملف الأصلي بنجاح مع الحفاظ على التنسيق")

            # إنشاء اسم الملف للتنزيل
            filename_parts = ["Roche KPI Dashboard Data"]
            if selected_months:
                filename_parts.append("-".join(selected_months))
            elif selected_month:
                filename_parts.append(selected_month)
            safe_filename = " ".join(filename_parts)

            response = HttpResponse(
                output.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{safe_filename}.xlsx"'
            )
            return response

        except Exception as e:
            print(f"⚠️ [EXPORT] حدث خطأ عند قراءة الملف الأصلي: {e}")
            import traceback

            traceback.print_exc()
            return HttpResponse(f"❌ حدث خطأ عند تصدير الملف: {str(e)}", status=500)

    def render_raw_sheet(self, request, sheet_name):
        """عرض أي شيت كجدول خام إذا مفيش فلتر خاص"""
        print(f"🟢 [DEBUG] ✅ دخل على render_raw_sheet() - التاب: {sheet_name}")

        # 📁 جلب مسار ملف الإكسل
        excel_file_path = self.get_uploaded_file_path(request)
        if not excel_file_path or not os.path.exists(excel_file_path):
            print("⚠️ [ERROR] لم يتم العثور على ملف Excel.")
            return {
                "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                "count": 0,
            }

        try:
            # 📖 قراءة جميع الشيتات
            xls = pd.ExcelFile(excel_file_path, engine="openpyxl")

            # 🔍 البحث عن الشيت بدون حساسية لحالة الأحرف
            matching_sheet = next(
                (
                    s
                    for s in xls.sheet_names
                    if s.lower().strip() == sheet_name.lower().strip()
                ),
                None,
            )

            if not matching_sheet:
                print(
                    f"⚠️ [WARNING] التاب '{sheet_name}' غير موجود. الشيتات المتاحة: {xls.sheet_names}"
                )
                return {
                    "detail_html": f"<p class='text-danger'>❌ Tab '{sheet_name}' does not exist in the file.</p>",
                    "count": 0,
                }

            # 🧾 قراءة الشيت المطابق
            df = pd.read_excel(
                excel_file_path, sheet_name=matching_sheet, engine="openpyxl"
            )

            # 🧹 تنظيف الأعمدة
            df.columns = df.columns.str.strip().str.title()

            # 🗓️ فلترة حسب الشهر إذا تم اختياره
            selected_month = request.GET.get("month")
            if selected_month:
                date_cols = [c for c in df.columns if "Date" in c]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors="coerce")
                    df["Month"] = df[date_cols[0]].dt.strftime("%b")
                    df = df[df["Month"] == selected_month]

            # 🧩 طباعة حالة البيانات
            if df.empty:
                print(
                    f"⚠️ [WARNING] الشيت '{matching_sheet}' فاضي أو غير موجود بعد الفلترة!"
                )
            else:
                print(
                    f"✅ [INFO] الشيت '{matching_sheet}' اتقرأ بنجاح وفيه {len(df)} صفوف."
                )
                print(f"📋 [COLUMNS] الأعمدة: {list(df.columns)}")

            # 🔢 تجهيز أول 50 صف فقط للعرض
            data = df.head(50).to_dict(orient="records")
            for row in data:
                for col, val in row.items():
                    row[col] = self.safe_format_value(val)

            # 🧩 توليد HTML من التمبلت
            tab_data = {
                "name": matching_sheet,
                "columns": df.columns.tolist(),
                "data": data,
            }
            month_norm = self.apply_month_filter_to_tab(tab_data, selected_month)

            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm},
            )

            # 📤 إرجاع النتيجة للواجهة
            return {"detail_html": html, "count": len(df), "tab_data": tab_data}

        except Exception as e:
            print(f"❌ [ERROR] أثناء قراءة الشيت '{sheet_name}': {e}")
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error while reading sheet: {e}</p>",
                "count": 0,
            }

    def filter_by_month(self, request, selected_month):
        import pandas as pd
        from django.template.loader import render_to_string

        try:
            excel_file_path = self.get_uploaded_file_path(request)
            xls = pd.ExcelFile(excel_file_path, engine="openpyxl")

            # 🧩 تحديد اسم الشيت المطلوب تلقائيًا
            # نحاول نختار شيت يحتوي على "Data logger" أو "Dock to stock"
            possible_sheets = [
                s
                for s in xls.sheet_names
                if any(key in s.lower() for key in ["data logger", "dock to stock"])
            ]

            if not possible_sheets:
                print(
                    "⚠️ لم يتم العثور على أي شيت يحتوي على Data logger أو Dock to stock"
                )
                return {
                    "error": "⚠️ No sheet containing Data logger or Dock to stock was found."
                }

            sheet_name = possible_sheets[0]  # ناخد أول واحد مطابق
            print(f"📄 قراءة الشيت: {sheet_name}")

            df = pd.read_excel(
                excel_file_path, sheet_name=sheet_name, engine="openpyxl"
            )
        except Exception as e:
            return {"error": f"⚠️ Unable to read the tab: {e}"}

        # تنظيف الأعمدة
        df.columns = df.columns.str.strip()

        # التحقق من عمود التاريخ
        if "Month" not in df.columns:
            return {"error": "⚠️ Column 'Month' is missing."}

        # تحويل/تطبيع عمود الشهر لقبول كل الصيغ (تاريخ، اختصار، اسم كامل، رقم 1-12)
        import calendar

        month_raw = df["Month"]
        # حاول تحويله لتاريخ؛ اللي يفشل هنرجّعه نصياً
        parsed = pd.to_datetime(month_raw, errors="coerce")
        month_abbr_from_dates = parsed.dt.strftime("%b")

        # طبّع النصوص: أول 3 حروف من اسم الشهر (Jan/February -> Feb)، والأرقام 1-12 إلى اختصار
        def normalize_month_val(v):
            if pd.isna(v):
                return None
            s = str(v).strip()
            # أرقام
            if s.isdigit():
                n = int(s)
                if 1 <= n <= 12:
                    return calendar.month_abbr[n]
            # أسماء كاملة أو مختصرة
            # جرّب اسم كامل
            for i, mname in enumerate(calendar.month_name):
                if i == 0:
                    continue
                if s.lower() == mname.lower():
                    return calendar.month_abbr[i]
            # جرّب اختصار جاهز أو نص عام -> أول 3 أحرف بحالة Capitalize
            return s[:3].capitalize()

        month_abbr_fallback = month_raw.apply(normalize_month_val)
        # استخدم من التاريخ حيث متاح وإلا fallback
        df["Month"] = month_abbr_from_dates.where(~parsed.isna(), month_abbr_fallback)

        # توحيد تمثيل الشهر المختار (أمان لحالات الإدخال المختلفة)
        selected_month_norm = (
            str(selected_month).strip().capitalize() if selected_month else None
        )

        # حفظ الشهر في الجلسة ليستخدمه باقي التابات عند الاستعلامات اللاحقة
        try:
            if selected_month_norm:
                request.session["selected_month"] = selected_month_norm
        except Exception:
            # في حال عدم توفر الجلسة (مثلاً في طلبات غير مرتبطة بمستخدم)، نتجاوز بهدوء
            pass

        # فلترة الشهر المختار أولاً
        month_df = df[df["Month"] == selected_month_norm]

        if month_df.empty:
            return {
                "error": f"⚠️ لا توجد بيانات متاحة للشهر {selected_month_norm}.",
                "month": selected_month_norm,
                "sheet_name": sheet_name,
            }

        # البحث عن عمود KPI بشكل مرن (ممكن يكون اسمه مختلف)
        kpi_miss_col = None
        possible_kpi_names = [
            "kpi miss in",
            "kpi miss",
            "kpi",
            "miss",
            "clearance handling kpi",
            "transit kpi",
        ]

        for kpi_name in possible_kpi_names:
            kpi_miss_col = next(
                (col for col in df.columns if str(col).strip().lower() == kpi_name),
                None,
            )
            if kpi_miss_col:
                break

        # حساب الإحصائيات
        total = len(month_df.drop_duplicates())

        # لو وجدنا عمود KPI، نحسب Miss
        if kpi_miss_col:
            miss_df = month_df[month_df[kpi_miss_col].astype(str).str.lower() == "miss"]
            miss_count = len(miss_df)
            valid = total - miss_count
        else:
            # لو مفيش عمود KPI، نعرض كل البيانات بدون فلترة Miss
            miss_df = pd.DataFrame()  # جدول فاضي
            miss_count = 0
            valid = total
            print(
                f"⚠️ لم يتم العثور على عمود KPI، سيتم عرض جميع البيانات للشهر {selected_month_norm}"
            )

        # تحويل النتائج إلى HTML (للحفاظ على التوافق مع أي استخدام حالي)
        dedup_html = month_df.to_html(
            classes="table table-bordered table-hover text-center",
            index=False,
            border=0,
        )
        miss_html = miss_df.to_html(
            classes="table table-bordered table-hover text-center text-danger",
            index=False,
            border=0,
        )

        print(
            f"📆 فلترة الشهر {selected_month}: إجمالي={total}, Miss={miss_count}, Valid={valid}"
        )

        hit_pct = int(round((valid / total) * 100)) if total else 0

        # تجهيز البيانات للتمبلت القياسي (جداول + شارت)
        month_df_display = month_df.fillna("").astype(str)
        sub_tables = [
            {
                "title": f"{sheet_name} – {selected_month_norm} (كل السجلات)",
                "columns": month_df_display.columns.tolist(),
                "data": month_df_display.to_dict(orient="records"),
            }
        ]

        if miss_count > 0:
            miss_df_display = miss_df.fillna("").astype(str)
            sub_tables.append(
                {
                    "title": f"{sheet_name} – {selected_month_norm} (السجلات المتأخرة)",
                    "columns": miss_df_display.columns.tolist(),
                    "data": miss_df_display.to_dict(orient="records"),
                }
            )

        summary_table = [
            {"المؤشر": "إجمالي الشحنات", "القيمة": int(total)},
            {"المؤشر": "شحنات صحيحة", "القيمة": int(valid)},
            {"المؤشر": "شحنات Miss", "القيمة": int(miss_count)},
            {"المؤشر": "Hit %", "القيمة": f"{hit_pct}%"},
        ]
        sub_tables.append(
            {
                "title": f"{sheet_name} – {selected_month_norm} (ملخص الأداء)",
                "columns": ["المؤشر", "القيمة"],
                "data": summary_table,
            }
        )

        chart_title = f"{sheet_name} – {selected_month_norm} Performance"
        chart_data = [
            {
                "title": chart_title,
                "type": "column",
                "name": "Valid Shipments",
                "color": "#4caf50",
                "showInLegend": True,
                "dataPoints": [{"label": selected_month_norm, "y": int(valid)}],
                "related_table": sub_tables[0]["title"],
            },
            {
                "title": chart_title,
                "type": "column",
                "name": "Miss Shipments",
                "color": "#f44336",
                "showInLegend": True,
                "dataPoints": [{"label": selected_month_norm, "y": int(miss_count)}],
                "related_table": sub_tables[0]["title"],
            },
            {
                "title": chart_title,
                "type": "line",
                "name": "Hit %",
                "color": "#1976d2",
                "showInLegend": True,
                "dataPoints": [{"label": selected_month_norm, "y": hit_pct}],
                "related_table": sub_tables[-1]["title"],
            },
        ]

        tab_data = {
            "name": f"{sheet_name} ({selected_month_norm})",
            "sub_tables": sub_tables,
            "chart_data": chart_data,
            "chart_title": chart_title,
        }
        month_norm_filtered = self.apply_month_filter_to_tab(
            tab_data, selected_month_norm
        )

        combined_html = render_to_string(
            "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
            {"tab": tab_data, "selected_month": month_norm_filtered},
        )

        return {
            "month": selected_month_norm,
            "selected_month": selected_month_norm,
            "sheet_name": sheet_name,
            "total_shipments": total,
            "miss_count": miss_count,
            "valid_shipments": valid,
            "hit_pct": hit_pct,
            "dedup_html": dedup_html,
            "miss_html": miss_html,
            "html": combined_html,
            "detail_html": combined_html,
            "chart_data": chart_data,
            "chart_title": chart_title,
            "tab_data": tab_data,
        }

    def _resolve_quarter_months(self, selected_quarter):
        if not selected_quarter:
            return []

        import re

        quarter_pattern = re.compile(r"^Q([1-4])(?:[-\s]?(\d{4}))?$", re.IGNORECASE)
        match = quarter_pattern.match(str(selected_quarter).strip())
        if not match:
            raise ValueError(f"⚠️ كورتر غير معروف: {selected_quarter}")

        quarter_number = int(match.group(1))
        quarter_months_map = {
            1: ["Jan", "Feb", "Mar"],
            2: ["Apr", "May", "Jun"],
            3: ["Jul", "Aug", "Sep"],
            4: ["Oct", "Nov", "Dec"],
        }

        months = quarter_months_map.get(quarter_number, [])
        if not months:
            raise ValueError(f"⚠️ لا توجد شهور معرّفة للكوارتر {selected_quarter}.")
        return months

    def filter_by_quarter(self, request, selected_quarter):
        from django.template.loader import render_to_string
        import re

        if not selected_quarter:
            return {"error": "⚠️ Please select a valid quarter."}

        quarter_pattern = re.compile(r"^Q([1-4])(?:[-\s]?(\d{4}))?$", re.IGNORECASE)
        match = quarter_pattern.match(str(selected_quarter).strip())
        if not match:
            return {"error": f"⚠️ Unknown quarter: {selected_quarter}"}

        quarter_number = int(match.group(1))
        quarter_months_map = {
            1: ["Jan", "Feb", "Mar"],
            2: ["Apr", "May", "Jun"],
            3: ["Jul", "Aug", "Sep"],
            4: ["Oct", "Nov", "Dec"],
        }

        display_month_list = quarter_months_map.get(quarter_number, [])
        if not display_month_list:
            return {
                "error": f"⚠️ No months were defined for quarter {selected_quarter}."
            }

        try:
            total_lead_time_result = self.filter_total_lead_time_performance(
                request, selected_months=display_month_list
            )
        except Exception as exc:
            import traceback

            traceback.print_exc()
            total_lead_time_result = {
                "detail_html": f"<p class='text-danger text-center p-4'>⚠️ Error while loading Total Lead Time Performance: {exc}</p>"
            }

        section_html = (
            total_lead_time_result.get("detail_html")
            or total_lead_time_result.get("html")
            or "<p class='text-warning text-center p-4'>⚠️ No data available for this quarter.</p>"
        )

        section_wrapper = f"""
        <section class="quarter-section mb-5">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="mb-0 text-primary">Total Lead Time Performance – Quarter {selected_quarter}</h4>
                <span class="badge bg-light text-dark px-3 py-2">{', '.join(display_month_list)}</span>
            </div>
            {section_html}
        </section>
        """

        header_html = f"""
        <div class="quarter-header text-center mb-4">
            <h3 class="fw-bold text-primary mb-1">Quarter {selected_quarter}</h3>
            <p class="text-muted mb-0">Months in scope: {', '.join(display_month_list)}</p>
        </div>
        """

        combined_html = (
            f"<div class='quarter-wrapper'>{header_html}{section_wrapper}</div>"
        )

        return {
            "quarter": selected_quarter,
            "months": ", ".join(display_month_list),
            "detail_html": combined_html,
            "html": combined_html,
            "chart_data": total_lead_time_result.get("chart_data", []),
            "chart_title": total_lead_time_result.get("chart_title"),
            "hit_pct": total_lead_time_result.get("hit_pct"),
        }

    def filter_all_tabs(self, request=None, selected_month=None, selected_months=None):
        cache.clear()
        try:
            month_for_filters = selected_month if not selected_months else None
            # ✅ تحديد الفلتر الحالي
            status_filter = "all"
            if request is not None and hasattr(request, "GET"):
                status_filter = request.GET.get("status", "all")

            # ✅ الحصول على مسار ملف Excel
            excel_path = self.get_uploaded_file_path(request)
            if not excel_path or not os.path.exists(excel_path):
                html = render_to_string(
                    "components/ui-kits/tab-bootstrap/components/dashboard-overview.html",
                    {"message": "⚠️ لم يتم العثور على ملف Excel."},
                )
                return {"detail_html": html}

            # ✅ جلب بيانات الـ overview_tab (منها نبدأ النسب)
            overview_data = self.overview_tab(
                request=request,
                selected_month=month_for_filters,
                selected_months=selected_months,
                from_all_in_one=True,
            )

            if not overview_data or "tab_cards" not in overview_data:
                html = render_to_string(
                    "components/ui-kits/tab-bootstrap/components/dashboard-overview.html",
                    {"message": "⚠️ لا توجد بيانات متاحة من overview_tab."},
                )
                return {"detail_html": html}

            # ✅ قائمة التابات المحذوفة
            excluded_tabs = [
                "return & refusal",
                "airport clearance",
                "seaport clearance",
                "data logger measurement",
            ]

            clean_tabs = []
            for tab in overview_data.get("tab_cards", []):
                name = tab.get("name", "غير معروف")
                name_lower = name.strip().lower()

                # ✅ حذف التابات المطلوبة
                if name_lower in excluded_tabs:
                    continue

                # ✅ النسبة الفعلية
                try:
                    hit = float(tab.get("hit_pct", 0))
                except Exception:
                    hit = 0
                hit = int(round(max(0, min(hit, 100))))

                # ✅ التارجت
                try:
                    target = float(tab.get("target_pct", 100))
                except Exception:
                    target = 100

                # ✅ نستخدم أي chart_data و chart_type راجعين من الـ overview كما هي
                chart_data = tab.get("chart_data", []) or []
                chart_type = tab.get("chart_type", "bar")

                clean_tabs.append(
                    {
                        "name": name,
                        "hit_pct": hit,
                        "target_pct": int(target),
                        "count": tab.get("count", 0),
                        "chart_type": chart_type,
                        "chart_data": chart_data,
                    }
                )

            # ✅ PODs Update - إضافة مع الشارتات
            pods_data = self.filter_pods_update(request, month_for_filters)
            if pods_data and pods_data.get("hit_pct") is not None:
                try:
                    hit_pods = float(pods_data.get("hit_pct", 0))
                except:
                    hit_pods = 0
                hit_pods = int(round(max(0, min(hit_pods, 100))))

                existing_names = [t["name"].strip().lower() for t in clean_tabs]
                if "pods update" not in existing_names:
                    # ✅ جلب الشارتات من pods_data
                    pods_chart_data = pods_data.get("chart_data", [])
                    pods_chart_type = "column"
                    if pods_chart_data and len(pods_chart_data) > 0:
                        pods_chart_type = pods_chart_data[0].get("type", "column")

                    clean_tabs.append(
                        {
                            "name": "PODs update",
                            "hit_pct": hit_pods,
                            "target_pct": 100,
                            "count": pods_data.get("count", 0),
                            "chart_type": pods_chart_type,
                            "chart_data": pods_chart_data,
                        }
                    )

            # ✅ ترتيب التابات حسب الأولوية (بدون التابات المحذوفة)
            desired_order = [
                "Inbound",
                "Outbound",
                "PODs update",
            ]
            clean_tabs.sort(
                key=lambda x: (
                    desired_order.index(x["name"])
                    if x["name"] in desired_order
                    else len(desired_order)
                )
            )

            # ✅ بيانات الميتنج - جلب كل النقاط (مثل meeting_points_tab)
            meeting_points = MeetingPoint.objects.all().order_by(
                "is_done", "-created_at"
            )

            if status_filter == "done":
                meeting_points = meeting_points.filter(is_done=True)
            elif status_filter == "pending":
                meeting_points = meeting_points.filter(is_done=False)

            meeting_data = [
                {
                    "id": p.id,
                    "description": p.description,
                    "assigned_to": getattr(p, "assigned_to", "") or "",
                    "status": "Done" if p.is_done else "Pending",
                    "created_at": p.created_at,
                    "target_date": p.target_date,
                }
                for p in meeting_points
            ]

            tabs_for_display = clean_tabs

            warehouse_overview = context_helpers.get_warehouse_overview_list()
            clerk_interview_rows = context_helpers.get_clerk_interview_list()
            dashboard_theme = context_helpers.get_dashboard_theme_dict()
            phases_sections = context_helpers.get_phases_sections_list()
            html = render_to_string(
                "components/ui-kits/tab-bootstrap/components/dashboard-overview.html",
                {
                    "tabs": tabs_for_display,
                    "tabs_json": json.dumps(tabs_for_display),
                    "meeting_data": meeting_data,
                    "status_filter": status_filter,
                    "warehouse_overview": warehouse_overview,
                    "clerk_interview_rows": clerk_interview_rows,
                    "dashboard_theme": dashboard_theme,
                    "phases_sections": phases_sections,
                },
                request=request,
            )

            return {"detail_html": html}

        except Exception as e:
            traceback.print_exc()
            return {
                "detail_html": f"<div class='alert alert-danger'>⚠️ Error: {e}</div>"
            }

    def get_meeting_points_section_html(self, request, status_filter="all"):
        """
        ✅ دالة مساعدة لإرجاع HTML قسم Meeting Points فقط
        """
        try:
            meeting_points = MeetingPoint.objects.all().order_by(
                "is_done", "-created_at"
            )

            if status_filter == "done":
                meeting_points = meeting_points.filter(is_done=True)
            elif status_filter == "pending":
                meeting_points = meeting_points.filter(is_done=False)

            meeting_data = [
                {
                    "id": p.id,
                    "description": p.description,
                    "assigned_to": getattr(p, "assigned_to", "") or "",
                    "status": "Done" if p.is_done else "Pending",
                    "created_at": p.created_at,
                    "target_date": p.target_date,
                }
                for p in meeting_points
            ]

            # ✅ إرجاع HTML قسم Meeting Points فقط
            html = render_to_string(
                "components/ui-kits/tab-bootstrap/components/meeting_points_section.html",
                {
                    "meeting_data": meeting_data,
                    "status_filter": status_filter,
                },
                request=request,
            )
            return html
        except Exception as e:
            import traceback

            traceback.print_exc()
            return f"<div class='alert alert-danger'>⚠️ Error: {e}</div>"

    def filter_total_lead_time_detail(self, request, selected_month=None):
        try:
            # تحميل الملف من الجلسة
            excel_path = request.session.get("uploaded_excel_path")
            if not excel_path or not os.path.exists(excel_path):
                return {"error": "⚠️ Excel file was not found in the session."}

            # قراءة الشيت المطلوب
            df = pd.read_excel(
                excel_path, sheet_name="Total lead time preformance", engine="openpyxl"
            )
            df.columns = df.columns.str.strip().str.lower()

            # التأكد من الأعمدة المطلوبة
            required_cols = [
                "month",
                "outbound delivery",
                "kpi",
                "reason group",
                "miss reason",
            ]
            for col in required_cols:
                if col not in df.columns:
                    return {"error": f"⚠️ Column '{col}' does not exist in the sheet."}

            # تحويل التاريخ إلى الشهر
            df["month"] = (
                pd.to_datetime(df["month"], errors="coerce")
                .dt.strftime("%b")
                .str.capitalize()
            )

            # استخراج الشهور الموجودة فعليًا في الملف (بترتيب زمني)
            existing_months = df["month"].dropna().unique().tolist()
            existing_months = sorted(
                existing_months, key=lambda x: pd.to_datetime(x, format="%b").month
            )

            if not existing_months:
                return {"error": "⚠️ No valid months were found in the file."}

            # إزالة التكرارات حسب رقم الشحنة
            df = df.drop_duplicates(subset=["outbound delivery"])

            # تنظيف النصوص
            df["reason group"] = df["reason group"].astype(str).str.strip().str.lower()
            df["kpi"] = df["kpi"].astype(str).str.strip().str.lower()

            # بيانات Miss الخاصة بـ 3PL فقط
            df_miss_3pl = df[
                (df["kpi"] == "miss") & (df["reason group"] == "3pl")
            ].copy()

            # 🔹 تنظيف السبب فقط (بدون تغيير الحروف الأصلية)
            df_miss_3pl["miss reason"] = (
                df_miss_3pl["miss reason"]
                .astype(str)
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)  # إزالة المسافات المكررة
            )

            # معالجة اختلاف الحروف أثناء التجميع (case-insensitive grouping)
            df_miss_3pl["_miss_reason_key"] = df_miss_3pl["miss reason"].str.lower()

            # بيانات On Time Delivery (Hit)
            df_hit = df[df["kpi"] != "miss"].copy()

            # تجميع Miss حسب السبب والشهر (باستخدام المفتاح الموحد للحروف)
            miss_grouped = (
                df_miss_3pl.groupby(["_miss_reason_key", "month"], as_index=False)
                .agg(
                    {
                        "miss reason": "first",
                        "month": "first",
                        "_miss_reason_key": "count",
                    }
                )
                .rename(columns={"_miss_reason_key": "count"})
            )

            # Pivot الجدول
            miss_pivot = miss_grouped.pivot_table(
                index="miss reason", columns="month", values="count", fill_value=0
            )

            # تأكد أن كل الشهور الموجودة في الملف موجودة في الجدول
            for m in existing_months:
                if m not in miss_pivot.columns:
                    miss_pivot[m] = 0
            miss_pivot = miss_pivot[existing_months]

            # حساب On Time Delivery لكل شهر
            hit_counts = (
                df_hit.groupby("month").size().reindex(existing_months, fill_value=0)
            )

            # بناء الجدول النهائي
            final_df = miss_pivot.copy()
            final_df.loc["On Time Delivery"] = hit_counts
            final_df = final_df.fillna(0)

            # ترتيب الصفوف بحيث On Time في الأعلى
            final_df = final_df.reindex(
                ["On Time Delivery"]
                + [r for r in final_df.index if r != "On Time Delivery"]
            )

            # إضافة عمود الإجمالي
            final_df["Total"] = final_df.sum(axis=1)

            # صف الإجمالي النهائي
            final_df.loc["TOTAL"] = final_df.sum(numeric_only=True)

            # 🟦 إنشاء جدول HTML
            html_table = """
            <table class='table table-bordered text-center align-middle mb-0'>
                <thead class='table-warning'>
                    <tr><th colspan='{colspan}'>Reason From 3PL Side</th></tr>
                </thead>
                <thead class='table-primary'>
                    <tr>
                        <th>KPI</th>
                        {month_headers}
                        <th>2025</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            """

            # رؤوس الأعمدة
            month_headers = "".join([f"<th>{m}</th>" for m in existing_months])

            # الصفوف
            rows_html = ""
            for reason, row in final_df.iterrows():
                rows_html += f"<tr><td>{reason}</td>"
                for m in existing_months:
                    rows_html += f"<td>{int(row[m])}</td>"
                rows_html += f"<td class='fw-bold'>{int(row['Total'])}</td></tr>"

            # استبدال القيم في القالب
            html_table = html_table.format(
                colspan=len(existing_months) + 2,
                month_headers=month_headers,
                table_rows=rows_html,
            )

            # وضع الجدول داخل واجهة مرتبة
            html_output = f"""
            <div class='container-fluid'>
                <h5 class='text-center text-primary mb-3'>KPI Summary - 3PL Performance</h5>
                <div class='card shadow'>
                    <div class='card-body'>
                        {html_table}
                    </div>
                </div>
            </div>
            """

            return {"detail_html": html_output, "months": existing_months}

        except Exception as e:
            import traceback

            print("❌ خطأ أثناء تحليل البيانات:", str(e))
            print(traceback.format_exc())
            return {"error": f"⚠️ Error while analyzing data: {e}"}

    def filter_rejection_data(self, request, month=None):
        print("🟣 [DEBUG] filter_rejection_data CALLED ✅ month:", month)

        excel_path = request.session.get("uploaded_excel_path")

        if not excel_path or not os.path.exists(excel_path):
            return {"error": "⚠️ Excel file not found."}

        try:
            df = pd.read_excel(excel_path, sheet_name="Rejection", engine="openpyxl")
            print("🟢 [DEBUG] الأعمدة:", df.columns.tolist())
            print(df.head(3))
        except Exception as e:
            return {"error": f"⚠️ Unable to read the 'Rejection' sheet: {e}"}

        df.columns = df.columns.str.strip().str.title()
        required = ["Month", "Total Number Of Orders", "Booking Orders"]
        if not all(col in df.columns for col in required):
            return {
                "error": "⚠️ Required columns (Month, Total Number Of Orders, Booking Orders) are missing."
            }

        if month:
            df = df[df["Month"].astype(str).str.contains(month, case=False, na=False)]

        if df.empty:
            return {"error": "⚠️ No data available."}

        # ✅ خدي القيم زي ما هي من الإكسل (من العمود Booking Orders)
        summary = df[["Month", "Booking Orders"]].copy()

        # 🧠 تنظيف القيم — شيل علامة % لو موجودة وحوّليها لأرقام
        summary["Booking Orders"] = (
            summary["Booking Orders"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .astype(float)
        )

        # 🎯 البيانات للشارت مباشرة
        chart_data = [
            {"month": row["Month"], "percentage": row["Booking Orders"]}
            for _, row in summary.iterrows()
        ]

        html = df.to_html(
            index=False,
            classes="table table-bordered table-striped text-center align-middle",
            border=0,
        )

        print("📊 DEBUG - chart_data:", chart_data)  # <-- شوفيها في التيرمنال
        return {"detail_html": html, "chart_data": chart_data}

    def filter_dock_to_stock_roche(self, request, selected_month=None):
        print("🟢 [DEBUG] ✅ دخل على filter_dock_to_stock_roche()")

        excel_path = request.session.get("uploaded_excel_path")
        if not excel_path or not os.path.exists(excel_path):
            return {"error": "⚠️ Excel file not found."}

        try:
            import pandas as pd
            from django.template.loader import render_to_string

            sheet_name = "Dock to stock - Roche"
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
            df.columns = df.columns.astype(str).str.strip()

            if df.empty:
                return {"error": "⚠️ Sheet 'Dock to stock - Roche' is empty."}

            # أول عمود هو الشهر
            month_col = df.columns[0]
            # باقي الأعمدة هي الأسباب (KPIs)
            kpi_cols = df.columns[1:]

            # تحويل البيانات بحيث تكون الأسباب صفوف والشهور أعمدة
            melted_df = df.melt(id_vars=[month_col], var_name="KPI", value_name="Value")

            # Pivot فعلي (KPI كصفوف والشهور كأعمدة)
            pivot_df = melted_df.pivot_table(
                index="KPI", columns=month_col, values="Value", aggfunc="sum"
            ).reset_index()
            pivot_df = pivot_df.rename_axis(None, axis=1)

            # ترتيب الأعمدة حسب تسلسل الشهور الموجود في الشيت الأصلي
            month_order = list(df[month_col].unique())
            ordered_cols = ["KPI"] + month_order
            pivot_df = pivot_df.reindex(columns=ordered_cols)

            # ✅ حذف أي عمود اسمه "Total" (اللي بيتولد من الشيت أو من الخطأ)
            if "Total" in pivot_df.columns:
                pivot_df = pivot_df.drop(columns=["Total"])

            # ✅ إضافة عمود "2025" فقط بعد الشهور
            pivot_df["2025"] = pivot_df.iloc[:, 1:].sum(axis=1)

            # ✅ إضافة صف Total (اللي بيكون تحت الجدول)
            total_row = {"KPI": "Total"}
            for col in pivot_df.columns[1:]:  # تجاهل عمود KPI
                total_row[col] = pivot_df[col].sum()
            pivot_df = pd.concat(
                [pivot_df, pd.DataFrame([total_row])], ignore_index=True
            )

            print("✅ [DEBUG] جدول KPI النهائي بعد التعديل:")
            print(pivot_df.to_string(index=False))

            # تجهيز البيانات للعرض
            columns = list(pivot_df.columns)
            table_data = pivot_df.fillna("").to_dict(orient="records")

            tab = {
                "name": "Dock to Stock - Roche",
                "columns": columns,
                "data": table_data,
            }

            month_norm = self.apply_month_filter_to_tab(tab, selected_month)

            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {
                    "tab": tab,
                    "table_title": "Dock to Stock - Roche (KPI Summary)",
                    "selected_month": month_norm,
                },
            )

            return {
                "detail_html": html,
                "chart_title": "Dock to Stock - Roche",
            }

        except Exception as e:
            print(f"❌ [ERROR] {e}")
            return {"error": f"⚠️ Error while reading data: {e}"}

    def filter_dock_to_stock_3pl(
        self, request, selected_month=None, selected_months=None
    ):
        try:
            print("🟢 [DEBUG] ✅ دخل على filter_dock_to_stock_3pl()")
            file_path = self.get_uploaded_file_path(request)
            print(f"📁 [DEBUG] مسار الملف المستخدم: {file_path}")

            if not file_path or not os.path.exists(file_path):
                return {"error": "⚠️ File not found."}

            # 🧩 قراءة الشيت
            df = pd.read_excel(file_path, sheet_name="Dock to stock", engine="openpyxl")
            print(f"📄 [DEBUG] أول 10 صفوف من الشيت Dock to stock:\n{df.head(10)}")

            # ✅ التحقق من وجود الأعمدة المطلوبة
            if "Delv #" not in df.columns or "Month" not in df.columns:
                return {
                    "error": "⚠️ Columns 'Delv #' or 'Month' are missing in the sheet."
                }

            # 🧮 استخراج الشهر من العمود Month
            df["Month"] = pd.to_datetime(df["Month"], errors="coerce").dt.strftime("%b")

            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in seen:
                        seen.add(norm)
                        selected_months_norm.append(norm)

            selected_month_norm = (
                self.normalize_month_label(selected_month)
                if selected_month and not selected_months_norm
                else None
            )
            if selected_months_norm:
                df = df[
                    df["Month"]
                    .str.lower()
                    .isin([m.lower() for m in selected_months_norm])
                ]
                if df.empty:
                    return {
                        "detail_html": "<p class='text-warning text-center'>⚠️ No data available for the selected quarter months.</p>",
                        "chart_data": [],
                    }
            elif selected_month_norm:
                df = df[df["Month"].str.lower() == selected_month_norm.lower()]
                if df.empty:
                    return {
                        "detail_html": "<p class='text-warning text-center'>⚠️ No data available for this month.</p>",
                        "chart_data": [],
                    }

            # 🧱 حذف الصفوف اللي مافيهاش شهر
            df = df.dropna(subset=["Month"])

            # ✅ حساب عدد الشحنات الفريدة (hit) لكل شهر من العمود Delv #
            hits_per_month = (
                df.drop_duplicates(subset=["Delv #"])
                .groupby("Month")["Delv #"]
                .count()
                .reset_index(name="Hits")
            )

            print("📊 [DEBUG] نتائج عدد الشحنات الفريدة لكل شهر:")
            print(hits_per_month)

            # ✅ حساب إجمالي الشحنات (Total) لكل شهر قبل حذف المكرر
            total_per_month = (
                df.groupby("Month")["Delv #"]
                .count()
                .reset_index(name="Total_Shipments")
            )

            # ✅ دمج نتائج الـ hits مع الإجمالي
            merged = pd.merge(hits_per_month, total_per_month, on="Month", how="left")

            # ✅ حساب نسبة التارجت لكل شهر
            merged["Target_%"] = (
                merged["Hits"] / merged["Total_Shipments"] * 100
            ).round(2)

            print("📈 [DEBUG] بعد حساب نسبة التارجت:")
            print(merged)

            # ✅ تجهيز جدول KPI بصيغة نهائية
            kpi_name = "On Time Receiving"
            df_kpi = pd.DataFrame({"KPI": [kpi_name]})

            for _, row in merged.iterrows():
                month = row["Month"]
                hits = int(row["Hits"])
                df_kpi[month] = hits

            # ✅ إضافة صف جديد Total
            total_row = {"KPI": "Total"}
            for col in df_kpi.columns[1:]:  # تجاهل عمود KPI
                total_row[col] = df_kpi[col].sum()
            df_kpi = pd.concat([df_kpi, pd.DataFrame([total_row])], ignore_index=True)

            # ✅ إضافة عمود جديد "2025" يمثل مجموع كل الشهور
            df_kpi["2025"] = df_kpi.iloc[:, 1:].sum(axis=1)

            # ✅ إضافة صف جديد لنسبة التارجت
            target_row = {"KPI": "Target (%)"}
            for _, row in merged.iterrows():
                month = row["Month"]
                target_row[month] = row["Target_%"]
            target_row["2025"] = round(merged["Target_%"].mean(), 2)
            df_kpi = pd.concat([df_kpi, pd.DataFrame([target_row])], ignore_index=True)

            print("✅ [DEBUG] جدول KPI النهائي بعد الإضافات:")
            print(df_kpi.to_string(index=False))

            if selected_months_norm:
                desired_cols = ["KPI"] + [
                    m for m in selected_months_norm if m in df_kpi.columns
                ]
                if "2025" in df_kpi.columns:
                    desired_cols.append("2025")
                df_kpi = df_kpi[[col for col in desired_cols if col in df_kpi.columns]]
            elif selected_month_norm:
                keep_cols = ["KPI", selected_month_norm]
                if "2025" in df_kpi.columns:
                    keep_cols.append("2025")
                df_kpi = df_kpi[[col for col in keep_cols if col in df_kpi.columns]]

            # 🧾 تحويل الجدول إلى HTML
            html_table = df_kpi.to_html(
                classes="table table-bordered text-center table-striped", index=False
            )

            # 🔹 الإرجاع لعرض الجدول في الواجهة
            return {
                "detail_html": html_table,
                "chart_data": df_kpi.to_dict(orient="records"),
            }

        except Exception as e:
            print(f"❌ [EXCEPTION] خطأ أثناء تنفيذ الدالة: {e}")
            return {"error": str(e)}

    def filter_total_lead_time_detail(self, request, selected_month=None):
        excel_path = request.session.get("uploaded_excel_path")
        if not excel_path or not os.path.exists(excel_path):
            return {
                "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                "count": 0,
            }

        try:
            # قراءة الشيت المطلوب
            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sheet_name = next(
                (
                    s
                    for s in xls.sheet_names
                    if "total lead time preformance" in s.lower()
                ),
                None,
            )
            if not sheet_name:
                return {
                    "detail_html": "<p class='text-danger'>❌ Tab 'Total lead time preformance' does not exist in the file.</p>",
                    "count": 0,
                }

            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
            df.columns = df.columns.str.strip().str.lower()

            # التحقق من الأعمدة المطلوبة
            required_cols = [
                "month",
                "outbound delivery",
                "kpi",
                "reason group",
                "miss reason",
            ]
            if not all(col in df.columns for col in required_cols):
                html = render_to_string(
                    "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                    {
                        "tabs": [
                            {
                                "name": sheet_name,
                                "columns": df.columns.tolist(),
                                "data": df.head(50).to_dict(orient="records"),
                            }
                        ]
                    },
                )
                return {"detail_html": html, "count": len(df)}

            # تحويل التاريخ إلى شهر
            df["month"] = (
                pd.to_datetime(df["month"], errors="coerce")
                .dt.strftime("%b")
                .str.capitalize()
            )

            # استخراج الشهور الموجودة فعليًا
            existing_months = sorted(
                df["month"].dropna().unique().tolist(),
                key=lambda x: pd.to_datetime(x, format="%b").month,
            )
            if not existing_months:
                return {
                    "detail_html": "<p class='text-danger'>⚠️ No valid months were found in the file.</p>",
                    "count": 0,
                }

            # تنظيف النصوص
            df["reason group"] = df["reason group"].astype(str).str.strip().str.lower()
            df["kpi"] = df["kpi"].astype(str).str.strip().str.lower()
            df["miss reason"] = (
                df["miss reason"]
                .astype(str)
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
            )

            # بيانات Miss الخاصة بـ 3PL فقط
            df_miss_3pl = df[
                (df["kpi"] == "miss") & (df["reason group"] == "3pl")
            ].copy()
            df_miss_3pl["_reason_key"] = df_miss_3pl["miss reason"].str.lower()

            # بيانات Hit (On Time Delivery)
            df_hit = df[df["kpi"] != "miss"].copy()

            # تجميع Miss حسب السبب والشهر
            miss_grouped = df_miss_3pl.groupby(
                ["_reason_key", "month"], as_index=False
            ).agg({"miss reason": "first"})
            miss_grouped["count"] = (
                df_miss_3pl.groupby(["_reason_key", "month"]).size().values
            )

            miss_pivot = miss_grouped.pivot_table(
                index="miss reason", columns="month", values="count", fill_value=0
            )

            # إضافة أعمدة الشهور الناقصة
            for m in existing_months:
                if m not in miss_pivot.columns:
                    miss_pivot[m] = 0
            miss_pivot = miss_pivot[existing_months]

            # حساب On Time Delivery
            hit_counts = (
                df_hit.groupby("month").size().reindex(existing_months, fill_value=0)
            )

            # بناء الجدول النهائي
            final_df = miss_pivot.copy()
            final_df.loc["On Time Delivery"] = hit_counts
            final_df = final_df.fillna(0)

            # تحويل كل القيم لأعداد صحيحة
            final_df = final_df.astype(int)

            # إضافة عمود الإجمالي (2025 بدل TOTAL)
            final_df["2025"] = final_df.sum(axis=1)

            # صف الإجمالي النهائي
            total_row = final_df.sum(numeric_only=True)
            total_row.name = "TOTAL"
            final_df = pd.concat([final_df, pd.DataFrame([total_row])])

            # ترتيب الأعمدة
            final_df.reset_index(inplace=True)
            # final_df.rename(columns={"miss reason": "KPI"}, inplace=True)
            final_df.rename(columns={"index": "KPI"}, inplace=True)

            # ✅ تجهيز البيانات للتمبلت الديناميكي
            tab_data = {
                "name": "KPI Summary - 3PL Performance",
                "sub_tables": [
                    {
                        "title": "Reason From 3PL Side",
                        "columns": ["KPI"] + existing_months + ["2025"],
                        "data": final_df.to_dict(orient="records"),
                    }
                ],
            }

            month_norm = self.apply_month_filter_to_tab(tab_data, selected_month)
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm},
            )

            return {"detail_html": html, "count": len(df), "tab_data": tab_data}

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error while reading data: {e}</p>",
                "count": 0,
            }

    def filter_total_lead_time_roche(self, request, selected_month=None):
        """
        🔹 قراءة شيت "Total lead time preformance -R" من التمبلت المرفوع
        🔹 استخراج أسباب التأخير وترتيبها حسب الشهور
        🔹 عرضها بتصميم الجدول الموحد
        """
        print("🟢 [DEBUG] ✅ دخل على filter_total_lead_time_roche()")

        excel_path = request.session.get("uploaded_excel_path")
        if not excel_path or not os.path.exists(excel_path):
            return {"error": "⚠️ Excel file not found."}

        try:
            # فتح ملف الإكسل
            xls = pd.ExcelFile(excel_path, engine="openpyxl")

            # 🔍 البحث عن الشيت المطلوب
            sheet_name = next(
                (s for s in xls.sheet_names if "preformance -r" in s.lower()), None
            )
            if not sheet_name:
                return {
                    "error": "⚠️ No sheet containing 'Total lead time preformance -R' was found."
                }

            # قراءة الشيت
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
            df.columns = df.columns.str.strip()

            # التحقق من وجود الأعمدة المطلوبة
            if "Month" not in df.columns:
                return {"error": "⚠️ Column named 'Month' was not found in the sheet."}

            # ترتيب الشهور بالترتيب الزمني
            month_order = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            df["Month"] = pd.Categorical(
                df["Month"], categories=month_order, ordered=True
            )
            df = df.sort_values("Month")

            # تحويل البيانات إلى شكل طويل (Melt)
            df_melted = df.melt(id_vars=["Month"], var_name="KPI", value_name="Count")

            # تجميع البيانات حسب السبب والشهر
            pivot_df = (
                df_melted.groupby(["KPI", "Month"])["Count"]
                .sum()
                .unstack(fill_value=0)
                .reindex(columns=month_order, fill_value=0)
            )

            # إضافة عمود الإجمالي السنوي
            pivot_df["2025"] = pivot_df.sum(axis=1)

            # صف الإجمالي الكلي
            total_row = pivot_df.sum(numeric_only=True)
            total_row.name = "TOTAL"
            pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])])

            # ✅ إعادة تسمية العمود الأول إلى KPI
            pivot_df.reset_index(inplace=True)
            pivot_df.rename(columns={"index": "KPI"}, inplace=True)

            # حذف الشهور الفارغة تمامًا (بدون بيانات)
            pivot_df = pivot_df.loc[:, (pivot_df != 0).any(axis=0)]

            # ✅ تجهيز بيانات الجدول لتمبلت الـ HTML
            tab = {
                "name": "Total Lead Time Performance - Roche Side",
                "columns": list(pivot_df.columns),
                "data": pivot_df.to_dict(orient="records"),
            }

            month_norm = self.apply_month_filter_to_tab(tab, selected_month)
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {
                    "tab": tab,
                    "table_title": "Roche Lead Time 2025",
                    "selected_month": month_norm,
                },
            )

            return {
                "detail_html": html,
                "message": "✅ تم عرض بيانات Roche Lead Time بنجاح.",
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {"error": f"⚠️ Error while reading Roche Lead Time data: {e}"}

    def filter_outbound(self, request, selected_month=None):
        """
        🔹 عرض تاب Outbound بخطوات أفقية من تمبلت خارجي
        """
        try:
            # ✅ الخطوات مع ألوان وخلفيات مختلفة
            raw_steps = [
                {
                    "title": "GI Issue<br>Pick & Pack",
                    "icon": "bi-receipt",
                    "bg": "#9fc0e4",
                    "text_color": "#fff",
                    "border": "4px solid #9fc0e4",
                    "sub_color": "#eee",
                },
                {
                    "title": "Prepare Docs<br>Invoice, PO and Market place",
                    "icon": "bi-box-seam",
                    "bg": "#e8f1fb",
                    "text_color": "#007fa3",
                    "border": "4px solid #9fc0e4",
                    "sub_color": "#000",
                },
                {
                    "title": "Dispatch Time<br>from Docs Ready till left from WH",
                    "icon": "bi-arrow-left-right",
                    "bg": "#9fc0e4",
                    "text_color": "#fff",
                    "border": "4px solid #9fc0e4",
                    "sub_color": "#eee",
                },
                {
                    "title": "Delivery<br>Deliver to Customer",
                    "icon": "bi-file-earmark-text",
                    "bg": "#e8f1fb",
                    "text_color": "#007fa3",
                    "border": "4px solid #9fc0e4",
                    "sub_color": "#000",
                },
            ]

            steps = []
            for step in raw_steps:
                # نقسم النص على <br>
                parts = step["title"].split("<br>")
                styled_title = ""
                for i, part in enumerate(parts):
                    # لو دا السطر الأخير → نستخدم sub_color
                    color = (
                        step["sub_color"] if i == len(parts) - 1 else step["text_color"]
                    )
                    styled_title += f"<span class='step-line d-block' style='color:{color};'>{part.strip()}</span>"

                steps.append(
                    {
                        "title": styled_title,
                        "icon": step["icon"],
                        "bg": step["bg"],
                        "text_color": step["text_color"],
                        "border": step["border"],
                    }
                )

            # ✅ تمرير البيانات إلى التمبلت
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/workflow.html",
                {
                    "table_title": "Outbound workflow",
                    "table_text": "Process Stages",
                    "table_span": "Way Of Calculation",
                    "table_text_bottom": "The KPI was calculated based full lead time Order creation to deliver the order to the customer Based on SLA for each city",
                    "process_steps_text": "=NETWORKDAYS(Order Date, Delivery Date,7)-1",
                    "steps": steps,
                    "workflow_type": "outbound",
                },
            )

            return {
                "detail_html": html,
                "message": "✅ Outbound steps displayed successfully.",
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {"error": f"⚠️ Error while rendering the Outbound tab: {e}"}

    def filter_outbound_shipments(
        self, request, selected_month=None, selected_months=None
    ):
        """
        🔹 يقرأ من شيت Outbound1: Order Nbr, Customer Name, Create Timestamp, Customer City,
           Order Type, Status, Ship Date.
        🔹 يقرأ من شيت Outbound2: Packed Timestamp (الربط على Order Nbr).
        🔹 Hit/Miss: من Packed Timestamp إلى Ship Date — لو ≤24 ساعة = Hit وإلا Miss.
        🔹 يعيد نفس هيكل Inbound (stats, sub_tables, chart_data) لعرضه بنفس التمبلت.
        """
        try:
            import os

            excel_path = self.get_uploaded_file_path(request) or self.get_excel_path()
            if not excel_path or not os.path.exists(excel_path):
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                    "stats": {},
                }

            xls = pd.ExcelFile(excel_path, engine="openpyxl")

            # طباعة أسماء الشيتات في الملف عشان نعرف مين موجود
            print("\n[Outbound] أسماء الشيتات في ملف الإكسل:", xls.sheet_names)

            # إيجاد شيت Outbound1 و Outbound2 (أي تسمية تحتوي على outbound + 1 أو 2)
            outbound1_name = None
            outbound2_name = None
            for i, name in enumerate(xls.sheet_names):
                low = name.lower().strip()
                if "outbound" in low and (
                    "1" in low or "one" in low or low == "outbound1"
                ):
                    outbound1_name = name
                if "outbound" in low and (
                    "2" in low or "two" in low or low == "outbound2"
                ):
                    outbound2_name = name
            if not outbound1_name:
                outbound1_name = next(
                    (
                        s
                        for s in xls.sheet_names
                        if "outbound" in s.lower() and "2" not in s.lower()
                    ),
                    None,
                )
            if not outbound2_name:
                outbound2_name = next(
                    (
                        s
                        for s in xls.sheet_names
                        if "outbound" in s.lower() and "1" not in s.lower()
                    ),
                    None,
                )
            # لو لسه مفيش Outbound2: نجرب أي شيت فيه عمود Packed Timestamp (أو Packed) + Order Nbr
            if not outbound2_name and outbound1_name:
                for sheet in xls.sheet_names:
                    if sheet == outbound1_name:
                        continue
                    try:
                        probe = pd.read_excel(
                            excel_path, sheet_name=sheet, engine="openpyxl", nrows=2
                        )
                        probe.columns = probe.columns.astype(str).str.strip()
                        has_order = any(
                            "order" in c.lower() and "nbr" in c.lower()
                            for c in probe.columns
                        ) or any("order nbr" in c.lower() for c in probe.columns)
                        has_packed = any("packed" in c.lower() for c in probe.columns)
                        if has_order and has_packed:
                            outbound2_name = sheet
                            print(
                                f"[Outbound] تم استخدام الشيت '{sheet}' كـ Outbound2 (فيه Order Nbr + Packed)"
                            )
                            break
                    except Exception:
                        continue
            if not outbound2_name and outbound1_name:
                print(
                    "[Outbound] ⚠️ لم يتم العثور على شيت Outbound2. تأكدي أن اسم الشيت يحتوي على 'outbound' و '2' أو أن فيه عمود Packed Timestamp و Order Nbr."
                )

            if not outbound1_name:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ Sheet 'Outbound1' (or similar) not found.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                    "stats": {},
                }

            df1 = pd.read_excel(
                excel_path, sheet_name=outbound1_name, engine="openpyxl"
            )
            df1.columns = df1.columns.astype(str).str.strip()

            def find_col(df, candidates):
                for c in df.columns:
                    if str(c).strip().lower() in [x.lower() for x in candidates]:
                        return c
                for cand in candidates:
                    for c in df.columns:
                        if cand.lower() in str(c).lower():
                            return c
                return None

            # Outbound1 columns
            order_nbr_col = find_col(
                df1, ["Order Nbr", "Order Nbr.", "Order Number", "Order No", "Order #"]
            )
            customer_col = find_col(df1, ["Customer Name", "Customer"])
            create_ts_col = find_col(
                df1, ["Create Timestamp", "Create Date", "Order Date", "Created"]
            )
            city_col = find_col(df1, ["Customer City", "City"])
            order_type_col = find_col(df1, ["Order Type", "Type"])
            status_col = find_col(df1, ["Status"])
            ship_date_col = find_col(
                df1, ["Ship Date", "Shipment Date", "Shipped Date"]
            )

            required_ob1 = [
                order_nbr_col,
                customer_col,
                create_ts_col,
                status_col,
                ship_date_col,
            ]
            if not all(required_ob1):
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Outbound1: missing required columns (Order Nbr, Customer Name, Create Timestamp, Status, Ship Date).</p>",
                    "sub_tables": [],
                    "chart_data": [],
                    "stats": {},
                }

            rename_ob1 = {
                order_nbr_col: "Order Nbr",
                customer_col: "Customer Name",
                create_ts_col: "Create Timestamp",
                status_col: "Status",
                ship_date_col: "Ship Date",
            }
            if city_col and city_col in df1.columns:
                rename_ob1[city_col] = "Customer City"
            if order_type_col and order_type_col in df1.columns:
                rename_ob1[order_type_col] = "Order Type"
            df1 = df1.rename(columns=rename_ob1)
            if "Customer City" not in df1.columns:
                df1["Customer City"] = ""
            if "Order Type" not in df1.columns:
                df1["Order Type"] = ""

            for dt_col in ["Create Timestamp", "Ship Date"]:
                if dt_col in df1.columns:
                    df1[dt_col] = pd.to_datetime(df1[dt_col], errors="coerce")

            df1["Order Nbr"] = df1["Order Nbr"].astype(str).str.strip()
            df1["Status"] = df1["Status"].astype(str).str.strip()

            # مفتاح ربط موحّد (يحل اختلاف التنسيق مثل 001 vs 1)
            def _order_key(ser):
                def _norm(v):
                    s = str(v).strip()
                    try:
                        return str(int(float(s)))
                    except (ValueError, TypeError):
                        return s

                return ser.astype(str).str.strip().apply(_norm)

            # Outbound2: Packed Timestamp + key to join (Order Nbr)
            packed_series = None
            if outbound2_name:
                df2 = pd.read_excel(
                    excel_path, sheet_name=outbound2_name, engine="openpyxl"
                )
                df2.columns = df2.columns.astype(str).str.strip()
                order_nbr_col2 = find_col(
                    df2,
                    ["Order Nbr", "Order Nbr.", "Order Number", "Order No", "Order #"],
                )
                packed_col = find_col(
                    df2, ["Packed Timestamp", "Packed Date", "Packed", "Packed Time"]
                )
                if order_nbr_col2 and packed_col:
                    df2 = df2[[order_nbr_col2, packed_col]].copy()
                    df2.columns = ["Order Nbr", "Packed Timestamp"]
                    df2["Order Nbr"] = df2["Order Nbr"].astype(str).str.strip()
                    df2["Packed Timestamp"] = pd.to_datetime(
                        df2["Packed Timestamp"], errors="coerce"
                    )
                    # إزالة التكرار في Order Nbr عشان الـ map يشتغل (نحتفظ بأول صف لكل Order Nbr)
                    df2_unique = df2.drop_duplicates(subset=["Order Nbr"], keep="first")
                    packed_series = df2_unique.set_index("Order Nbr")[
                        "Packed Timestamp"
                    ]
                    df1["Packed Timestamp"] = df1["Order Nbr"].map(packed_series)
                    # طباعة عينة من Outbound2 للتأكد من الداتا
                    print("\n[Outbound2] عينة من الشيت — Order Nbr و Packed Timestamp:")
                    for idx, r in df2.head(8).iterrows():
                        print(
                            f"  Order Nbr: {r['Order Nbr']!r}  |  Packed: {r['Packed Timestamp']}"
                        )
                    print(f"  عدد صفوف Outbound2: {len(df2)}\n")
                    # لو معظم القيم فاضية، نجرب المفتاح الموحّد (مثلاً 1 و 001 يتطابقان)
                    if df1["Packed Timestamp"].notna().sum() < len(df1) // 2:
                        df2["_ok"] = _order_key(df2["Order Nbr"])
                        packed_by_ok = df2.drop_duplicates(
                            subset=["_ok"], keep="first"
                        ).set_index("_ok")["Packed Timestamp"]
                        df1["_ok"] = _order_key(df1["Order Nbr"])
                        df1["Packed Timestamp"] = df1["Packed Timestamp"].fillna(
                            df1["_ok"].map(packed_by_ok)
                        )
                        df1.drop(columns=["_ok"], inplace=True, errors="ignore")
                else:
                    df1["Packed Timestamp"] = pd.NaT
            else:
                df1["Packed Timestamp"] = pd.NaT

            if "Packed Timestamp" not in df1.columns:
                df1["Packed Timestamp"] = pd.NaT

            # طباعة في الترمينال: نتيجة الربط مع Outbound2
            packed_filled = df1["Packed Timestamp"].notna().sum()
            print("\n" + "=" * 70)
            print("Outbound — نتيجة الربط (Packed Timestamp من Outbound2)")
            print("=" * 70)
            print(f"  إجمالي الصفوف (Outbound1): {len(df1)}")
            print(f"  صفوف فيها Packed Timestamp غير فاضي: {packed_filled}")
            print(f"  صفوف فاضية (مفيش ربط): {len(df1) - packed_filled}")
            if outbound2_name:
                print(f"  شيت Outbound2 المستخدم: {outbound2_name}")
            else:
                print("  ⚠️ مفيش شيت Outbound2 تم استخدامه")
            print("  عينة من df1 (Order Nbr | Packed Timestamp | Ship Date):")
            for i, row in df1.head(10).iterrows():
                pt = row.get("Packed Timestamp")
                pt_str = str(pt)[:19] if pd.notna(pt) and pt is not pd.NaT else "(فاضي)"
                sd = row.get("Ship Date")
                sd_str = str(sd)[:19] if pd.notna(sd) and sd is not pd.NaT else "(فاضي)"
                print(
                    f"    Order Nbr: {row.get('Order Nbr')!r}  |  Packed: {pt_str}  |  Ship: {sd_str}"
                )
            print("=" * 70 + "\n")

            # لو لسه فاضي: نجرب نأخذ Packed من Outbound1 لو العمود موجود فيه
            if df1["Packed Timestamp"].isna().all():
                packed_in_ob1 = find_col(
                    df1, ["Packed Timestamp", "Packed Date", "Packed", "Packed Time"]
                )
                if packed_in_ob1 and packed_in_ob1 in df1.columns:
                    df1["Packed Timestamp"] = pd.to_datetime(
                        df1[packed_in_ob1], errors="coerce"
                    )

            # ========== علاقة Outbound1 و Outbound2 — حساب Hit/Miss ==========
            # المقارنة: Ship Date (من Outbound1) مع Packed Timestamp (من Outbound2).
            # الفرق = كم يوم/ساعة من التعبئة (Packed) لحد الشحن (Ship).
            #   • لو الفرق ≤ يوم واحد (أو ≤ 24 ساعة) → Hit
            #   • لو الفرق > يوم واحد (أو > 24 ساعة) → Miss
            #   • لو Packed Timestamp ناقص (مفيش ربط) → Pending
            # ==========
            # الفرق بالساعات: Ship Date - Packed Timestamp
            df1["Cycle Hours"] = (
                (df1["Ship Date"] - df1["Packed Timestamp"])
                .dt.total_seconds()
                .div(3600)
            )
            df1["Cycle Hours"] = df1["Cycle Hours"].round(2)
            # الفرق بالأيام (للعرض في الجدول)
            df1["Cycle Days"] = (df1["Cycle Hours"] / 24).round(2)
            # Hit = فرق ≤ 24 ساعة (يعني ≤ يوم واحد)، Miss = أكتر من 24 ساعة
            df1["is_hit"] = df1["Cycle Hours"].le(24) & df1["Cycle Hours"].notna()
            df1["HIT or MISS"] = np.where(df1["is_hit"], "Hit", "Miss")
            df1.loc[df1["Cycle Hours"].isna(), "HIT or MISS"] = "Pending"

            # الشهر من Ship Date أو Create Timestamp
            month_source = df1["Ship Date"].copy()
            month_source = month_source.fillna(df1["Create Timestamp"])
            df1["Month"] = month_source.dt.strftime("%b")

            # فلتر الشهر
            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in selected_months_norm:
                        selected_months_norm.append(norm)
            selected_month_norm = (
                self.normalize_month_label(selected_month)
                if selected_month and not selected_months_norm
                else None
            )
            if selected_months_norm:
                df1 = df1[
                    df1["Month"]
                    .fillna("")
                    .str.lower()
                    .isin([m.lower() for m in selected_months_norm])
                ]
            elif selected_month_norm:
                df1 = df1[
                    df1["Month"].fillna("").str.lower() == selected_month_norm.lower()
                ]

            if df1.empty:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ No outbound records for the selected period.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                    "stats": {},
                }

            df_summary = df1.dropna(subset=["Month"]).copy()
            if df_summary.empty:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ No valid month values in outbound data.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                    "stats": {},
                }

            def month_order_value(label):
                if not label:
                    return 999
                label = str(label).strip()[:3].title()
                for idx in range(1, 13):
                    if month_abbr[idx] == label:
                        return idx
                return 999

            total_per_month = (
                df_summary.groupby("Month")["Order Nbr"]
                .nunique()
                .reset_index(name="Total_Shipments")
            )
            hits_df = (
                df_summary[df_summary["is_hit"]]
                .groupby("Month")["Order Nbr"]
                .nunique()
                .reset_index(name="Hits")
            )
            summary_df = total_per_month.merge(hits_df, on="Month", how="left")
            summary_df["Hits"] = summary_df["Hits"].fillna(0).astype(int)
            summary_df["Misses"] = summary_df["Total_Shipments"] - summary_df["Hits"]
            summary_df["Hit %"] = (
                summary_df["Hits"]
                / summary_df["Total_Shipments"].replace(0, np.nan)
                * 100
            )
            summary_df["Hit %"] = summary_df["Hit %"].fillna(0).round(2)
            summary_df = summary_df.sort_values(
                by="Month", key=lambda col: col.map(month_order_value)
            )

            months_with_miss = summary_df[summary_df["Misses"] > 0]["Month"].tolist()
            months_with_hit_only_ob = summary_df[summary_df["Misses"] == 0][
                "Month"
            ].tolist()
            ordered_months = months_with_miss + months_with_hit_only_ob

            kpi_rows = []
            for _, row in summary_df.iterrows():
                m = row["Month"]
                kpi_rows.append(
                    {
                        "Month": m,
                        "Total Shipments": int(row["Total_Shipments"]),
                        "Hit (≤24h)": int(row["Hits"]),
                        "Miss (>24h)": int(row["Misses"]),
                        "Hit %": float(row["Hit %"]),
                    }
                )

            pivot_cols = ["KPI"] + ordered_months
            if len(ordered_months) >= 2:
                pivot_cols.append("2025")

            hit_pct_row = {"KPI": "Hit %"}
            total_row = {"KPI": "Total Shipments"}
            hit_row = {"KPI": "Hit (≤24h)"}
            miss_row = {"KPI": "Miss (>24h)"}
            for m in ordered_months:
                r = next((x for x in kpi_rows if x["Month"] == m), None)
                if r:
                    total_val = int(r["Total Shipments"])
                    hit_val = int(r["Hit (≤24h)"])
                    miss_val = int(r["Miss (>24h)"])
                    total_row[m] = total_val
                    hit_row[m] = hit_val
                    miss_row[m] = miss_val
                    hit_pct_row[m] = (
                        int(round(hit_val / total_val * 100)) if total_val > 0 else 0
                    )
            if "2025" in pivot_cols:
                total_2025 = sum(r["Total Shipments"] for r in kpi_rows)
                hit_2025 = sum(r["Hit (≤24h)"] for r in kpi_rows)
                hit_pct_row["2025"] = (
                    int(round(hit_2025 / total_2025 * 100)) if total_2025 > 0 else 0
                )
                total_row["2025"] = int(sum(r["Total Shipments"] for r in kpi_rows))
                hit_row["2025"] = int(sum(r["Hit (≤24h)"] for r in kpi_rows))
                miss_row["2025"] = int(sum(r["Miss (>24h)"] for r in kpi_rows))

            # Total Shipments آخر صف في الجدول
            summary_data_pivot = [hit_pct_row, hit_row, miss_row, total_row]
            summary_columns = pivot_cols
            summary_data = summary_data_pivot

            overall_total = int(df1.shape[0])
            overall_hits = int(df1["is_hit"].sum())
            overall_miss = overall_total - overall_hits
            overall_hit_pct = (
                round((overall_hits / overall_total) * 100, 2) if overall_total else 0
            )

            chart_data = []
            hit_pct_for_chart = next(
                (r for r in summary_data if r.get("KPI") == "Hit %"), None
            )
            if hit_pct_for_chart:
                data_points = [
                    {"label": m, "y": float(hit_pct_for_chart.get(m, 0))}
                    for m in ordered_months
                    if hit_pct_for_chart.get(m) is not None
                ]
                if "2025" in hit_pct_for_chart:
                    data_points.append(
                        {"label": "2025", "y": float(hit_pct_for_chart["2025"])}
                    )
                chart_data.append(
                    {
                        "type": "column",
                        "name": "Outbound Hit %",
                        "color": "#74c0fc",
                        "related_table": "sub-table-outbound-hit-summary",
                        "dataPoints": data_points,
                    }
                )

            months_with_miss_label = (
                " — Months with Miss: " + ", ".join(months_with_miss)
                if months_with_miss
                else " — All months Hit"
            )
            summary_table = {
                "id": "sub-table-outbound-hit-summary",
                "title": "Outbound KPI ≤ 24h" + months_with_miss_label,
                "columns": summary_columns,
                "data": summary_data,
                "chart_data": chart_data,
                "months_with_miss": months_with_miss,
                "months_with_hit_only": months_with_hit_only_ob,
            }

            # جدول التفاصيل: Order Nbr أولاً ثم Customer Name وباقي الأعمدة
            detail_columns = [
                "Order Nbr",
                "Customer Name",
                "Create Timestamp",
                "Customer City",
                "Order Type",
                "Status",
                "Packed Timestamp",
                "Ship Date",
                "Days",
                "Month",
                "HIT or MISS",
            ]

            detail_df = df1.copy()
            detail_df["_sort_ts"] = detail_df["Ship Date"]

            def _fmt_date(x):
                if pd.isna(x) or x is pd.NaT:
                    return ""
                try:
                    return pd.Timestamp(x).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    return ""

            for col in ["Create Timestamp", "Ship Date", "Packed Timestamp"]:
                if col in detail_df.columns:
                    detail_df[col] = detail_df[col].apply(_fmt_date)
                else:
                    detail_df[col] = ""

            detail_df["Days"] = detail_df["Cycle Days"].apply(
                lambda x: "" if pd.isna(x) else str(int(np.ceil(float(x))))
            )

            for col in detail_columns:
                if col not in detail_df.columns:
                    detail_df[col] = ""

            drop_cols = [
                c
                for c in [
                    "_sort_ts",
                    "Cycle Hours",
                    "Cycle Days",
                    "is_hit",
                ]
                if c in detail_df.columns
            ]
            detail_rows_raw = (
                detail_df.sort_values("_sort_ts", ascending=False)
                .drop(columns=drop_cols)
                .head(500)[detail_columns]
                .to_dict(orient="records")
            )

            def _to_blank(val):
                if val is None:
                    return ""
                if isinstance(val, float) and (pd.isna(val) or (val != val)):
                    return ""
                s = str(val).strip()
                if s.lower() in ("nan", "nat", "none", "<nat>"):
                    return ""
                return s

            detail_rows = [
                {k: _to_blank(v) for k, v in row.items()} for row in detail_rows_raw
            ]

            # طباعة بيانات جدول Outbound Shipments Detail في الترمينال (مع Packed Timestamp)
            print("\n" + "=" * 90)
            print(
                "Outbound Shipments Detail — بيانات الجدول المرسلة للقالب (أول 15 صف)"
            )
            print("=" * 90)
            print("  الأعمدة:", detail_columns)
            print("-" * 90)
            for i, row in enumerate(detail_rows[:15], 1):
                packed_val = row.get("Packed Timestamp", "")
                ship_val = row.get("Ship Date", "")
                cust = row.get("Customer Name", "")[:25]
                print(
                    f"  {i:2d} | Customer: {cust:25s} | Packed Timestamp: {str(packed_val):20s} | Ship Date: {str(ship_val):20s} | HIT or MISS: {row.get('HIT or MISS', '')}"
                )
            print("-" * 90)
            print(f"  إجمالي الصفوف في الجدول: {len(detail_rows)}")
            print("=" * 90 + "\n")

            detail_df_for_options = detail_df.sort_values(
                "_sort_ts", ascending=False
            ).drop(columns=[c for c in drop_cols if c in detail_df.columns])
            facility_options = sorted(
                detail_df_for_options["Customer Name"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            status_options = sorted(
                detail_df_for_options["Status"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            month_options = sorted(
                detail_df_for_options["Month"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            city_options = sorted(
                detail_df_for_options["Customer City"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            hit_miss_options = ["Hit", "Miss", "Pending"]

            detail_table = {
                "id": "sub-table-outbound-detail",
                "title": "Outbound Shipments Detail",
                "columns": detail_columns,
                "data": detail_rows,
                "chart_data": [],
                "full_width": True,
                "filter_options": {
                    "facility_codes": facility_options,
                    "statuses": status_options,
                    "months": month_options,
                    "customer_cities": city_options,
                    "hit_miss": hit_miss_options,
                },
            }

            return {
                "detail_html": "",
                "sub_tables": [summary_table, detail_table],
                "chart_data": chart_data,
                "stats": {
                    "total": overall_total,
                    "hit": overall_hits,
                    "miss": overall_miss,
                    "hit_pct": overall_hit_pct,
                },
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error processing outbound shipments: {e}</p>",
                "sub_tables": [],
                "chart_data": [],
                "stats": {},
            }

    def filter_inbound(self, request, selected_month=None, selected_months=None):
        """
        🔹 يحسب KPI لشحنات الـ Inbound (≤24 ساعة بين Create Timestamp و Last LPN Rcv TS).
        🔹 يعيد جدول ملخص شهري + جدول تفصيلي للشحنات.
        """
        try:
            import os

            excel_path = self.get_uploaded_file_path(request) or self.get_excel_path()
            if not excel_path or not os.path.exists(excel_path):
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sheet_name = next(
                (s for s in xls.sheet_names if "inbound" in s.lower()), None
            )
            if not sheet_name:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ Sheet containing 'Inbound' was not found.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
            if df.empty:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ Inbound sheet is empty.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            df.columns = df.columns.astype(str).str.strip()

            def normalize_name(val):
                return re.sub(r"[^a-z0-9]", "", str(val).strip().lower())

            def find_column(possible_names):
                normalized_map = {normalize_name(col): col for col in df.columns}
                for name in possible_names:
                    norm = normalize_name(name)
                    if norm in normalized_map:
                        return normalized_map[norm]
                for col in df.columns:
                    col_norm = normalize_name(col)
                    if any(normalize_name(name) in col_norm for name in possible_names):
                        return col
                return None

            column_aliases = {
                "facility": [
                    "facility code",
                    "facility",
                    "facilitycode",
                ],
                "shipment": [
                    "shipment nbr",
                    "shipment number",
                    "shipment no",
                    "shipment#",
                    "shipment id",
                ],
                "status": ["status", "shipment status"],
                "create_ts": ["create timestamp", "created timestamp", "creation time"],
                "arrival": ["arrival date", "arrival timestamp"],
                "offload": ["offloading date", "offload date", "offload timestamp"],
                "last_lpn": [
                    "last lpn rcv ts",
                    "last lpn receive ts",
                    "last lpn rcv timestamp",
                    "last lpn rcv",
                ],
                "reason": [
                    "reason",
                    "miss reason",
                    "delay reason",
                    "remarks",
                    "comments",
                    "cause",
                    "reason code",
                ],
            }

            column_map = {
                key: find_column(names) for key, names in column_aliases.items()
            }

            required_keys = ["shipment", "status", "create_ts", "last_lpn"]
            missing_required = [key for key in required_keys if not column_map.get(key)]
            if missing_required:
                missing_labels = ", ".join(missing_required)
                return {
                    "detail_html": f"<p class='text-danger'>⚠️ Missing required columns for inbound analysis: {missing_labels}</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            rename_map = {}
            if column_map.get("facility"):
                rename_map[column_map["facility"]] = "Facility Code"
            if column_map["shipment"]:
                rename_map[column_map["shipment"]] = "Shipment Nbr"
            if column_map["status"]:
                rename_map[column_map["status"]] = "Status"
            if column_map["create_ts"]:
                rename_map[column_map["create_ts"]] = "Create Timestamp"
            if column_map["arrival"]:
                rename_map[column_map["arrival"]] = "Arrival Date"
            if column_map["offload"]:
                rename_map[column_map["offload"]] = "Offloading Date"
            if column_map["last_lpn"]:
                rename_map[column_map["last_lpn"]] = "Last LPN Rcv TS"
            if column_map.get("reason"):
                rename_map[column_map["reason"]] = "Reason"

            df = df.rename(columns=rename_map)
            if "Reason" not in df.columns:
                df["Reason"] = ""
            if "Facility Code" not in df.columns:
                df["Facility Code"] = ""

            for col in [
                "Create Timestamp",
                "Arrival Date",
                "Offloading Date",
                "Last LPN Rcv TS",
            ]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                else:
                    df[col] = pd.NaT

            df["Shipment Nbr"] = df["Shipment Nbr"].astype(str).str.strip()
            df["Status"] = df["Status"].astype(str).str.strip()
            if "Facility Code" in df.columns:
                df["Facility Code"] = df["Facility Code"].astype(str).str.strip()

            df["Cycle Hours"] = (
                (df["Last LPN Rcv TS"] - df["Create Timestamp"])
                .dt.total_seconds()
                .div(3600)
            )
            df["Cycle Hours"] = df["Cycle Hours"].round(2)
            df["Cycle Days"] = (df["Cycle Hours"] / 24).round(2)

            df["is_hit"] = df["Cycle Hours"].le(24)
            df["is_hit"] = df["is_hit"] & df["Cycle Hours"].notna()

            df["HIT or MISS"] = np.where(df["is_hit"], "Hit", "Miss")
            df.loc[df["Cycle Hours"].isna(), "HIT or MISS"] = "Pending"

            month_source = df["Create Timestamp"].copy()
            month_source = month_source.fillna(df["Arrival Date"])
            month_source = month_source.fillna(df["Offloading Date"])
            df["Month"] = month_source.dt.strftime("%b")

            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in seen:
                        seen.add(norm)
                        selected_months_norm.append(norm)

            selected_month_norm = (
                self.normalize_month_label(selected_month)
                if selected_month and not selected_months_norm
                else None
            )

            if selected_months_norm:
                df = df[
                    df["Month"]
                    .fillna("")
                    .str.lower()
                    .isin([m.lower() for m in selected_months_norm])
                ]
            elif selected_month_norm:
                df = df[
                    df["Month"].fillna("").str.lower() == selected_month_norm.lower()
                ]

            if df.empty:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ No inbound records for the selected period.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            df_summary = df.dropna(subset=["Month"]).copy()
            if df_summary.empty:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ Inbound data has no valid month values.</p>",
                    "sub_tables": [],
                    "chart_data": [],
                }

            def month_order_value(label):
                if not label:
                    return 999
                label = label.strip()[:3].title()
                for idx in range(1, 13):
                    if month_abbr[idx] == label:
                        return idx
                return 999

            total_per_month = (
                df_summary.groupby("Month")["Shipment Nbr"]
                .nunique()
                .reset_index(name="Total_Shipments")
            )
            hits_df = (
                df_summary[df_summary["is_hit"]]
                .groupby("Month")["Shipment Nbr"]
                .nunique()
                .reset_index(name="Hits")
            )
            summary_df = total_per_month.merge(hits_df, on="Month", how="left")
            summary_df["Hits"] = summary_df["Hits"].fillna(0).astype(int)
            summary_df["Misses"] = summary_df["Total_Shipments"] - summary_df["Hits"]
            summary_df["Hit %"] = (
                summary_df["Hits"]
                / summary_df["Total_Shipments"].replace(0, np.nan)
                * 100
            )
            summary_df["Hit %"] = summary_df["Hit %"].fillna(0).round(2)
            summary_df = summary_df.sort_values(
                by="Month", key=lambda col: col.map(month_order_value)
            )

            months_with_miss = summary_df[summary_df["Misses"] > 0]["Month"].tolist()
            months_with_hit_only = summary_df[summary_df["Misses"] == 0][
                "Month"
            ].tolist()
            ordered_months = months_with_miss + months_with_hit_only

            df_miss = df_summary[~df_summary["is_hit"]].copy()
            df_miss["Reason"] = (
                df_miss.get("Reason", pd.Series([""] * len(df_miss)))
                .astype(str)
                .str.strip()
            )
            # لا نعيّن "(No reason)" — سنستبعد صفوف الـ Reason الفارغة من الجدول لاحقاً

            reason_pivot = None
            if not df_miss.empty and "Reason" in df_miss.columns:
                reason_counts = (
                    df_miss.groupby(["Reason", "Month"])["Shipment Nbr"]
                    .nunique()
                    .reset_index(name="cnt")
                )
                if not reason_counts.empty:
                    reason_pivot = reason_counts.pivot_table(
                        index="Reason", columns="Month", values="cnt", fill_value=0
                    ).reset_index()
                    # استبعاد "(No reason)" أو صفوف Reason فارغة من العرض
                    reason_pivot = reason_pivot[
                        reason_pivot["Reason"].astype(str).str.strip().isin(["", "nan", "NaN", "(No reason)"]) == False
                    ].copy()
                    for m in ordered_months:
                        if m not in reason_pivot.columns:
                            reason_pivot[m] = 0
                    if not reason_pivot.empty:
                        reason_pivot = reason_pivot.reindex(
                            columns=["Reason"]
                            + [c for c in ordered_months if c in reason_pivot.columns]
                        )
                    else:
                        reason_pivot = None

            kpi_rows = []
            for _, row in summary_df.iterrows():
                m = row["Month"]
                kpi_rows.append(
                    {
                        "Month": m,
                        "Total Shipments": int(row["Total_Shipments"]),
                        "Hit (≤24h)": int(row["Hits"]),
                        "Miss (>24h)": int(row["Misses"]),
                        "Hit %": float(row["Hit %"]),
                        "_has_miss": row["Misses"] > 0,
                    }
                )

            pivot_cols = ["KPI"] + ordered_months
            if len(ordered_months) >= 2:
                pivot_cols.append("2025")

            hit_pct_row = {"KPI": "Hit %"}
            total_row = {"KPI": "Total Shipments"}
            hit_row = {"KPI": "Hit (≤24h)"}
            miss_row = {"KPI": "Miss (>24h)"}
            for m in ordered_months:
                r = next((x for x in kpi_rows if x["Month"] == m), None)
                if r:
                    total_val = int(r["Total Shipments"])
                    hit_val = int(r["Hit (≤24h)"])
                    miss_val = int(r["Miss (>24h)"])
                    total_row[m] = total_val
                    hit_row[m] = hit_val
                    miss_row[m] = miss_val
                    hit_pct_row[m] = (
                        int(round(hit_val / total_val * 100)) if total_val > 0 else 0
                    )
            if "2025" in pivot_cols:
                total_2025 = sum(r["Total Shipments"] for r in kpi_rows)
                hit_2025 = sum(r["Hit (≤24h)"] for r in kpi_rows)
                hit_pct_row["2025"] = (
                    int(round(hit_2025 / total_2025 * 100)) if total_2025 > 0 else 0
                )
                total_row["2025"] = int(sum(r["Total Shipments"] for r in kpi_rows))
                hit_row["2025"] = int(sum(r["Hit (≤24h)"] for r in kpi_rows))
                miss_row["2025"] = int(sum(r["Miss (>24h)"] for r in kpi_rows))

            # ترتيب الصفوف: Hit % ثم Hit (≤24h) ثم Miss (>24h) ثم أسباب الـ Miss ثم Total Shipments آخراً
            summary_data_pivot = [hit_pct_row, hit_row, miss_row]

            if reason_pivot is not None and not reason_pivot.empty:
                for _, r in reason_pivot.iterrows():
                    reason_row = {"KPI": str(r["Reason"])}
                    for c in ordered_months:
                        if c in r.index:
                            reason_row[c] = int(r[c]) if pd.notna(r[c]) else 0
                    if "2025" in pivot_cols:
                        reason_row["2025"] = int(
                            sum(
                                int(r[c]) if c in r.index and pd.notna(r[c]) else 0
                                for c in ordered_months
                            )
                        )
                    summary_data_pivot.append(reason_row)
            summary_data_pivot.append(total_row)

            def _to_display_int(val):
                if val is None or (
                    isinstance(val, float) and (np.isnan(val) or np.isinf(val))
                ):
                    return 0
                if isinstance(val, (int, np.integer)):
                    return int(val)
                try:
                    return int(round(float(val)))
                except (ValueError, TypeError):
                    return 0

            for row in summary_data_pivot:
                for k in list(row.keys()):
                    if k != "KPI" and isinstance(
                        row[k], (int, float, np.integer, np.floating)
                    ):
                        row[k] = _to_display_int(row[k])

            summary_columns = pivot_cols
            summary_data = summary_data_pivot

            overall_total = int(df.shape[0])
            overall_hits = int(df["is_hit"].sum())
            overall_miss = overall_total - overall_hits
            overall_hit_pct = (
                round((overall_hits / overall_total) * 100, 2) if overall_total else 0
            )

            chart_data = []
            hit_pct_for_chart = next(
                (r for r in summary_data if r.get("KPI") == "Hit %"), None
            )
            if hit_pct_for_chart:
                data_points = []
                for m in ordered_months:
                    v = hit_pct_for_chart.get(m)
                    if v is not None and isinstance(v, (int, float)):
                        data_points.append({"label": m, "y": float(v)})
                if "2025" in hit_pct_for_chart:
                    data_points.append(
                        {"label": "2025", "y": float(hit_pct_for_chart["2025"])}
                    )
                chart_data.append(
                    {
                        "type": "column",
                        "name": "Inbound Hit %",
                        "color": "#74c0fc",
                        "related_table": "sub-table-inbound-hit-summary",
                        "dataPoints": data_points,
                    }
                )

            detail_columns = [
                "Facility Code",
                "Shipment Nbr",
                "Status",
                "Create Timestamp",
                "Arrival Date",
                "Offloading Date",
                "Last LPN Rcv TS",
                "Days",
                "Month",
                "HIT or MISS",
            ]

            detail_df = df.copy()
            detail_df["_sort_ts"] = detail_df["Create Timestamp"]

            def _fmt_date(x):
                if pd.isna(x) or x is pd.NaT:
                    return ""
                try:
                    return pd.Timestamp(x).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    return ""

            for col in [
                "Create Timestamp",
                "Arrival Date",
                "Offloading Date",
                "Last LPN Rcv TS",
            ]:
                if col in detail_df.columns:
                    detail_df[col] = detail_df[col].apply(_fmt_date)
                else:
                    detail_df[col] = ""

            detail_df["Days"] = detail_df["Cycle Days"].apply(
                lambda x: "" if pd.isna(x) else str(int(np.ceil(float(x))))
            )

            if "Facility Code" not in detail_df.columns:
                detail_df["Facility Code"] = ""
            if "HIT or MISS" not in detail_df.columns:
                detail_df["HIT or MISS"] = ""

            for col in detail_columns:
                if col not in detail_df.columns:
                    detail_df[col] = ""

            drop_cols = [
                c
                for c in ["_sort_ts", "Cycle Hours", "Cycle Days", "is_hit"]
                if c in detail_df.columns
            ]
            detail_rows_raw = (
                detail_df.sort_values("_sort_ts", ascending=False)
                .drop(columns=drop_cols)
                .head(500)[detail_columns]
                .to_dict(orient="records")
            )

            def _to_blank(val):
                if val is None:
                    return ""
                if isinstance(val, float) and (pd.isna(val) or (val != val)):
                    return ""
                s = str(val).strip()
                if s.lower() in ("nan", "nat", "none", "<nat>"):
                    return ""
                return s

            detail_rows = [
                {k: _to_blank(v) for k, v in row.items()} for row in detail_rows_raw
            ]

            # خيارات الفلاتر لجدول Inbound Shipments Detail (من كل البيانات قبل head(500))
            detail_df_for_options = detail_df.sort_values(
                "_sort_ts", ascending=False
            ).drop(columns=[c for c in drop_cols if c in detail_df.columns])
            facility_options = sorted(
                detail_df_for_options["Facility Code"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            status_options = sorted(
                detail_df_for_options["Status"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            month_options = sorted(
                detail_df_for_options["Month"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", None)
                .dropna()
                .unique()
                .tolist()
            )
            hit_miss_options = ["Hit", "Miss", "Pending"]

            months_with_miss_label = (
                " — Months with Miss: " + ", ".join(months_with_miss)
                if months_with_miss
                else " — All months Hit"
            )
            summary_table = {
                "id": "sub-table-inbound-hit-summary",
                "title": "Inbound KPI ≤ 24h" + months_with_miss_label,
                "columns": summary_columns,
                "data": summary_data,
                "chart_data": chart_data,
                "months_with_miss": months_with_miss,
                "months_with_hit_only": months_with_hit_only,
            }

            # طباعة جدول KPI (Inbound KPI ≤ 24h) في الترمينال
            print("\n" + "=" * 80)
            print("Inbound KPI ≤ 24h — summary_table data")
            print("=" * 80)
            print("Columns:", summary_columns)
            print("-" * 80)
            for row in summary_data:
                kpi_name = row.get("KPI", "")
                rest = {k: v for k, v in row.items() if k != "KPI"}
                print(f"  KPI: {kpi_name}")
                for col, val in rest.items():
                    print(f"    {col}: {val}")
                print("-" * 80)
            print("=" * 80 + "\n")

            detail_table = {
                "id": "sub-table-inbound-detail",
                "title": "Inbound Shipments Detail",
                "columns": detail_columns,
                "data": detail_rows,
                "chart_data": [],
                "full_width": True,
                "filter_options": {
                    "facility_codes": facility_options,
                    "statuses": status_options,
                    "months": month_options,
                    "hit_miss": hit_miss_options,
                },
            }

            # طباعة جدول Inbound Shipments Detail في الترمينال
            print("\n" + "=" * 100)
            print(
                "Inbound Shipments Detail — Create Timestamp | Arrival Date | Offloading Date | Status | HIT or MISS"
            )
            print("=" * 100)
            for i, row in enumerate(detail_rows[:50], 1):  # أول 50 صف
                create_ts = str(row.get("Create Timestamp", ""))[:16]
                arrival = str(row.get("Arrival Date", ""))[:16]
                offload = str(row.get("Offloading Date", ""))[:16]
                status = str(row.get("Status", ""))[:18]
                hit_miss = str(row.get("HIT or MISS", ""))
                print(
                    f"  {i:3d} | Create: {create_ts:16s} | Arrival: {arrival:16s} | Offload: {offload:16s} | Status: {status:18s} | {hit_miss}"
                )
            if len(detail_rows) > 50:
                print(f"  ... و {len(detail_rows) - 50} صف إضافي")
            print("=" * 100 + "\n")

            return {
                "detail_html": "",
                "sub_tables": [summary_table, detail_table],
                "chart_data": chart_data,
                "stats": {
                    "total": overall_total,
                    "hit": overall_hits,
                    "miss": overall_miss,
                    "hit_pct": overall_hit_pct,
                },
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error while processing inbound data: {e}</p>",
                "sub_tables": [],
                "chart_data": [],
            }

    # Merge sheets from Excel
    def filter_pods_update(self, request, selected_month=None, selected_months=None):
        """
        تاب PODs: قراءة من شيت PODs.
        - فلترة بـ W.HNAME، Created on، PGI Date.
        - حساب الأيام بين Created on و PGI Date (باستثناء يوم الجمعة).
        - Hit = استلام خلال 7 أيام أو أقل، Miss = أكثر من 7 أيام.
        - الجدول العلوي: KPI + صفوف المدن لكل شهر.
        - الجدول السفلي: التفاصيل مع فلتر W.HNAME، الشهور، Hit/Miss؛ البادجات على المدن و Hit/Miss.
        """
        import pandas as pd
        from django.template.loader import render_to_string
        import os
        from datetime import datetime, timedelta

        try:
            excel_path = self.get_excel_path()
            if not excel_path or not os.path.exists(excel_path):
                return {"error": "⚠️ Excel file not found."}

            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sheet_name = next(
                (
                    s
                    for s in xls.sheet_names
                    if "pod" in s.lower() and "update" not in s.lower()
                ),
                None,
            )
            if not sheet_name:
                return {"error": "⚠️ Sheet 'PODs' was not found."}

            df = pd.read_excel(
                excel_path,
                sheet_name=sheet_name,
                engine="openpyxl",
                dtype=str,
                header=0,
            ).fillna("")
            df.columns = df.columns.astype(str).str.strip()

            def _norm(val):
                return re.sub(r"[^a-z0-9]", "", str(val).strip().lower())

            def _find_col(dframe, names):
                nmap = {_norm(c): c for c in dframe.columns}
                for name in names:
                    n = _norm(name)
                    if n in nmap:
                        return nmap[n]
                for col in dframe.columns:
                    if any(_norm(n) in _norm(col) for n in names):
                        return col
                return None

            col_created = _find_col(df, ["created on", "createdon", "created"])
            col_pgi = _find_col(df, ["pgi date", "pgidate", "pgi"])
            col_whname = _find_col(
                df, ["w.hname", "whname", "warehouse name", "warehouse"]
            )
            col_shpng = _find_col(df, ["shpng pnt", "shpngpnt", "shipping point"])
            col_plant = _find_col(df, ["plant"])
            col_whno = _find_col(df, ["wh no", "whno", "warehouse no"])
            col_delivery = _find_col(df, ["delivery"])
            col_inv = _find_col(df, ["inv", "invoice"])
            col_shipto = _find_col(df, ["ship-to party", "shiptoparty", "ship to"])
            col_shipto_name = _find_col(
                df, ["name of the ship-to party", "ship-to party name"]
            )
            col_qty = _find_col(df, ["qty", "quantity"])
            col_unit = _find_col(df, ["unit"])
            col_city = _find_col(df, ["city"])

            if not col_created or not col_pgi or not col_whname:
                return {
                    "error": "⚠️ Required columns (Created on, PGI Date, W.HNAME) not found."
                }

            # تحويل التواريخ
            df["_created_dt"] = pd.to_datetime(df[col_created], errors="coerce")
            df["_pgi_dt"] = pd.to_datetime(df[col_pgi], errors="coerce")

            # حساب Days (باستثناء يوم الجمعة) - الفرق بين Created on و PGI Date
            def business_days_between(start, end):
                if pd.isna(start) or pd.isna(end):
                    return None
                if start > end:
                    return None
                days = 0
                current = start.date()
                end_date = end.date()
                # نحسب الأيام بدون الجمعة (من Created on إلى PGI Date)
                while current < end_date:  # < وليس <= لأننا لا نحسب اليوم الأخير
                    if current.weekday() != 4:  # 4 = Friday
                        days += 1
                    current += timedelta(days=1)
                return days

            df["Days"] = df.apply(
                lambda row: business_days_between(row["_created_dt"], row["_pgi_dt"]),
                axis=1,
            )
            # Hit = استلام خلال 7 أيام أو أقل (بدون الجمعة)، Miss = أكثر من 7 أيام
            df["Hit or Miss"] = df["Days"].apply(
                lambda d: (
                    "Hit"
                    if d is not None and d <= 7
                    else ("Miss" if d is not None else "Pending")
                )
            )
            df["Days"] = df["Days"].apply(
                lambda d: str(int(d)) if d is not None else ""
            )

            # استخراج الشهر من Created on (نحتفظ بـ _created_dt و _pgi_dt لجدول التفاصيل)
            df["Month"] = df["_created_dt"].dt.strftime("%b").fillna("")

            # فلترة الشهر
            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm.lower() not in seen:
                        seen.add(norm.lower())
                        selected_months_norm.append(norm)

            if selected_months_norm:
                df = df[
                    df["Month"]
                    .str.lower()
                    .isin([m.lower() for m in selected_months_norm])
                ]
            elif selected_month:
                month_norm = self.normalize_month_label(selected_month)
                if month_norm:
                    df = df[df["Month"].str.lower() == month_norm.lower()]

            if df.empty:
                return {
                    "detail_html": "<p class='text-warning text-center p-4'>⚠️ No data available for selected period.</p>",
                    "count": 0,
                    "hit_pct": 0,
                }

            # إحصائيات عامة (لكروت KPI): عدد الشحنات الكل = Hit + Miss فقط
            hit_count = len(df[df["Hit or Miss"] == "Hit"])
            miss_count = len(df[df["Hit or Miss"] == "Miss"])
            total_shipments = hit_count + miss_count
            hit_pct = (
                round((hit_count / total_shipments * 100), 2)
                if total_shipments > 0
                else 0
            )
            miss_pct = (
                round((miss_count / total_shipments * 100), 2)
                if total_shipments > 0
                else 0
            )

            # تجميع كل المدن مع بعض (جدول واحد وشارت واحد)
            month_order = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            months_raw = df["Month"].dropna().unique().tolist()
            months = sorted(
                months_raw,
                key=lambda m: month_order.index(m) if m in month_order else 999,
            )

            # الحصول على قائمة المدن
            cities = sorted(
                df[col_whname]
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )

            if not months:
                return {
                    "detail_html": "<p class='text-warning text-center p-4'>⚠️ No months found in data.</p>",
                    "count": 0,
                    "hit_pct": 0,
                }

            # تجميع حسب المدينة والشهر: Hit (Closed), Miss (Pending), Total
            # لكل مدينة: Closed, Pending, Total
            city_data = {}
            for city in cities:
                df_city = df[df[col_whname].astype(str).str.strip() == city].copy()
                if df_city.empty:
                    continue

                closed_by_month_city = []
                pending_by_month_city = []
                total_by_month_city = []

                for month in months:
                    df_month_city = df_city[df_city["Month"] == month]
                    hit_month = len(
                        df_month_city[df_month_city["Hit or Miss"] == "Hit"]
                    )
                    miss_month = len(
                        df_month_city[df_month_city["Hit or Miss"] == "Miss"]
                    )
                    closed_by_month_city.append(hit_month)
                    pending_by_month_city.append(miss_month)
                    total_by_month_city.append(hit_month + miss_month)

                # YTD لكل مدينة
                closed_ytd_city = sum(closed_by_month_city)
                pending_ytd_city = sum(pending_by_month_city)
                total_ytd_city = sum(total_by_month_city)

                city_data[city] = {
                    "closed": closed_by_month_city + [closed_ytd_city],
                    "pending": pending_by_month_city + [pending_ytd_city],
                    "total": total_by_month_city + [total_ytd_city],
                }

            # تجميع حسب الشهر: Hit (Closed), Miss (Pending), Total (كل المدن مجمعة)
            closed_by_month = []
            pending_by_month = []
            total_by_month = []

            for month in months:
                df_month = df[df["Month"] == month]
                hit_month = len(df_month[df_month["Hit or Miss"] == "Hit"])
                miss_month = len(df_month[df_month["Hit or Miss"] == "Miss"])
                closed_by_month.append(hit_month)
                pending_by_month.append(miss_month)
                total_by_month.append(hit_month + miss_month)

            # إضافة YTD
            closed_ytd = sum(closed_by_month)
            pending_ytd = sum(pending_by_month)
            total_ytd = sum(total_by_month)

            months_display = months + ["YTD"]
            closed_by_month.append(closed_ytd)
            pending_by_month.append(pending_ytd)
            total_by_month.append(total_ytd)

            # حساب النسب المئوية
            closed_pct = [
                round((c / t * 100), 2) if t > 0 else 0
                for c, t in zip(closed_by_month, total_by_month)
            ]

            # بناء الجدول: KPI، ثم أعمدة المدن جانب أعمدة الشهور، ثم الشهور + YTD
            # الأعمدة: KPI, City1, City2, ..., Jan, Feb, ..., YTD
            columns = ["KPI"] + cities + months_display
            table_rows = []

            # صف Closed (الإجمالي): لكل مدينة نعرض YTD، ثم لكل شهر نعرض الإجمالي
            closed_row = {"KPI": "Closed"}
            for city in cities:
                closed_row[city] = int(city_data.get(city, {}).get("closed", [0])[-1])
            for i, month in enumerate(months_display):
                closed_row[month] = int(closed_by_month[i])
            table_rows.append(closed_row)

            # صف Pending (الإجمالي)
            pending_row = {"KPI": "Pending"}
            for city in cities:
                pending_row[city] = int(city_data.get(city, {}).get("pending", [0])[-1])
            for i, month in enumerate(months_display):
                pending_row[month] = int(pending_by_month[i])
            table_rows.append(pending_row)

            # صف Total (الإجمالي)
            total_row = {"KPI": "Total"}
            for city in cities:
                total_row[city] = int(city_data.get(city, {}).get("total", [0])[-1])
            for i, month in enumerate(months_display):
                total_row[month] = int(total_by_month[i])
            table_rows.append(total_row)

            # شارت واحد (كل المدن مجمعة)
            chart_data = [
                {
                    "type": "column",
                    "name": "Closed %",
                    "color": "#9fc0e4",
                    "showInLegend": True,
                    "indexLabel": "{y}%",
                    "related_table": "PODs YTD",
                    "dataPoints": [
                        {"label": m, "y": closed_pct[i]}
                        for i, m in enumerate(months_display)
                    ],
                },
                {
                    "type": "line",
                    "name": "Target 100%",
                    "color": "red",
                    "showInLegend": True,
                    "related_table": "PODs YTD",
                    "dataPoints": [{"label": m, "y": 100} for m in months_display],
                },
            ]

            sub_tables = [
                {
                    "id": "sub-table-pods-ytd",
                    "title": "PODs YTD",
                    "columns": columns,
                    "data": table_rows,
                    "chart_data": chart_data,
                }
            ]

            # ✅ بناء جدول التفاصيل الكامل (مثل Outbound و Inbound)
            detail_columns = [
                col_shpng if col_shpng else "Shpng Pnt",
                col_whname if col_whname else "W.HNAME",
                col_plant if col_plant else "PLANT",
                col_whno if col_whno else "WH No",
                col_created if col_created else "Created on",
                col_pgi if col_pgi else "PGI Date",
                col_delivery if col_delivery else "Delivery",
                col_inv if col_inv else "INV",
                col_shipto if col_shipto else "Ship-to party",
                col_shipto_name if col_shipto_name else "Name of the ship-to party",
                col_qty if col_qty else "QTY",
                col_unit if col_unit else "Unit",
                col_city if col_city else "City",
                "Days",
                "Hit or Miss",
                "Month",
            ]

            # تنظيف الأعمدة (إزالة None)
            detail_columns = [c for c in detail_columns if c]

            # إعداد البيانات للجدول التفصيلي
            detail_df = df.copy()

            # حفظ عمود الترتيب قبل التحويل
            if "_created_dt" in detail_df.columns:
                detail_df["_sort_ts"] = detail_df["_created_dt"]

            def _fmt_date(x):
                if pd.isna(x) or x is pd.NaT:
                    return ""
                try:
                    return pd.Timestamp(x).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    return ""

            # تحويل التواريخ إلى نص
            if col_created in detail_df.columns and "_created_dt" in detail_df.columns:
                detail_df[col_created] = detail_df["_created_dt"].apply(_fmt_date)
            if col_pgi in detail_df.columns and "_pgi_dt" in detail_df.columns:
                detail_df[col_pgi] = detail_df["_pgi_dt"].apply(_fmt_date)

            # ترتيب البيانات قبل إزالة الأعمدة المؤقتة
            if "_sort_ts" in detail_df.columns:
                detail_df = detail_df.sort_values("_sort_ts", ascending=False)

            # إزالة الأعمدة المؤقتة
            drop_cols = ["_created_dt", "_pgi_dt", "_sort_ts"]
            detail_df = detail_df.drop(
                columns=[c for c in drop_cols if c in detail_df.columns],
                errors="ignore",
            )

            # استخراج البيانات
            detail_rows_raw = detail_df.head(500)[detail_columns].to_dict(
                orient="records"
            )

            def _to_blank(val):
                if val is None:
                    return ""
                if isinstance(val, float) and (pd.isna(val) or (val != val)):
                    return ""
                s = str(val).strip()
                if s.lower() in ("nan", "nat", "none", "<nat>"):
                    return ""
                return s

            detail_rows = [
                {k: _to_blank(v) for k, v in row.items()} for row in detail_rows_raw
            ]

            # بناء قائمة الفلاتر
            detail_df_for_options = detail_df.copy()
            whname_options = (
                sorted(
                    detail_df_for_options[col_whname]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if col_whname in detail_df_for_options.columns
                else []
            )

            city_options = (
                sorted(
                    detail_df_for_options[col_city]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if col_city in detail_df_for_options.columns
                else []
            )

            status_options = (
                sorted(
                    detail_df_for_options["Hit or Miss"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Hit or Miss" in detail_df_for_options.columns
                else []
            )

            month_options = (
                sorted(
                    detail_df_for_options["Month"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Month" in detail_df_for_options.columns
                else []
            )

            # إضافة جدول التفاصيل
            detail_table = {
                "id": "sub-table-pods-detail",
                "title": "PODs Shipments Detail",
                "columns": detail_columns,
                "data": detail_rows,
                "chart_data": [],
                "full_width": True,
                "filter_options": {
                    "whnames": whname_options,
                    "statuses": status_options,
                    "months": month_options,
                },
            }

            sub_tables.append(detail_table)

            # كروت KPI
            stats = {
                "total_shipments": total_shipments,
                "hit_pct": hit_pct,
                "miss_pct": miss_pct,
                "target": 100,
            }

            tab_data = {
                "name": "PODs Update",
                "sub_tables": sub_tables,
                "chart_data": chart_data,
                "chart_title": "PODs Closed % Performance",
                "hit_pct": hit_pct,
                "target_pct": 100,
                "stats": stats,
            }

            month_norm_tab = self.apply_month_filter_to_tab(
                tab_data, selected_month, selected_months_norm or None
            )
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm_tab},
            )

            return {
                "detail_html": html,
                "chart_data": chart_data,
                "chart_title": "PODs Closed % Performance",
                "hit_pct": hit_pct,
                "target_pct": 100,
                "count": total_shipments,
                "tab_data": tab_data,
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {"error": f"⚠️ Error processing PODs: {e}"}

    def filter_rejections_combined(
        self, request, selected_month=None, selected_months=None
    ):
        """
        تاب Return & Refusal: عرض جدول Return فقط من شيت Inbound (Shipment Type = RMA).
        بدون Rejection / Rejection breakdown / شارت — جدول فقط بعرض الصفحة.
        """
        import pandas as pd
        import os
        from django.template.loader import render_to_string

        try:
            excel_path = self.get_excel_path()
            if not excel_path or not os.path.exists(excel_path):
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sheet_names = [s.strip() for s in xls.sheet_names]
            sub_tables = []
            chart_data = []

            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in seen:
                        seen.add(norm)
                        selected_months_norm.append(norm)

            # ✅ جدول Return فقط من شيت Inbound: فلتر Shipment Type = RMA
            return_columns_display = [
                "Shipment Nbr",
                "Shipment Type",
                "Status",
                "Create Timestamp",
                "Arrival Date",
                "Offloading Date",
                "Last LPN Rcv TS",
            ]

            def _normalize_col(val):
                return re.sub(r"[^a-z0-9]", "", str(val).strip().lower())

            def _find_col(df, possible_names):
                norm_map = {_normalize_col(c): c for c in df.columns}
                for name in possible_names:
                    n = _normalize_col(name)
                    if n in norm_map:
                        return norm_map[n]
                for col in df.columns:
                    if any(
                        _normalize_col(name) in _normalize_col(col)
                        for name in possible_names
                    ):
                        return col
                return None

            inbound_sheet = next(
                (s for s in sheet_names if "inbound" in s.lower()), None
            )
            if inbound_sheet:
                try:
                    df_in = pd.read_excel(
                        excel_path,
                        sheet_name=inbound_sheet,
                        engine="openpyxl",
                        dtype=str,
                        header=0,
                    ).fillna("")
                    df_in.columns = df_in.columns.astype(str).str.strip()

                    col_ship_nbr = _find_col(
                        df_in, ["shipment nbr", "shipment number", "shipment no"]
                    )
                    col_ship_type = _find_col(
                        df_in, ["shipment type", "shipmenttype", "type"]
                    )
                    col_status = _find_col(df_in, ["status", "shipment status"])
                    col_create = _find_col(
                        df_in, ["create timestamp", "created timestamp"]
                    )
                    col_arrival = _find_col(
                        df_in, ["arrival date", "arrival timestamp"]
                    )
                    col_offload = _find_col(df_in, ["offloading date", "offload date"])
                    col_last_lpn = _find_col(
                        df_in, ["last lpn rcv ts", "last lpn receive ts"]
                    )

                    if col_ship_type is not None:
                        df_in = df_in[
                            df_in[col_ship_type].astype(str).str.strip().str.upper()
                            == "RMA"
                        ]
                    else:
                        df_in = df_in.iloc[0:0]

                    if not df_in.empty and all(
                        [
                            col_ship_nbr,
                            col_status,
                            col_create,
                            col_arrival,
                            col_offload,
                            col_last_lpn,
                        ]
                    ):
                        rename = {
                            col_ship_nbr: "Shipment Nbr",
                            col_status: "Status",
                            col_create: "Create Timestamp",
                            col_arrival: "Arrival Date",
                            col_offload: "Offloading Date",
                            col_last_lpn: "Last LPN Rcv TS",
                        }
                        if col_ship_type is not None:
                            rename[col_ship_type] = "Shipment Type"
                        df_in = df_in.rename(columns=rename)

                        for c in return_columns_display:
                            if c not in df_in.columns:
                                df_in[c] = ""

                        df_in = df_in[return_columns_display]
                        if selected_month or selected_months_norm:
                            month_col = _find_col(df_in, ["month", "create timestamp"])
                            if month_col and month_col in df_in.columns:
                                if selected_months_norm:
                                    active = {
                                        self.normalize_month_label(m)
                                        for m in selected_months_norm
                                    }
                                else:
                                    active = {
                                        self.normalize_month_label(selected_month)
                                    }
                                if "Create Timestamp" in df_in.columns:
                                    try:
                                        ts = pd.to_datetime(
                                            df_in["Create Timestamp"],
                                            errors="coerce",
                                        )
                                        df_in["_month"] = ts.dt.strftime("%b")
                                        df_in = df_in[
                                            df_in["_month"]
                                            .fillna("")
                                            .str.lower()
                                            .isin([m.lower() for m in active])
                                        ]
                                        df_in = df_in.drop(
                                            columns=["_month"], errors="ignore"
                                        )
                                    except Exception:
                                        pass

                        # حساب Hit/Miss للـ Return (≤24h بين Create Timestamp و Last LPN Rcv TS)
                        return_kpi = None
                        try:
                            ts_create = pd.to_datetime(
                                df_in["Create Timestamp"], errors="coerce"
                            )
                            ts_last = pd.to_datetime(
                                df_in["Last LPN Rcv TS"], errors="coerce"
                            )
                            hours = (ts_last - ts_create).dt.total_seconds() / 3600.0
                            df_in["_is_hit"] = (hours <= 24) & (hours.notna())
                            total_ret = len(df_in)
                            successful_ret = int(df_in["_is_hit"].sum())
                            failed_ret = total_ret - successful_ret
                            hit_pct_ret = (
                                round(100.0 * successful_ret / total_ret, 2)
                                if total_ret else 0
                            )
                            return_kpi = {
                                "total_shipments": total_ret,
                                "successful": successful_ret,
                                "failed": failed_ret,
                                "target": 99,
                                "hit_pct": hit_pct_ret,
                            }
                            df_in = df_in.drop(columns=["_is_hit"], errors="ignore")
                        except Exception:
                            total_ret = len(df_in)
                            return_kpi = {
                                "total_shipments": total_ret,
                                "successful": total_ret,
                                "failed": 0,
                                "target": 99,
                                "hit_pct": 100.0 if total_ret else 0,
                            }

                        sub_tables.append(
                            {
                                "title": "Return",
                                "columns": return_columns_display,
                                "data": df_in.to_dict(orient="records"),
                                "return_kpi": return_kpi,
                            }
                        )
                    else:
                        sub_tables.append(
                            {
                                "title": "Return",
                                "columns": return_columns_display,
                                "data": [],
                                "error": (
                                    "Inbound sheet missing required columns or no RMA rows."
                                    if col_ship_type is not None
                                    else "Column 'Shipment Type' not found in Inbound."
                                ),
                            }
                        )
                except Exception as e_in:
                    import traceback

                    print(traceback.format_exc())
                    sub_tables.append(
                        {
                            "title": "Return",
                            "columns": return_columns_display,
                            "data": [],
                            "error": str(e_in),
                        }
                    )
            else:
                sub_tables.append(
                    {
                        "title": "Return",
                        "columns": return_columns_display,
                        "data": [],
                        "error": "Sheet containing 'Inbound' was not found.",
                    }
                )

            # ✅ التحقق من وجود بيانات بعد الفلترة
            total_count = sum(len(st["data"]) for st in sub_tables)
            if (selected_month or selected_months_norm) and total_count == 0:
                if selected_months_norm:
                    msg = ", ".join(selected_months_norm)
                else:
                    msg = str(selected_month).strip().capitalize()
                return {
                    "detail_html": f"<p class='text-warning text-center p-4'>⚠️ No data available for {msg} in Return & Refusal.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            # 🧩 بناء الـ HTML — نمرّر return_kpi من أول sub_table للكروت فوق الجدول
            return_kpi_for_tab = None
            if sub_tables:
                return_kpi_for_tab = sub_tables[0].get("return_kpi")
            tab_data = {
                "name": "Return & Refusal",
                "sub_tables": sub_tables,
                "chart_data": chart_data,
                "chart_title": "Return & Refusal Overview",
                "return_kpi": return_kpi_for_tab,
            }
            month_norm_tab = self.apply_month_filter_to_tab(
                tab_data,
                selected_month if not selected_months_norm else None,
                selected_months_norm or None,
            )
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm_tab},
            )

            # 🧮 حساب hit% من متوسط القيم في % of Rejection (بالنسبة المئوية)
            hit_values = []
            for st in sub_tables:
                if "rejection" in st["title"].lower():
                    for row in st["data"]:
                        val = row.get("% of Rejection", "")
                        try:
                            num = to_percentage_number(val)
                            if num is not None:
                                hit_values.append(num)
                        except:
                            pass

            hit_pct = round(sum(hit_values) / len(hit_values), 2) if hit_values else 0

            result = {
                "detail_html": html,
                "chart_data": chart_data,
                "chart_title": "Return & Refusal Overview",
                "count": total_count,
                "hit_pct": hit_pct,
                "tab_data": tab_data,
            }

            return result

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error while processing Return & Refusal data: {e}</p>",
                "chart_data": [],
                "count": 0,
            }

    def filter_expiry(self, request, selected_month=None, selected_months=None):
        """
        تاب Expiry: قراءة من شيت Expiry.
        - فلتر Status: Located, Allocated, Partly Allocated فقط.
        - أعمدة: Facility, Company, LPN Nbr, Status, Item Code, Item Description, Current Qty, batch_nbr, Expiry Date.
        - تحذير: اللي ينتهي خلال 3 شهور = قريب، خلال 6 شهور = warning، يعرض تحت الجدول في Bootstrap 5 alert.
        """
        import pandas as pd
        import os
        from datetime import datetime, timedelta
        from django.template.loader import render_to_string

        try:
            excel_path = self.get_excel_path()
            if not excel_path or not os.path.exists(excel_path):
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sheet_names = [s.strip() for s in xls.sheet_names]
            expiry_sheet = next((s for s in sheet_names if "expiry" in s.lower()), None)
            if not expiry_sheet:
                return {
                    "detail_html": "<p class='text-warning'>⚠️ Sheet containing 'Expiry' was not found.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            df = pd.read_excel(
                excel_path,
                sheet_name=expiry_sheet,
                engine="openpyxl",
                dtype=str,
                header=0,
            ).fillna("")
            df.columns = df.columns.astype(str).str.strip()

            def _norm(val):
                return re.sub(r"[^a-z0-9]", "", str(val).strip().lower())

            def _find_col(dframe, names):
                nmap = {_norm(c): c for c in dframe.columns}
                for name in names:
                    n = _norm(name)
                    if n in nmap:
                        return nmap[n]
                for col in dframe.columns:
                    if any(_norm(n) in _norm(col) for n in names):
                        return col
                return None

            col_facility = _find_col(df, ["facility", "facility code"])
            col_company = _find_col(df, ["company"])
            col_lpn = _find_col(df, ["lpn nbr", "lpn", "lpn nbr"])
            col_status = _find_col(df, ["status"])
            col_item_code = _find_col(df, ["item code", "itemcode"])
            col_item_desc = _find_col(df, ["item description", "item desc"])
            col_qty = _find_col(df, ["current qty", "currentqty", "qty"])
            col_batch = _find_col(df, ["batch_nbr", "batch nbr", "batch"])
            col_expiry = _find_col(df, ["expiry date", "expirydate", "expiry"])

            if not col_status:
                return {
                    "detail_html": "<p class='text-danger'>⚠️ Column 'Status' not found in Expiry sheet.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            # فلتر Status: Located, Allocated, Partly Allocated
            status_vals = {"located", "allocated", "partly allocated"}
            df = df[
                df[col_status].astype(str).str.strip().str.lower().isin(status_vals)
            ]

            display_columns = [
                "Facility",
                "Company",
                "LPN Nbr",
                "Status",
                "Item Code",
                "Item Description",
                "Current Qty",
                "batch_nbr",
                "Expiry Date",
            ]
            rename_map = {}
            if col_facility:
                rename_map[col_facility] = "Facility"
            if col_company:
                rename_map[col_company] = "Company"
            if col_lpn:
                rename_map[col_lpn] = "LPN Nbr"
            if col_status:
                rename_map[col_status] = "Status"
            if col_item_code:
                rename_map[col_item_code] = "Item Code"
            if col_item_desc:
                rename_map[col_item_desc] = "Item Description"
            if col_qty:
                rename_map[col_qty] = "Current Qty"
            if col_batch:
                rename_map[col_batch] = "batch_nbr"
            if col_expiry:
                rename_map[col_expiry] = "Expiry Date"

            df = df.rename(columns=rename_map)
            for c in display_columns:
                if c not in df.columns:
                    df[c] = ""

            df = df[display_columns]

            # تحويل Expiry Date وتحديد نطاقات: 1–3، 3–6، 6–9 شهور
            today = pd.Timestamp(datetime.now().date())
            three_months = today + pd.DateOffset(months=3)
            six_months = today + pd.DateOffset(months=6)
            nine_months = today + pd.DateOffset(months=9)

            expiry_ser = pd.to_datetime(df["Expiry Date"], errors="coerce")
            df["_expiry_dt"] = expiry_ser
            df["Expiry Date"] = expiry_ser.dt.strftime("%Y-%m-%d").fillna("")

            within_1_3 = (
                (df["_expiry_dt"].notna())
                & (df["_expiry_dt"] >= today)
                & (df["_expiry_dt"] <= three_months)
            )
            within_3_6 = (
                (df["_expiry_dt"].notna())
                & (df["_expiry_dt"] > three_months)
                & (df["_expiry_dt"] <= six_months)
            )
            within_6_9 = (
                (df["_expiry_dt"].notna())
                & (df["_expiry_dt"] > six_months)
                & (df["_expiry_dt"] <= nine_months)
            )
            df = df.drop(columns=["_expiry_dt"], errors="ignore")

            table_data = df[display_columns].to_dict(orient="records")

            # أعداد المنتجات لكل نطاق
            expiry_counts = {
                "within_1_3": int(within_1_3.sum()),
                "within_3_6": int(within_3_6.sum()),
                "within_6_9": int(within_6_9.sum()),
            }

            # خيارات الفلاتر: Facility, Company, Status, Expiry Date
            facility_codes = (
                sorted(
                    df["Facility"]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Facility" in df.columns
                else []
            )
            companies = (
                sorted(
                    df["Company"]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Company" in df.columns
                else []
            )
            statuses = (
                sorted(
                    df["Status"]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Status" in df.columns
                else []
            )
            expiry_dates = (
                sorted(
                    df["Expiry Date"]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .unique()
                    .tolist()
                )
                if "Expiry Date" in df.columns
                else []
            )

            filter_options = {
                "facility_codes": facility_codes,
                "companies": companies,
                "statuses": statuses,
                "expiry_dates": expiry_dates,
            }

            sub_tables = [
                {
                    "id": "sub-table-expiry-detail",
                    "title": "Expiry",
                    "columns": display_columns,
                    "data": table_data,
                    "filter_options": filter_options,
                }
            ]
            tab_data = {
                "name": "Expiry",
                "sub_tables": sub_tables,
                "chart_data": [],
                "expiry_counts": expiry_counts,
            }
            month_norm = self.apply_month_filter_to_tab(tab_data, selected_month, None)
            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm},
            )
            return {
                "detail_html": html,
                "chart_data": [],
                "count": len(table_data),
                "tab_data": tab_data,
            }
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error processing Expiry: {e}</p>",
                "chart_data": [],
                "count": 0,
            }

    def filter_total_lead_time_performance(
        self, request, selected_month=None, selected_months=None
    ):
        cache.clear()
        """
        🔹 عرض جدول Miss Breakdown (3PL و Roche كل واحد منفصل)
        🔹 عرض الشارت الخاص بـ 3PL On-Time Delivery
        🔹 عرض خطوات Outbound في الأسفل
        """
        try:
            excel_path = self.get_uploaded_file_path(request)
            if not excel_path or not os.path.exists(excel_path):
                return {
                    "detail_html": "<p class='text-danger text-center'>⚠️ Excel file not found for display.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            xls = pd.ExcelFile(excel_path, engine="openpyxl")
            sub_tables = []
            chart_data = []
            selected_month_norm = None
            selected_months_norm = []
            actual_target = 0  # يُحدَّث من الشيت الرئيسي إن وُجد

            if selected_month:
                raw_month = str(selected_month).strip()
                parsed = pd.to_datetime(raw_month, errors="coerce")
                if pd.isna(parsed):
                    selected_month_norm = raw_month[:3].capitalize()
                else:
                    selected_month_norm = parsed.strftime("%b")

            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm:
                        selected_months_norm.append(norm)
                # إزالة التكرارات مع الحفاظ على الترتيب
                seen = set()
                selected_months_norm = [
                    m for m in selected_months_norm if not (m in seen or seen.add(m))
                ]

            # ----------------------------
            # 🟦 جدول 3PL SIDE
            # ----------------------------
            sheet_3pl = next(
                (
                    s
                    for s in xls.sheet_names
                    if "total lead time preformance" in s.lower()
                    and "-r" not in s.lower()
                ),
                None,
            )

            final_df_3pl = None

            if sheet_3pl:
                df = pd.read_excel(excel_path, sheet_name=sheet_3pl, engine="openpyxl")
                df.columns = df.columns.str.strip().str.lower()

                required_cols = [
                    "month",
                    "outbound delivery",
                    "kpi",
                    "reason group",
                    "miss reason",
                ]
                if all(col in df.columns for col in required_cols):
                    df["year"] = pd.to_datetime(df["month"], errors="coerce").dt.year
                    df = df[df["year"] == 2025]

                    if "month" in df.columns:
                        # نحاول تحويل القيم في عمود Month إلى تاريخ، ثم استخراج اسم الشهر المختصر
                        df["month"] = pd.to_datetime(
                            df["month"], errors="coerce"
                        ).dt.strftime("%b")
                    else:
                        # fallback لو مفيش عمود Month
                        df["month"] = pd.to_datetime(
                            df["ob distribution date"], errors="coerce"
                        ).dt.strftime("%b")

                    # ترتيب الشهور
                    month_order = [
                        "Jan",
                        "Feb",
                        "Mar",
                        "Apr",
                        "May",
                        "Jun",
                        "Jul",
                        "Aug",
                        "Sep",
                        "Oct",
                        "Nov",
                        "Dec",
                    ]

                    df["month"] = pd.Categorical(
                        df["month"], categories=month_order, ordered=True
                    )
                    missing_months = []
                    if selected_month_norm:
                        df = df[df["month"] == selected_month_norm]
                        if df.empty:
                            return {
                                "detail_html": f"<p class='text-warning text-center p-4'>⚠️ No data available for month {selected_month_norm} in Total Lead Time Performance.</p>",
                                "chart_data": [],
                                "count": 0,
                                "hit_pct": 0,
                            }
                        existing_months = [selected_month_norm]
                    elif selected_months_norm:
                        df = df[df["month"].isin(selected_months_norm)]
                        available_months = [
                            m
                            for m in selected_months_norm
                            if m in df["month"].dropna().unique()
                        ]
                        missing_months = [
                            m for m in selected_months_norm if m not in available_months
                        ]
                        if df.empty:
                            return {
                                "detail_html": "<p class='text-warning text-center p-4'>⚠️ No data available for the selected quarter months in Total Lead Time Performance.</p>",
                                "chart_data": [],
                                "count": 0,
                                "hit_pct": 0,
                            }
                        existing_months = selected_months_norm
                    else:
                        existing_months = [
                            m for m in month_order if m in df["month"].dropna().unique()
                        ]

                    df["reason group"] = (
                        df["reason group"].astype(str).str.strip().str.lower()
                    )
                    df["kpi"] = df["kpi"].astype(str).str.strip().str.lower()
                    df["miss reason"] = (
                        df["miss reason"].astype(str).str.strip().str.lower()
                    )

                    df_hit = df[df["kpi"].str.lower() == "hit"].copy()
                    hit_counts = (
                        df_hit.groupby("month")["outbound delivery"]
                        .nunique()
                        .reindex(existing_months, fill_value=0)
                    )

                    df_3pl_miss = df[
                        (df["kpi"].str.lower() == "miss")
                        & (df["reason group"] == "3pl")
                    ].copy()

                    miss_grouped = (
                        df_3pl_miss.groupby(["miss reason", "month"])[
                            "outbound delivery"
                        ]
                        .nunique()
                        .reset_index(name="count")
                        .pivot_table(
                            index="miss reason",
                            columns="month",
                            values="count",
                            fill_value=0,
                        )
                    )

                    for m in existing_months:
                        if m not in miss_grouped.columns:
                            miss_grouped[m] = 0
                    miss_grouped = miss_grouped[existing_months]

                    final_df_3pl = miss_grouped.copy()
                    final_df_3pl.loc["on time delivery"] = hit_counts
                    final_df_3pl = final_df_3pl.fillna(0).astype(int)
                    final_df_3pl["2025"] = final_df_3pl.sum(axis=1)

                    total_row = final_df_3pl.sum(numeric_only=True)
                    total_row.name = "total"
                    final_df_3pl = pd.concat([final_df_3pl, pd.DataFrame([total_row])])

                    final_df_3pl.reset_index(inplace=True)
                    final_df_3pl.rename(columns={"index": "KPI"}, inplace=True)
                    final_df_3pl["KPI"] = final_df_3pl["KPI"].str.title()

                    desired_order = [
                        "On Time Delivery",
                        "Late Arrive To The Customer",
                        "Customer Close On Arrive",
                        "Remote Area",
                    ]
                    final_df_3pl["order_key"] = final_df_3pl["KPI"].apply(
                        lambda x: (
                            desired_order.index(x)
                            if x in desired_order
                            else len(desired_order) + 1
                        )
                    )
                    final_df_3pl = final_df_3pl.sort_values(
                        by=["order_key", "KPI"]
                    ).drop(columns=["order_key"])
                    # final_df_3pl.insert(1, "Reason Group", "3PL")
                    #
                    # # ✅ حذف عمود Reason Group قبل الإرسال
                    # if "Reason Group" in final_df_3pl.columns:
                    #     final_df_3pl = final_df_3pl.drop(columns=["Reason Group"])

                    # ✅ حساب التارجت الفعلي لكل شهر (On Time ÷ Total × 100)
                    percent_hit = []
                    existing_months = [
                        m
                        for m in final_df_3pl.columns
                        if m not in ["KPI", "Reason Group", "2025", "Total"]
                    ]

                    on_time_row = final_df_3pl.loc[
                        final_df_3pl["KPI"].str.lower() == "on time delivery"
                    ].iloc[0]
                    total_row = final_df_3pl.loc[
                        final_df_3pl["KPI"].str.lower() == "total"
                    ].iloc[0]

                    for m in existing_months:
                        on_time_val = float(on_time_row.get(m, 0))
                        total_val = float(total_row.get(m, 0))

                        # ✅ لو الشهر فيه صفر فعلاً، خليه 0 في الشارت كمان
                        if total_val == 0 or on_time_val == 0:
                            percent = 0
                        else:
                            percent = int(round((on_time_val / total_val) * 100))

                        percent_hit.append(percent)

                    try:
                        total_year_val = total_row["2025"]
                        on_time_year_val = on_time_row["2025"]
                        actual_target = (
                            int(round((on_time_year_val / total_year_val) * 100))
                            if total_year_val > 0
                            else 0
                        )
                    except Exception:
                        actual_target = 100

                    # ✅ إنشاء قائمة بالشهور اللي فيها قيم غير صفرية (فقط للشارت)
                    nonzero_months = [
                        m for i, m in enumerate(existing_months) if percent_hit[i] > 0
                    ]
                    nonzero_percents = [
                        percent_hit[i]
                        for i, m in enumerate(existing_months)
                        if percent_hit[i] > 0
                    ]
                    if not nonzero_months:
                        nonzero_months = existing_months
                        nonzero_percents = [
                            percent_hit[i] for i in range(len(existing_months))
                        ]

                    chart_data.append(
                        {
                            "type": "column",
                            "name": "On-Time Delivery (%)",
                            "color": "#9fc0e4",
                            "showInLegend": True,
                            "related_table": "Miss Breakdown – 3PL Side",  # ✅ ربط الشارت بالجدول
                            "dataPoints": [
                                {"label": m, "y": nonzero_percents[i]}
                                for i, m in enumerate(nonzero_months)
                            ],
                        }
                    )
                    chart_data.append(
                        {
                            "type": "line",
                            "name": f"Target ({actual_target}%)",
                            "color": "red",
                            "showInLegend": True,
                            "related_table": "Miss Breakdown – 3PL Side",  # ✅ ربط الشارت بالجدول
                            "dataPoints": [
                                {"label": m, "y": actual_target} for m in nonzero_months
                            ],
                        }
                    )

                    sub_tables.append(
                        {
                            "title": "Miss Breakdown – 3PL Side",
                            "columns": list(final_df_3pl.columns),
                            "data": final_df_3pl.to_dict(orient="records"),
                        }
                    )
                    # لم نعد نضيف جدول Missing Months هنا، يتم التعامل معه لاحقًا عبر apply_month_filter_to_tab

            # ----------------------------
            # 🟥 جدول ROCHE SIDE
            # ----------------------------
            sheet_roche = next(
                (s for s in xls.sheet_names if "preformance -r" in s.lower()), None
            )
            if sheet_roche:
                df = pd.read_excel(
                    excel_path, sheet_name=sheet_roche, engine="openpyxl"
                )
                df.columns = df.columns.str.strip()
                if "Month" in df.columns:
                    month_order = [
                        "Jan",
                        "Feb",
                        "Mar",
                        "Apr",
                        "May",
                        "Jun",
                        "Jul",
                        "Aug",
                        "Sep",
                        "Oct",
                        "Nov",
                        "Dec",
                    ]
                    df["Month"] = pd.Categorical(
                        df["Month"], categories=month_order, ordered=True
                    )
                    df = df.sort_values("Month")

                    if selected_month_norm:
                        df_filtered = df[
                            df["Month"].astype(str).str.lower()
                            == selected_month_norm.lower()
                        ]
                        if df_filtered.empty:
                            sub_tables.append(
                                {
                                    "title": "Miss Breakdown – Roche Side",
                                    "columns": [],
                                    "data": [],
                                    "message": f"⚠️ لا توجد بيانات متاحة للشهر {selected_month_norm}.",
                                }
                            )
                        else:
                            df_melted = df_filtered.melt(
                                id_vars=["Month"], var_name="KPI", value_name="Count"
                            )
                            pivot_df = (
                                df_melted.groupby(["KPI", "Month"])["Count"]
                                .sum()
                                .unstack(fill_value=0)
                            )
                            pivot_df["2025"] = pivot_df.sum(axis=1)
                            total_row = pivot_df.sum(numeric_only=True)
                            total_row.name = "TOTAL"
                            pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])])
                            pivot_df.reset_index(inplace=True)
                            pivot_df.rename(columns={"index": "KPI"}, inplace=True)
                            keep_cols = [
                                col
                                for col in ["KPI", selected_month_norm]
                                if col in pivot_df.columns
                            ]
                            pivot_df = pivot_df[keep_cols]
                            sub_tables.append(
                                {
                                    "title": "Miss Breakdown – Roche Side",
                                    "columns": list(pivot_df.columns),
                                    "data": pivot_df.to_dict(orient="records"),
                                }
                            )
                    elif selected_months_norm:
                        df_filtered = df[
                            df["Month"]
                            .astype(str)
                            .str.lower()
                            .isin([m.lower() for m in selected_months_norm])
                        ]
                        if df_filtered.empty:
                            sub_tables.append(
                                {
                                    "title": "Miss Breakdown – Roche Side",
                                    "columns": [],
                                    "data": [],
                                    "message": "⚠️ No data available for the selected quarter months.",
                                }
                            )
                        else:
                            df_melted = df_filtered.melt(
                                id_vars=["Month"], var_name="KPI", value_name="Count"
                            )
                            pivot_df = (
                                df_melted.groupby(["KPI", "Month"])["Count"]
                                .sum()
                                .unstack(fill_value=0)
                            )
                            ordered_months = [
                                m for m in selected_months_norm if m in pivot_df.columns
                            ]
                            for m in selected_months_norm:
                                if m not in pivot_df.columns:
                                    pivot_df[m] = 0
                            pivot_df = pivot_df[selected_months_norm]
                            pivot_df["2025"] = pivot_df.sum(axis=1)
                            total_row = pivot_df.sum(numeric_only=True)
                            total_row.name = "TOTAL"
                            pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])])
                            pivot_df.reset_index(inplace=True)
                            pivot_df.rename(columns={"index": "KPI"}, inplace=True)
                            sub_tables.append(
                                {
                                    "title": "Miss Breakdown – Roche Side",
                                    "columns": list(pivot_df.columns),
                                    "data": pivot_df.to_dict(orient="records"),
                                }
                            )
                    else:
                        df_melted = df.melt(
                            id_vars=["Month"], var_name="KPI", value_name="Count"
                        )
                        pivot_df = (
                            df_melted.groupby(["KPI", "Month"])["Count"]
                            .sum()
                            .unstack(fill_value=0)
                            .reindex(columns=month_order, fill_value=0)
                        )
                        pivot_df["2025"] = pivot_df.sum(axis=1)
                        total_row = pivot_df.sum(numeric_only=True)
                        total_row.name = "TOTAL"
                        pivot_df = pd.concat([pivot_df, pd.DataFrame([total_row])])
                        pivot_df.reset_index(inplace=True)
                        pivot_df.rename(columns={"index": "KPI"}, inplace=True)
                        pivot_df = pivot_df.loc[:, (pivot_df != 0).any(axis=0)]

                        sub_tables.append(
                            {
                                "title": "Miss Breakdown – Roche Side",
                                "columns": list(pivot_df.columns),
                                "data": pivot_df.to_dict(orient="records"),
                            }
                        )

            # Outbound Shipments (Outbound1 + Outbound2, Hit/Miss) — نفس فكرة Inbound
            outbound_result = self.filter_outbound_shipments(
                request,
                selected_month if not selected_months_norm else None,
                selected_months_norm if selected_months_norm else None,
            )
            # ✅ جلب نسبة الـ Hit من Outbound (هي اللي هنستخدمها كـ KPI للتاب ده)
            outbound_stats = outbound_result.get("stats", {}) or {}
            outbound_hit_pct = outbound_stats.get("hit_pct", 0) or 0
            # ✅ إذا لم تكن موجودة في stats، نحاول جلبها مباشرة من outbound_result
            if not outbound_hit_pct:
                outbound_hit_pct = outbound_result.get("hit_pct", 0) or 0
            print(
                f"🔍 Total Lead Time Performance - Outbound hit_pct: {outbound_hit_pct}% (from stats: {outbound_stats.get('hit_pct', 'N/A')})"
            )

            if outbound_result.get("sub_tables"):
                outbound_tab = {
                    "name": "Outbound Shipments",
                    "stats": outbound_result.get("stats", {}),
                    "sub_tables": outbound_result["sub_tables"],
                    "chart_data": outbound_result.get("chart_data", []),
                }
                outbound_html = render_to_string(
                    "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                    {
                        "tab": outbound_tab,
                        "selected_month": selected_month
                        or (selected_months_norm[0] if selected_months_norm else None),
                    },
                )
            else:
                outbound_html = outbound_result.get("detail_html", "")

            # لا نرجع "لا توجد بيانات" إلا لو مفيش جداول رئيسية ومفيش محتوى Outbound
            has_outbound = bool(outbound_html and str(outbound_html).strip())
            if not sub_tables and not has_outbound:
                return {
                    "detail_html": "<p class='text-muted'>⚠️ No valid data was found in any sheets.</p>",
                    "chart_data": [],
                    "count": 0,
                }

            # ✅ لا نحتاج لتعيين related_table هنا لأنه تم تعيينه بالفعل لكل dataset
            # if chart_data:
            #     for dataset in chart_data:
            #         dataset.setdefault("related_table", "Total Lead Time Performance")

            tab_data = {
                "name": "Outbound",
                "sub_tables": sub_tables,
                "outbound_html": outbound_html,
                "chart_data": chart_data,
            }
            month_norm_tab = self.apply_month_filter_to_tab(
                tab_data,
                selected_month_norm if not selected_months_norm else None,
                selected_months_norm or None,
            )

            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {
                    "tab": tab_data,
                    "selected_month": month_norm_tab,
                    "selected_months": selected_months_norm,
                },
            )

            total_count = sum(len(st["data"]) for st in sub_tables)

            # ✅ نسبة الـ Hit الخاصة بالـ Outbound (هي اللي هنستخدمها كـ KPI للتاب ده)
            try:
                hit_pct_calculated = (
                    float(outbound_hit_pct) if outbound_hit_pct else 0.0
                )
                hit_pct_calculated = round(hit_pct_calculated, 2)  # تقريب لرقمين عشريين
            except (ValueError, TypeError):
                hit_pct_calculated = 0.0
            print(
                f"✅ Total Lead Time Performance - Using Outbound hit_pct: {hit_pct_calculated}%"
            )

            # ✅ إذا لم يكن هناك chart_data من 3PL، نستخدم chart_data من Outbound
            if not chart_data:
                outbound_chart_data = outbound_result.get("chart_data", []) or []
                if outbound_chart_data:
                    chart_data = outbound_chart_data
                    print(
                        f"✅ Total Lead Time Performance - Using Outbound chart_data: {len(chart_data)} datasets"
                    )

            print(
                f"✅ Total Lead Time Performance - Final chart_data: {len(chart_data)} datasets"
            )

            return {
                "detail_html": html,
                "chart_data": chart_data,
                "chart_title": "Total Lead Time Performance – On-Time Delivery",
                "count": total_count,
                "hit_pct": hit_pct_calculated,  # ✅ نسبة الـ Hit من Outbound
                "tab_data": tab_data,
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "detail_html": f"<p class='text-danger'>⚠️ Error while processing data: {e}</p>",
                "chart_data": [],
                "count": 0,
                "hit_pct": 0,  # ✅ إضافة hit_pct في حالة الخطأ
            }

    def filter_dock_to_stock_combined(
        self, request, selected_month=None, selected_months=None
    ):
        """
        🔹 يعرض تاب Dock to stock بالاعتماد على تحليل Inbound (KPI ≤24h).
        """
        cache.clear()
        print("🚀 معالجة Dock to stock — Inbound KPI")

        try:
            from django.template.loader import render_to_string

            inbound_result = self.filter_inbound(
                request, selected_month, selected_months
            )
            sub_tables = inbound_result.get("sub_tables", [])
            chart_data = inbound_result.get("chart_data", [])

            if not sub_tables:
                fallback_html = inbound_result.get("detail_html") or (
                    "<p class='text-warning'>⚠️ No inbound data available.</p>"
                )
                return {
                    "chart_data": chart_data,
                    "detail_html": fallback_html,
                    "count": 0,
                }

            tab_data = {
                "name": "Inbound",
                "sub_tables": sub_tables,
                "chart_data": chart_data,
                "canvas_id": "chart-inbound-kpi",
            }

            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in seen:
                        seen.add(norm)
                        selected_months_norm.append(norm)

            month_norm_tab = self.apply_month_filter_to_tab(
                tab_data,
                None if selected_months_norm else selected_month,
                selected_months_norm or None,
            )

            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm_tab},
            )

            stats = inbound_result.get("stats", {})
            total_count = stats.get(
                "total", sum(len(st.get("data", [])) for st in sub_tables)
            )
            hit_pct = stats.get("hit_pct", 0)

            result = {
                "chart_data": chart_data,
                "detail_html": html,
                "count": total_count,
                "canvas_id": tab_data["canvas_id"],
                "hit_pct": hit_pct,
                "target_pct": 100,
                "tab_data": tab_data,
            }
            return _sanitize_for_json(result)
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "chart_data": [],
                "detail_html": f"<p class='text-danger'>⚠️ Error: {e}</p>",
                "count": 0,
            }
        cache.clear()
        print("🚀 دخلنا الدالة filter_dock_to_stock_combined")

        """
        ✅ فصل Dock to stock إلى جدولين (3PL + Roche)
        ✅ ترتيب الشهور Jan → Dec
        ✅ حساب التارجت الصحيح (on time / total * 100)
        ✅ الشارت موحد (On Time % + Target)
        ✅ عرض الجداول منفصلة
        """
        try:
            import pandas as pd
            import numpy as np
            import os
            from django.template.loader import render_to_string
            from django.utils.text import slugify

            if request and hasattr(request, "session"):
                excel_path = (
                    request.session.get("uploaded_excel_path") or self.get_excel_path()
                )
            else:
                excel_path = self.get_excel_path()

            if not excel_path or not os.path.exists(excel_path):
                return {
                    "chart_data": [],
                    "detail_html": "<p class='text-danger'>⚠️ Excel file not found.</p>",
                    "count": 0,
                }

            # ترتيب الشهور
            def order_months(months):
                month_map = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                }
                months_unique = list(dict.fromkeys(months))

                def month_key(m):
                    if m is None:
                        return 999
                    m_str = str(m).strip()
                    m_lower = m_str.lower()[:3]
                    if m_lower in month_map:
                        return month_map[m_lower]
                    if m_str.isdigit():
                        return 1000 + int(m_str)
                    return 2000 + months_unique.index(m)

                return sorted(months_unique, key=month_key)

            # =======================================
            # 🟢 معالجة Dock to Stock (3PL)
            # =======================================
            selected_months_norm = []
            if selected_months:
                if isinstance(selected_months, str):
                    selected_months = [selected_months]
                seen = set()
                for m in selected_months:
                    norm = self.normalize_month_label(m)
                    if norm and norm not in seen:
                        seen.add(norm)
                        selected_months_norm.append(norm)

            result_3pl = self.filter_dock_to_stock_3pl(
                request, selected_month, selected_months
            )
            df_3pl_table = pd.DataFrame()
            df_chart_combined = {}
            selected_month_norm = None
            if selected_month and not selected_months_norm:
                raw_month = str(selected_month).strip()
                parsed = pd.to_datetime(raw_month, errors="coerce")
                if pd.isna(parsed):
                    selected_month_norm = raw_month[:3].capitalize()
                else:
                    selected_month_norm = parsed.strftime("%b")

            if "chart_data" in result_3pl and result_3pl["chart_data"]:
                df_kpi_full = pd.DataFrame(result_3pl["chart_data"])

                # تحويل الأرقام إلى int
                for col in df_kpi_full.columns:
                    if col != "KPI":
                        df_kpi_full[col] = df_kpi_full[col].apply(
                            lambda x: int(round(float(x))) if pd.notna(x) else 0
                        )

                # حساب النسب الشهرية
                on_time_rows = df_kpi_full[
                    df_kpi_full["KPI"].str.lower().str.contains("on time", na=False)
                ]
                total_rows = df_kpi_full[
                    df_kpi_full["KPI"].str.lower().str.contains("total", na=False)
                ]

                target_correct, on_time_percentage = {}, {}
                month_cols = [
                    c
                    for c in df_kpi_full.columns
                    if c not in ["KPI", "2025", "Total", "TOTAL"]
                ]

                for col in month_cols:
                    try:
                        on_time_val = float(on_time_rows[col].sum())
                        total_val = float(total_rows[col].sum())
                        percentage = (
                            int(round((on_time_val / total_val) * 100))
                            if total_val
                            else 0
                        )
                        target_correct[col] = percentage
                        on_time_percentage[col] = percentage
                    except Exception as e:
                        print(f"⚠️ Error in {col}: {e}")
                        target_correct[col] = on_time_percentage[col] = 0

                df_chart_combined["3PL On Time %"] = on_time_percentage
                df_chart_combined["Target"] = target_correct

                # تجهيز الجدول النهائي
                df_kpi = df_kpi_full[
                    ~df_kpi_full["KPI"].str.lower().str.contains("target", na=False)
                ].copy()
                ordered_cols = ["KPI"] + [
                    c for c in order_months(df_kpi.columns.tolist()) if c != "KPI"
                ]
                df_3pl_table = df_kpi[ordered_cols]
                if selected_months_norm:
                    keep_cols = ["KPI"] + [
                        m for m in selected_months_norm if m in df_3pl_table.columns
                    ]
                    if "2025" in df_3pl_table.columns:
                        keep_cols.append("2025")
                    df_3pl_table = df_3pl_table[
                        [col for col in keep_cols if col in df_3pl_table.columns]
                    ]
                elif selected_month_norm:
                    keep_cols = ["KPI", selected_month_norm]
                    if "2025" in df_3pl_table.columns:
                        keep_cols.append("2025")
                    df_3pl_table = df_3pl_table[
                        [col for col in keep_cols if col in df_3pl_table.columns]
                    ]

                # ✅ إضافة صف "3PL Delay" بعد "On Time Receiving"
                on_time_receiving_idx = None
                for idx in df_3pl_table.index:
                    kpi_value = str(df_3pl_table.loc[idx, "KPI"]).strip()
                    if "on time receiving" in kpi_value.lower():
                        on_time_receiving_idx = idx
                        break

                if on_time_receiving_idx is not None:
                    # إنشاء صف جديد بقيم صفرية
                    delay_row = {"KPI": "3PL Delay"}
                    for col in df_3pl_table.columns:
                        if col != "KPI":
                            delay_row[col] = 0

                    # تحويل DataFrame إلى قائمة من القواميس
                    rows_list = df_3pl_table.to_dict(orient="records")

                    # العثور على موضع الصف في القائمة
                    insert_position = None
                    for i, row_dict in enumerate(rows_list):
                        kpi_value = str(row_dict.get("KPI", "")).strip()
                        if "on time receiving" in kpi_value.lower():
                            insert_position = i + 1
                            break

                    # إدراج الصف الجديد
                    if insert_position is not None:
                        rows_list.insert(insert_position, delay_row)
                        df_3pl_table = pd.DataFrame(rows_list)

            reasons_3pl = result_3pl.get("reason", [])

            # =======================================
            # 🔵 معالجة Dock to Stock (Roche)
            # =======================================
            reasons_roche = []
            try:

                # df_roche = pd.read_excel(excel_path, sheet_name="Dock to stock - Roche", engine="openpyxl")
                # قراءة كل الشيتات أولاً
                xls = pd.ExcelFile(excel_path, engine="openpyxl")

                # محاولة إيجاد الشيت الصحيح تلقائيًا (حتى لو الاسم فيه مسافات أو اختلاف حروف)
                sheet_name = None
                for name in xls.sheet_names:
                    if (
                        "dock" in name.lower()
                        and "stock" in name.lower()
                        and "roche" in name.lower()
                    ):
                        sheet_name = name
                        break

                if not sheet_name:
                    raise ValueError(
                        f"❌ لم يتم العثور على شيت Roche في الملف. الشيتات المتاحة: {xls.sheet_names}"
                    )

                print(f"✅ تم استخدام الشيت: {sheet_name}")

                # قراءة الشيت الصحيح
                df_roche = pd.read_excel(xls, sheet_name=sheet_name)
                df_roche.columns = df_roche.columns.astype(str).str.strip()

                print("🔍 Roche columns:", df_roche.columns.tolist())

                month_col = df_roche.columns[0]

                melted_df = df_roche.melt(
                    id_vars=[month_col], var_name="KPI", value_name="Value"
                )
                pivot_df = (
                    melted_df.pivot_table(
                        index="KPI", columns=month_col, values="Value", aggfunc="sum"
                    )
                    .reset_index()
                    .rename_axis(None, axis=1)
                )

                # تحويل القيم إلى int
                for col in pivot_df.columns:
                    if col != "KPI":
                        pivot_df[col] = pivot_df[col].apply(
                            lambda x: int(round(float(x))) if pd.notna(x) else 0
                        )

                ordered_cols = ["KPI"] + [
                    c for c in order_months(pivot_df.columns.tolist()) if c != "KPI"
                ]
                pivot_df = pivot_df[ordered_cols]

                # حذف الأعمدة "Total" بعد الشهور
                pivot_df = pivot_df.loc[
                    :, ~pivot_df.columns.str.lower().str.contains("total")
                ]

                # حساب عمود 2025 (إجمالي كل الشهور)
                # حساب عمود 2025 (إجمالي كل الشهور)
                month_cols = [
                    c
                    for c in pivot_df.columns
                    if c not in ["KPI", "Reason Group", "2025"]
                ]
                pivot_df["2025"] = pivot_df[month_cols].sum(axis=1).astype(int)

                # إضافة صف Total في نهاية الجدول
                total_row = {"KPI": "Total (Roche)"}
                for col in pivot_df.columns:
                    if col != "KPI":
                        total_row[col] = int(pivot_df[col].sum())
                pivot_df = pd.concat(
                    [pivot_df, pd.DataFrame([total_row])], ignore_index=True
                )

                # حذف عمود Reason Group نهائيًا قبل الإرجاع
                if "Reason Group" in pivot_df.columns:
                    pivot_df = pivot_df.drop(columns=["Reason Group"])

                df_roche_table = pivot_df
                if selected_months_norm:
                    roche_cols = ["KPI"] + [
                        m for m in selected_months_norm if m in df_roche_table.columns
                    ]
                    if "2025" in df_roche_table.columns:
                        roche_cols.append("2025")
                    df_roche_table = df_roche_table[
                        [col for col in roche_cols if col in df_roche_table.columns]
                    ]
                elif selected_month_norm:
                    roche_cols = ["KPI", selected_month_norm]
                    if "2025" in df_roche_table.columns:
                        roche_cols.append("2025")
                    df_roche_table = df_roche_table[
                        [col for col in roche_cols if col in df_roche_table.columns]
                    ]
                # reasons_roche = self.filter_dock_to_stock_roche_reasons(request)
                reasons_roche = []

            except Exception as e:
                print(f"⚠️ Roche read error: {e}")
                df_roche_table = pd.DataFrame()

            # =======================================
            # 🟣 تجهيز الشارت
            # =======================================
            all_months = order_months(
                sorted(
                    set().union(*[list(v.keys()) for v in df_chart_combined.values()])
                )
            )
            if selected_months_norm:
                all_months = [m for m in selected_months_norm if m in all_months]
            on_time_values = df_chart_combined.get("3PL On Time %", {})
            target_values = df_chart_combined.get("Target", {})

            hit_pct = (
                min(round(float(np.mean(list(on_time_values.values()))), 2), 100)
                if on_time_values
                else 0
            )
            target_pct = (
                min(round(float(np.mean(list(target_values.values()))), 2), 100)
                if target_values
                else 100
            )

            chart_data = []
            if selected_month_norm or any(v != 0 for v in on_time_values.values()):
                chart_data.append(
                    {
                        "type": "column",
                        "name": "On time receiving (%)",
                        "color": "#d0e7ff",
                        "showInLegend": False,  # ✅ إخفاء الـ legend لتجنب التكرار
                        "dataPoints": [
                            {"label": m, "y": min(float(on_time_values.get(m, 0)), 100)}
                            for m in all_months
                        ],
                    }
                )

            # ✅ إزالة dataset الـ target لأننا نستخدم خط مخصص فقط
            # if selected_month_norm or any(v != 0 for v in target_values.values()):
            #     chart_data.append(...)

            inbound_result = self.filter_inbound(
                request, selected_month, selected_months
            )
            inbound_html = inbound_result.get("detail_html", "")
            inbound_sub_table = inbound_result.get("sub_table")
            combined_reasons = list(reasons_3pl) + list(reasons_roche)

            # =======================================
            # 🧱 بناء العرض النهائي
            # =======================================
            if chart_data:
                for dataset in chart_data:
                    dataset.setdefault("related_table", "Inbound")

            # ✅ إضافة chart_data لكل sub_table بشكل منفصل
            chart_data_3pl = []
            chart_data_roche = []
            if chart_data:
                for dataset in chart_data:
                    dataset_3pl = dataset.copy()
                    dataset_3pl["related_table"] = "Inbound — 3PL"
                    chart_data_3pl.append(dataset_3pl)

                    dataset_roche = dataset.copy()
                    dataset_roche["related_table"] = "Inbound — Roche"
                    chart_data_roche.append(dataset_roche)

            tab_data = {
                "name": "Inbound",
                "sub_tables": [
                    {
                        "id": "sub-table-inbound-3pl",
                        "title": "Inbound — 3PL",
                        "columns": df_3pl_table.columns.tolist(),
                        "data": df_3pl_table.to_dict(orient="records"),
                        "chart_data": chart_data_3pl,
                    },
                    {
                        "id": "sub-table-inbound-roche",
                        "title": "Inbound — Roche",
                        "columns": df_roche_table.columns.tolist(),
                        "data": df_roche_table.to_dict(orient="records"),
                        "chart_data": chart_data_roche,
                    },
                ],
                "combined_reasons": combined_reasons,
                "canvas_id": f"chart-{slugify('inbound')}",
                "inbound_html": inbound_html,
                "chart_data": chart_data,  # ✅ الاحتفاظ بـ chart_data العام أيضاً
            }
            if inbound_sub_table:
                tab_data["sub_tables"].append(inbound_sub_table)
            month_norm_tab = self.apply_month_filter_to_tab(
                tab_data,
                (
                    (selected_month_norm or selected_month)
                    if not selected_months_norm
                    else None
                ),
                selected_months_norm or None,
            )

            html = render_to_string(
                "forms-table/table/bootstrap-table/basic-table/components/excel-sheet-table.html",
                {"tab": tab_data, "selected_month": month_norm_tab},
            )

            total_count = len(df_3pl_table) + len(df_roche_table)

            print(f"📊 [RESULT] Inbound — Hit={hit_pct}%, Target={target_pct}")

            return {
                "chart_data": chart_data,
                "detail_html": html,
                "count": total_count,
                "canvas_id": tab_data["canvas_id"],
                "hit_pct": hit_pct,
                "target_pct": target_pct,
                "tab_data": tab_data,
            }

        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return {
                "chart_data": [],
                "detail_html": f"<p class='text-danger'>⚠️ Error: {e}</p>",
                "count": 0,
            }

    def overview_tab(
        self,
        request=None,
        selected_month=None,
        selected_months=None,
        from_all_in_one=False,
    ):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cache.clear()
        tab_cards = []

        target_manual = {
            "inbound": 99,
            "outbound": 98,
            "total lead time performance": 98,
            "pods update": 98,
            "return & refusal": 100,
        }

        def process_tab(tab_name):
            detail_html, count, hit_pct = "", 0, 0
            try:
                res = {}
                tab_lower = tab_name.lower()
                month_for_filters = selected_month if not selected_months else None

                if tab_lower in ["rejections", "return & refusal"]:
                    res = self.filter_rejections_combined(
                        request,
                        month_for_filters,
                        selected_months=selected_months,
                    )
                elif tab_lower == "inbound":
                    res = self.filter_dock_to_stock_combined(
                        request,
                        month_for_filters,
                        selected_months=selected_months,
                    )
                elif "pods update" in tab_lower:
                    res = self.filter_pods_update(request, month_for_filters)
                elif tab_lower == "outbound" or "total lead time performance" in tab_lower:
                    res = self.filter_total_lead_time_performance(
                        request,
                        month_for_filters,
                        selected_months=selected_months,
                    )

                # النسبة الحقيقية زي ما راجعة من الدالة
                hit_pct = res.get("hit_pct", 0)
                if isinstance(hit_pct, dict):
                    if selected_month and selected_month.capitalize() in hit_pct:
                        hit_pct_val = hit_pct[selected_month.capitalize()]
                    else:
                        # نحسب المتوسط
                        hit_pct_val = int(round(sum(hit_pct.values()) / len(hit_pct)))
                else:
                    try:
                        hit_pct_val = int(round(float(hit_pct)))
                    except:
                        hit_pct_val = 0

                hit_pct_val = max(0, min(hit_pct_val, 100))

                target_pct = target_manual.get(tab_lower, 100)
                color_class = "bg-success" if hit_pct >= target_pct else "bg-danger"

                progress_html = f"""
                    <div class='mb-3'>
                        <div class='d-flex justify-content-between align-items-center mb-1'>
                            <strong class='text-capitalize'>{tab_name}</strong>
                            <small>{hit_pct}% / Target: {target_pct}%</small>
                        </div>
                        <div class='progress' style='height: 20px;'>
                            <div class='progress-bar {color_class}' role='progressbar'
                                 style='width: {hit_pct}%;' aria-valuenow='{hit_pct}'
                                 aria-valuemin='0' aria-valuemax='100'>
                                 {hit_pct}%
                            </div>
                        </div>
                    </div>
                """

                detail_html = progress_html + (res.get("detail_html", "") or "")
                count = res.get("count", 0)

            except Exception:
                detail_html = "<p class='text-muted'>No data available.</p>"
                hit_pct = 0
                target_pct = target_manual.get(tab_name.lower(), 100)

            return {
                "name": tab_name,
                "hit_pct": hit_pct_val,
                "target_pct": target_pct,
                "detail_html": detail_html,
                "count": count,
            }

        tabs_order = [
            "Inbound",
            "Outbound",
            "Return & Refusal",
            "PODs update",
        ]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(process_tab, t): t for t in tabs_order}
            for future in as_completed(futures):
                tab_cards.append(future.result())

        tab_cards.sort(key=lambda x: tabs_order.index(x["name"]))

        if not from_all_in_one:
            tab_cards = [
                t
                for t in tab_cards
                if t.get("name", "").strip().lower()
                not in ["rejections", "return & refusal"]
            ]

        all_progress_html = "<div class='card p-4 shadow-sm rounded-4 mb-4'>"
        all_progress_html += (
            "<h5 class='fw-bold text-primary mb-3'>📈 نسب الأداء لكل التابات</h5>"
        )
        for tab in tab_cards:
            color_class = (
                "bg-success" if tab["hit_pct"] >= tab["target_pct"] else "bg-danger"
            )
            all_progress_html += f"""
                <div class='mb-3'>
                    <div class='d-flex justify-content-between align-items-center mb-1'>
                        <strong>{tab['name']}</strong>
                        <small>{tab['hit_pct']}% / Target: {tab['target_pct']}%</small>
                    </div>
                    <div class='progress' style='height: 20px;'>
                        <div class='progress-bar {color_class}' role='progressbar'
                             style='width: {tab['hit_pct']}%;' aria-valuenow='{tab['hit_pct']}'
                             aria-valuemin='0' aria-valuemax='100'>
                             {tab['hit_pct']}%
                        </div>
                    </div>
                </div>
            """
        all_progress_html += "</div>"

        return {"tab_cards": tab_cards, "detail_html": all_progress_html}

    def _get_dashboard_include_context(self, request):
        """
        يُرجع سياق الداشبورد (نفس منطق dashboard_tab) لاستخدامه عند include
        container-fluid-dashboard في التمبلت حتى تورث base واللينكات والشارتس.
        """
        context = get_dashboard_tab_context(request)
        context["title"] = self.DASHBOARD_TAB_NAME
        excel_path = _get_dashboard_excel_path(request) or _get_excel_path_for_request(request)
        if excel_path:
            inbound_data = _read_inbound_data_from_excel(excel_path)
            if inbound_data:
                context["inbound_kpi"] = inbound_data["inbound_kpi"]
                context["pending_shipments"] = inbound_data["pending_shipments"]
            # شارتات دينامك من الإكسل (نفس فكرة chart_data في rejection)
            charts_from_excel = _read_dashboard_charts_from_excel(excel_path)
            for key, value in charts_from_excel.items():
                if value is not None:
                    context[key] = value
            outbound_data = _read_outbound_data_from_excel(excel_path)
            if outbound_data:
                context.setdefault(
                    "outbound_kpi",
                    {
                        "released_orders": 146,
                        "picked_orders": 120,
                        "pod_compliance_pct": 94,
                        "insight_text": "Delays mainly caused by transportation issues or customer confirmation.",
                    },
                )
                context["outbound_kpi"]["released_orders"] = outbound_data["released_orders"]
                context["outbound_kpi"]["picked_orders"] = outbound_data["picked_orders"]
            pods_chart = _read_pods_data_from_excel(excel_path)
            if pods_chart:
                context["pod_compliance_chart_data"] = pods_chart
            returns_data = _read_returns_data_from_excel(excel_path)
            if returns_data:
                context["returns_kpi"] = returns_data["returns_kpi"]
                context["returns_chart_data"] = returns_data["returns_chart_data"]
            inventory_data = _read_inventory_data_from_excel(excel_path)
            if inventory_data:
                context["inventory_kpi"] = inventory_data["inventory_kpi"]
            capacity_data = _read_inventory_snapshot_capacity_from_excel(excel_path)
            if capacity_data:
                context["inventory_capacity_data"] = capacity_data["inventory_capacity_data"]
            warehouse_table = _read_inventory_warehouse_table_from_excel(excel_path)
            if warehouse_table:
                context["inventory_warehouse_table"] = warehouse_table["inventory_warehouse_table"]
            returns_region = _read_returns_region_table_from_excel(excel_path)
            if returns_region:
                context["returns_region_table"] = returns_region["returns_region_table"]
        context.setdefault("inbound_kpi", INBOUND_DEFAULT_KPI.copy())
        context.setdefault("pending_shipments", list(INBOUND_DEFAULT_PENDING_SHIPMENTS))
        context.setdefault(
            "outbound_kpi",
            {
                "released_orders": 146,
                "picked_orders": 120,
                "pod_compliance_pct": 94,
                "insight_text": "Delays mainly caused by transportation issues or customer confirmation.",
            },
        )
        context.setdefault("outbound_chart_data", DASHBOARD_DEFAULT_CHART_DATA["outbound_chart_data"].copy())
        context.setdefault(
            "pod_compliance_chart_data",
            {
                "categories": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                "series": [
                    {"name": "On Time", "data": [70, 72, 68, 75, 74, 78]},
                    {"name": "Pending", "data": [15, 14, 18, 12, 13, 10]},
                    {"name": "Late", "data": [15, 14, 14, 13, 13, 12]},
                ],
            },
        )
        context.setdefault("returns_kpi", {"total_skus": 2538, "total_lpns": 4810})
        context.setdefault("returns_chart_data", DASHBOARD_DEFAULT_CHART_DATA["returns_chart_data"].copy())
        context.setdefault(
            "returns_region_table",
            [
                {"region": "Main warehouse", "skus": "2,538", "available": "1118", "utilization_pct": "71%"},
                {"region": "Dammam DC", "skus": "501", "available": "200", "utilization_pct": "—"},
                {"region": "Riyadh DC", "skus": "3,996", "available": "209", "utilization_pct": "—"},
                {"region": "Jeddah DC", "skus": "7,996", "available": "300", "utilization_pct": "—"},
            ],
        )
        context.setdefault("inventory_kpi", {"total_skus": 2538, "total_lpns": 4810, "utilization_pct": "78"})
        context.setdefault("inventory_capacity_data", DASHBOARD_DEFAULT_CHART_DATA["inventory_capacity_data"].copy())
        context.setdefault(
            "inventory_warehouse_table",
            [
                {"warehouse": "Main Warehouse", "skus": "117", "available_space": "9,536,995", "utilization_pct": "223"},
                {"warehouse": "Dammam DC", "skus": "108", "available_space": "9,260,995", "utilization_pct": "553"},
                {"warehouse": "Riyadh DC", "skus": "145", "available_space": "9,827,955", "utilization_pct": "535"},
                {"warehouse": "Jeddah DC", "skus": "159", "available_space": "5,324,353", "utilization_pct": "279"},
            ],
        )
        # Override with DB models if available (Region, WarehouseMetric)
        regions_from_db = context_helpers.get_regions_table_from_db()
        if regions_from_db:
            context["returns_region_table"] = regions_from_db
        warehouse_metrics_from_db = context_helpers.get_warehouse_metrics_table_from_db()
        if warehouse_metrics_from_db:
            context["inventory_warehouse_table"] = warehouse_metrics_from_db
        context["dashboard_theme"] = context_helpers.get_dashboard_theme_dict()
        return context

    def dashboard_tab(self, request):
        """
        🔹 تاب Dashboard: يعرض تصميم الداشبورد (container-fluid-dashboard).
        التمبلت منفصل عن excel-sheet-table ويُحمّل داخل منطقة المحتوى عند اختيار تاب Dashboard.
        نفس فكرة rejection: نرجع detail_html + chart_data + chart_title عشان الشارتات تبقى دينامك.
        """
        try:
            context = self._get_dashboard_include_context(request)
            html = render_to_string(
                "container-fluid-dashboard.html",
                context,
                request=request,
            )
            # نفس شكل الـ rejection: chart_data و chart_title للشارتات الدينامك
            outbound_chart = context.get("outbound_chart_data")
            chart_data = []
            if outbound_chart and isinstance(outbound_chart, dict):
                categories = outbound_chart.get("categories", [])
                series = outbound_chart.get("series", [])
                if categories and series is not None:
                    chart_data.append({
                        "type": "line",
                        "name": "POD Compliance",
                        "dataPoints": [{"label": c, "y": float(s)} for c, s in zip(categories, series)],
                    })
            return {
                "detail_html": html,
                "chart_data": chart_data,
                "chart_title": "Dashboard – POD Compliance",
                "dashboard_charts": {
                    "outbound": context.get("outbound_chart_data"),
                    "returns": context.get("returns_chart_data"),
                    "inventory": context.get("inventory_capacity_data"),
                },
            }
        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"error": f"An error occurred while loading Dashboard: {e}"}

    def warehouse_tab(self, request):
        """
        🔹 تاب Warehouse فقط: يعرض كروت المستودعات ديناميك من الأدمن.
        كل مستودع مضاف في الأدمن = كارد واحد في الصفحة.
        """
        try:
            warehouse_overview = context_helpers.get_warehouse_overview_list()
            clerk_interview_rows = context_helpers.get_clerk_interview_list()
            dashboard_theme = context_helpers.get_dashboard_theme_dict()
            phases_sections = context_helpers.get_phases_sections_list()
            html = render_to_string(
                "components/ui-kits/tab-bootstrap/components/warehouse-cards.html",
                {
                    "warehouse_overview": warehouse_overview,
                    "clerk_interview_rows": clerk_interview_rows,
                    "dashboard_theme": dashboard_theme,
                    "phases_sections": phases_sections,
                },
                request=request,
            )
            return {"detail_html": html}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "detail_html": f"<div class='alert alert-danger'>⚠️ {e}</div>"}

    def meeting_points_tab(self, request):
        """
        🔹 عرض تاب Meeting Points & Action مع إمكانية الفلترة حسب الحالة (منتهية / غير منتهية)
        """
        if not request.session.get("meeting_points_unlocked"):
            return JsonResponse({"require_password": True})
        try:
            # ✅ جلب الحالة من الـ GET parameter
            status_filter = request.GET.get(
                "status"
            )  # القيم الممكنة: done / pending / all

            # ✅ استرجاع كل النقاط بالترتيب
            meeting_points = MeetingPoint.objects.all().order_by(
                "is_done", "-created_at"
            )

            # ✅ تطبيق الفلترة بناءً على الحالة
            if status_filter == "done":
                meeting_points = meeting_points.filter(is_done=True)
            elif status_filter == "pending":
                meeting_points = meeting_points.filter(is_done=False)
            # 'all' يعرض كل النقاط (done + pending)
            # لا حاجة لفلترة إضافية لأنه استرجعنا كل النقاط في البداية

            # ✅ إحصائيات
            done_count = meeting_points.filter(is_done=True).count()
            total_count = meeting_points.count()

            # ✅ تجهيز البيانات للتمبلت مع assigned_to
            meeting_data = [
                {
                    "id": p.id,
                    "description": p.description,
                    "assigned_to": getattr(
                        p, "assigned_to", ""
                    ),  # ✅ الاسم ممكن يكون فاضي
                    "status": "Done" if p.is_done else "Pending",
                    "created_at": p.created_at,
                    "target_date": p.target_date,
                }
                for p in meeting_points
            ]

            context = {
                "meeting_points": meeting_points,
                "meeting_data": meeting_data,  # لو حابة تستخدمي البيانات مباشرة في JS
                "done_count": done_count,
                "total_count": total_count,
                "status_filter": status_filter,
            }

            # ✅ بناء HTML من التمبلت
            html = render_to_string("meeting_points.html", context, request=request)

            # ✅ إرجاع النتيجة
            return JsonResponse(
                {
                    "detail_html": html,
                    "count": meeting_points.count(),
                    "done_count": done_count,
                    "total_count": total_count,
                },
                safe=False,
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"error": f"An error occurred while loading data: {e}"}, status=500
            )

    def project_tracker_tab(self, request):
        """تاب Project Tracker: عرض بيانات من الأدمن (project_tracker_items)."""
        try:
            pt_filter = (request.GET.get("project_type") or "").strip().lower()
            if pt_filter not in ("idea", "automation"):
                pt_filter = None
            project_tracker_items = context_helpers.get_project_tracker_list(project_type=pt_filter)
            html = render_to_string(
                "components/ui-kits/tab-bootstrap/components/project-tracker-cards.html",
                {"project_tracker_items": project_tracker_items},
                request=request,
            )
            return {"detail_html": html}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "detail_html": f"<div class='alert alert-danger'>⚠️ {e}</div>"}


def meeting_points_unlock(request):
    """
    فك قفل تاب Meeting Points & Actions بإدخال كلمة المرور الصحيحة.
    يخزن في الجلسة حتى إغلاق المتصفح.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    password = request.POST.get("password", "").strip()
    if not password:
        try:
            body = json.loads(request.body) if request.body else {}
            password = (body.get("password") or "").strip()
        except (ValueError, TypeError):
            pass
    if not password:
        return JsonResponse({"ok": False, "message": "Password required"}, status=400)
    expected = getattr(settings, "MEETING_POINTS_TAB_PASSWORD", None)
    if not expected:
        return JsonResponse({"ok": False, "message": "Not configured"}, status=500)
    if password != expected:
        return JsonResponse({"ok": False, "message": "Wrong password"}, status=400)
    request.session["meeting_points_unlocked"] = True
    return JsonResponse({"ok": True})


class MeetingPointListCreateView(View):
    template_name = "meeting_points.html"

    def get(self, request, *args, **kwargs):
        status_filter = request.GET.get("status")  # "done" أو "pending" أو None

        today = date.today()
        current_month, current_year = today.month, today.year

        # حساب الشهر السابق
        if current_month == 1:
            prev_month = 12
            prev_year = current_year - 1
        else:
            prev_month = current_month - 1
            prev_year = current_year

        # ✅ جلب كل النقاط (الشهر الحالي كله + pending من الشهر السابق)
        meeting_points = MeetingPoint.objects.filter(
            Q(created_at__year=current_year, created_at__month=current_month)
            | Q(created_at__year=prev_year, created_at__month=prev_month, is_done=False)
        ).order_by("is_done", "-created_at")

        # ✅ تطبيق الفلتر لو المستخدم اختار حاجة
        if status_filter == "done":
            meeting_points = meeting_points.filter(is_done=True)
        elif status_filter == "pending":
            meeting_points = meeting_points.filter(is_done=False)

        done_count = meeting_points.filter(is_done=True).count()
        total_count = meeting_points.count()

        return render(
            request,
            self.template_name,
            {
                "meeting_points": meeting_points,
                "done_count": done_count,
                "total_count": total_count,
                "status_filter": status_filter,
            },
        )

    def post(self, request, *args, **kwargs):
        description = request.POST.get("description", "").strip()
        target_date = request.POST.get("target_date", "").strip() or None
        assigned_to = request.POST.get("assigned_to", "").strip() or None

        if description:
            point = MeetingPoint.objects.create(
                description=description,
                target_date=target_date,
                assigned_to=assigned_to if assigned_to else None,
            )

            return JsonResponse(
                {
                    "id": point.id,
                    "description": point.description,
                    "assigned_to": point.assigned_to,
                    "created_at": str(point.created_at),
                    "target_date": str(point.target_date),
                    "is_done": point.is_done,
                }
            )

        return JsonResponse({"error": "Empty description"}, status=400)


class ToggleMeetingPointView(View):
    def post(self, request, pk, *args, **kwargs):
        point = get_object_or_404(MeetingPoint, pk=pk)
        point.is_done = not point.is_done
        point.save()
        return JsonResponse({"is_done": point.is_done})


class DoneMeetingPointView(View):
    def post(self, request, pk, *args, **kwargs):
        point = get_object_or_404(MeetingPoint, pk=pk)
        point.is_done = not point.is_done
        point.save()
        return JsonResponse({"is_done": point.is_done})
