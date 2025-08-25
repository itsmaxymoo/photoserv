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


@register.filter
def exposure_program(value):
    if not value:
        return None

    mapping = {
        0: "Not Defined",
        1: "Manual",
        2: "Program",
        3: "Aperture priority",
        4: "Shutter speed priority",
        5: "Creative (Slow speed)",
        6: "Action (High speed)",
        7: "Portrait",
        8: "Landscape",
        9: "Bulb",
    }
    return mapping.get(value, "Unknown")
