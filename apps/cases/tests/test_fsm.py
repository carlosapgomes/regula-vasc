"""Tests for Case FSM transitions."""

import pytest
from django.contrib.auth import get_user_model
from django_fsm import TransitionNotAllowed

from apps.cases.models import Case, CaseStatus

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
class TestFSMTransitions:
    """Test all FSM transitions."""

    def test_start_extraction(self, case):
        """NEW → EXTRACTING."""
        case.start_extraction()
        case.save()
        assert case.status == CaseStatus.EXTRACTING

    def test_extraction_complete_success(self, case):
        """EXTRACTING → LLM1_STRUCT."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        assert case.status == CaseStatus.LLM1_STRUCT

    def test_extraction_complete_failure(self, case):
        """EXTRACTING → FAILED."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=False)
        case.save()
        assert case.status == CaseStatus.FAILED

    def test_llm1_complete_success(self, case):
        """LLM1_STRUCT → LLM2_SUGGEST."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        assert case.status == CaseStatus.LLM2_SUGGEST

    def test_llm1_complete_failure(self, case):
        """LLM1_STRUCT → FAILED."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=False)
        case.save()
        assert case.status == CaseStatus.FAILED

    def test_llm2_complete_success(self, case):
        """LLM2_SUGGEST → WAIT_DOCTOR."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()
        assert case.status == CaseStatus.WAIT_DOCTOR

    def test_llm2_complete_failure(self, case):
        """LLM2_SUGGEST → FAILED."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=False)
        case.save()
        assert case.status == CaseStatus.FAILED

    def test_doctor_decide_accept(self, case):
        """WAIT_DOCTOR → DOCTOR_ACCEPTED."""
        # Go through pipeline to WAIT_DOCTOR
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()
        assert case.status == CaseStatus.WAIT_DOCTOR

        case.doctor_decide(decision="accept")
        case.save()
        assert case.status == CaseStatus.DOCTOR_ACCEPTED

    def test_doctor_decide_deny(self, case):
        """WAIT_DOCTOR → DOCTOR_DENIED."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()

        case.doctor_decide(decision="deny")
        case.save()
        assert case.status == CaseStatus.DOCTOR_DENIED

    def test_ready_for_nurse_from_accepted(self, case):
        """DOCTOR_ACCEPTED → WAIT_NURSE_ACK."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()
        case.doctor_decide(decision="accept")
        case.save()

        case.ready_for_nurse()
        case.save()
        assert case.status == CaseStatus.WAIT_NURSE_ACK

    def test_ready_for_nurse_from_denied(self, case):
        """DOCTOR_DENIED → WAIT_NURSE_ACK."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()
        case.doctor_decide(decision="deny")
        case.save()

        case.ready_for_nurse()
        case.save()
        assert case.status == CaseStatus.WAIT_NURSE_ACK

    def test_nurse_ack(self, case):
        """WAIT_NURSE_ACK → CLEANED."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()
        case.doctor_decide(decision="accept")
        case.save()
        case.ready_for_nurse()
        case.save()

        case.nurse_ack()
        case.save()
        assert case.status == CaseStatus.CLEANED

    def test_administratively_close_from_wait_doctor(self, case):
        """WAIT_DOCTOR → CLEANED via administratively_close."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=True)
        case.save()
        case.llm1_complete(success=True)
        case.save()
        case.llm2_complete(success=True)
        case.save()

        case.administratively_close(user=None)
        case.save()
        assert case.status == CaseStatus.CLEANED

    def test_administratively_close_from_new(self, case):
        """NEW → CLEANED via administratively_close."""
        case.administratively_close(user=None)
        case.save()
        assert case.status == CaseStatus.CLEANED

    def test_administratively_close_from_failed(self, case):
        """FAILED → CLEANED via administratively_close."""
        case.start_extraction()
        case.save()
        case.extraction_complete(success=False)
        case.save()
        assert case.status == CaseStatus.FAILED

        case.administratively_close(user=None)
        case.save()
        assert case.status == CaseStatus.CLEANED

    def test_invalid_transition_raises_error(self, case):
        """Transitioning from wrong state raises TransitionNotAllowed."""
        # Case is in NEW, cannot doctor_decide
        with pytest.raises(TransitionNotAllowed):
            case.doctor_decide(decision="accept")

    def test_nurse_ack_from_wrong_state_raises_error(self, case):
        """nurse_ack from NEW raises TransitionNotAllowed."""
        with pytest.raises(TransitionNotAllowed):
            case.nurse_ack()
