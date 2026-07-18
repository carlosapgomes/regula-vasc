"""Context processors for the accounts app."""

from django.conf import settings

ROLE_DISPLAY_NAMES = {
    "nurse": "Enfermeiro",
    "doctor": "Médico",
    "admin": "Administrador",
}


def role_context(request):
    """Adiciona active_role_display ao contexto de todos os templates."""
    active_role = request.session.get("active_role", "")
    return {
        "active_role_display": ROLE_DISPLAY_NAMES.get(active_role, active_role),
        "active_role": active_role,
    }


def app_display_name(request):
    """Adiciona app_display_name ao contexto de todos os templates."""
    return {
        "app_display_name": getattr(settings, "APP_DISPLAY_NAME", "Regulação Vascular"),
    }
