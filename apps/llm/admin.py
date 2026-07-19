"""Admin registration for llm models."""

from django.contrib import admin

from .models import PromptTemplate


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin[PromptTemplate]):
    list_display = ("name", "version", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "name")
    search_fields = ("name", "content")
    readonly_fields = ("version", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "content", "is_active")}),
        ("Metadados", {"fields": ("version", "created_at", "updated_at")}),
    )
