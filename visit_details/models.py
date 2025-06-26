#visit_details/models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from leads.models import Lead

from django.core.validators import FileExtensionValidator

from django.utils import timezone


def validate_file_size(value):
    max_mb = 10
    if value.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Each file must be ≤ {max_mb}MB")

class VisitDetail(models.Model):
    lead          = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="visits")
    visit_date    = models.DateField()
    start_time    = models.TimeField()
    end_time      = models.TimeField()
    inspection_report = models.FileField(
        upload_to="visit_reports/%Y/%m/%d/",
        validators=[
            validate_file_size,                            # your 10 MB size check
            FileExtensionValidator(allowed_extensions=["pdf"]),
        ],
    )

    # up to 10 site images
    images        = models.ManyToManyField(
        "VisitImage",
        blank=True,
        related_name="visit_details"
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    updated_at    = models.DateTimeField(auto_now=True)
    updated_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
  
    def clean(self):
        super().clean()

        # 1) Date not in future
        if self.visit_date and self.visit_date > timezone.localdate():
            raise ValidationError({"visit_date": "Visit date cannot be in the future."})

        # 2) Only compare times if both are set
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValidationError({"end_time": "End time must be after start time."})

    def __str__(self):
        return f"Visit {self.pk} for Lead #{self.lead_id} on {self.visit_date}"

class VisitImage(models.Model):
    image = models.ImageField(
        upload_to="visit_images/%Y/%m/%d/",
        validators=[
            validate_file_size,  # your existing 10 MB check
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png"]
            ),
        ],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image {self.pk}"