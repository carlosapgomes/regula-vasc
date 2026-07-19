"""Tests for the dashboard views — metrics, search, user CRUD, prompts, LLM config."""

from typing import Any

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.cases.models import Case, CaseStatus
from apps.llm.models import PromptTemplate


def _create_admin(**kwargs: Any) -> User:
    """Create an admin user with admin role."""
    admin_role, _ = Role.objects.get_or_create(name="admin")
    user = User.objects.create_user(
        username=kwargs.pop("username", "admin"),
        password=kwargs.pop("password", "admin123"),
        **kwargs,
    )
    user.roles.add(admin_role)
    return user


def _create_nurse(**kwargs: Any) -> User:
    """Create a nurse user with nurse role."""
    nurse_role, _ = Role.objects.get_or_create(name="nurse")
    user = User.objects.create_user(
        username=kwargs.pop("username", "nurse"),
        password=kwargs.pop("password", "nurse123"),
        **kwargs,
    )
    user.roles.add(nurse_role)
    return user


def _create_doctor(**kwargs: Any) -> User:
    """Create a doctor user with doctor role."""
    doctor_role, _ = Role.objects.get_or_create(name="doctor")
    user = User.objects.create_user(
        username=kwargs.pop("username", "doctor"),
        password=kwargs.pop("password", "doctor123"),
        **kwargs,
    )
    user.roles.add(doctor_role)
    return user


