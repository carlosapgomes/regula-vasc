"""Tests for attachment suppression and supplemental attachments."""

from typing import Any

import pytest
from django.urls import reverse

from apps.cases.models import Case, CaseAttachment

pytestmark = pytest.mark.django_db


class TestSuppressAttachmentRequiresReason:
    """RED: POST sem motivo → erro."""

    def test_suppress_without_reason_fails(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        from .conftest import make_jpeg_file

        # Create an attachment first
        attachment = CaseAttachment.objects.create(
            case=created_case,
            file=make_jpeg_file(),
            original_filename="test.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            sha256="abc123",
            uploaded_by=authenticated_nurse,
        )

        url = reverse(
            "intake:suppress_attachment",
            args=[created_case.case_id, attachment.attachment_id],
        )
        response = client.post(url, {"reason": ""})

        assert response.status_code == 302
        updated_att = CaseAttachment.objects.get(pk=attachment.pk)
        assert not updated_att.is_suppressed

    def test_suppress_with_reason_succeeds(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        from .conftest import make_jpeg_file

        attachment = CaseAttachment.objects.create(
            case=created_case,
            file=make_jpeg_file(),
            original_filename="test.jpg",
            content_type="image/jpeg",
            size_bytes=100,
            sha256="abc123",
            uploaded_by=authenticated_nurse,
        )

        url = reverse(
            "intake:suppress_attachment",
            args=[created_case.case_id, attachment.attachment_id],
        )
        response = client.post(url, {"reason": "Anexo errado"})

        assert response.status_code == 302
        updated_att = CaseAttachment.objects.get(pk=attachment.pk)
        assert updated_att.is_suppressed
        assert updated_att.suppression_reason == "Anexo errado"


class TestAddSupplementalAttachmentSuccess:
    """RED: POST com JPEG + justificativa → CaseAttachment criado."""

    def test_add_supplemental_with_justification(
        self, client: Any, authenticated_nurse: Any, waiting_doctor_case: Case
    ) -> None:
        from .conftest import make_jpeg_file

        url = reverse(
            "intake:supplemental_attachment_add",
            args=[waiting_doctor_case.case_id],
        )
        jpg = make_jpeg_file("raio-x.jpg")

        response = client.post(
            url,
            {"attachment_files": [jpg], "note": "Raio-X adicional do pé"},
        )

        assert response.status_code == 302
        assert waiting_doctor_case.attachments.count() == 1
        att = waiting_doctor_case.attachments.first()
        assert att is not None
        assert att.original_filename == "raio-x.jpg"
        assert att.note == "Raio-X adicional do pé"
        assert att.upload_phase == "supplemental"

    def test_add_supplemental_without_note_fails(
        self, client: Any, authenticated_nurse: Any, waiting_doctor_case: Case
    ) -> None:
        from .conftest import make_jpeg_file

        url = reverse(
            "intake:supplemental_attachment_add",
            args=[waiting_doctor_case.case_id],
        )
        jpg = make_jpeg_file()

        response = client.post(url, {"attachment_files": [jpg], "note": ""})

        assert response.status_code == 302
        assert waiting_doctor_case.attachments.count() == 0

    def test_add_supplemental_to_cleaned_fails(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        from apps.cases.models import CaseStatus

        from .conftest import make_jpeg_file

        # Use update() to bypass FSM protected field
        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED.value)

        url = reverse(
            "intake:supplemental_attachment_add",
            args=[created_case.case_id],
        )
        jpg = make_jpeg_file()

        response = client.post(url, {"attachment_files": [jpg], "note": "Justificativa"})

        assert response.status_code == 302
        assert created_case.attachments.count() == 0
