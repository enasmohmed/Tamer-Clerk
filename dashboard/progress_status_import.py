# استيراد جدول Progress Status من Excel
# الملف: Quick_wins.xlsx — الشيت: Sheet1
# الأعمدة: Clerk, Account, Remark, Status

import pandas as pd
from django.db.models import Max


def _normalize_col(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def _find_column(df, *candidates):
    for cand in candidates:
        c_clean = _normalize_col(cand).lower().replace(" ", "")
        for col in df.columns:
            if _normalize_col(col).lower().replace(" ", "") == c_clean:
                return col
    for cand in candidates:
        c_clean = _normalize_col(cand).lower().replace(" ", "")
        if len(c_clean) < 3:
            continue
        for col in df.columns:
            if c_clean in _normalize_col(col).lower().replace(" ", ""):
                return col
    return None


def _normalize_status(val):
    s = _normalize_col(val).lower()
    if "completed" in s or "done" in s:
        return "completed"
    if "progress" in s or "in progress" in s:
        return "in_progress"
    if "not" in s and "started" in s:
        return "not_started"
    return "not_started"


def import_progress_status_from_excel(file, sheet_name="Sheet1"):
    """
    يقرأ من الشيت (افتراضي Sheet1) ويحفظ في ProgressStatus.
    الأعمدة: Clerk, Account, Remark, Status
    الملف: Quick_wins.xlsx
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import ProgressStatus

    created_count = 0
    errors = []

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception as e:
        err_msg = str(e).strip().lower()
        if "not found" in err_msg or "worksheet" in err_msg or "no sheet" in err_msg:
            try:
                xl = pd.ExcelFile(file, engine="openpyxl")
                first_sheet = xl.sheet_names[0] if xl.sheet_names else None
                if first_sheet:
                    df = pd.read_excel(file, sheet_name=first_sheet, engine="openpyxl", header=0)
                else:
                    return 0, [f"Could not read file: {e}"]
            except Exception as e2:
                return 0, [f"Could not read file: {e2}"]
        else:
            return 0, [f"Could not read file: {e}"]

    if df.empty:
        return 0, ["File or sheet is empty."]

    col_clerk = _find_column(df, "Clerk", "clerk")
    col_account = _find_column(df, "Account", "Accunt", "account")
    col_remark = _find_column(df, "Remark", "remark", "Remarks")
    col_status = _find_column(df, "Status", "status")

    if not col_clerk and not col_account:
        errors.append("Could not find at least one of: Clerk, Account.")

    df = df.dropna(how="all")
    max_order = 0
    try:
        agg = ProgressStatus.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        if all(_normalize_col(row.get(c, "")) == "" for c in df.columns):
            continue

        clerk_val = _normalize_col(row.get(col_clerk, "")) if col_clerk else ""
        account_val = _normalize_col(row.get(col_account, "")) if col_account else ""
        if not clerk_val and not account_val:
            continue

        remark_val = _normalize_col(row.get(col_remark, "")) if col_remark else ""
        status_raw = _normalize_col(row.get(col_status, "")) if col_status else ""
        status_val = _normalize_status(status_raw) if status_raw else "not_started"

        max_order += 1
        try:
            ProgressStatus.objects.create(
                clerk=clerk_val or "",
                account=account_val or "",
                remark=remark_val or "",
                status=status_val,
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
