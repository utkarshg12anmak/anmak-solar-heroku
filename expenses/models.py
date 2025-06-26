import os
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class ExpenseRole(models.Model):
    class Role(models.TextChoices):
        SELF_SERVICE   = "self",   "Self-Service"
        GLOBAL_VIEWER  = "viewer", "Global Viewer"
        GLOBAL_EDITOR  = "editor", "Global Editor"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_role"
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.SELF_SERVICE,
        help_text="What scope this user has for expenses"
    )

    def __str__(self):
        return f"{self.user.username} → {self.get_role_display()}"

def attachment_upload_to(instance, filename):
    # organize uploads by expense ID
    return f'expenses/{instance.id}/{filename}'

def validate_attachment(file):
    # 10 MB limit
    max_size = 10 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(_("File must be ≤ 10 MB."))

    # allowed extensions
    valid_exts = ['.pdf', '.jpg', '.jpeg', '.png']
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_exts:
        raise ValidationError(_("Unsupported file type. Allowed: PDF, JPG, PNG."))

class ExpenseCategory(models.Model):
    name        = models.CharField(max_length=100)
    parent      = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
        help_text=_("Leave blank for a top-level (L1) category.")
    )

    class Meta:
        verbose_name = _("Expense Category")
        verbose_name_plural = _("Expense Categories")
        ordering = ['parent__id', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name


class Expense(models.Model):
    class Type(models.TextChoices):
        ONE_TIME     = 'one_time',     _("One-Time")
        SUBSCRIPTION = 'subscription', _("Subscription")

    expense_type    = models.CharField(
        max_length=12,
        choices=Type.choices,
        default=Type.ONE_TIME,
    )
    parent_category = models.ForeignKey(
        ExpenseCategory,
        related_name='expenses_as_l1',
        on_delete=models.PROTECT,
        limit_choices_to={'parent__isnull': True},
        help_text=_("Select an L1 (parent) category.")
    )
    child_category  = models.ForeignKey(
        ExpenseCategory,
        related_name='expenses_as_l2',
        on_delete=models.PROTECT,
        limit_choices_to={'parent__isnull': False},
        help_text=_("Select an L2 (child) category.")
    )
    amount          = models.DecimalField(max_digits=10, decimal_places=2, help_text=_("In ₹"))
    expense_date    = models.DateField(
        null=True,
        blank=True,
        help_text=_("Required if One-Time"),
    )
    start_date      = models.DateField(
        null=True,
        blank=True,
        help_text=_("Subscription start")
    )
    end_date        = models.DateField(
        null=True,
        blank=True,
        help_text=_("Subscription end")
    )
    remarks         = models.TextField(help_text=_("Enter any notes or comments"))

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses_created",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses_updated",
        editable=False,
    )

    attachment = models.FileField(
        upload_to="expenses/%Y/%m/%d/",
        null=True,
        blank=True,
        help_text="Upload a PDF/PNG/JPG (max 10 MB)."
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.expense_type == self.Type.ONE_TIME:
            if not self.expense_date:
                raise ValidationError({"expense_date": _("This field is required for one-time expenses.")})
        else:
            # subscription
            if not self.start_date or not self.end_date:
                raise ValidationError({
                    "start_date": _("Start and end dates are required for subscriptions."),
                    "end_date": _("Start and end dates are required for subscriptions.")
                })

    def __str__(self):
        return f"{self.get_expense_type_display()} – ₹{self.amount} on {self.expense_date or self.start_date}"