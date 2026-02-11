# استيراد جدول WH Data Rows من ملف Excel
# يُقرأ من شيت اسمه part_2 فقط.
# الأعمدة: WH | Emp No | Full Name | Busines (أو Business) | Business 2

import pandas as pd


def _normalize_col(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip()


def _find_column(df, *candidates):
    """يرجع اسم العمود الأول الموجود في الداتا فريم من قائمة الأسماء (بدون مراعاة حالة الأحرف)."""
    cols_lower = {c: c for c in df.columns if hasattr(c, "strip")}
    for cand in candidates:
        cand_clean = cand.strip().lower()
        for col in df.columns:
            if _normalize_col(col).lower() == cand_clean:
                return col
    return None


def import_wh_data_rows_from_excel(file, sheet_name="part_2"):
    """
    يقرأ من شيت part_2 فقط ويحفظ الصفوف في WHDataRow.
    الأعمدة في الشيت: WH | Emp No | Full Name | Busines (أو Business) | Business 2
    ترجع: (عدد_الصفوف_المحفوظة, قائمة_أخطاء)
    """
    from .models import WHDataRow, BusinessUnit

    created_count = 0
    errors = []

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, engine="openpyxl", header=0)
    except Exception as e:
        return 0, [f"تعذر قراءة الملف: {e}"]

    if df.empty:
        return 0, ["الملف أو الشيت فارغ."]

    # أعمدة الشيت part_2: WH | Emp No | Full Name | Busines (أو Business) | Business 2
    col_wh = _find_column(df, "WH", "wh")
    col_emp = _find_column(df, "Emp No", "Emp No.", "EmpNo", "emp_no")
    col_name = _find_column(df, "Full Name", "FullName", "full_name")
    col_biz = _find_column(df, "Busines", "Business", "business")
    col_biz2 = _find_column(df, "Business 2", "Business2", "business_2")

    if not col_wh:
        errors.append("لم يُعثر على عمود WH في شيت part_2.")
    if not col_emp:
        errors.append("لم يُعثر على عمود Emp No في شيت part_2.")
    if not col_name:
        errors.append("لم يُعثر على عمود Full Name في شيت part_2.")
    if not col_biz:
        errors.append("لم يُعثر على عمود Busines أو Business في شيت part_2.")

    if errors:
        return 0, errors

    # إزالة صفوف كل القيم فيها فارغة
    df = df.dropna(how="all")
    from django.db.models import Max
    max_order = 0
    try:
        agg = WHDataRow.objects.aggregate(m=Max("display_order"))
        max_order = agg.get("m") or 0
    except Exception:
        pass

    for idx, row in df.iterrows():
        wh = _normalize_col(row.get(col_wh, ""))
        emp_no = _normalize_col(row.get(col_emp, ""))
        full_name = _normalize_col(row.get(col_name, ""))
        biz_name = _normalize_col(row.get(col_biz, ""))
        biz2_name = _normalize_col(row.get(col_biz2, "")) if col_biz2 else ""

        if not wh and not emp_no and not full_name:
            continue

        if not biz_name:
            errors.append(f"صف {idx + 2}: Business مطلوب.")
            continue

        try:
            # استخدم first() بدل get_or_create لتجنب خطأ "returned more than one" لو الاسم مكرر
            business_unit = BusinessUnit.objects.filter(name=biz_name).first()
            if not business_unit:
                business_unit = BusinessUnit.objects.create(name=biz_name, display_order=0)
            business_2_unit = None
            if biz2_name:
                business_2_unit = BusinessUnit.objects.filter(name=biz2_name).first()
                if not business_2_unit:
                    business_2_unit = BusinessUnit.objects.create(name=biz2_name, display_order=0)
        except Exception as e:
            errors.append(f"صف {idx + 2}: {e}")
            continue

        try:
            max_order += 1
            WHDataRow.objects.create(
                wh=wh or "—",
                emp_no=emp_no or "—",
                full_name=full_name or "—",
                business=business_unit,
                business_2=business_2_unit,
                display_order=max_order,
            )
            created_count += 1
        except Exception as e:
            errors.append(f"صف {idx + 2}: {e}")

    return created_count, errors
