# استيراد Clerk Details (Employee Interview Profiles) من Excel
# الملف: Clerk_details.xlsx — الشيت: interview
# العمود الجانبي (Sidebar): DEPT_NAME_EN

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


def import_clerk_details_from_excel(file, sheet_name="interview"):
    """
    يقرأ من الشيت المحدد (افتراضي interview) ويحفظ الصفوف في ClerkDetail.
    الملف: Clerk_details.xlsx، الشيت: interview.
    العمود DEPT_NAME_EN يُستخدم للـ sidebar وعرض اسم الموظف.
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import ClerkDetail

    created_count = 0
    errors = []

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception as e:
        return 0, [f"Could not read file: {e}"]

    if df.empty:
        return 0, ["File or sheet is empty."]

    col_map = [
        ("dept_name_en", ["DEPT_NAME_EN", "Dept Name En", "dept_name_en", "Name", "Person Name"]),
        ("department", ["Department", "department", "DEPT"]),
        ("company", ["Company", "company"]),
        ("business", ["Business", "business"]),
        ("account", ["Account", "account"]),
        ("mobile", ["Mobile", "mobile", "Phone"]),
        ("interview_date", ["Interview Date", "InterviewDate", "interview_date", "Date"]),
        ("work_details", ["Work Details", "WorkDetails", "work_details", "Details", "Process Note"]),
        ("reports_used", ["Reports Used", "ReportsUsed", "reports_used"]),
        ("system_badge", ["System", "System Used", "system_badge", "System Used", "Tag", "Badge"]),
    ]
    found_cols = {}
    for field_name, candidates in col_map:
        c = _find_column(df, *candidates)
        if c is not None:
            found_cols[field_name] = c

    if "dept_name_en" not in found_cols:
        errors.append("Could not find column: DEPT_NAME_EN (required for sidebar).")

    df = df.dropna(how="all")
    max_order = 0
    try:
        agg = ClerkDetail.objects.aggregate(m=Max("display_order"))
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

        dept_val = _normalize_col(get_val("dept_name_en"))
        if not dept_val:
            continue

        max_order += 1
        try:
            ClerkDetail.objects.create(
                dept_name_en=dept_val,
                department=_normalize_col(get_val("department")) or "",
                company=_normalize_col(get_val("company")) or "",
                business=_normalize_col(get_val("business")) or "",
                account=_normalize_col(get_val("account")) or "",
                mobile=_normalize_col(get_val("mobile")) or "",
                interview_date=_normalize_col(get_val("interview_date")) or "",
                work_details=_normalize_col(get_val("work_details")) or "",
                reports_used=_normalize_col(get_val("reports_used")) or "",
                system_badge=_normalize_col(get_val("system_badge")) or "",
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
