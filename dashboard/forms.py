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




class ClerkInterviewTrackingExcelUploadForm(forms.Form):
    """Excel upload for Clerk Interview Tracking (15 columns)."""
    excel_file = forms.FileField(
        label="Excel file",
        required=True,
        widget=forms.ClearableFileInput(attrs={
            "accept": ".xlsx,.xlsm,.xls",
        }),
    )
    sheet_name = forms.CharField(
        label="Sheet name",
        initial="Sheet1",
        required=False,
        max_length=100,
        help_text="Sheet name in the file (default: Sheet1).",
    )
    clear_before_import = forms.BooleanField(
        label="Clear existing data before import",
        required=False,
        initial=False,
        help_text="Enable to delete all current rows before importing.",
    )


class WeeklyProjectTrackerExcelUploadForm(forms.Form):
    """Excel upload form for Weekly Project Tracker (Week | Task | Status | Progress % | Impact)."""
    excel_file = forms.FileField(
        label="Excel file",
        required=True,
        widget=forms.ClearableFileInput(attrs={
            "accept": ".xlsx,.xlsm,.xls",
        }),
    )
    sheet_name = forms.CharField(
        label="Sheet name",
        initial="Weekly Tracker",
        required=False,
        max_length=100,
        help_text="Sheet name in the file (default: Weekly Tracker).",
    )
    clear_before_import = forms.BooleanField(
        label="Clear existing data before import",
        required=False,
        initial=False,
        help_text="Enable to delete all current rows before importing from the file.",
    )


class PotentialChallengesExcelUploadForm(forms.Form):
    """Excel upload for Potential Challenges (e.g. Potential_Challenges.xlsx, sheet Potential_Challenges)."""
    excel_file = forms.FileField(
        label="Excel file",
        required=True,
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,.xlsm,.xls"}),
        help_text="e.g. Potential_Challenges.xlsx",
    )
    sheet_name = forms.CharField(
        label="Sheet name",
        initial="Potential_Challenges",
        required=False,
        max_length=100,
        help_text="Sheet name in the file (default: Potential_Challenges).",
    )
    clear_before_import = forms.BooleanField(
        label="Clear existing data before import",
        required=False,
        initial=False,
    )


class MeetingPointForm(forms.ModelForm):
    class Meta:
        model = MeetingPoint
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Enter the meeting point or action here...',
            }),
        }
