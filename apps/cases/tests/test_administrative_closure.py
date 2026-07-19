"""Tests for administrative closure service."""

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseEvent, CaseStatus
from apps.cases.services import administratively_close_case

User = get_user_model()


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="admin@test.com", password="pass123")
    role, _ = Role.objects.get_or_create(name="admin")
    user.roles.add(role)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user


@pytest.fixture
def nurse(db):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nurse@test.com", password="pass123")
    role, _ = Role.objects.get_or_create(name="nurse")
    user.roles.add(role)
    return user


@pytest.fixture
def case_wait_doctor(db, nurse):
    """Move case to WAIT_DOCTOR."""
    case = Case.objects.create(created_by=nurse)
    case.start_extraction()
    case.save()
    case.extraction_complete(success=True)
    case.save()
    case.llm1_complete(success=True)
    case.save()
    case.llm2_complete(success=True)
    case.save()
    assert case.status == CaseStatus.WAIT_DOCTOR
    return case


@pytest.fixture
def cleaned_case(db, nurse, case_wait_doctor):
    """Move case to CLEANED."""
    case_wait_doctor.doctor_decide(decision="accept")
    case_wait_doctor.save()
    case_wait_doctor.ready_for_nurse()
    case_wait_doctor.save()
    case_wait_doctor.nurse_ack()
    case_wait_doctor.save()
    assert case_wait_doctor.status == CaseStatus.CLEANED
    return case_wait_doctor


@pytest.mark.django_db
class TestAdministrativeClosure:
    """Tests for administratively_close_case."""

    def test_close_from_wait_doctor(self, admin_user, case_wait_doctor):
        """Close a WAIT_DOCTOR case."""
        result = administratively_close_case(
            case=case_wait_doctor,
            user=admin_user,
            reason_code="duplicate",
            reason_text="Caso duplicado",
            active_role="admin",
        )
        assert result.status == CaseStatus.CLEANED
        assert result.admin_closed_by == admin_user
        assert result.admin_closure_reason_code == "duplicate"
        assert result.admin_closure_reason_text == "Caso duplicado"

    def test_close_from_wait_doctor_records_event(self, admin_user, case_wait_doctor):
        """Administrative closure records CASE_ADMINISTRATIVELY_CLOSED event."""
        result = administratively_close_case(
            case=case_wait_doctor,
            user=admin_user,
            reason_code="duplicate",
            reason_text="Caso duplicado",
            active_role="admin",
        )
        event = CaseEvent.objects.filter(case=result, event_type="CASE_ADMINISTRATIVELY_CLOSED").first()
        assert event is not None
        assert event.payload.get("reason_code") == "duplicate"
        assert event.payload.get("reason_text") == "Caso duplicado"
        assert event.payload.get("active_role") == "admin"

    def test_cannot_close_cleaned_case(self, admin_user, cleaned_case):
        """Cannot close an already CLEANED case."""
        with pytest.raises(ValueError, match="já está encerrado"):
            administratively_close_case(
                case=cleaned_case,
                user=admin_user,
                reason_code="duplicate",
                reason_text="Tentativa",
                active_role="admin",
            )

    def test_close_requires_reason_text(self, admin_user, case_wait_doctor):
        """Closure requires non-empty reason_text."""
        with pytest.raises(ValueError, match="Motivo obrigatório"):
            administratively_close_case(
                case=case_wait_doctor,
                user=admin_user,
                reason_code="other",
                reason_text="",
                active_role="admin",
            )

    def test_close_requires_reason_code(self, admin_user, case_wait_doctor):
        """Closure requires reason_code."""
        with pytest.raises(ValueError, match="Código de motivo obrigatório"):
            administratively_close_case(
                case=case_wait_doctor,
                user=admin_user,
                reason_code="",
                reason_text="Teste",
                active_role="admin",
            )

    def test_close_from_failed(self, admin_user, nurse):
        """Close a FAILED case."""
        case = Case.objects.create(created_by=nurse)
        case.start_extraction()
        case.save()
        case.extraction_complete(success=False)
        case.save()
        assert case.status == CaseStatus.FAILED

        result = administratively_close_case(
            case=case,
            user=admin_user,
            reason_code="processing_error",
            reason_text="Erro de processamento",
            active_role="admin",
        )
        assert result.status == CaseStatus.CLEANED
