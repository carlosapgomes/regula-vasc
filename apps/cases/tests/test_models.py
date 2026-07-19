"""Tests for Case model fields and properties."""

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseAttachment, CaseCommunicationMessage, CaseEvent, CaseStatus

User = get_user_model()


@pytest.fixture
def nurse(db):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nurse@test.com", password="pass123")
    role, _ = Role.objects.get_or_create(name="nurse")
    user.roles.add(role)
    return user


@pytest.fixture
def case(db, nurse):
    return Case.objects.create(created_by=nurse)


@pytest.mark.django_db
class TestCaseModel:
    """Tests for Case model."""

    def test_case_creation_default_status(self, case):
        """Case is created with status NEW."""
        assert case.status == CaseStatus.NEW
        assert case.case_id is not None

    def test_case_str(self, case):
        """String representation includes id and status."""
        assert str(case) == f"Case {case.case_id} [NEW]"

    def test_patient_name_empty(self, case):
        """patient_name returns 'Paciente' when no structured_data."""
        assert case.patient_name == "Paciente"

    def test_patient_name_from_structured_data(self, case):
        """patient_name returns name from structured_data."""
        case.structured_data = {"patient": {"name": "Maria Silva", "age": 65}}
        assert case.patient_name == "Maria Silva"

    def test_patient_age_from_structured_data(self, case):
        """patient_age returns age from structured_data."""
        case.structured_data = {"patient": {"name": "João", "age": 72}}
        assert case.patient_age == "72"

    def test_patient_age_empty(self, case):
        """patient_age returns '' when no age in structured_data."""
        assert case.patient_age == ""

    def test_doctor_display_no_doctor(self, case):
        """doctor_display returns '' when no doctor assigned."""
        assert case.doctor_display == ""

    def test_doctor_display_with_doctor(self, case):
        """doctor_display returns doctor name when assigned."""
        doctor = User.objects.create_user(username="doctor@test.com", password="pass123")
        case.doctor = doctor
        assert "doctor@test.com" in case.doctor_display


@pytest.mark.django_db
class TestCaseEventModel:
    """Tests for CaseEvent model."""

    def test_case_event_created_on_save(self, case):
        """CaseEvent is created when Case is saved with transition."""
        case.start_extraction()
        case.save()
        events = CaseEvent.objects.filter(case=case)
        assert events.count() > 0
        assert events.filter(event_type="CASE_START_EXTRACTION").exists()

    def test_case_event_str(self, nurse):
        """String representation includes event type."""
        case = Case.objects.create(created_by=nurse)
        event = CaseEvent.objects.get(case=case)
        assert "CASE_CREATED" in str(event)


@pytest.mark.django_db
class TestCaseAttachmentModel:
    """Tests for CaseAttachment model."""

    def test_attachment_creation(self, nurse, case):
        """CaseAttachment can be created."""
        from apps.cases.models import ACCEPTED_ATTACHMENT_CONTENT_TYPES

        attachment = CaseAttachment.objects.create(
            case=case,
            original_filename="test.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            sha256="abc123",
            uploaded_by=nurse,
        )
        assert attachment.original_filename == "test.pdf"
        assert attachment.content_type in ACCEPTED_ATTACHMENT_CONTENT_TYPES
        assert not attachment.is_suppressed

    def test_attachment_validation_rejects_invalid_content_type(self, nurse, case):
        """CaseAttachment with invalid content_type raises ValidationError."""
        import pytest
        from django.core.exceptions import ValidationError

        attachment = CaseAttachment(
            case=case,
            original_filename="test.txt",
            content_type="text/plain",
            size_bytes=100,
            sha256="def456",
            uploaded_by=nurse,
        )
        with pytest.raises(ValidationError):
            attachment.full_clean()


@pytest.mark.django_db
class TestCaseCommunicationMessageModel:
    """Tests for CaseCommunicationMessage model."""

    def test_message_creation(self, nurse, case):
        """CaseCommunicationMessage can be created."""
        msg = CaseCommunicationMessage.objects.create(
            case=case,
            author=nurse,
            author_role="nurse",
            body="Observação sobre o caso.",
        )
        assert msg.body == "Observação sobre o caso."
        assert msg.author_role == "nurse"
        assert str(msg) == f"CaseCommunicationMessage {msg.message_id} [nurse]"

    def test_message_without_author_raises_validation_error(self, case):
        """CaseCommunicationMessage without author for user type raises error."""
        from django.core.exceptions import ValidationError

        msg = CaseCommunicationMessage(
            case=case,
            author=None,
            author_role="",
            body="Teste",
            message_type="user",
        )
        with pytest.raises(ValidationError):
            msg.full_clean()

    def test_system_message_no_author_ok(self, case):
        """System message without author is valid."""
        msg = CaseCommunicationMessage.objects.create(
            case=case,
            author=None,
            author_role="",
            body="Mensagem sistêmica.",
            message_type="system",
        )
        assert msg.message_type == "system"
