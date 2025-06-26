from django.db import models
from django.core.validators import RegexValidator

from django.db import models
from django.conf import settings

from django.contrib.auth import get_user_model


# new table for dynamic designations
class Designation(models.Model):
    title = models.CharField(max_length=100)
    def __str__(self): return self.title

phone_validator = RegexValidator(r'^\d{10}$',
    'Phone number must be exactly 10 digits.')

class City(models.Model):
    name = models.CharField(max_length=100, unique=True)

    # newly added:
    view_only_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="cities_view_only",
        help_text="Users who can view (but not edit) customers in this city."
    )
    view_edit_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="cities_view_edit",
        help_text="Users who can both view and edit customers in this city."
    )

    def __str__(self): return self.name

class CustomerSource(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

    # A simple regex that forces “#” followed by exactly 6 hex digits
    color = models.CharField(
        max_length=7,
        validators=[RegexValidator(
           r'^#([0-9A-Fa-f]{6})$',
           "Enter a valid hex color (e.g. '#A1B2C3')."
        )],
        default="#CCCCCC",
        help_text="Hex color code for this source (e.g. #A1B2C3)."
    )

class Customer(models.Model):
    first_name      = models.CharField(max_length=100, blank=True, null=True)
    last_name       = models.CharField(max_length=100, blank=True, null=True)
    primary_phone   = models.CharField(max_length=10, validators=[phone_validator], unique=True)
    secondary_phone = models.CharField(max_length=10, validators=[phone_validator], blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="customers_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="customers_updated",
    )  
    designation = models.ForeignKey(
        Designation,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    address         = models.TextField(blank=True)
    city            = models.ForeignKey(City, on_delete=models.PROTECT, related_name="customers")
    source          = models.ForeignKey(CustomerSource, on_delete=models.PROTECT, related_name="customers")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} — {self.primary_phone}"