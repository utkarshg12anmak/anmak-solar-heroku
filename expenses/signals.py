# expenses/signals.py

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ExpenseRole

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_expense_role(sender, instance, created, **kwargs):
    if created:
        ExpenseRole.objects.create(user=instance)