"""Tests for dual-LLM parallel execution (LLM1 + LLM2 stages)."""

import asyncio
import json

from django.test import TestCase

from apps.pipeline.llm import StaticLlmClient
from apps.pipeline.llm1_service import (
    LLM1_DEFAULT_SYSTEM_PROMPT,
    LLM1_DEFAULT_USER_PROMPT,
)
from apps.pipeline.llm2_service import (
    LLM2_DEFAULT_SYSTEM_PROMPT,
    LLM2_DEFAULT_USER_PROMPT,
)
from apps.pipeline.orchestrator import _run_dual_llm1, _run_dual_llm2


def _make_valid_llm1_response(name: str = "João Silva") -> dict[str, object]:
    return {
        "patient": {"name": name, "age": 65, "sex": "M"},
        "origin_context": {"city": None, "hospital": None, "unit": None, "state_uf": None},
        "referral": {
            "main_complaint": "Lesão em pé",
            "evolution_time_days": 15,
            "affected_limb": "right",
            "suspected_diagnosis": "Isquemia crítica",
        },
        "lesion": {
            "exact_location": "Pé direito",
            "size_cm": 3.0,
            "depth": "profunda",
            "aspect": "necrótica",
            "odor": "yes",
            "larvae": "no",
            "gangrene_location": None,
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
        "infection": {"local_signs": [], "systemic_signs": []},
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
        "imaging": {"xray": None, "duplex": None, "angiotomography": None},
        "acute_ischemia": {"signs": [], "time_onset_hours": None, "rutherford_category": "unknown"},
        "extraction_quality": {"confidence": "alta", "missing_fields": []},
    }


def _make_valid_llm2_response(suggestion: str = "accept") -> dict[str, object]:
    return {
        "suggestion": suggestion,
        "recommendation_text": "Recomendação de triagem.",
        "acceptance_criteria_met": ["Lesão trófica com pulsos ausentes"] if suggestion == "accept" else [],
        "exclusion_criteria_met": [] if suggestion == "accept" else ["Creatinina elevada"],
        "confidence": "alta",
        "rationale": "Parecer baseado nos dados fornecidos.",
    }


class TestDualLlm1(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="test@dual.com", password="testpass123")

    def test_both_succeed(self):
        """Both primary and secondary LLM1 should return results."""
        primary_client = StaticLlmClient(json.dumps(_make_valid_llm1_response("Primary")))
        secondary_client = StaticLlmClient(json.dumps(_make_valid_llm1_response("Secondary")))

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm1(
                case=case,
                extracted_text="Test text",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=secondary_client,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is not None
        assert secondary_result is not None
        from typing import cast

        assert cast(dict[str, object], primary_result.structured_data["patient"])["name"] == "Primary"
        assert cast(dict[str, object], secondary_result.structured_data["patient"])["name"] == "Secondary"

    def test_secondary_fails_primary_succeeds(self):
        """When secondary fails, primary result should still be returned."""
        primary_client = StaticLlmClient(json.dumps(_make_valid_llm1_response("Primary Works")))
        secondary_client = StaticLlmClient("invalid json {{{")

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm1(
                case=case,
                extracted_text="Test text",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=secondary_client,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is not None
        from typing import cast

        assert cast(dict[str, object], primary_result.structured_data["patient"])["name"] == "Primary Works"
        assert secondary_result is None

    def test_primary_fails_secondary_succeeds(self):
        """When primary fails, secondary still runs but pipeline should detect primary failure."""
        primary_client = StaticLlmClient("invalid json")
        secondary_client = StaticLlmClient(json.dumps(_make_valid_llm1_response("Secondary Works")))

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm1(
                case=case,
                extracted_text="Test text",
                system_prompt=LLM1_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM1_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=secondary_client,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is None
        assert secondary_result is not None
        from typing import cast

        assert cast(dict[str, object], secondary_result.structured_data["patient"])["name"] == "Secondary Works"


class TestDualLlm2(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="test2@dual.com", password="testpass123")

    def test_both_succeed(self):
        """Both primary and secondary LLM2 should return suggestions."""
        primary_client = StaticLlmClient(json.dumps(_make_valid_llm2_response("accept")))
        secondary_client = StaticLlmClient(json.dumps(_make_valid_llm2_response("deny")))

        llm1_data = _make_valid_llm1_response()

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm2(
                case=case,
                llm1_structured_data=llm1_data,
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=secondary_client,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is not None
        assert secondary_result is not None
        assert primary_result.suggested_action["suggestion"] == "accept"
        assert secondary_result.suggested_action["suggestion"] == "deny"

    def test_secondary_fails_primary_succeeds(self):
        """When secondary LLM2 fails, primary should still return result."""
        primary_client = StaticLlmClient(json.dumps(_make_valid_llm2_response("accept")))
        secondary_client = StaticLlmClient("not json")

        llm1_data = _make_valid_llm1_response()

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm2(
                case=case,
                llm1_structured_data=llm1_data,
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=secondary_client,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is not None
        assert primary_result.suggested_action["suggestion"] == "accept"
        assert secondary_result is None

    def test_no_secondary_configured(self):
        """When secondary is None, only primary should run."""
        primary_client = StaticLlmClient(json.dumps(_make_valid_llm2_response("accept")))

        llm1_data = _make_valid_llm1_response()

        from apps.cases.models import Case

        case = Case.objects.create(
            extracted_text="Test text",
            created_by=self.user,
        )

        result = asyncio.run(
            _run_dual_llm2(
                case=case,
                llm1_structured_data=llm1_data,
                system_prompt=LLM2_DEFAULT_SYSTEM_PROMPT,
                user_prompt_template=LLM2_DEFAULT_USER_PROMPT,
                primary_client=primary_client,
                secondary_client=None,
            )
        )

        primary_result, secondary_result = result
        assert primary_result is not None
        assert secondary_result is None
