"""Tests for LLM1 vascular structured extraction service."""

import json

import pytest
from django.test import TestCase

from apps.pipeline.llm import RecordingLlmClient, StaticLlmClient
from apps.pipeline.llm1_service import (
    LLM1_DEFAULT_SYSTEM_PROMPT,
    LLM1_DEFAULT_USER_PROMPT,
    Llm1Service,
    Llm1ValidationError,
)
from apps.pipeline.schemas.llm1 import Llm1VascularResponse


def _make_valid_llm1_response() -> dict[str, object]:
    """Build a minimal but valid LLM1 vascular response dict."""
    return {
        "patient": {
            "name": "João Silva",
            "age": 65,
            "sex": "M",
        },
        "origin_context": {
            "city": "Humaitá",
            "hospital": "Hospital Metropolitano",
            "unit": "Pronto Socorro",
            "state_uf": "AM",
        },
        "referral": {
            "main_complaint": "Lesão em pé direito há 15 dias",
            "evolution_time_days": 15,
            "affected_limb": "right",
            "suspected_diagnosis": "Isquemia crítica de membro inferior",
        },
        "lesion": {
            "exact_location": "Dorso do pé direito",
            "size_cm": 3.5,
            "depth": "profunda",
            "aspect": "necrótica com secreção",
            "odor": "yes",
            "larvae": "no",
            "gangrene_location": "2º e 3º pododáctilos",
            "necrosis_type": "seca",
            "purulent_secretion": "yes",
        },
        "pain": {
            "has_pain": "yes",
            "rest_pain": "yes",
            "night_pain": "yes",
            "improves_with_dangling": "yes",
            "prior_claudication": "yes",
            "sudden_onset": "no",
        },
        "pulses": {
            "femoral_r": "2+",
            "femoral_l": "2+",
            "popliteal_r": "1+",
            "popliteal_l": "2+",
            "tibial_posterior_r": "0",
            "tibial_posterior_l": "1+",
            "pedal_r": "0",
            "pedal_l": "1+",
        },
        "edema": {
            "present": "yes",
            "unilateral_bilateral": "unilateral",
            "depressible": "yes",
            "hardened": "no",
            "hot": "no",
            "cold": "no",
        },
        "infection": {
            "local_signs": ["hiperemia", "calor local", "secreção purulenta"],
            "systemic_signs": ["febre"],
        },
        "history": {
            "diabetes": "yes",
            "smoking": "yes",
            "hypertension": "yes",
            "ckd": "no",
            "mi": "no",
            "stroke": "no",
            "arrhythmia": "no",
            "heart_failure": "no",
            "copd": "no",
            "prior_amputation": "no",
            "prior_revascularization": "no",
            "anticoagulation_use": "no",
            "antiplatelet_use": "yes",
        },
        "labs": {
            "hemoglobin": 12.5,
            "leukocytes": 11000,
            "crp": 8.2,
            "glucose": 180,
            "creatinine": 1.1,
            "urea": 42.0,
            "potassium": 4.1,
            "lactate": 1.8,
        },
        "imaging": {
            "xray": "Sem alterações ósseas agudas",
            "duplex": "Oclusão de artéria tibial anterior direita",
            "angiotomography": None,
        },
        "acute_ischemia": {
            "signs": [],
            "time_onset_hours": None,
            "rutherford_category": "unknown",
        },
        "extraction_quality": {
            "confidence": "alta",
            "missing_fields": [],
        },
    }


class TestLlm1Service(TestCase):
    def test_extracts_valid_data(self):
        """LLM1 service should parse valid JSON and return structured data."""
        valid_response = _make_valid_llm1_response()
        client = StaticLlmClient(json.dumps(valid_response, ensure_ascii=False))

        service = Llm1Service(client)
        result = service.run(
            extracted_text="Relatório de regulação vascular...",
            system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
            user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
        )

        assert result.structured_data is not None
        # Validate the structured_data can be loaded back into Pydantic
        validated = Llm1VascularResponse.model_validate(result.structured_data)
        assert validated.patient.name == "João Silva"
        assert validated.patient.age == 65
        assert validated.referral.affected_limb == "right"

    def test_rejects_invalid_json(self):
        """LLM1 service should raise Llm1ValidationError on invalid JSON."""
        client = StaticLlmClient("not valid json at all {{{")

        service = Llm1Service(client)
        with pytest.raises(Llm1ValidationError):
            service.run(
                extracted_text="Relatório...",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
            )

    def test_rejects_invalid_field_types(self):
        """LLM1 service should reject JSON with wrong field types."""
        # "age" should be int but we send a string that can't be coerced
        invalid = _make_valid_llm1_response()
        from typing import cast

        cast(dict[str, object], invalid["patient"])["age"] = "not_a_number"
        client = StaticLlmClient(json.dumps(invalid))

        service = Llm1Service(client)
        with pytest.raises(Llm1ValidationError):
            service.run(
                extracted_text="Relatório...",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
            )

    def test_rejects_invalid_enum_values(self):
        """LLM1 service should reject responses with invalid enum values."""
        valid = _make_valid_llm1_response()
        from typing import cast

        cast(dict[str, object], valid["referral"])["affected_limb"] = "invalid_limb"  # not a valid enum
        client = StaticLlmClient(json.dumps(valid))

        service = Llm1Service(client)
        with pytest.raises(Llm1ValidationError):
            service.run(
                extracted_text="Relatório...",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
            )

    def test_handles_empty_extracted_text(self):
        """LLM1 service should handle empty extracted text gracefully."""
        valid_response = _make_valid_llm1_response()
        client = StaticLlmClient(json.dumps(valid_response, ensure_ascii=False))

        service = Llm1Service(client)
        result = service.run(
            extracted_text="",
            system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
            user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
        )

        assert result.structured_data is not None

    def test_records_calls(self):
        """Verify that the service passes prompts correctly."""
        valid = _make_valid_llm1_response()
        client = RecordingLlmClient(responses=[json.dumps(valid, ensure_ascii=False)])

        service = Llm1Service(client)
        service.run(
            extracted_text="Paciente João, 65 anos...",
            system_prompt="System prompt test",
            user_prompt_template="User template test",
        )

        assert len(client.calls) == 1
        assert client.calls[0]["system_prompt"] == "System prompt test"
        assert "User template test" in client.calls[0]["user_prompt"]
        assert "Paciente João, 65 anos..." in client.calls[0]["user_prompt"]
