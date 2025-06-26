# items/models.py
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class CategoryLevel1(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "L1 Category"
        verbose_name_plural = "L1 Categories"

    def __str__(self):
        return self.name


class CategoryLevel2(models.Model):
    parent = models.ForeignKey(
        CategoryLevel1,
        on_delete=models.PROTECT,
        related_name="level2_categories",
        help_text="Choose the L1 category this L2 belongs under",
    )
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = [("parent", "name")]
        ordering = ["parent__name", "name"]
        verbose_name = "L2 Category"
        verbose_name_plural = "L2 Categories"

    def __str__(self):
        return f"{self.parent.name} → {self.name}"


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Brand/Make"
        verbose_name_plural = "Brands/Makes"

    def __str__(self):
        return self.name


class UOM(models.Model):
    unit_name = models.CharField(
        max_length=50,
        unique=True,
        help_text="E.g. “Each”, “Box”, “Kilogram”"
    )

    class Meta:
        ordering = ["unit_name"]
        verbose_name = "Unit of Measure"
        verbose_name_plural = "Units of Measure"

    def __str__(self):
        return self.unit_name

class Item(models.Model):
    l1_category = models.ForeignKey(
        CategoryLevel1,
        on_delete=models.PROTECT,
        related_name="items",
        help_text="Select the L1 Category",
    )
    l2_category = models.ForeignKey(
        CategoryLevel2,
        on_delete=models.PROTECT,
        related_name="items",
        help_text="Select the L2 Category (must belong under chosen L1)",
    )

    product_name = models.CharField(
        max_length=200,
        help_text="Full product name/description"
    )

    sku = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        editable=False,
        help_text="Auto-generated 10-char alphanumeric SKU"
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="items",
        help_text="Select the Brand/Make",
    )

    uom = models.ForeignKey(
        UOM,
        on_delete=models.PROTECT,
        related_name="items",
        help_text="Select the unit of measure",
    )

    # ← ADD THESE TWO FIELDS:
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="items_created",
        help_text="User who first created this Item",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="items_updated",
        help_text="User who last modified this Item",
    )

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = [
            "l1_category__name",
            "l2_category__name",
            "product_name"
        ]
        verbose_name = "Item"
        verbose_name_plural = "Items"

    def __str__(self):
        return f"{self.product_name} [{self.sku}]"

    def save(self, *args, **kwargs):
        """
        Auto-generate a 10-character alphanumeric SKU if it’s blank.

        Format: [2 chars L1][2 digits L2_id][2 digits Brand_id][2 chars from product_name][2-digit counter]
        """
        if not self.sku:
            # --- 1) Build L1 part (2 letters) ---
            # Remove spaces, uppercase, take the first 2 letters (pad with 'X' if too short)
            raw_l1 = (self.l1_category.name or "").replace(" ", "").upper()
            l1_part = (raw_l1[:2]).ljust(2, "X")  # e.g. "SO"

            # --- 2) Build L2_id part (2 digits, zero-padded) ---
            l2_id = self.l2_category.id
            l2_part = str(l2_id).zfill(2)  # e.g. "05"

            # --- 3) Build Brand_id part (2 digits, zero-padded) ---
            brand_id = self.brand.id
            brand_part = str(brand_id).zfill(2)  # e.g. "03"

            # --- 4) Build Product initials part (2 letters) ---
            # Take first two words of the product_name, extract their first letters
            initials = []
            for word in self.product_name.split()[:2]:
                if word:
                    initials.append(word[0].upper())
            # If fewer than 2 initials found, pad with 'X'
            while len(initials) < 2:
                initials.append("X")
            product_part = "".join(initials[:2])  # e.g. "DS" for "DCR Solar"

            # --- 5) Combine into an 8-character prefix ---
            prefix = f"{l1_part}{l2_part}{brand_part}{product_part}"
            # e.g. "SO0503DS"

            # --- 6) Find a 2-digit counter that makes this unique (01..99) ---
            counter = 1
            candidate = f"{prefix}{str(counter).zfill(2)}"  # e.g. "SO0503DS01"
            # Keep bumping until no collision
            from django.db.models import Q
            while Item.objects.filter(sku=candidate).exists():
                counter += 1
                if counter > 99:
                    raise ValidationError(
                        "Cannot generate unique SKU: too many items with the same prefix."
                    )
                candidate = f"{prefix}{str(counter).zfill(2)}"

            self.sku = candidate

        super().save(*args, **kwargs)


