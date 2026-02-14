# استيراد جدول Weekly Project Tracker من ملف Excel
# الملف: Weekly_Project_Tracker.xlsx
# الشيت: Weekly Tracker
# الأعمدة: Week | Task | Status | Progress % | Impact

import pandas as pd


def _normalize_col(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def _find_column(df, *candidates):
    """يرجع اسم العمود الأول الموجود في الداتا فريم من قائمة الأسماء (بدون مراعاة حالة الأحرف والمسافات و%)"""
    def normalize_for_match(s):
        return _normalize_col(s).lower().replace(" ", "").replace("%", "").replace("(", "").replace(")", "")

    # Exact match first
    for cand in candidates:
        cand_norm = normalize_for_match(cand)
        if not cand_norm:
            continue
        for col in df.columns:
            if normalize_for_match(col) == cand_norm:
                return col
    # Loose match: column name contains the candidate (e.g. "Progress" matches "Progress %")
    for cand in candidates:
        cand_norm = normalize_for_match(cand)
        if not cand_norm or len(cand_norm) < 4:
            continue
        for col in df.columns:
            col_norm = normalize_for_match(col)
            if cand_norm in col_norm:
                return col
    return None


def _normalize_status(val):
    """تحويل قيمة Status من الاكسل لأحد الخيارات: completed, in_progress, not_started."""
    s = _normalize_col(val).lower()
    if "completed" in s or "done" in s:
        return "completed"
    if "progress" in s or "in progress" in s:
        return "in_progress"
    if "not" in s and "started" in s:
        return "not_started"
    if "started" in s and "not" not in s:
        return "in_progress"
    return "not_started"


def import_weekly_tracker_from_excel(file, sheet_name="Weekly Tracker"):
    """
    يقرأ من شيت "Weekly Tracker" ويحفظ الصفوف في WeeklyProjectTrackerRow.
    الأعمدة: Week | Task | Status | Progress % | Impact
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import WeeklyProjectTrackerRow

    created_count = 0
    errors = []

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception as e:
        return 0, [f"Could not read file: {e}"]

    if df.empty:
        return 0, ["File or sheet is empty."]

    col_week = _find_column(df, "Week", "week")
    col_task = _find_column(df, "Task", "task")
    col_status = _find_column(df, "Status", "status")
    col_progress = _find_column(
        df,
        "Progress %",
        "Progress%",
        "Progress",
        "progress %",
        "progress%",
        "progress",
        "Progress (%)",
        "Progress % ",
        "% Progress",
    )
    col_impact = _find_column(df, "Impact", "impact")

    if not col_week:
        errors.append("Column 'Week' not found.")
    if not col_task:
        errors.append("Column 'Task' not found.")
    if not col_progress:
        errors.append("Column 'Progress %' (or similar) not found. Available columns: " + ", ".join(str(c) for c in df.columns[:10]))

    if errors:
        return 0, errors

    df = df.dropna(how="all")
    from django.db.models import Max
    max_order = 0
    try:
        agg = WeeklyProjectTrackerRow.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        week = _normalize_col(row.get(col_week, ""))
        task = _normalize_col(row.get(col_task, ""))
        status_raw = _normalize_col(row.get(col_status, "")) if col_status else ""
        progress_raw = row.get(col_progress, 0) if col_progress else 0
        impact = _normalize_col(row.get(col_impact, "")) if col_impact else ""

        if not week and not task:
            continue

        status_val = _normalize_status(status_raw) if status_raw else "not_started"

        try:
            if progress_raw is None or (isinstance(progress_raw, float) and pd.isna(progress_raw)):
                progress_val = 0
            else:
                raw = progress_raw
                if isinstance(raw, str):
                    raw = raw.strip().replace("%", "").strip()
                val = float(raw)
                # If value is between 0 and 1 (e.g. 0.75), treat as fraction -> multiply by 100
                if 0 <= val <= 1 and val != int(val):
                    val = val * 100
                progress_val = int(round(val))
            progress_val = max(0, min(100, progress_val))
        except (ValueError, TypeError):
            progress_val = 0

        try:
            max_order += 1
            WeeklyProjectTrackerRow.objects.create(
                week=week or "—",
                task=task or "—",
                status=status_val,
                progress_pct=progress_val,
                impact=impact,
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
