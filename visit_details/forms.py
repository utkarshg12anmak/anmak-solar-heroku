# visit_details/forms.py
from django import forms
from django.utils import timezone
from django.forms.widgets import ClearableFileInput
from .models import VisitDetail

from django.core.validators import FileExtensionValidator

class VisitDetailForm(forms.ModelForm):
    class Meta:
        model = VisitDetail
        fields = ["visit_date", "start_time", "end_time", "inspection_report"]
        widgets = {
            "visit_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
             # only allow .pdf in the file‐picker dialog:
            "inspection_report": forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
        }


    def clean_inspection_report(self):
        f = self.cleaned_data.get("inspection_report")
        # FileExtensionValidator already ran, and validate_file_size too,
        # so here you could add any extra logic if you like.
        return f

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end   = cleaned.get("end_time")

        # Only if both fields were filled in
        if start and end and end <= start:
            self.add_error("end_time", "End time must be after start time.")
        return cleaned    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # now that timezone is imported, this will work:
        today = timezone.localdate().isoformat()
        self.fields["visit_date"].widget.attrs["max"] = today

class MultiFileInput(ClearableFileInput):
    allow_multiple_selected = True

class VisitImageForm(forms.Form):
    images = forms.FileField(
      widget=MultiFileInput(attrs={
        "multiple": True,
        "accept": "image/png, image/jpeg"     # only show images in the file-picker
      }),
      required=False,
      label="Site Images (up to 10)",
      help_text="JPEG, PNG; max 10 files, 10 MB each.",
    )