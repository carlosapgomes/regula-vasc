"""Tests for PromptTemplate model."""

import pytest

from apps.llm.models import PromptTemplate


@pytest.mark.django_db
class TestPromptTemplateModel:
    """Tests for PromptTemplate model."""

    def test_create_prompt_template(self):
        """PromptTemplate can be created with all fields."""
        pt = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Teste de prompt.",
            is_active=True,
        )
        assert pt.name == "llm1_system"
        assert pt.version == 1
        assert pt.content == "Teste de prompt."
        assert pt.is_active is True
        assert pt.created_at is not None
        assert pt.updated_at is not None

    def test_str_representation(self):
        """String representation shows name, version and active status."""
        pt = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Teste.",
        )
        assert str(pt) == "llm1_system v1 (ativo)"

    def test_str_inactive(self):
        """Inactive prompt shows no active indicator."""
        pt = PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Teste.",
            is_active=False,
        )
        assert "(ativo)" not in str(pt)

    def test_get_active_returns_none_when_empty(self):
        """get_active returns None when no template exists."""
        result = PromptTemplate.get_active("llm1_system")
        assert result is None

    def test_get_active_returns_active_template(self):
        """get_active returns the active template."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Ativo.",
            is_active=True,
        )
        result = PromptTemplate.get_active("llm1_system")
        assert result is not None
        assert result.content == "Ativo."

    def test_get_active_ignores_inactive(self):
        """get_active ignores inactive templates."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Inativo.",
            is_active=False,
        )
        result = PromptTemplate.get_active("llm1_system")
        assert result is None

    def test_get_active_prefers_active_over_inactive(self):
        """get_active returns the active template when both exist."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Inativo.",
            is_active=False,
        )
        PromptTemplate.objects.create(
            name="llm1_system",
            version=2,
            content="Ativo.",
            is_active=True,
        )
        result = PromptTemplate.get_active("llm1_system")
        assert result is not None
        assert result.content == "Ativo."
        assert result.version == 2

    def test_versioned_templates_same_name(self):
        """Multiple versions of the same name can coexist."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Versão 1.",
            is_active=False,
        )
        PromptTemplate.objects.create(
            name="llm1_system",
            version=2,
            content="Versão 2.",
            is_active=True,
        )
        assert PromptTemplate.objects.filter(name="llm1_system").count() == 2

    def test_unique_together_name_version(self):
        """Duplicate (name, version) raises IntegrityError."""
        import django.db.utils

        PromptTemplate.objects.create(name="llm1_system", version=1, content="Primeira.")
        with pytest.raises(django.db.utils.IntegrityError):
            PromptTemplate.objects.create(name="llm1_system", version=1, content="Duplicada.")

    def test_get_active_returns_none_for_wrong_name(self):
        """get_active returns None for a name that doesn't exist."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Existente.",
            is_active=True,
        )
        result = PromptTemplate.get_active("nonexistent_name")
        assert result is None

    def test_verbose_name_plural(self):
        """Meta.verbose_name_plural matches expected value."""
        assert PromptTemplate._meta.verbose_name_plural == "Templates de Prompt"