class UPC(models.Model):
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Enter a UPC (barcode). Must be unique across Items."
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="upcs"
    )

    class Meta:
        ordering = ["code"]
        verbose_name = "UPC"
        verbose_name_plural = "UPCs"

    def __str__(self):
        return self.code


# We assume there is a City model in the customers app:
# from customers.models import City

UNIT_TYPE_CHOICES = [
    ("per_uom", "Per UOM"),
    ("per_kw",  "Per kW"),
]

class PriceBook(models.Model):
    # … fields for PriceBook (e.g. name, related cities, created_by, etc.) …
    # Use a ManyToManyField to City (imported from customers.models) if you
    # want a PriceBook to apply to multiple cities. 
    # …
    name = models.CharField(max_length=100)

    # Which cities this PriceBook applies to:
    cities = models.ManyToManyField(
        "customers.City",
        related_name="pricebooks",
        help_text="Cities where this PriceBook is active."
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pricebooks_created",
        editable=False
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pricebooks_updated",
        editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return self.name

class PriceRule(models.Model):
    price_book    = models.ForeignKey(
        PriceBook,
        on_delete=models.CASCADE,
        related_name="price_rules"
    )
    item          = models.ForeignKey(
        "Item",    # assuming you have an Item model elsewhere in items/models.py
        on_delete=models.CASCADE,
        related_name="price_rules"
    )
    base_price    = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Base price per unit (or per kW, depending on unit_type)."
    )
    UNIT_TYPE_CHOICES = [
        ("per_uom", "Per UOM"),
        ("per_kw",  "Per kW"),
    ]
    unit_type     = models.CharField(
        max_length=10,
        choices=UNIT_TYPE_CHOICES,
        default="per_uom",
        help_text="Whether this rule is per UOM or per kW."
    )
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pricerules_created",
        editable=False
    )
    updated_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pricerules_updated",
        editable=False
    )
    available = models.BooleanField(
        default=True,
        help_text="Is this item currently available for quoting?"
    )
    created_at    = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at    = models.DateTimeField(auto_now=True, editable=False)

    def clean(self):
        super().clean()

        # If this PriceRule instance hasn’t been saved yet, don’t try to inspect self.tiers
        if self.pk is None:
            return

        # Now safe to check the related Tier objects (assuming related_name="tiers" on PriceTier)
        tiers_qs = self.tiers.order_by("min_quantity")

        last_min_q = None
        for tier in tiers_qs:
            # Example: ensure no overlapping min_quantity
            if last_min_q is not None and tier.min_quantity <= last_min_q:
                raise ValidationError("Each tier's min_quantity must be strictly greater than the previous tier.")
            last_min_q = tier.min_quantity

            # Ensure no negative values
            if tier.min_quantity < 0:
                raise ValidationError("Tier min_quantity cannot be negative.")
            if tier.price < 0:
                raise ValidationError("Tier price cannot be negative.")

    def __str__(self):
        return f"{self.item} @ {self.base_price} ({self.get_unit_type_display()})"


class PriceTier(models.Model):
    price_rule    = models.ForeignKey(
        PriceRule,
        on_delete=models.CASCADE,
        related_name="tiers"
    )
    min_quantity  = models.PositiveIntegerField(
        help_text="Minimum quantity for this tier."
    )
    price         = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price applicable once quantity ≥ min_quantity."
    )

    class Meta:
        ordering = ["min_quantity"]

    def __str__(self):
        return f"Tier ≥ {self.min_quantity}: {self.price}"


class Availability(models.Model):
    """
    Optional: If you want to explicitly mark when an Item is *available* 
    in a particular city (beyond just having a PriceBook), you could use this model.
    For example, perhaps an item is NOT sold in some city even though a PriceBook exists.
    """
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.CASCADE,
        related_name="availabilities",
        help_text="Which item is available/unavailable here."
    )
    city = models.ForeignKey(
        "customers.City",
        on_delete=models.CASCADE,
        related_name="item_availabilities"
    )
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ("item", "city")
        verbose_name = "Item Availability"
        verbose_name_plural = "Item Availabilities"

    def __str__(self):
        return f"{self.item.sku} @ {self.city.name} → {'Available' if self.is_available else 'Unavailable'}"