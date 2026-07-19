"""Tests for pipeline orchestrator — happy path and error handling."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from apps.cases.models import Case, CaseStatus
from apps.pipeline.llm import StaticLlmClient

User = get_user_model()


def _create_test_pdf_bytes(text: str) -> bytes:
    """Create a minimal PDF as bytes for testing."""
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("pymupdf not available")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    pdf_bytes: bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_valid_llm1_response() -> dict[str, object]:
    return {
        "patient": {"name": "João Silva", "age": 65, "sex": "M"},
        "origin_context": {"city": None, "hospital": None, "unit": None, "state_uf": None},
        "referral": {
            "main_complaint": "Lesão em pé direito",
            "evolution_time_days": 15,
            "affected_limb": "right",
            "suspected_diagnosis": "Isquemia crítica",
        },
        "lesion": {
            "exact_location": "Dorso do pé direito",
            "size_cm": 3.5,
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


def _make_valid_llm2_response() -> dict[str, object]:
    return {
        "suggestion": "accept",
        "recommendation_text": "Recomenda-se avaliação presencial.",
        "acceptance_criteria_met": ["Lesão trófica com pulsos distais ausentes"],
        "exclusion_criteria_met": [],
        "confidence": "alta",
        "rationale": "Isquemia crítica com lesão trófica estabelecida.",
    }


@pytest.mark.django_db
class TestOrchestratorHappyPath:
    def test_happy_path_new_to_wait_doctor(self):
        """Full pipeline from NEW to WAIT_DOCTOR with mocked LLM clients."""
        user = User.objects.create_user(username="nurse@test.com", password="testpass123")

        pdf_bytes = _create_test_pdf_bytes(
            "Código: 12345\nRelatório de Regulação Vascular\n"
            "Paciente João Silva, 65 anos, masculino.\n"
            "Lesão em pé direito há 15 dias. Pulsos pediosos ausentes.\n"
            "Dias em tela: 10"
        )

        case = Case.objects.create(
            created_by=user,
            extracted_text="",
        )
        case.pdf_file.save("test.pdf", ContentFile(pdf_bytes))

        from apps.pipeline.orchestrator import run_pipeline

        llm1_client = StaticLlmClient(json.dumps(_make_valid_llm1_response(), ensure_ascii=False))
        llm2_client = StaticLlmClient(json.dumps(_make_valid_llm2_response(), ensure_ascii=False))

        run_pipeline(
            case.case_id,
            primary_llm1_client=llm1_client,
            primary_llm2_client=llm2_client,
            llm1_system_prompt="System prompt llm1",
            llm1_user_template="User prompt llm1",
            llm2_system_prompt="System prompt llm2",
            llm2_user_template="User prompt llm2",
        )

        case = Case.objects.get(pk=case.pk)

        assert case.status == CaseStatus.WAIT_DOCTOR
        assert case.extracted_text != ""
        assert "João Silva" in case.extracted_text
        assert case.agency_record_number == "12345"
        assert case.regulation_days_on_screen == 10
        assert case.structured_data is not None
        assert case.suggested_action is not None
        assert case.suggested_action["suggestion"] == "accept"

        events = list(case.events.values_list("event_type", flat=True))
        assert "CASE_EXTRACTION_OK" in events
        assert "LLM1_OK" in events
        assert "LLM2_OK" in events


@pytest.mark.django_db
class TestOrchestratorErrorHandling:
    def test_handles_extraction_failure_empty_pdf(self):
        """Pipeline should transition to FAILED when PDF has no text."""
        user = User.objects.create_user(username="nurse2@test.com", password="testpass123")

        pdf_bytes = _create_test_pdf_bytes("")

        case = Case.objects.create(created_by=user)
        case.pdf_file.save("empty.pdf", ContentFile(pdf_bytes))

        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            primary_llm1_client=StaticLlmClient("{}"),
            primary_llm2_client=StaticLlmClient("{}"),
            llm1_system_prompt="s",
            llm1_user_template="u",
            llm2_system_prompt="s2",
            llm2_user_template="u2",
        )

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED

    def test_handles_llm1_failure(self):
        """Pipeline should transition to FAILED when LLM1 fails."""
        user = User.objects.create_user(username="nurse3@test.com", password="testpass123")

        pdf_bytes = _create_test_pdf_bytes("Relatório válido com texto suficiente para extração.")

        case = Case.objects.create(created_by=user)
        case.pdf_file.save("test_llm1_fail.pdf", ContentFile(pdf_bytes))

        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            primary_llm1_client=StaticLlmClient("invalid json {{{{"),
            primary_llm2_client=StaticLlmClient(json.dumps(_make_valid_llm2_response())),
            llm1_system_prompt="s",
            llm1_user_template="u",
            llm2_system_prompt="s2",
            llm2_user_template="u2",
        )

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED

        events = list(case.events.values_list("event_type", flat=True))
        assert "LLM1_FAILED" in events

    def test_handles_llm2_failure(self):
        """Pipeline should transition to FAILED when LLM2 fails after LLM1 succeeds."""
        user = User.objects.create_user(username="nurse4@test.com", password="testpass123")

        pdf_bytes = _create_test_pdf_bytes("Relatório válido com texto suficiente para extração.")

        case = Case.objects.create(created_by=user)
        case.pdf_file.save("test_llm2_fail.pdf", ContentFile(pdf_bytes))

        from apps.pipeline.orchestrator import run_pipeline

        run_pipeline(
            case.case_id,
            primary_llm1_client=StaticLlmClient(json.dumps(_make_valid_llm1_response(), ensure_ascii=False)),
            primary_llm2_client=StaticLlmClient("invalid json {{{{"),
            llm1_system_prompt="s",
            llm1_user_template="u",
            llm2_system_prompt="s2",
            llm2_user_template="u2",
        )

        case = Case.objects.get(pk=case.pk)
        assert case.status == CaseStatus.FAILED

        events = list(case.events.values_list("event_type", flat=True))
        assert "LLM1_OK" in events
        assert "LLM2_FAILED" in events
