"""PromptTemplate model with versioning."""

from django.db import models


class PromptTemplate(models.Model):
    """Template de prompt versionado.

    Cada prompt tem um nome único (ex: ``llm1_system``, ``llm1_user``,
    ``llm2_system``, ``llm2_user``). Apenas uma versão ativa por nome.
    """

    name = models.CharField(
        "Nome do prompt",
        max_length=60,
        db_index=True,
    )
    version = models.PositiveIntegerField("Versão", default=1)
    content = models.TextField("Conteúdo do prompt")
    is_active = models.BooleanField("Ativo", default=True, db_index=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Template de Prompt"
        verbose_name_plural = "Templates de Prompt"
        unique_together = [("name", "version")]
        ordering = ["name", "-version"]

    def __str__(self) -> str:
        return f"{self.name} v{self.version} {'(ativo)' if self.is_active else ''}"

    @staticmethod
    def get_active(name: str) -> "PromptTemplate | None":
        """Retorna o template ativo para o nome dado, ou None."""
        try:
            return PromptTemplate.objects.get(name=name, is_active=True)
        except PromptTemplate.DoesNotExist:
            return None
