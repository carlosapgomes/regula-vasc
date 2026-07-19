"""Tests for seed_prompts management command."""

import pytest
from django.core.management import call_command

from apps.llm.models import PromptTemplate

EXPECTED_PROMPT_NAMES = {"llm1_system", "llm1_user", "llm2_system", "llm2_user"}


@pytest.mark.django_db
class TestSeedPromptsCommand:
    """Tests for seed_prompts management command."""

    def test_seed_creates_four_templates(self):
        """Seed creates exactly 4 active PromptTemplate records with version 1."""
        call_command("seed_prompts")

        count = PromptTemplate.objects.count()
        assert count == 4

        names = set(PromptTemplate.objects.values_list("name", flat=True))
        assert names == EXPECTED_PROMPT_NAMES

        for pt in PromptTemplate.objects.all():
            assert pt.version == 1
            assert pt.is_active is True
            assert pt.content != ""

    def test_seed_idempotent(self):
        """Running seed twice does not create duplicates."""
        call_command("seed_prompts")
        call_command("seed_prompts")

        assert PromptTemplate.objects.count() == 4

    def test_seed_updates_content_on_re_run(self):
        """Running seed again updates content if changed."""
        call_command("seed_prompts")

        # Manually change content
        pt = PromptTemplate.objects.get(name="llm1_system", version=1)
        pt.content = "Conteúdo alterado manualmente."
        pt.save()

        # Re-run seed
        call_command("seed_prompts")

        pt.refresh_from_db()
        assert pt.content != "Conteúdo alterado manualmente."
        assert len(pt.content) > 50  # back to original long content

    def test_get_active_after_seed(self):
        """After seed, get_active returns the seeded prompt for each name."""
        call_command("seed_prompts")

        for name in EXPECTED_PROMPT_NAMES:
            pt = PromptTemplate.get_active(name)
            assert pt is not None, f"get_active('{name}') returned None"
            assert pt.name == name
            assert pt.version == 1
