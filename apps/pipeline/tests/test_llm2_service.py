"""Tests for LLM2 vascular suggestion service."""

import json

import pytest
from django.test import TestCase

from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm2_service import (
    LLM2_DEFAULT_SYSTEM_PROMPT,
    LLM2_DEFAULT_USER_PROMPT,
    Llm2Service,
)
from apps.pipeline.schemas.llm2 import Llm2VascularResponse


def _make_valid_llm2_response() -> dict[str, object]:
    """Build a minimal but valid LLM2 vascular response dict."""
    return {
        "suggestion": "accept",
        "recommendation_text": "Paciente com isquemia crítica — recomenda-se avaliação presencial.",
        "acceptance_criteria_met": [
            "Lesão trófica em MID com pulsos distais ausentes",
        ],
        "exclusion_criteria_met": [],
        "confidence": "alta",
        "rationale": "Paciente apresenta lesão trófica com pulsos pedioso e tibial posterior ausentes à direita, "
        "caracterizando isquemia crítica. Creatinina 1.1, sem critérios de exclusão.",
    }


class TestLlm2Service(TestCase):
    def test_returns_suggestion_accept(self):
        """LLM2 should return suggestion dict with accept."""
        valid_response = _make_valid_llm2_response()
        client = StaticLlmClient(json.dumps(valid_response, ensure_ascii=False))

        llm1_data: dict[str, object] = {"patient": {"name": "Test"}, "lesion": {}}

        service = Llm2Service(client)
        result = service.run(
            llm1_structured_data=llm1_data,
            system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
            user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
        )

        assert result.suggested_action is not None
        # Validate roundtrip
        validated = Llm2VascularResponse.model_validate(result.suggested_action)
        assert validated.suggestion == "accept"
        assert validated.confidence == "alta"

    def test_returns_suggestion_deny(self):
        """LLM2 should handle deny suggestions."""
        response = {
            "suggestion": "deny",
            "recommendation_text": "Paciente sem critérios de cirurgia vascular.",
            "acceptance_criteria_met": [],
            "exclusion_criteria_met": ["Creatinina 3.2 sem diálise estabelecida"],
            "confidence": "alta",
            "rationale": "Creatinina elevada contraindica procedimento eletivo sem preparo.",
        }
        client = StaticLlmClient(json.dumps(response, ensure_ascii=False))

        llm1_data: dict[str, object] = {"patient": {"name": "Test"}, "labs": {"creatinine": 3.2}}

        service = Llm2Service(client)
        result = service.run(
            llm1_structured_data=llm1_data,
            system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
            user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
        )

        validated = Llm2VascularResponse.model_validate(result.suggested_action)
        assert validated.suggestion == "deny"
        assert len(validated.exclusion_criteria_met) == 1

    def test_rejects_invalid_json(self):
        """LLM2 should raise ValueError on invalid JSON."""
        client = StaticLlmClient("garbage not json")

        service = Llm2Service(client)
        with pytest.raises(ValueError):
            service.run(
                llm1_structured_data={},
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
            )

    def test_rejects_invalid_suggestion_enum(self):
        """LLM2 should reject responses with invalid suggestion values."""
        invalid = _make_valid_llm2_response()
        invalid["suggestion"] = "maybe"  # not a valid enum
        client = StaticLlmClient(json.dumps(invalid))

        service = Llm2Service(client)
        with pytest.raises(ValueError):
            service.run(
                llm1_structured_data=dict[str, object](),
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
            )

    def test_rejects_invalid_confidence_enum(self):
        """LLM2 should reject responses with invalid confidence values."""
        invalid = _make_valid_llm2_response()
        invalid["confidence"] = "muito_alta"  # not a valid enum
        client = StaticLlmClient(json.dumps(invalid))

        service = Llm2Service(client)
        with pytest.raises(ValueError):
            service.run(
                llm1_structured_data=dict[str, object](),
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
            )

    def test_records_calls(self):
        """Verify that the service passes prompts correctly."""
        valid = _make_valid_llm2_response()
        client = RecordingLlmClient(responses=[json.dumps(valid, ensure_ascii=False)])

        llm1_data: dict[str, object] = {"patient": {"name": "João", "age": 65}}

        service = Llm2Service(client)
        service.run(
            llm1_structured_data=llm1_data,
            system_prompt="LLM2 system test",
            user_prompt_template="LLM2 user test",
        )

        assert len(client.calls) == 1
        assert client.calls[0]["system_prompt"] == "LLM2 system test"
        assert "LLM2 user test" in client.calls[0]["user_prompt"]
        # Should contain the LLM1 data
        assert "João" in client.calls[0]["user_prompt"]