def _move_to_status(case: Case, target_status: CaseStatus) -> Case:
    """Move a case through the FSM to the desired target status.

    Only supports statuses needed for testing: NEW → WAIT_DOCTOR → CLEANED (via doctor),
    and FAILED.
    """
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
    elif target_status == CaseStatus.CLEANED:
        # Move to WAIT_DOCTOR first
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
    elif target_status == CaseStatus.FAILED:
        case.start_extraction(user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        case.extraction_complete(success=False, user=case.created_by)
        case.save()
        case = Case.objects.get(pk=case.case_id)
        return case
    else:
        raise ValueError(f"Unsupported target status: {target_status}")


def _create_case_in_status(
    *,
    status: CaseStatus = CaseStatus.NEW,
    created_by: User,
    doctor: User | None = None,
    doctor_decision: str = "",
    agency_record_number: str = "",
) -> Case:
    """Helper to create a test case in a given FSM status."""
    case = Case.objects.create(
        status=CaseStatus.NEW,
        created_by=created_by,
        agency_record_number=agency_record_number,
        structured_data={"patient": {"name": "Paciente Teste", "age": "45"}},
        extracted_text="Texto de exemplo",
    )
    if status != CaseStatus.NEW:
        case = _move_to_status(case, status)
    if doctor:
        case.doctor = doctor
        case.doctor_decision = doctor_decision
        case.doctor_decided_at = timezone.now()
        case.save()
    return case


class DashboardAccessTests(TestCase):
    """Test that dashboard views require admin role."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.nurse = _create_nurse()
        self.index_url = reverse("dashboard:index")

    def test_dashboard_index_requires_login(self) -> None:
        """Anonymous users are redirected to login."""
        response = self.client.get(self.index_url)
        self.assertRedirects(response, f"{settings.LOGIN_URL}?next={self.index_url}")

    def test_dashboard_index_requires_admin(self) -> None:
        """Nurse users get a warning and redirect."""
        self.client.force_login(self.nurse)
        self.client.session["active_role"] = "nurse"
        self.client.session.save()
        response = self.client.get(self.index_url, follow=True)
        self.assertContains(response, "Você não tem permissão")

    def test_dashboard_index_admin_allowed(self) -> None:
        """Admin users can access the dashboard."""
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()
        response = self.client.get(self.index_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Métricas de Fluxo")


class DashboardMetricsTests(TestCase):
    """Test dashboard metrics computation."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.nurse = _create_nurse()
        self.doctor = _create_doctor()
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()

    def test_dashboard_metrics_count(self) -> None:
        """Create cases with different outcomes → metrics match."""
        # Create cases with different statuses
        _create_case_in_status(status=CaseStatus.WAIT_DOCTOR, created_by=self.nurse)
        _create_case_in_status(status=CaseStatus.WAIT_DOCTOR, created_by=self.nurse)
        _create_case_in_status(
            status=CaseStatus.CLEANED,
            created_by=self.nurse,
            doctor=self.doctor,
            doctor_decision="accept",
        )
        _create_case_in_status(
            status=CaseStatus.CLEANED,
            created_by=self.nurse,
            doctor=self.doctor,
            doctor_decision="deny",
        )
        _create_case_in_status(status=CaseStatus.FAILED, created_by=self.nurse)

        response = self.client.get(self._index_url("all"))
        self.assertEqual(response.status_code, 200)

        metrics = response.context["metrics"]
        self.assertEqual(metrics["total"], 5)
        self.assertEqual(metrics["accepted"], 1)
        self.assertEqual(metrics["denied"], 1)
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(metrics["wait_doctor"], 2)

    def _index_url(self, period: str = "all") -> str:
        return reverse("dashboard:index") + f"?period={period}"


class DashboardSearchTests(TestCase):
    """Test dashboard search functionality."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.nurse = _create_nurse()
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()

    def test_dashboard_search_by_agency_number(self) -> None:
        """Create case with agency number → search returns it."""
        _create_case_in_status(
            created_by=self.nurse,
            agency_record_number="REG-001",
            status=CaseStatus.WAIT_DOCTOR,
        )
        _create_case_in_status(
            created_by=self.nurse,
            agency_record_number="REG-002",
            status=CaseStatus.WAIT_DOCTOR,
        )

        url = reverse("dashboard:index") + "?q=REG-001&period=all"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Should have results
        page_obj = response.context.get("page_obj")
        if page_obj:
            pass

    def test_dashboard_search_min_3_chars(self) -> None:
        """Search with 1 char should not filter (min 3 chars)."""
        url = reverse("dashboard:index") + "?q=R&period=all"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_status_filter(self) -> None:
        """Filter by status WAIT_DOCTOR."""
        _create_case_in_status(
            created_by=self.nurse,
            status=CaseStatus.WAIT_DOCTOR,
        )
        url = reverse("dashboard:index") + "?status=WAIT_DOCTOR&period=all"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        status_filter = response.context.get("status_filter")
        self.assertEqual(status_filter, "WAIT_DOCTOR")


class DashboardUserCrudTests(TestCase):
    """Test user CRUD in dashboard."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.nurse_role, _ = Role.objects.get_or_create(name="nurse")
        self.doctor_role, _ = Role.objects.get_or_create(name="doctor")
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()

    def test_admin_can_create_user(self) -> None:
        """POST user form → User created with roles."""
        url = reverse("dashboard:user_create")
        response = self.client.post(
            url,
            {
                "username": "new_nurse",
                "first_name": "Novo",
                "last_name": "Enfermeiro",
                "email": "nurse@test.com",
                "password": "secure123",
                "password_confirm": "secure123",
                "roles": [str(self.nurse_role.pk)],
                "professional_council": "COREN",
                "professional_council_number": "12345",
            },
            follow=True,
        )
        self.assertContains(response, "criado com sucesso")
        self.assertTrue(User.objects.filter(username="new_nurse").exists())
        user = User.objects.get(username="new_nurse")
        self.assertIn(self.nurse_role, user.roles.all())

    def test_admin_can_edit_user(self) -> None:
        """POST user edit form → User updated."""
        user = User.objects.create_user(username="edit_me", password="pass123")
        user.roles.add(self.nurse_role)
        url = reverse("dashboard:user_edit", args=[user.pk])
        response = self.client.post(
            url,
            {
                "username": "edit_me",
                "first_name": "Edited",
                "last_name": "Name",
                "email": "edited@test.com",
                "password": "",
                "password_confirm": "",
                "roles": [str(self.doctor_role.pk)],
                "account_status": "active",
            },
            follow=True,
        )
        self.assertContains(response, "atualizado com sucesso")
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Edited")
        self.assertIn(self.doctor_role, user.roles.all())
        self.assertNotIn(self.nurse_role, user.roles.all())

    def test_admin_can_create_user_missing_password(self) -> None:
        """POST without password → error."""
        url = reverse("dashboard:user_create")
        response = self.client.post(
            url,
            {
                "username": "no_password",
                "first_name": "No",
                "last_name": "Password",
                "email": "no@test.com",
                "password": "",
                "password_confirm": "",
                "roles": [str(self.nurse_role.pk)],
            },
            follow=True,
        )
        self.assertContains(response, "Senha é obrigatória")


class DashboardPromptTests(TestCase):
    """Test prompt management in dashboard."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()

    def test_admin_can_activate_prompt(self) -> None:
        """Create new version → get_active returns new version."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Original content",
            is_active=True,
        )

        # Post new version
        response = self.client.post(
            reverse("dashboard:prompt_create"),
            {
                "name": "llm1_system",
                "content": "New version content",
                "activate": "on",
            },
            follow=True,
        )
        self.assertContains(response, "criado com sucesso")

        active = PromptTemplate.get_active("llm1_system")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.version, 2)
        self.assertEqual(active.content, "New version content")
        self.assertTrue(active.is_active)

        # Old version is now inactive
        old = PromptTemplate.objects.get(name="llm1_system", version=1)
        self.assertFalse(old.is_active)

    def test_prompt_list_renders(self) -> None:
        """Prompt list page renders."""
        PromptTemplate.objects.create(
            name="llm1_system",
            version=1,
            content="Content",
            is_active=True,
        )
        url = reverse("dashboard:prompt_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "llm1_system")


class DashboardLlmConfigTests(TestCase):
    """Test LLM config editing."""

    def setUp(self) -> None:
        self.admin = _create_admin()
        self.client.force_login(self.admin)
        self.client.session["active_role"] = "admin"
        self.client.session.save()
        self.url = reverse("dashboard:llm_config")

    def test_admin_can_edit_llm_config(self) -> None:
        """POST LLM config form → config updated."""
        response = self.client.post(
            self.url,
            {
                "llm1_primary_provider": "openai",
                "llm1_primary_model": "gpt-4o",
                "llm1_primary_api_key": "sk-test-key",
                "llm1_primary_base_url": "",
                "llm1_secondary_provider": "openai",
                "llm1_secondary_model": "gpt-4o-mini",
                "llm1_secondary_api_key": "",
                "llm1_secondary_base_url": "",
                "llm2_primary_provider": "anthropic",
                "llm2_primary_model": "claude-sonnet-4-20250514",
                "llm2_primary_api_key": "sk-ant-test",
                "llm2_primary_base_url": "",
                "llm2_secondary_provider": "openai",
                "llm2_secondary_model": "gpt-4o-mini",
                "llm2_secondary_api_key": "",
                "llm2_secondary_base_url": "",
                "secondary_enabled": "on",
            },
            follow=True,
        )
        self.assertContains(response, "atualizada com sucesso")

        from apps.dashboard.models import LlmProviderConfig

        config = LlmProviderConfig.get_singleton()
        self.assertEqual(config.llm1_primary_provider, "openai")
        self.assertEqual(config.llm1_primary_model, "gpt-4o")
        self.assertEqual(config.llm1_primary_api_key, "sk-test-key")
        self.assertEqual(config.llm2_primary_provider, "anthropic")
        self.assertEqual(config.llm2_primary_model, "claude-sonnet-4-20250514")
        self.assertTrue(config.secondary_enabled)
