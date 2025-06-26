# leads/templatetags/lead_extras.py

import hashlib
from django import template

register = template.Library()

@register.filter
def initials(full_name):
    """
    Given a full name (e.g. "Vivek Nain" or "John Paul Smith"),
    return up to the first two initials uppercase (e.g. "VN" or "JP").
    """
    if not full_name:
        return ""
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[1][0]).upper()

# A small palette of colors for avatars:
AVATAR_COLORS = ["#3182ce", "#059669", "#d69e2e", "#e53e3e", "#805ad5"]

@register.filter
def avatar_color(full_name):
    """
    Pick one hex color from AVATAR_COLORS based on a hash of the full name.
    """
    if not full_name:
        return AVATAR_COLORS[0]
    # Create a stable hash from the user’s name
    digest = hashlib.md5(full_name.encode("utf-8")).hexdigest()
    idx = int(digest, 16) % len(AVATAR_COLORS)
    return AVATAR_COLORS[idx]

@register.filter
def dict_get(dictionary, key):
    """
    Look up dictionary[key] (or return None if missing).
    Usage: {{ my_dict|dict_get:some_key }}
    """
    if not dictionary:
        return None
    return dictionary.get(key)