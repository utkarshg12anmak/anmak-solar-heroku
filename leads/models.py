# leads/models.py
from django.conf import settings
from django.db import models
from customers.models import Customer 
from interests.models import Interest   # new import
from profiles.models import Department

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

    def save(self, *args, **kwargs):
        # if it’s a brand-new instance and no stage was set,
        # pick the one with order=1
        if not self.pk and not self.stage_id:
            default_stage = LeadStage.objects.filter(order=1).first()
            if default_stage:
                self.stage = default_stage
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