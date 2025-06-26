# items/services.py

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from customers.models import City
from .models import PriceBook, PriceRule, PriceTier, Availability, Item

class NoPriceBookForCity(Exception):
    """Raised when no active PriceBook covers this city."""
    pass

class NoPriceRuleForItem(Exception):
    """Raised when no PriceRule exists for this item in the chosen PriceBook."""
    pass

class ItemUnavailable(Exception):
    """Raised when the item is marked unavailable in that city (if using Availability)."""
    pass


def get_unit_price(item: Item, city: City, quantity: int) -> float:
    """
    Returns the correct unit price (decimal) for an item in a given city and quantity.
    1) Look up all PriceBooks that include this city.
    2) Among them, find the PriceRule whose item matches.
       (If multiple PriceBooks apply, pick the one with highest priority—here we assume the first in id order, or you can add a `priority` field.)
    3) Once you have a PriceRule, check its set of tiers:
       - If any tier’s (min_quantity <= quantity <= max_quantity), return that tier’s tier_price.
       - Otherwise, return the rule’s base_price.
    4) If you want to respect “availability,” check the Availability model first.
    """
    # 0) Optionally check explicit Availability:
    try:
        avail = Availability.objects.get(item=item, city=city)
        if not avail.is_available:
            raise ItemUnavailable(f"Item {item.sku} is not available in {city.name}.")
    except Availability.DoesNotExist:
        # If you do not require explicit availability, just pass.
        pass

    # 1) Fetch all PriceBooks that include this city
    pricebooks = PriceBook.objects.filter(cities=city).order_by("name")
    if not pricebooks.exists():
        raise NoPriceBookForCity(f"No PriceBook defined for city '{city.name}'.")

    # 2) Look for a PriceRule for this item in any of those pricebooks, in preferred order
    rule = (
        PriceRule.objects
            .filter(price_book__in=pricebooks, item=item)
            .select_related("price_book")
            .prefetch_related("tiers")
            .first()
    )
    if not rule:
        raise NoPriceRuleForItem(f"No PriceRule for item '{item.sku}' in city '{city.name}'.")

    # 3) Determine which tier (if any) matches the requested quantity
    matching_tier = (
        rule.tiers
            .filter(min_quantity__lte=quantity)
            .order_by("-min_quantity")  # pick the highest‐threshold tier that is ≤ quantity
            .first()
    )
    if matching_tier:
        return float(matching_tier.price)

    # 4) Otherwise, fallback to base_price
    return float(rule.base_price)