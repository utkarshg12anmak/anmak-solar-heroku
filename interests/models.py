from django.db import models
from django.conf import settings
from customers.models import Customer
from django.core.validators import RegexValidator



phone_validator = RegexValidator(
    r'^\d{10}$', 
    'Enter a valid 10-digit phone number.'
)

class InterestStatus(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class ModeOfContact(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class InterestSource(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class AuthorizedInterestUser(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authorized_interest_users'
    )
    # — new field —
    ROLE_CHOICES = [
        ('supervisor', 'Supervisor'),
        ('member',    'Member'),
    ]
    role_type = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='member',
        help_text="Supervisor can manage, Member can log interests"
    )

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_type_display()})"

class Interest(models.Model):
    phone_number = models.CharField(
        max_length=10,
        validators=[phone_validator],
        help_text="Enter a 10-digit number"
    )
    attempted_times = models.PositiveIntegerField(default=0)
    remarks         = models.TextField(blank=True)
    is_connected    = models.BooleanField(default=False)
    status          = models.ForeignKey(InterestStatus,   on_delete=models.PROTECT, null=True, blank=True)
    source          = models.ForeignKey(InterestSource,   on_delete=models.PROTECT)
    mode            = models.ForeignKey(ModeOfContact,     on_delete=models.PROTECT)
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="interests_created", on_delete=models.SET_NULL, null=True, blank=True)
    updated_by      = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="interests_updated", on_delete=models.SET_NULL, null=True, blank=True)
    dials = models.IntegerField(default=0, help_text="How many times this lead was dialed")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    customer = models.ForeignKey(
      Customer,
      on_delete=models.PROTECT,
      null=True, blank=True,
      related_name="interests",
      help_text="Once set, this interest is locked to that customer."
    )

    @property
    def has_lead(self):
        # This will return True if there’s a Lead pointing at this Interest,
        # otherwise False, without ever throwing a DoesNotExist
        return hasattr(self, 'lead')

    def save(self, *args, **kwargs):
        if not self.pk:
            prev = Interest.objects.filter(phone_number=self.phone_number).count()
            self.attempted_times = prev + 1
        super().save(*args, **kwargs)	

    def __str__(self):
        return f"{self.phone_number} ({self.attempted_times} attempts)"





