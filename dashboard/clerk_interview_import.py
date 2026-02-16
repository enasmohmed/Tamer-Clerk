# استيراد Clerk Interview Tracking من Excel
# الأعمدة: NO, DEPT_NAME_EN, Date, Clerk Name, Mobile, Company, Business, Account, System Used, Report Used, Details, WH Visit Reasons, Physical Dependency, Automation Potential, CT Suitability

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


def _parse_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "date"):
        return val.date() if hasattr(val, "date") else val
    s = _normalize_col(val)
    if not s:
        return None
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def import_clerk_interview_from_excel(file, sheet_name="Sheet1"):
    """
    يقرأ من الشيت المحدد ويحفظ الصفوف في ClerkInterviewTracking.
    الأعمدة: NO, DEPT_NAME_EN, Date, Clerk Name, Mobile, Company, Business, Account,
    System Used, Report Used, Details, WH Visit Reasons, Physical Dependency, Automation Potential, CT Suitability
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

    # Map display names to possible column names
    col_map = [
        ("no", ["NO", "No", "no", "#"]),
        ("dept_name_en", ["DEPT_NAME_EN", "DEPT NAME EN", "Dept Name En", "Department"]),
        ("date", ["Date", "date", "التاريخ"]),
        ("clerk_name", ["Clerk Name", "ClerkName", "clerk_name", "Name"]),
        ("mobile", ["Mobile", "mobile", "موبايل"]),
        ("company", ["Company", "company"]),
        ("business", ["Business", "business", "Businees"]),
        ("account", ["Account", "account"]),
        ("system_used", ["System Used", "SystemUsed", "system_used"]),
        ("report_used", ["Report Used", "ReportUsed", "report_used"]),
        ("details", ["Details", "details"]),
        ("wh_visit_reasons", ["WH Visit Reasons", "WH Visit Resons", "WHVisitReasons", "wh_visit_reasons"]),
        ("physical_dependency", ["Physical Dependency", "PhysicalDependency", "physical_dependency"]),
        ("automation_potential", ["Automation Potential", "AutomationPotential", "automation_potential"]),
        ("ct_suitability", ["CT Suitability", "CT Suitbility", "CTSuitability", "ct_suitability"]),
        ("optimization_plan", ["Optimization Plan", "OptimizationPlan", "optimization_plan"]),
    ]
    found_cols = {}
    for field_name, candidates in col_map:
        c = _find_column(df, *candidates)
        if c is not None:
            found_cols[field_name] = c

    # At least some key columns should exist
    if not any(k in found_cols for k in ("no", "clerk_name", "dept_name_en", "date")):
        errors.append("Could not find at least one of: NO, Clerk Name, DEPT_NAME_EN, Date.")

    df = df.dropna(how="all")
    max_order = 0
    try:
        agg = ClerkInterviewTracking.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        # Skip if entire row is empty
        if all(_normalize_col(row.get(c, "")) == "" for c in df.columns):
            continue

        def get_val(field):
            col = found_cols.get(field)
            if col is None:
                return "" if field != "date" else None
            return row.get(col)

        date_val = _parse_date(get_val("date")) if "date" in found_cols else None
        no_val = _normalize_col(get_val("no"))
        dept_val = _normalize_col(get_val("dept_name_en"))
        clerk_val = _normalize_col(get_val("clerk_name"))
        if not no_val and not clerk_val and not dept_val:
            continue

        max_order += 1
        try:
            ClerkInterviewTracking.objects.create(
                no=no_val or "",
                dept_name_en=dept_val or "",
                date=date_val,
                clerk_name=clerk_val or "",
                mobile=_normalize_col(get_val("mobile")) or "",
                company=_normalize_col(get_val("company")) or "",
                business=_normalize_col(get_val("business")) or "",
                account=_normalize_col(get_val("account")) or "",
                system_used=_normalize_col(get_val("system_used")) or "",
                report_used=_normalize_col(get_val("report_used")) or "",
                details=_normalize_col(get_val("details")) or "",
                wh_visit_reasons=_normalize_col(get_val("wh_visit_reasons")) or "",
                physical_dependency=_normalize_col(get_val("physical_dependency")) or "",
                automation_potential=_normalize_col(get_val("automation_potential")) or "",
                ct_suitability=_normalize_col(get_val("ct_suitability")) or "",
                optimization_plan=_normalize_col(get_val("optimization_plan")) or "",
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
