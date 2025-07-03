from django import template

register = template.Library()

@register.filter
def short_name(full_name):
    if not full_name:
        return ''
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1][0]}."
    return parts[0]
