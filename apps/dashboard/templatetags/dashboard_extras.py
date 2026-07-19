"""Template tags for the dashboard app."""

from django import template

register = template.Library()


@register.filter
def duration_format(seconds: int | None) -> str:
    """Formata uma duração em segundos para exibição legível.

    Exemplos:
        3600 → "1h 0min"
        7320 → "2h 2min"
        120 → "2min"
    """
    if seconds is None or seconds < 0:
        return "—"

    total_minutes = int(seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


@register.filter
def percentage(value: float | None, total: float | None) -> str:
    """Calcula e formata percentual.

    Uso: {{ value|percentage:total }}
    """
    if value is None or total is None or total == 0:
        return "—"
    pct = (float(value) / float(total)) * 100
    return f"{pct:.1f}%"
