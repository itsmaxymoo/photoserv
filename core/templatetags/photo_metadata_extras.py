from django import template


register = template.Library()


@register.filter
def shutter_speed(value):
    if not value:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value  # return as-is if cannot convert

    if value >= 1:
        return f"{int(value)}s"
    else:
        denominator = round(1 / value)
        return f"1/{denominator}s"
