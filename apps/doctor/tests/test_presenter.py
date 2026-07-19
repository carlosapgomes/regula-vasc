"""Tests for the doctor presenter — vascular report HTML generation."""

from __future__ import annotations

from apps.doctor.presenters import build_report


class TestPresenter:
    """Tests for build_report and sections."""

    def test_build_report_empty_data(self) -> None:
        """Empty structured_data returns empty message."""
        html = build_report(None)
        assert "Dados estruturados não disponíveis" in html

    def test_build_report_empty_dict(self) -> None:
        """Empty dict structured_data returns empty report container (no crash)."""
        html = build_report({})
        # Should not crash, contains report container
        assert '<div class="doctor-report">' in html
        # Should NOT show the "not available" message
        assert "não disponíveis" not in html

    def test_build_report_patient_name(self) -> None:
        """Patient section is present when patient data is provided."""
        data = {
            "patient": {"name": "Maria Silva", "age": 65, "sex": "F"},
        }
        html = build_report(data)
        assert "Dados do Paciente" in html
        assert "Maria Silva" in html
        assert "65" in html
        assert "F" in html

    def test_build_report_all_sections_present(self) -> None:
        """All vascular sections are present in the report."""
        data = {
            "patient": {"name": "João", "age": 70, "sex": "M"},
            "referral": {"main_complaint": "Dor na perna", "evolution_time_days": 30},
            "lesion": {"exact_location": "Tornozelo D", "size_cm": 3.5},
            "pain": {"has_pain": "yes", "rest_pain": "no"},
            "pulses": {"femoral_r": "2+", "femoral_l": "2+"},
            "history": {"diabetes": "yes", "smoking": "no"},
            "labs": {"hemoglobin": 12.5, "creatinine": 1.2},
            "edema": {"present": "yes", "unilateral_bilateral": "unilateral"},
            "infection": {"local_signs": ["eritema", "secreção"], "systemic_signs": ["febre"]},
            "imaging": {"duplex": "Estenose de 70%"},
            "acute_ischemia": {"rutherford_category": "IIa", "signs": ["dor", "palidez"]},
            "extraction_quality": {"confidence": "alta", "missing_fields": []},
        }
        html = build_report(data)

        assert "Dados do Paciente" in html
        assert "Queixa e Evolução" in html
        assert "Lesão" in html
        assert "Dor" in html
        assert "Pulsos" in html
        assert "Antecedentes" in html
        assert "Exames Laboratoriais" in html
        assert "Edema" in html
        assert "Sinais Locais" in html
        assert "Sinais Sistêmicos" in html
        assert "Exames de Imagem" in html
        assert "Isquemia Aguda" in html
        assert "Qualidade da Extração" in html

    def test_pulse_formatting(self) -> None:
        """Pulse values are rendered with proper CSS classes."""
        data = {
            "pulses": {
                "femoral_r": "3+",
                "femoral_l": "2+",
                "popliteal_r": "1+",
                "popliteal_l": "0",
            },
        }
        html = build_report(data)
        assert "pulse-strong" in html
        assert "pulse-normal" in html
        assert "pulse-weak" in html
        assert "pulse-absent" in html

    def test_confidence_display(self) -> None:
        """Extraction quality confidence is displayed correctly."""
        data = {
            "extraction_quality": {"confidence": "alta", "missing_fields": []},
        }
        html = build_report(data)
        assert "Alta" in html
        assert "Nenhum" in html  # no missing fields

    def test_missing_fields_listed(self) -> None:
        """Missing fields are listed in the extraction quality section."""
        data = {
            "extraction_quality": {"confidence": "baixa", "missing_fields": ["pulses", "labs"]},
        }
        html = build_report(data)
        assert "Baixa" in html
        assert "pulses" in html
        assert "labs" in html

    def test_prepare_doctor_case_report_alias(self) -> None:
        """prepare_doctor_case_report is an alias for build_report."""
        from apps.doctor.presenters import prepare_doctor_case_report

        html1 = build_report(None)
        html2 = prepare_doctor_case_report(None)
        assert html1 == html2
