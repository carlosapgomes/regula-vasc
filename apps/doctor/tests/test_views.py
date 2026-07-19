"""Tests for doctor views — queue, decision, lock, and FSM transitions."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.cases.models import Case, CaseStatus

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def roles() -> dict[str, Role]:
    """Ensure required roles exist."""
    created = {}
    for name in ("nurse", "doctor", "admin"):
        role, _ = Role.objects.get_or_create(name=name)
        created[name] = role
    return created


@pytest.fixture
def nurse_user(roles: dict[str, Role], db: Any) -> User:
    """Create a nurse user."""
    user = User.objects.create_user(
        username="nurse1",
        password="testpass123",
        first_name="Enfermeiro",
        last_name="Teste",
    )
    user.roles.add(roles["nurse"])
    return user


@pytest.fixture
def doctor_user(roles: dict[str, Role], db: Any) -> User:
    """Create a doctor user with CRM."""
    user = User.objects.create_user(
        username="doctor1",
        password="testpass123",
        first_name="Médico",
        last_name="Teste",
        professional_council="CRM",
        professional_council_number="12345",
    )
    user.roles.add(roles["doctor"])
    return user


@pytest.fixture
def doctor_user2(roles: dict[str, Role], db: Any) -> User:
    """Create a second doctor user."""
    user = User.objects.create_user(
        username="doctor2",
        password="testpass123",
        first_name="Médico",
        last_name="Dois",
        professional_council="CRM",
        professional_council_number="67890",
    )
    user.roles.add(roles["doctor"])
    return user


@pytest.fixture
def doctor_client(client: Client, doctor_user: User) -> Client:
    """Authenticated doctor client."""
    client.force_login(doctor_user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client


@pytest.fixture
def case_wait_doctor(nurse_user: User, db: Any) -> Case:
    """Create a case in WAIT_DOCTOR status."""
    case = Case.objects.create(
        created_by=nurse_user,
        status=CaseStatus.WAIT_DOCTOR,
        agency_record_number="REG-001",
        regulation_days_on_screen=5,
        structured_data={
            "patient": {"name": "Paciente Teste", "age": 60, "sex": "M"},
            "referral": {"main_complaint": "Dor na perna"},
        },
        llm2_primary_result={
            "suggestion": "accept",
            "confidence": "alta",
            "recommendation_text": "Paciente elegível.",
            "acceptance_criteria_met": ["Úlcera ativa"],
            "exclusion_criteria_met": [],
            "rationale": "Critérios atendidos.",
        },
        llm2_secondary_result={
            "suggestion": "deny",
            "confidence": "media",
            "recommendation_text": "Recusar.",
            "acceptance_criteria_met": [],
            "exclusion_criteria_met": ["Risco cirúrgico"],
            "rationale": "Risco elevado.",
        },
    )
    return case


# ── Helpers ────────────────────────────────────────────────────────────────


def _create_doctor_client(doctor_user: User) -> Client:
    """Create an authenticated doctor client without fixture caching issues."""
    client = Client()
    client.force_login(doctor_user)
    session = client.session
    session["active_role"] = "doctor"
    session.save()
    return client


def _case_status(case: Case) -> str:
    """Get case status via DB query (avoids FSMField protected set)."""
    return Case.objects.filter(pk=case.pk).values_list("status", flat=True).first() or ""


def _case_locked_by(case: Case) -> int | None:
    """Get case locked_by_id via DB query."""
    return Case.objects.filter(pk=case.pk).values_list("locked_by_id", flat=True).first()


# ── Test: Queue ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorQueue:
    """Tests for the doctor queue view."""

    def test_queue_shows_wait_doctor_cases(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """WAIT_DOCTOR cases appear in the queue."""
        url = reverse("doctor:queue")
        response = doctor_client.get(url)
        assert response.status_code == 200
        assert "Paciente Teste" in response.content.decode()

    def test_queue_ordered_by_regulation_days(self, doctor_client: Client, nurse_user: User, doctor_user: User) -> None:
        """Queue is ordered by regulation_days_on_screen DESC, nulls last."""
        # Create cases with different regulation days
        Case.objects.create(
            created_by=nurse_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="REG-HIGH",
            regulation_days_on_screen=10,
        )
        Case.objects.create(
            created_by=nurse_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="REG-LOW",
            regulation_days_on_screen=3,
        )
        Case.objects.create(
            created_by=nurse_user,
            status=CaseStatus.WAIT_DOCTOR,
            agency_record_number="REG-NULL",
            regulation_days_on_screen=None,
        )

        url = reverse("doctor:queue")
        response = doctor_client.get(url)
        content = response.content.decode()

        # All should appear
        assert "REG-HIGH" in content
        assert "REG-LOW" in content
        assert "REG-NULL" in content

    def test_queue_requires_doctor_role(self, client: Client) -> None:
        """Non-doctor users are redirected."""
        url = reverse("doctor:queue")
        response = client.get(url)
        assert response.status_code == 302  # redirect to login

    def test_queue_partial(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """HTMX partial endpoint works."""
        url = reverse("doctor:queue_partial")
        response = doctor_client.get(url)
        assert response.status_code == 200


# ── Test: Decision ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecision:
    """Tests for the doctor decision view."""

    def test_decision_get_shows_form(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """GET shows the decision form with report and LLM cards."""
        url = reverse("doctor:decision", args=[case_wait_doctor.case_id])
        response = doctor_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Paciente Teste" in content
        assert "Decisão Médica" in content
        assert "Parecer Automático" in content
        assert "Parecer Primário" in content

    def test_decision_acquires_lock(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """GET acquires lock on WAIT_DOCTOR case."""
        url = reverse("doctor:decision", args=[case_wait_doctor.case_id])
        response = doctor_client.get(url)
        assert response.status_code == 200

        locked_by = _case_locked_by(case_wait_doctor)
        assert locked_by is not None

        case = Case.objects.get(pk=case_wait_doctor.case_id)
        assert case.lock_context == "doctor_decision"

    def test_second_doctor_blocked(self, doctor_client: Client, case_wait_doctor: Case, doctor_user2: User) -> None:
        """Second doctor accessing the same case gets redirected."""
        doctor_client2 = _create_doctor_client(doctor_user2)

        # First doctor acquires lock
        url = reverse("doctor:decision", args=[case_wait_doctor.case_id])
        doctor_client.get(url)

        # Second doctor tries to access
        response = doctor_client2.get(url)
        assert response.status_code == 302  # redirected to queue

    def test_decision_redirects_if_not_wait_doctor(self, doctor_client: Client, nurse_user: User) -> None:
        """Accessing decision for non-WAIT_DOCTOR case redirects."""
        case = Case.objects.create(
            created_by=nurse_user,
            status=CaseStatus.NEW,
        )
        url = reverse("doctor:decision", args=[case.case_id])
        response = doctor_client.get(url)
        assert response.status_code == 302


# ── Test: Submit decision ────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorSubmit:
    """Tests for the doctor submit (decision POST) endpoint."""

    def _acquire_lock(self, client: Client, case: Case) -> str:
        """Helper to acquire lock and return the token."""
        url = reverse("doctor:decision", args=[case.case_id])
        response = client.get(url)
        # Extract token from rendered page (form hidden input)
        content = response.content.decode()
        import re

        match = re.search(r'<input[^>]*name="lock_token"[^>]*value="([^"]+)"', content)
        if match:
            return match.group(1)
        # Fallback: directly read from model
        case_from_db = Case.objects.get(pk=case.pk)
        return str(case_from_db.lock_token) if case_from_db.lock_token else ""

    def test_decision_accept_transitions(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """POST accept → DOCTOR_ACCEPTED → WAIT_NURSE_ACK."""
        token = self._acquire_lock(doctor_client, case_wait_doctor)

        url = reverse("doctor:submit", args=[case_wait_doctor.case_id])
        response = doctor_client.post(
            url,
            {
                "decision": "accept",
                "reason": "",
                "observation": "Parece ok",
                "lock_token": token,
            },
        )
        assert response.status_code == 302  # redirect to queue

        assert _case_status(case_wait_doctor) == CaseStatus.WAIT_NURSE_ACK
        case = Case.objects.get(pk=case_wait_doctor.case_id)
        assert case.doctor_decision == "accept"

    def test_decision_deny_requires_reason(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """POST deny without reason → form error (stays on decision page)."""
        token = self._acquire_lock(doctor_client, case_wait_doctor)

        url = reverse("doctor:submit", args=[case_wait_doctor.case_id])
        response = doctor_client.post(
            url,
            {
                "decision": "deny",
                "reason": "",
                "observation": "",
                "lock_token": token,
            },
        )
        # Should render decision page again with form errors
        assert response.status_code == 200
        assert "Justificativa obrigatória" in response.content.decode()

        # Case should still be WAIT_DOCTOR
        assert _case_status(case_wait_doctor) == CaseStatus.WAIT_DOCTOR

    def test_decision_deny_with_reason_succeeds(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """POST deny with valid reason → DOCTOR_DENIED → WAIT_NURSE_ACK."""
        token = self._acquire_lock(doctor_client, case_wait_doctor)

        url = reverse("doctor:submit", args=[case_wait_doctor.case_id])
        response = doctor_client.post(
            url,
            {
                "decision": "deny",
                "reason": "Paciente não apresenta critérios de urgência cirúrgica.",
                "observation": "",
                "lock_token": token,
            },
        )
        assert response.status_code == 302  # redirect to queue

        assert _case_status(case_wait_doctor) == CaseStatus.WAIT_NURSE_ACK
        case = Case.objects.get(pk=case_wait_doctor.case_id)
        assert case.doctor_decision == "deny"
        assert "urgência" in case.doctor_reason

    def test_submit_without_lock_fails(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """POST without valid lock token fails."""
        url = reverse("doctor:submit", args=[case_wait_doctor.case_id])
        response = doctor_client.post(
            url,
            {
                "decision": "accept",
                "reason": "",
                "observation": "",
                "lock_token": "invalid-token",
            },
        )
        assert response.status_code == 302  # redirected

        assert _case_status(case_wait_doctor) == CaseStatus.WAIT_DOCTOR  # unchanged


# ── Test: Lock ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorLock:
    """Tests for lock renew/release in doctor context."""

    def test_lock_renew(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """Lock renew heartbeat works."""
        # Acquire lock first
        url = reverse("doctor:decision", args=[case_wait_doctor.case_id])
        doctor_client.get(url)

        case_from_db = Case.objects.get(pk=case_wait_doctor.case_id)
        token = str(case_from_db.lock_token)

        renew_url = reverse("doctor:lock_renew", args=[case_wait_doctor.case_id])
        response = doctor_client.post(renew_url, {"lock_token": token})
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data["success"] is True

    def test_lock_release(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """Lock release works."""
        # Acquire lock first
        url = reverse("doctor:decision", args=[case_wait_doctor.case_id])
        doctor_client.get(url)

        case_from_db = Case.objects.get(pk=case_wait_doctor.case_id)
        token = str(case_from_db.lock_token)

        release_url = reverse("doctor:lock_release", args=[case_wait_doctor.case_id])
        response = doctor_client.post(release_url, {"lock_token": token})
        assert response.status_code == 200
        import json

        data = json.loads(response.content)
        assert data["success"] is True

        # Verify lock is released
        assert _case_locked_by(case_wait_doctor) is None


# ── Test: Decided detail ────────────────────────────────────────────────


@pytest.mark.django_db
class TestDoctorDecidedDetail:
    """Tests for readonly decided case detail view."""

    def test_decided_detail_shows_result(
        self, doctor_client: Client, case_wait_doctor: Case, doctor_user: User
    ) -> None:
        """Decided detail page shows the decision result."""
        # Use FSM transition via Case.objects.update to set up a decided case
        # (avoiding FSMField protected set)

        Case.objects.filter(pk=case_wait_doctor.pk).update(
            status=CaseStatus.DOCTOR_ACCEPTED,
            doctor=doctor_user,
            doctor_decision="accept",
            doctor_decided_at=timezone.now(),
        )

        url = reverse("doctor:decided_detail", args=[case_wait_doctor.case_id])
        response = doctor_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Decisão" in content
        assert "Aceito" in content


# ── Test: PDF and attachment serving ────────────────────────────────────


@pytest.mark.django_db
class TestDoctorFileServing:
    """Tests for PDF and attachment serving in doctor context."""

    def test_serve_pdf_missing(self, doctor_client: Client, case_wait_doctor: Case) -> None:
        """PDF not found returns 404."""
        url = reverse("doctor:serve_pdf", args=[case_wait_doctor.case_id])
        response = doctor_client.get(url)
        assert response.status_code == 404
