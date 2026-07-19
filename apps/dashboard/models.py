"""LlmProviderConfig model for storing LLM configuration in the database."""

from django.db import models


class LlmProviderConfig(models.Model):
    """Configuração de providers LLM editável pelo administrador via dashboard.

    É um modelo singleton (apenas um registro). O admin edita os valores
    via dashboard, e o pipeline lê daqui em vez de settings.py.
    """

    # LLM1 Primary
    llm1_primary_provider = models.CharField("LLM1 Provider primário", max_length=20, default="openai")
    llm1_primary_model = models.CharField("LLM1 Model primário", max_length=100, default="gpt-4o-mini")
    llm1_primary_api_key = models.CharField("LLM1 API Key primário", max_length=255, blank=True)
    llm1_primary_base_url = models.CharField("LLM1 Base URL primário", max_length=255, blank=True)

    # LLM1 Secondary
    llm1_secondary_provider = models.CharField("LLM1 Provider secundário", max_length=20, default="openai")
    llm1_secondary_model = models.CharField("LLM1 Model secundário", max_length=100, default="gpt-4o-mini")
    llm1_secondary_api_key = models.CharField("LLM1 API Key secundário", max_length=255, blank=True)
    llm1_secondary_base_url = models.CharField("LLM1 Base URL secundário", max_length=255, blank=True)

    # LLM2 Primary
    llm2_primary_provider = models.CharField("LLM2 Provider primário", max_length=20, default="openai")
    llm2_primary_model = models.CharField("LLM2 Model primário", max_length=100, default="gpt-4o-mini")
    llm2_primary_api_key = models.CharField("LLM2 API Key primário", max_length=255, blank=True)
    llm2_primary_base_url = models.CharField("LLM2 Base URL primário", max_length=255, blank=True)

    # LLM2 Secondary
    llm2_secondary_provider = models.CharField("LLM2 Provider secundário", max_length=20, default="openai")
    llm2_secondary_model = models.CharField("LLM2 Model secundário", max_length=100, default="gpt-4o-mini")
    llm2_secondary_api_key = models.CharField("LLM2 API Key secundário", max_length=255, blank=True)
    llm2_secondary_base_url = models.CharField("LLM2 Base URL secundário", max_length=255, blank=True)

    # Dual-LLM toggle
    secondary_enabled = models.BooleanField("LLM secundário habilitado", default=False)

    # Singleton: garante apenas um registro
    single_id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração de Providers LLM"
        verbose_name_plural = "Configuração de Providers LLM"

    def __str__(self) -> str:
        return "Configuração LLM Providers"

    @classmethod
    def get_singleton(cls) -> "LlmProviderConfig":
        """Retorna o único registro, criando-o se não existir."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
