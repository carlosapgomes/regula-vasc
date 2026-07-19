"""Tests for PDF utilities."""

import tempfile
from pathlib import Path

from apps.pipeline.pdf_utils import (
    extract_agency_record_number,
    extract_pdf_text_from_path,
    extract_regulation_days_on_screen,
    remove_watermark,
    strip_watermark_and_extract_record,
)


def _create_test_pdf(text: str, path: str) -> None:
    """Create a minimal PDF with given text content for testing."""
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError:
        import pytest

        pytest.skip("pymupdf not available")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()


class TestExtractPdfText:
    def test_extracts_text_from_valid_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            _create_test_pdf("Relatório de Regulação Vascular\nPaciente: João Silva\nLesão em MID", pdf_path)
            text = extract_pdf_text_from_path(pdf_path)
            assert "João Silva" in text
            assert "Relatório" in text
            assert "Lesão" in text
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    def test_detects_empty_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name

        try:
            _create_test_pdf("", pdf_path)
            text = extract_pdf_text_from_path(pdf_path)
            assert text == "" or text.strip() == ""
        finally:
            Path(pdf_path).unlink(missing_ok=True)


class TestRemoveWatermark:
    def test_removes_repeated_five_digit_watermark(self):
        text = """
        12345
        Dados do paciente: relatório clínico vascular
        12345
        Lesão em membro inferior direito
        12345
        Pulsos pediosos ausentes
        12345
        """
        cleaned = remove_watermark(text)
        assert "12345" not in cleaned
        assert "Dados do paciente" in cleaned
        assert "Lesão em membro inferior direito" in cleaned

    def test_preserves_single_occurrence_numbers(self):
        text = "Registro: 98765\nDados do paciente sem watermark."
        cleaned = remove_watermark(text)
        # Single occurrence should be preserved (not a watermark)
        assert "98765" in cleaned

    def test_handles_no_watermark_text(self):
        text = "Relatório normal sem marcas d'água."
        cleaned = remove_watermark(text)
        assert cleaned.strip() == text


class TestExtractAgencyRecordNumber:
    def test_extracts_from_codigo_pattern(self):
        text = "Código: 54321\nDados do paciente..."
        assert extract_agency_record_number(text) == "54321"

    def test_extracts_from_codigo_case_insensitive(self):
        text = "cÓdIGO: 98765\nDados..."
        assert extract_agency_record_number(text) == "98765"

    def test_extracts_from_report_header(self):
        text = "RELATÓRIO DE OCORRÊNCIAS - 12/2024\n12345\nPaciente..."
        result = extract_agency_record_number(text)
        assert result == "12345"

    def test_returns_empty_when_no_match(self):
        text = "Texto sem nenhum código identificável."
        assert extract_agency_record_number(text) == ""


class TestExtractRegulationDaysOnScreen:
    def test_extracts_single_occurrence(self):
        text = "Dias em tela: 15"
        assert extract_regulation_days_on_screen(text) == 15

    def test_extracts_max_when_multiple(self):
        text = "Dias em tela: 15\nDias em tela: 30"
        assert extract_regulation_days_on_screen(text) == 30

    def test_case_insensitive(self):
        text = "dIaS Em TeLa: 7"
        assert extract_regulation_days_on_screen(text) == 7

    def test_handles_variable_spacing(self):
        text = "Dias   em  tela :  42"
        assert extract_regulation_days_on_screen(text) == 42

    def test_returns_none_when_not_found(self):
        text = "Sem informação de dias em tela."
        assert extract_regulation_days_on_screen(text) is None


class TestStripWatermarkAndExtractRecord:
    def test_returns_cleaned_text_and_record(self):
        text = "Código: 11111\nRelatório vascular\n11111\nPaciente estável\n11111"
        cleaned, record = strip_watermark_and_extract_record(text)
        assert record == "11111"
        assert "11111" not in cleaned
        assert "Relatório vascular" in cleaned
        assert "Paciente estável" in cleaned

    def test_fallback_to_timestamp_when_no_record(self):
        text = "Relatório sem código explícito."
        cleaned, record = strip_watermark_and_extract_record(text)
        # Should fallback to a timestamp-based number
        assert len(record) > 5
        assert record.isdigit()
