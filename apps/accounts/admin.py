"""Admin registration for accounts models."""

import django_stubs_ext
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Make ModelAdmin subscriptable for mypy type args at runtime
# (django-stubs makes it generic in stubs, but Django itself doesn't)
django_stubs_ext.monkeypatch()

from .models import Role, User  # noqa: E402


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin[Role]):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(User)
class UserAdmin(BaseUserAdmin[User]):
    list_display = ("username", "email", "account_status", "is_active")
    list_filter = ("account_status", "is_active", "roles")
    fieldsets = tuple(BaseUserAdmin.fieldsets or ()) + (
        ("Profissional", {"fields": ("professional_council", "professional_council_number")}),
        ("RegulaVasc Custom", {"fields": ("roles", "account_status")}),
    )
