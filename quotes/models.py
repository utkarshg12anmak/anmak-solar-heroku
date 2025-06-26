# quotes/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from leads.models import Lead

class Quote(models.Model):
    STATUS_PENDING = 'approval_pending'
    STATUS_APPROVED = 'approved'
    STATUS_DECLINED = 'declined'
    STATUS_DELETED  = 'deleted'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Approval Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_DELETED,  'Deleted'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='quotes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotes_approved'
    )
    
    approved_at = models.DateTimeField(null=True, blank=True)   # ← NEW

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='quotes_created',
        editable=False
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='quotes_updated',
        editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    minimum_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Calculated minimum price based on rules"
    )

    def __str__(self):
        return f"Quote #{self.pk} for Lead {self.lead_id} ({self.get_status_display()})"

class QuoteItem(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    price_rule = models.ForeignKey('items.PriceRule', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        # 1) find the best‐applicable tier
        qty = self.quantity or Decimal("0")
        tiers = (
            self.price_rule.tiers
                .filter(min_quantity__lte=qty)
                .order_by("-min_quantity")
        )
        if tiers.exists():
            unit_price = tiers.first().price
        else:
            unit_price = self.price_rule.base_price

        # 2) compute line total
        self.calculated_price = unit_price * qty
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.price_rule.item.product_name} × {self.quantity}"