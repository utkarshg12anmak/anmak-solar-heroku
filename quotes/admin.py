# quotes/admin.py
from django.contrib import admin
from decimal import Decimal
from .models import Quote, QuoteItem

class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    fields = ("price_rule", "quantity", "calculated_price",)
    readonly_fields = ("calculated_price",)
    extra = 0

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display    = ("id", "lead", "status", "minimum_price", "selling_price", "created_at")
    readonly_fields = ("minimum_price", "created_by", "updated_by", "created_at", "updated_at")
    inlines         = [QuoteItemInline]

    def save_model(self, request, obj, form, change):
        # stamp audit fields
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # 1) save the inlines first
        super().save_related(request, form, formsets, change)

        # 2) re-compute minimum_price
        obj = form.instance
        total = Decimal("0")
        for item in obj.items.all():
            # each item's `calculated_price` was auto-set in its save()
            total += item.calculated_price or Decimal("0")

        # 3) persist it
        Quote.objects.filter(pk=obj.pk).update(minimum_price=total)