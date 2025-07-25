# leads/models.py
from django.conf import settings
from django.db import models
from customers.models import Customer 
from interests.models import Interest   # new import
from profiles.models import Department
from simple_history.models import HistoricalRecords


SYSTEM_TYPE_CHOICES = [
    ("residential", "Residential"),
    ("commercial",  "Commercial"),
]

LEAD_QUALITY_CHOICES = [
    ("hot",    "Hot"),
    ("medium", "Medium"),
    ("cold",   "Cold"),
]

GRID_TYPE_CHOICES = [
    ("on",     "On-Grid"),
    ("off",    "Off-Grid"),
    ("hybrid", "Hybrid"),
]

class Lead(models.Model):
    customer     = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="leads")
    system_size = models.PositiveSmallIntegerField(
        help_text="Installed size in kilowatts (whole number only)",
        null=False,
        blank=False,
    )
    system_type = models.CharField(
        max_length=12,
        choices=SYSTEM_TYPE_CHOICES,
        default="residential",
        blank=False,
    )
    lead_quality = models.CharField(
        max_length=6,
        choices=LEAD_QUALITY_CHOICES,
        default="medium",
        blank=False,
    )
    remarks = models.TextField(
        blank=True,
        help_text="Any additional notes"
    )

    grid_type = models.CharField(
        max_length=6,
        choices=GRID_TYPE_CHOICES,
        blank=False,         
        help_text="If known, choose on-grid, off-grid or hybrid"
    )

    total_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total quoted amount in ₹ (whole rupees only)"
    )


    stage = models.ForeignKey(
        'LeadStage',
        on_delete=models.PROTECT,   # or CASCADE if you prefer
        null=False,                 # no NULLs allowed
        blank=False,                # already the default, but explicit
        related_name='leads',
        help_text="Current stage of this lead"
    )
    
    lead_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads_owned',
        help_text="Person responsible for this lead"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads_created",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="leads_updated",
        editable=False,
    )
    
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True,     editable=False)

    interest = models.OneToOneField(
        Interest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lead",
        help_text="If this lead was created from an Interest, store it here"
    )

 
    # ─── which Sales department should own this lead ──────────────
    from profiles.models import Department
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=False, blank=False,
        related_name="leads",
        help_text="Assign this lead to a Sales department"
    )

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        user = kwargs.pop("user", None)  # We'll pass this in from the view
        
        if not is_new:
            old = Lead.objects.get(pk=self.pk)
            monitored_fields = [
                "lead_manager", "stage", "department", "total_amount",
                "lead_quality", "remarks"
            ]
            for field in monitored_fields:
                old_val = getattr(old, field)
                new_val = getattr(self, field)
                if old_val != new_val:
                    from leads.models import LeadChangeLog
                    LeadChangeLog.objects.create(
                        lead=self,
                        changed_by=user,
                        field_name=field,
                        old_value=str(old_val),
                        new_value=str(new_val)
                    )

        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.system_size} kW — {self.get_system_type_display()}"

class LeadStage(models.Model):
    name    = models.CharField(max_length=100, unique=True)
    order   = models.PositiveSmallIntegerField(default=0, help_text="Lower numbers come first")
    class Meta:
        ordering = ['order','name']
    def __str__(self):
        return self.name

class DepartmentAssignmentPointer(models.Model):
    department      = models.OneToOneField(
        "profiles.Department",
        on_delete=models.PROTECT,
        related_name="assignment_pointer",
        null=True,    # allow old rows to stay null
        blank=True
    )
    last_assigned   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    def __str__(self):
        return f"{self.department.name} → {self.last_assigned}"

class LeadAssignmentLog(models.Model):
    lead           = models.ForeignKey("Lead",        on_delete=models.CASCADE, related_name="assignment_logs")
    assigned_to    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    department     = models.ForeignKey("profiles.Department",   on_delete=models.SET_NULL, null=True)
    timestamp      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Lead Assignment Log"
        verbose_name_plural = "Lead Assignment Logs"

    def __str__(self):
        user = self.assigned_to.get_full_name() if self.assigned_to else "—"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] Lead #{self.lead_id} → {user}"
    

# leads/models.py

class LeadChangeLog(models.Model):
    lead         = models.ForeignKey("Lead", on_delete=models.CASCADE, related_name="change_logs")
    changed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    field_name   = models.CharField(max_length=100)
    old_value    = models.TextField(null=True, blank=True)
    new_value    = models.TextField(null=True, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Lead Change Log"
        verbose_name_plural = "Lead Change Logs"

    def __str__(self):
        return f"{self.field_name} changed on Lead #{self.lead_id} at {self.timestamp:%Y-%m-%d %H:%M}"
    