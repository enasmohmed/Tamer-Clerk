# استيراد Clerk Interview Tracking من Excel
# الأعمدة: WH, Clerk Name, NATIONALITY, Report Used, Optimization Status, Strength, System Used, Business, Remark
# الملف: CP_project.xlsx — الشيت: Sheet1

import pandas as pd
from django.db.models import Max


def _normalize_col(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def _find_column(df, *candidates):
    """يرجع اسم العمود الأول الموجود في الداتا فريم من قائمة الأسماء."""
    for cand in candidates:
        cand_clean = cand.strip().lower()
        for col in df.columns:
            if _normalize_col(col).lower() == cand_clean:
                return col
    return None


def import_clerk_interview_from_excel(file, sheet_name="Sheet1"):
    """
    يقرأ من الشيت المحدد (افتراضي Sheet1) ويحفظ الصفوف في ClerkInterviewTracking.
    الأعمدة: WH, Clerk Name, NATIONALITY, Report Used, Optimization Status, Strength, System Used, Business, Remark
    الملف المطلوب: CP_project.xlsx (أو أي ملف بنفس الأعمدة).
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import ClerkInterviewTracking

    created_count = 0
    errors = []

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception as e:
        return 0, [f"Could not read file: {e}"]

    if df.empty:
        return 0, ["File or sheet is empty."]

    # Map display names to possible column names (new structure)
    col_map = [
        ("wh", ["WH", "Wh", "wh", "Warehouse"]),
        ("clerk_name", ["Clerk Name", "ClerkName", "clerk_name", "Name"]),
        ("nationality", ["NATIONALITY", "Nationality", "nationality"]),
        (
            "optimization_status",
            ["Optimization Status", "OptimizationStatus", "optimization_status"],
        ),
        ("system_used", ["System Used", "SystemUsed", "system_used"]),
        ("business", ["Business", "Busnise", "busnise", "business"]),
        ("remark", ["Remark", "remark", "Remarks"]),
    ]
    found_cols = {}
    for field_name, candidates in col_map:
        c = _find_column(df, *candidates)
        if c is not None:
            found_cols[field_name] = c

    if not any(k in found_cols for k in ("wh", "clerk_name")):
        errors.append("Could not find at least one of: WH, Clerk Name.")

    df = df.dropna(how="all")
    max_order = 0
    try:
        agg = ClerkInterviewTracking.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        if all(_normalize_col(row.get(c, "")) == "" for c in df.columns):
            continue

        def get_val(field):
            col = found_cols.get(field)
            if col is None:
                return ""
            return row.get(col)

        wh_val = _normalize_col(get_val("wh"))
        clerk_val = _normalize_col(get_val("clerk_name"))
        if not wh_val and not clerk_val:
            continue

        max_order += 1
        try:
            ClerkInterviewTracking.objects.create(
                wh=wh_val or "",
                clerk_name=clerk_val or "",
                nationality=_normalize_col(get_val("nationality")) or "",
                optimization_status=_normalize_col(get_val("optimization_status"))
                or "",
                system_used=_normalize_col(get_val("system_used")) or "",
                business=_normalize_col(get_val("business")) or "",
                remark=_normalize_col(get_val("remark")) or "",
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
