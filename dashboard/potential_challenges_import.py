# استيراد جدول Potential Challenges من Excel
# الأعمدة: Date | Challenges | Status | Progress % | Solutions

import pandas as pd
from django.db.models import Max


def _normalize_col(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def _find_column(df, *candidates):
    def normalize_for_match(s):
        return _normalize_col(s).lower().replace(" ", "").replace("%", "").replace("(", "").replace(")", "")

    for cand in candidates:
        cand_norm = normalize_for_match(cand)
        if not cand_norm:
            continue
        for col in df.columns:
            if normalize_for_match(col) == cand_norm:
                return col
    for cand in candidates:
        cand_norm = normalize_for_match(cand)
        if not cand_norm or len(cand_norm) < 3:
            continue
        for col in df.columns:
            col_norm = normalize_for_match(col)
            if cand_norm in col_norm:
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


def import_potential_challenges_from_excel(file, sheet_name="Potential_Challenges"):
    """
    يقرأ من الشيت ويحفظ في PotentialChallenge.
    الأعمدة: Date | Challenges | Status | Progress % | Solutions
    إذا الشيت المطلوب مش موجود، يقرأ أول شيت في الملف (مثلاً Sheet1).
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import PotentialChallenge

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

    col_date = _find_column(df, "Date", "date")
    col_challenges = _find_column(df, "Challenges", "challenges")
    col_status = _find_column(df, "Status", "status")
    col_progress = _find_column(
        df, "Progress %", "Progress%", "Progress", "progress %", "progress%", "progress"
    )
    col_solutions = _find_column(df, "Solutions", "solutions")

    if not col_challenges:
        errors.append("Column 'Challenges' not found. Available: " + ", ".join(str(c) for c in df.columns[:12]))

    if errors:
        return 0, errors

    df = df.dropna(how="all")
    max_order = 0
    try:
        agg = PotentialChallenge.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        date_val = _normalize_col(row.get(col_date, "")) if col_date else ""
        challenges_val = _normalize_col(row.get(col_challenges, "")) if col_challenges else ""
        status_raw = _normalize_col(row.get(col_status, "")) if col_status else ""
        progress_raw = row.get(col_progress, 0) if col_progress else 0
        solutions_val = _normalize_col(row.get(col_solutions, "")) if col_solutions else ""

        if not date_val and not challenges_val:
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
                if 0 <= val <= 1 and val != int(val):
                    val = val * 100
                progress_val = int(round(val))
            progress_val = max(0, min(100, progress_val))
        except (ValueError, TypeError):
            progress_val = 0

        try:
            max_order += 1
            PotentialChallenge.objects.create(
                date=date_val or "—",
                challenges=challenges_val or "—",
                status=status_val,
                progress_pct=progress_val,
                solutions=solutions_val or "—",
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    return created_count, errors
