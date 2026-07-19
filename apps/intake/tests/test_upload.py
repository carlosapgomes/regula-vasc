"""Tests for intake upload functionality."""

from typing import Any
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.cases.models import Case

pytestmark = pytest.mark.django_db


class TestUploadCreatesCaseAndEnqueues:
    """RED: POST with PDF → Case created, pipeline enqueued."""

    @patch("apps.pipeline.tasks.enqueue_pipeline")
    def test_upload_single_pdf_creates_case(self, mock_enqueue: Any, client: Any, authenticated_nurse: Any) -> None:
        url = reverse("intake:home")
        pdf = self._make_pdf()

        response = client.post(url, {"pdf_files": [pdf]})

        assert response.status_code == 302
        assert response.url == reverse("intake:my_cases")
        assert Case.objects.count() == 1

    @patch("apps.pipeline.tasks.enqueue_pipeline")
    def test_upload_single_pdf_enqueues_pipeline(
        self, mock_enqueue: Any, client: Any, authenticated_nurse: Any
    ) -> None:
        url = reverse("intake:home")
        pdf = self._make_pdf()

        client.post(url, {"pdf_files": [pdf]})

        assert mock_enqueue.called
        case = Case.objects.first()
        assert case is not None

    @patch("apps.pipeline.tasks.enqueue_pipeline")
    def test_upload_with_attachments(self, mock_enqueue: Any, client: Any, authenticated_nurse: Any) -> None:
        url = reverse("intake:home")
        pdf = self._make_pdf()
        jpg = self._make_jpeg()

        response = client.post(url, {"pdf_files": [pdf], "attachment_files": [jpg]})

        assert response.status_code == 302
        case = Case.objects.first()
        assert case is not None
        assert case.attachments.count() == 1
        first_attachment = case.attachments.first()
        assert first_attachment is not None
        assert first_attachment.original_filename == "test.jpg"

    @patch("apps.pipeline.tasks.enqueue_pipeline")
    def test_upload_rejects_invalid_file(self, mock_enqueue: Any, client: Any, authenticated_nurse: Any) -> None:
        """RED: POST with .docx → error."""
        url = reverse("intake:home")
        docx = self._make_docx()

        response = client.post(url, {"pdf_files": [docx]})

        assert response.status_code == 200  # stays on same page with error
        assert Case.objects.count() == 0
        content = response.content.decode()
        assert "não é um arquivo PDF" in content or "warning" in content.lower()

    def _make_pdf(self) -> Any:
        from .conftest import make_pdf_file

        return make_pdf_file()

    def _make_jpeg(self) -> Any:
        from .conftest import make_jpeg_file

        return make_jpeg_file()

    def _make_docx(self) -> Any:
        from .conftest import make_docx_file

        return make_docx_file()
