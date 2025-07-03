# items/templatetags/inr_filters.py
from django import template

register = template.Library()

@register.filter
def inr(value):
    """
    Format a number as Indian Rupees, e.g. ₹1,23,456.78 (Indian style grouping)
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value

    # Split integer and decimals
    int_part, dot, dec_part = f"{value:.2f}".partition(".")
    if len(int_part) > 3:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        # Group the rest in pairs from right to left
        pairs = []
        while len(rest) > 2:
            pairs.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            pairs.insert(0, rest)
        int_part = ",".join(pairs) + "," + last3
    return f"₹{int_part}.{dec_part}"

