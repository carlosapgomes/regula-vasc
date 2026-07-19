"""Tests for Case lock service."""

import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.cases.models import Case, CaseStatus
from apps.cases.services import (
    assert_case_lock,
    claim_case_lock,
    expire_stale_locks_for_statuses,
    release_case_lock,
    renew_case_lock,
)

User = get_user_model()


@pytest.fixture
def nurse(db):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="nurse@test.com", password="pass123")
    role, _ = Role.objects.get_or_create(name="nurse")
    user.roles.add(role)
    return user


@pytest.fixture
def doctor(db):
    from apps.accounts.models import Role

    user = User.objects.create_user(username="doctor@test.com", password="pass123")
    role, _ = Role.objects.get_or_create(name="doctor")
    user.roles.add(role)
    return user


@pytest.fixture
def case(db, nurse):
    return Case.objects.create(created_by=nurse)


@pytest.fixture
def case_wait_doctor(db, nurse, case):
    """Move case to WAIT_DOCTOR."""
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


@pytest.mark.django_db
class TestClaimLock:
    """Tests for claim_case_lock."""

    def test_claim_lock_success(self, doctor, case_wait_doctor):
        """Claim lock on WAIT_DOCTOR case succeeds."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is True
        assert result.token is not None

    def test_claim_lock_wrong_status(self, doctor, case):
        """Claim lock on wrong status fails."""
        result = claim_case_lock(
            case_id=case.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is False
        assert "não está em" in result.reason

    def test_claim_lock_already_locked(self, doctor, case_wait_doctor):
        """Claim lock on already locked case fails for different user."""
        claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        # Different doctor tries
        other_doctor = User.objects.create_user(username="otherdoc@test.com", password="pass123")
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=other_doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.acquired is False
        assert "reservado" in result.reason

    def test_claim_lock_same_user_renews(self, doctor, case_wait_doctor):
        """Same user can renew their lock."""
        result1 = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result1.acquired is True

        result2 = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result2.acquired is True


@pytest.mark.django_db
class TestAssertLock:
    """Tests for assert_case_lock."""

    def test_assert_lock_valid(self, doctor, case_wait_doctor):
        """Assert valid lock passes."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        case = Case.objects.get(pk=case_wait_doctor.pk)
        assert result.token is not None
        # Should not raise
        assert_case_lock(case=case, user=doctor, token=result.token, context="doctor_decision")

    def test_assert_lock_wrong_token(self, doctor, case_wait_doctor):
        """Assert with wrong token raises PermissionError."""
        claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        case = Case.objects.get(pk=case_wait_doctor.pk)
        with pytest.raises(PermissionError):
            assert_case_lock(case=case, user=doctor, token=uuid.uuid4(), context="doctor_decision")

    def test_assert_lock_expired(self, doctor, case_wait_doctor):
        """Assert expired lock raises PermissionError."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=-1,  # Expired immediately
        )
        case = Case.objects.get(pk=case_wait_doctor.pk)
        assert result.token is not None
        with pytest.raises(PermissionError):
            assert_case_lock(case=case, user=doctor, token=result.token, context="doctor_decision")


@pytest.mark.django_db
class TestReleaseLock:
    """Tests for release_case_lock."""

    def test_release_lock_success(self, doctor, case_wait_doctor):
        """Release lock succeeds."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.token is not None
        released = release_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            token=result.token,
            context="doctor_decision",
        )
        assert released is True
        case = Case.objects.get(pk=case_wait_doctor.pk)
        assert case.locked_by is None

    def test_release_lock_wrong_user_fails(self, doctor, case_wait_doctor):
        """Release with wrong user fails."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        other = User.objects.create_user(username="other@test.com", password="pass123")
        assert result.token is not None
        released = release_case_lock(
            case_id=case_wait_doctor.case_id,
            user=other,
            token=result.token,
            context="doctor_decision",
        )
        assert released is False


@pytest.mark.django_db
class TestRenewLock:
    """Tests for renew_case_lock."""

    def test_renew_lock_success(self, doctor, case_wait_doctor):
        """Renew lock succeeds."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
        )
        assert result.token is not None
        renewed = renew_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            token=result.token,
            context="doctor_decision",
        )
        assert renewed.acquired is True

    def test_renew_expired_lock_fails(self, doctor, case_wait_doctor):
        """Renew expired lock fails."""
        result = claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=-1,
        )
        assert result.token is not None
        renewed = renew_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            token=result.token,
            context="doctor_decision",
        )
        assert renewed.acquired is False


@pytest.mark.django_db
class TestExpireStaleLocks:
    """Tests for expire_stale_locks_for_statuses."""

    def test_expire_stale_locks(self, doctor, case_wait_doctor):
        """Expire stale locks clears expired locks."""
        claim_case_lock(
            case_id=case_wait_doctor.case_id,
            user=doctor,
            expected_status=CaseStatus.WAIT_DOCTOR,
            context="doctor_decision",
            role="doctor",
            lease_seconds=-1,
        )
        count = expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])
        assert count == 1
        case = Case.objects.get(pk=case_wait_doctor.pk)
        assert case.locked_by is None

    def test_expire_stale_no_locks(self, doctor, case_wait_doctor):
        """No locks to expire returns 0."""
        count = expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])
        assert count == 0
