# items/admin.py
from django.contrib import admin
from .models import (
    CategoryLevel1, CategoryLevel2,
    Brand, UOM,
    Item, UPC
)
from .models import PriceBook, PriceRule, PriceTier, Availability

@admin.register(CategoryLevel1)
class CategoryLevel1Admin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(CategoryLevel2)
class CategoryLevel2Admin(admin.ModelAdmin):
    list_display = ("name", "parent")
    list_filter = ("parent",)
    search_fields = ("name",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(UOM)
class UOMAdmin(admin.ModelAdmin):
    list_display = ("unit_name",)
    search_fields = ("unit_name",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "sku", "product_name",
        "l1_category", "l2_category",
        "brand", "uom",
        "created_at", "created_by",
        "updated_at", "updated_by",
    )
    list_filter = ("l1_category", "l2_category", "brand", "uom")
    search_fields = ("product_name", "sku")

    # Make sku and timestamps and creator/updater read-only:
    readonly_fields = (
        "sku",
        "created_at", "created_by",
        "updated_at", "updated_by",
    )

    fieldsets = (
        (None, {
            "fields": (
                "l1_category", "l2_category",
                "product_name", "brand", "uom",
            )
        }),
        ("SKU & Audit Info", {
            "classes": ("collapse",),
            "fields": ("sku", "created_at", "created_by", "updated_at", "updated_by"),
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Stamp created_by on first save, updated_by on every save.
        """
        if not change:  # first time we’re saving this object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UPC)
class UPCAdmin(admin.ModelAdmin):
    list_display = ("code", "item")
    search_fields = ("code",)
    list_filter = ("item__l1_category", "item__l2_category")


@admin.register(PriceBook)
class PriceBookAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "created_by", "updated_at", "updated_by")
    list_filter = ("cities",)
    search_fields = ("name",)
    filter_horizontal = ("cities",)
    readonly_fields = ("created_at", "created_by", "updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PriceRule)
class PriceRuleAdmin(admin.ModelAdmin):
    list_display = ("price_book", "item", "base_price", "unit_type","available",
                    "created_at", "created_by", "updated_at", "updated_by")
    search_fields = ("item__sku", "item__product_name")
    readonly_fields = ("created_at", "created_by", "updated_at", "updated_by")
    list_editable = ("available",)  # ← allow toggle right in the list

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PriceTier)
class PriceTierAdmin(admin.ModelAdmin):
    list_display = ("price_rule", "min_quantity", "price")
    search_fields = ("price_rule__item__sku",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("price_rule", "price_rule__item")


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("item", "city", "is_available")
    list_filter = ("city", "is_available")
    search_fields = ("item__sku",)    