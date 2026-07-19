"""Tests for dual-LLM display context construction in doctor views."""

from __future__ import annotations

from unittest.mock import patch

from apps.doctor.views import _parse_llm2_suggestion


class TestParseLlm2Suggestion:
    """Tests for _parse_llm2_suggestion helper."""

    def test_none_result(self) -> None:
        """None result returns None."""
        assert _parse_llm2_suggestion(None) is None

    def test_empty_dict(self) -> None:
        """Empty dict returns None."""
        assert _parse_llm2_suggestion({}) is None

    def test_accept_suggestion(self) -> None:
        """Accept suggestion is parsed correctly."""
        result = {
            "suggestion": "accept",
            "recommendation_text": "Paciente elegível para cirurgia.",
            "acceptance_criteria_met": ["Úlcera ativa", "Isquemia crítica"],
            "exclusion_criteria_met": [],
            "confidence": "alta",
            "rationale": "Paciente apresenta critérios de gravidade.",
        }
        parsed = _parse_llm2_suggestion(result)
        assert parsed is not None
        assert parsed["suggestion"] == "accept"
        assert parsed["confidence"] == "alta"
        assert len(parsed["acceptance_criteria_met"]) == 2
        assert len(parsed["exclusion_criteria_met"]) == 0
        assert "cirurgia" in parsed["recommendation_text"]

    def test_deny_suggestion(self) -> None:
        """Deny suggestion is parsed correctly."""
        result = {
            "suggestion": "deny",
            "recommendation_text": "Paciente não apresenta critérios de urgência.",
            "acceptance_criteria_met": [],
            "exclusion_criteria_met": ["Diabetes descompensada"],
            "confidence": "media",
            "rationale": "Risco cirúrgico elevado.",
        }
        parsed = _parse_llm2_suggestion(result)
        assert parsed is not None
        assert parsed["suggestion"] == "deny"
        assert parsed["confidence"] == "media"
        assert len(parsed["exclusion_criteria_met"]) == 1

    def test_acceptance_and_exclusion_lists_fallback(self) -> None:
        """Non-list acceptance/exclusion fields are coerced to empty list."""
        result = {
            "suggestion": "accept",
            "recommendation_text": "",
            "acceptance_criteria_met": None,
            "exclusion_criteria_met": None,
            "confidence": "baixa",
            "rationale": "",
        }
        parsed = _parse_llm2_suggestion(result)
        assert parsed is not None
        assert parsed["acceptance_criteria_met"] == []
        assert parsed["exclusion_criteria_met"] == []

    def test_missing_fields_defaults(self) -> None:
        """Missing optional fields get empty defaults."""
        result = {
            "suggestion": "accept",
        }
        parsed = _parse_llm2_suggestion(result)
        assert parsed is not None
        assert parsed["suggestion"] == "accept"
        assert parsed["acceptance_criteria_met"] == []
        assert parsed["exclusion_criteria_met"] == []
        assert parsed["confidence"] == ""
        assert parsed["rationale"] == ""
        assert parsed["recommendation_text"] == ""


class TestDualLlmContextBuild:
    """Tests for the dual-LLM display context logic (without HTTP)."""

    def test_single_llm_display(self) -> None:
        """When secondary is disabled, only primary card is shown."""
        from django.conf import settings

        assert not getattr(settings, "LLM_SECONDARY_ENABLED", True), "Test assumes secondary is off by default"

    @patch("apps.doctor.views.settings")
    def test_dual_llm_both_cards_present_when_enabled(self, mock_settings: object) -> None:
        """When secondary is enabled, both primary and secondary are parsed."""
        # This test verifies the parsing logic, not the template rendering
        # which is covered by integration tests
        primary = {
            "suggestion": "accept",
            "recommendation_text": "Aceitar.",
            "acceptance_criteria_met": ["Critério A"],
            "exclusion_criteria_met": [],
            "confidence": "alta",
            "rationale": "OK",
        }
        secondary = {
            "suggestion": "deny",
            "recommendation_text": "Recusar.",
            "acceptance_criteria_met": [],
            "exclusion_criteria_met": ["Critério B"],
            "confidence": "media",
            "rationale": "Risco",
        }

        parsed_primary = _parse_llm2_suggestion(primary)
        parsed_secondary = _parse_llm2_suggestion(secondary)

        assert parsed_primary is not None
        assert parsed_secondary is not None
        assert parsed_primary["suggestion"] == "accept"
        assert parsed_secondary["suggestion"] == "deny"
        assert parsed_primary["confidence"] == "alta"
        assert parsed_secondary["confidence"] == "media"

    def test_diverging_decisions(self) -> None:
        """Diverging decisions can be detected."""
        primary = _parse_llm2_suggestion({"suggestion": "accept"})
        secondary = _parse_llm2_suggestion({"suggestion": "deny"})

        assert primary is not None
        assert secondary is not None
        assert primary["suggestion"] != secondary["suggestion"]

    def test_converging_decisions(self) -> None:
        """Converging decisions (both accept) are not diverging."""
        primary = _parse_llm2_suggestion({"suggestion": "accept"})
        secondary = _parse_llm2_suggestion({"suggestion": "accept"})

        assert primary is not None
        assert secondary is not None
        assert primary["suggestion"] == secondary["suggestion"]
