"""Tests for administrative closure from the dashboard."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.cases.models import Case, CaseEvent, CaseStatus


def _create_admin(**kwargs):
    admin_role, _ = Role.objects.get_or_create(name="admin")
    user = User.objects.create_user(
        username=kwargs.pop("username", "admin"),
        password=kwargs.pop("password", "admin123"),
        **kwargs,
    )
    user.roles.add(admin_role)
    return user


def _create_nurse(**kwargs):
    nurse_role, _ = Role.objects.get_or_create(name="nurse")
    user = User.objects.create_user(
        username=kwargs.pop("username", "nurse"),
        password=kwargs.pop("password", "nurse123"),
        **kwargs,
    )
    user.roles.add(nurse_role)
    return user


def _create_doctor(**kwargs):
    doctor_role, _ = Role.objects.get_or_create(name="doctor")
    user = User.objects.create_user(
        username=kwargs.pop("username", "doctor"),
        password=kwargs.pop("password", "doctor123"),
        **kwargs,
    )
    user.roles.add(doctor_role)
    return user


def _move_to_status(case, target_status):
    """Move a case through the FSM to desired status."""
    if target_status == CaseStatus.NEW:
        return case
    elif target_status == CaseStatus.WAIT_DOCTOR:
        case.start_extraction(user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.extraction_complete(success=True, user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.llm1_complete(success=True, user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.llm2_complete(success=True, user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        return case
    elif target_status == CaseStatus.FAILED:
        case.start_extraction(user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.extraction_complete(success=False, user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        return case
    elif target_status == CaseStatus.CLEANED:
        case = _move_to_status(case, CaseStatus.WAIT_DOCTOR)
        case.doctor_decide(decision="accept", user=case.created_by)
        case.doctor_decision = "accept"
        case.doctor_decided_at = timezone.now()
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.ready_for_nurse(user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.nurse_ack(user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        return case
    raise ValueError(f"Unsupported target: {target_status}")


class AdministrativeClosureTests(TestCase):
    """Test administrative closure from dashboard."""

    def setUp(self):
        self.admin = _create_admin()
        self.nurse = _create_nurse()
        self.doctor = _create_doctor()
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()

    def _create_case_in_status(self, status=CaseStatus.NEW):
        case = Case.objects.create(
            status=CaseStatus.NEW,
            created_by=self.nurse,
            structured_data={"patient": {"name": "Paciente Admin Close", "age": "60"}},
        )
        if status != CaseStatus.NEW:
            case = _move_to_status(case, status)
        return case

    def test_administrative_close_from_wait_doctor(self):
        """POST from WAIT_DOCTOR → CLEANED, event registered."""
        case = self._create_case_in_status(status=CaseStatus.WAIT_DOCTOR)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "OTHER",
                "reason_text": "Paciente transferido para outro hospital.",
            },
            follow=True,
        )
        self.assertContains(response, "encerrado administrativamente")
        case = Case.objects.get(pk=case.case_id)
        self.assertEqual(case.status, CaseStatus.CLEANED)
        self.assertEqual(case.admin_closure_reason_code, "OTHER")
        self.assertIsNotNone(case.admin_closed_by)
        self.assertIsNotNone(case.admin_closed_at)

        # Check that a CaseEvent was created
        event = CaseEvent.objects.filter(case=case, event_type="CASE_ADMINISTRATIVELY_CLOSED").first()
        self.assertIsNotNone(event)
        if event:  # type narrowing
            self.assertEqual(event.actor, self.admin)

    def test_administrative_close_cleaned_rejected(self):
        """Try to close CLEANED case → error."""
        case = self._create_case_in_status(status=CaseStatus.CLEANED)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "DUPLICATE",
                "reason_text": "Caso duplicado.",
            },
            follow=True,
        )
        self.assertContains(response, "já está encerrado")

    def test_administrative_close_from_new(self):
        """Close from NEW state."""
        case = self._create_case_in_status(status=CaseStatus.NEW)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "DATA_ENTRY_ERROR",
                "reason_text": "Erro de cadastro.",
            },
            follow=True,
        )
        self.assertContains(response, "encerrado administrativamente")
        case = Case.objects.get(pk=case.case_id)
        self.assertEqual(case.status, CaseStatus.CLEANED)

    def test_administrative_close_from_failed(self):
        """Close from FAILED state."""
        case = self._create_case_in_status(status=CaseStatus.FAILED)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "OTHER",
                "reason_text": "Falha de processamento não recuperável.",
            },
            follow=True,
        )
        self.assertContains(response, "encerrado administrativamente")
        case = Case.objects.get(pk=case.case_id)
        self.assertEqual(case.status, CaseStatus.CLEANED)

    def test_administrative_close_requires_reason_code(self):
        """POST without reason_code → error."""
        case = self._create_case_in_status(status=CaseStatus.WAIT_DOCTOR)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "",
                "reason_text": "Motivo qualquer.",
            },
            follow=True,
        )
        self.assertContains(response, "Selecione um código de motivo")

    def test_administrative_close_requires_reason_text(self):
        """POST without reason_text → error."""
        case = self._create_case_in_status(status=CaseStatus.WAIT_DOCTOR)
        url = reverse("dashboard:administrative_close", args=[case.case_id])
        response = self.client.post(
            url,
            {
                "reason_code": "OTHER",
                "reason_text": "",
            },
            follow=True,
        )
        self.assertContains(response, "Descreva o motivo")
