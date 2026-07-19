"""Admin configuration for dashboard models."""

from django.contrib import admin

from .models import LlmProviderConfig


@admin.register(LlmProviderConfig)
class LlmProviderConfigAdmin(admin.ModelAdmin[LlmProviderConfig]):
    """Admin configuration for LLM provider settings."""

    list_display = [
        "llm1_primary_provider",
        "llm1_primary_model",
        "secondary_enabled",
        "updated_at",
    ]
    readonly_fields = ["single_id", "created_at", "updated_at"]

    def has_add_permission(self, request):
        """Only one config row allowed."""
        return not LlmProviderConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton config."""
        return False
