# reminders/models.py

import uuid
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

# If you want to attach a reminder to any Django model (Lead, Customer, etc.), use ContentType:
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

User = settings.AUTH_USER_MODEL  # typically 'auth.User' or your custom user model

class ReminderSettings(models.Model):
    """
    A single‐row table where an admin can set:
      default_ping_before_minutes = (e.g. 10)
    Any new Reminder that has no override will use this value.
    Enforces exactly one row in this table.
    """
    default_ping_before_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Number of minutes before the actual reminder_time to send the ping."
    )

    class Meta:
        verbose_name = "Reminder Settings"
        verbose_name_plural = "Reminder Settings"

    def clean(self):
        # Disallow creating more than one settings row
        if not self.pk and ReminderSettings.objects.exists():
            raise ValidationError("Only one ReminderSettings instance is allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Default ping-before: {self.default_ping_before_minutes} min"


class Reminder(models.Model):
    """
    A “Reminder” can be attached to any other model via a GenericForeignKey.
    - content_type / object_id = the “thing” we’re reminding about (Lead, Customer, etc.)
    - owner = which User should receive the ping/completion notification
    - reminder_time = when the reminder should fire
    - ping_before_override = if not null, use this many minutes instead of the global default
    - status = DUE, PINGED, COMPLETED, CANCELLED, OVERDUE
    - message = a short text describing what to do
    - created_at / updated_at / completed_at = timestamps
    """
    STATUS_CHOICES = [
        ('DUE',       'Due'),
        ('PINGED',    'Pinged'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('OVERDUE',   'Overdue'),
    ]

    PRIORITY_CHOICES = [
        ('LOW',  'Low'),
        ('MED',  'Medium'),
        ('HIGH', 'High'),
    ]

    # ——— 1) Generic foreign key to any “reference” model ———
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The type of object this reminder refers to (e.g. Lead, Customer, etc.)"
    )
    object_id = models.PositiveIntegerField(help_text="The primary key of that object")
    content_object = GenericForeignKey('content_type', 'object_id')

    # ——— 2) Who to notify ———
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reminders',
        help_text="Which user should receive the ping / mark this as completed."
    )

    # ——— 3) When the reminder should go off ———
    reminder_time = models.DateTimeField(
        help_text="Exact UTC datetime when this reminder is due."
    )

    # ——— 4) Optional “minutes before” override ———
    ping_before_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "If set, notify this many minutes before reminder_time. "
            "Otherwise, use the global default in ReminderSettings."
        )
    )

    # ——— 5) Status of the reminder ———
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='DUE',
        help_text="Current state of this reminder."
    )

    # ——— 6) Short message/descriptive text ———
    message = models.CharField(
        max_length=255,
        help_text="Brief description of why we’re reminding."
    )

    # ——— 7) Optional priority ———
    priority = models.CharField(
        max_length=4,
        choices=PRIORITY_CHOICES,
        default='MED',
        help_text="(Optional) Low / Medium / High priority."
    )

    # ——— 8) Timestamps ———
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-reminder_time']
        verbose_name = "Reminder"
        verbose_name_plural = "Reminders"

    def __str__(self):
        return (
            f"[{self.get_status_display()}] {self.message} → "
            f"{self.reminder_time.strftime('%Y-%m-%d %H:%M')} ({self.get_priority_display()})"
        )

    def clean(self):
        """
        Ensure reminder_time is not in the past when creating a new one.
        """
        if self.pk is None:  # only check on create
            now = timezone.now()
            if self.reminder_time < now:
                raise ValidationError("reminder_time cannot be in the past.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def effective_ping_minutes(self):
        """
        Return the number of minutes before `reminder_time` when
        we should send the ping. If ping_before_override is set,
        use that; otherwise, pull from the single ReminderSettings row.
        """
        if self.ping_before_override is not None:
            return self.ping_before_override

        try:
            settings = ReminderSettings.objects.first()
            return settings.default_ping_before_minutes
        except ReminderSettings.DoesNotExist:
            return 10  # fallback default if no settings row exists

    @property
    def ping_moment(self):
        """
        Compute reminder_time minus effective_ping_minutes.
        """
        return self.reminder_time - timedelta(minutes=self.effective_ping_minutes)

    def mark_completed(self):
        """Helper: mark this reminder as completed now."""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()

    def mark_cancelled(self):
        """Helper: mark this reminder as cancelled."""
        self.status = 'CANCELLED'
        self.save()

    def mark_overdue(self):
        """Helper: flip this reminder to OVERDUE."""
        self.status = 'OVERDUE'
        self.save()