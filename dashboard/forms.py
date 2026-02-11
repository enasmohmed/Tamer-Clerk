from django import forms

from dashboard.models import MeetingPoint


# class UploadExcelForm(forms.Form):
#     excel_file = forms.FileField(label="Excel File", required=True)


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Select Excel file (e.g. all sheet.xlsm)",
        required=True,
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx,.xlsm",
        })
    )




class WHDataRowExcelUploadForm(forms.Form):
    """رفع Excel لاستيراد صفوف جدول WH Data Rows (WH | Emp No | Full Name | Business | Business 2)."""
    excel_file = forms.FileField(
        label="ملف Excel",
        required=True,
        widget=forms.ClearableFileInput(attrs={
            "accept": ".xlsx,.xlsm,.xls",
        }),
    )
    sheet_name = forms.CharField(
        label="اسم الشيت",
        initial="part_2",
        required=False,
        max_length=100,
        help_text="اسم الشيت في الملف (الافتراضي: part_2).",
    )
    clear_before_import = forms.BooleanField(
        label="احذف البيانات الحالية قبل الاستيراد",
        required=False,
        initial=False,
        help_text="فعّل هذا إن أردت حذف كل الصفوف الحالية ثم استيراد البيانات من الملف من جديد.",
    )


class MeetingPointForm(forms.ModelForm):
    class Meta:
        model = MeetingPoint
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'اكتب النقطة أو الإجراء هنا...',
            }),
        }
