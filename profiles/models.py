#profiles/models.py
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError



def validate_file_size(value):
    limit = 100 * 1024 * 1024  # 100 MB
    if value.size > limit:
        raise ValidationError('PDF file too large. Size must be ≤ 100 MB.')


class DepartmentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name


class UserProfile(models.Model):
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    is_on_duty = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} Profile"

class DepartmentType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class DepartmentRegion(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class OnDutyChangeLog(models.Model):
    who_changed    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_changes_made"
    )
    target_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="duty_change_logs"
    )
    old_value      = models.BooleanField()
    new_value      = models.BooleanField()
    timestamp      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        who = self.who_changed.get_full_name() or self.who_changed.username
        whom = (self.target_profile.user.get_full_name()
                or self.target_profile.user.username)
        status = "ON" if self.new_value else "OFF"
        return f"{who} set {whom} {status}-duty at {self.timestamp:%Y-%m-%d %H:%M}"

class Department(models.Model):
    name      = models.CharField(max_length=200)
    parent    = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.PROTECT,
        help_text="Leave blank for a top-level (level 1) department"
    )
    dept_type = models.ForeignKey(DepartmentType, on_delete=models.PROTECT)
    region    = models.ForeignKey(DepartmentRegion, on_delete=models.PROTECT)
    category  = models.ForeignKey(
        DepartmentCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Optional category for this department"
    )

    draft_quotation = models.FileField(
        upload_to='departments/draft_quotations/',
        validators=[
            FileExtensionValidator(allowed_extensions=['docx']),
            validate_file_size
        ],        
        blank=True,
        null=True,
        help_text='Upload a DOCX (Microsoft Word) document up to 100 MB.'
    )

    class Meta:
        unique_together = ('parent', 'name')

    def clean(self):
        # enforce max depth = 3
        depth = 1
        p = self.parent
        while p:
            depth += 1
            if depth > 3:
                raise ValidationError("Departments may only be nested up to 3 levels.")
            p = p.parent

    def __str__(self):
        return ("— " * (self.get_level() - 1) or "") + self.name    

    def get_level(self):
        lvl = 1
        p = self.parent
        while p:
            lvl += 1
            p = p.parent
        return lvl


class DepartmentMembership(models.Model):
    LEVEL_CHOICES = [
      (1, "Level 1"),
      (2, "Level 2"),
      (3, "Level 3"),
    ]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    level      = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)

    class Meta:
        unique_together = ('user','department','level')

    def __str__(self):
        return f"{self.user.get_full_name()} → {self.department.name} (Level {self.level})"

class ApprovalLimit(models.Model):
    LEVEL_CHOICES = [
        (3, "L3 (Rep)"),
        (2, "L2 (Manager)"),
        (1, "L1 (Director)"),
    ]

    department = models.ForeignKey(
        "profiles.Department",
        on_delete=models.CASCADE,
        related_name="approval_limits",    # ← give it a distinct name
        related_query_name="approval_limit",
        help_text="The department this limit applies to",
    )

    level = models.PositiveSmallIntegerField(
        choices=LEVEL_CHOICES,
        help_text="Which approval level this limit is for",
    )

    max_amount = models.PositiveIntegerField(
        help_text="Maximum quote total (₹) auto‐approved at this level",
    )

    class Meta:
        unique_together = [("department", "level")]
        ordering = ["department__name", "-level"]
        verbose_name = "Approval Limit"
        verbose_name_plural = "Approval Limits"

    def __str__(self):
        return f"{self.department.name} – L{self.level} up to ₹{self.max_amount}"