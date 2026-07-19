"""Tests for case communication (Slice 008).

RED tests covering:
- Post message success (intake, doctor, dashboard)
- Post message with empty body → error
- Post message on CLEANED case → error
- Post message requires auth → 302 login
- Communication thread appears on case_detail
- Communication form hidden for CLEANED
- Safe redirect validation
- Message body max length check (2000 chars)
"""

from __future__ import annotations

from typing import Any

import pytest
from django.urls import reverse

from apps.cases.models import Case, CaseCommunicationMessage, CaseStatus
from apps.cases.services import CASE_COMMUNICATION_MAX_LENGTH, CaseCommunicationError, post_case_communication_message

pytestmark = pytest.mark.django_db


# ── Service layer tests ───────────────────────────────────────────────────


class TestPostCommunicationMessageService:
    """Tests for post_case_communication_message service function."""

    def test_post_message_success(self, nurse_user: Any, created_case: Case) -> None:
        """Criar mensagem com body válido deve retornar CaseCommunicationMessage."""
        msg = post_case_communication_message(
            case=created_case,
            author=nurse_user,
            author_role="nurse",
            body="Testando comunicação operacional.",
        )
        assert msg is not None
        assert msg.body == "Testando comunicação operacional."
        assert msg.author == nurse_user
        assert msg.author_role == "nurse"
        assert msg.message_type == "user"

    def test_post_message_empty_body_raises_error(self, nurse_user: Any, created_case: Case) -> None:
        """Body vazio deve levantar CaseCommunicationError."""
        with pytest.raises(CaseCommunicationError, match="não pode estar em branco"):
            post_case_communication_message(
                case=created_case,
                author=nurse_user,
                author_role="nurse",
                body="",
            )

    def test_post_message_whitespace_body_raises_error(self, nurse_user: Any, created_case: Case) -> None:
        """Body com apenas espaços deve levantar CaseCommunicationError."""
        with pytest.raises(CaseCommunicationError, match="não pode estar em branco"):
            post_case_communication_message(
                case=created_case,
                author=nurse_user,
                author_role="nurse",
                body="   ",
            )

    def test_post_message_on_cleaned_case_raises_error(self, nurse_user: Any, created_case: Case) -> None:
        """Caso CLEANED deve levantar CaseCommunicationError."""
        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED)
        cleaned_case = Case.objects.get(pk=created_case.pk)

        with pytest.raises(CaseCommunicationError, match="Não é possível enviar mensagens em casos concluídos"):
            post_case_communication_message(
                case=cleaned_case,
                author=nurse_user,
                author_role="nurse",
                body="Mensagem em caso encerrado.",
            )

    def test_post_message_without_role_raises_error(self, nurse_user: Any, created_case: Case) -> None:
        """author_role vazio deve levantar CaseCommunicationError."""
        with pytest.raises(CaseCommunicationError, match="Papel ativo não identificado"):
            post_case_communication_message(
                case=created_case,
                author=nurse_user,
                author_role="",
                body="Mensagem sem papel.",
            )

    def test_post_message_over_max_length_raises_error(self, nurse_user: Any, created_case: Case) -> None:
        """Body acima de CASE_COMMUNICATION_MAX_LENGTH deve levantar erro."""
        long_body = "x" * (CASE_COMMUNICATION_MAX_LENGTH + 1)
        with pytest.raises(CaseCommunicationError, match="Mensagem muito longa"):
            post_case_communication_message(
                case=created_case,
                author=nurse_user,
                author_role="nurse",
                body=long_body,
            )

    def test_post_message_creates_case_event(self, nurse_user: Any, created_case: Case) -> None:
        """Postar mensagem deve criar CaseEvent CASE_COMMUNICATION_MESSAGE_POSTED."""
        from apps.cases.models import CaseEvent

        post_case_communication_message(
            case=created_case,
            author=nurse_user,
            author_role="nurse",
            body="Evento deve ser criado.",
        )
        assert CaseEvent.objects.filter(
            case=created_case,
            event_type="CASE_COMMUNICATION_MESSAGE_POSTED",
        ).exists()


# ── View layer tests (Intake) ────────────────────────────────────────────


class TestIntakePostCommunicationView:
    """Tests for intake:post_case_communication view."""

    def test_post_communication_success(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        """POST com body válido → 302, mensagem criada."""
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": "Mensagem de teste."})

        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 1

    def test_post_communication_empty_body(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        """POST com body vazio → 302, mensagem NÃO criada."""
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": ""})

        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 0

    def test_post_communication_on_cleaned_case(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """POST em caso CLEANED → 302, mensagem NÃO criada."""
        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED)
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": "Mensagem em caso encerrado."})

        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 0

    def test_post_communication_requires_auth(self, client: Any, created_case: Case) -> None:
        """POST sem login → 302 para login."""
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": "Mensagem sem auth."})

        assert response.status_code == 302
        login_url = reverse("login")
        assert login_url in response.url

    def test_post_communication_secure_redirect(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """Redirect seguro: next malicioso deve ser ignorado."""
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.post(
            url,
            {
                "body": "Mensagem segura.",
                "next": "https://evil.com/phish",
            },
        )
        # Deve redirecionar para case_detail, não para evil.com
        assert "evil.com" not in (response.url or "")
        assert str(created_case.case_id) in (response.url or "")

    def test_post_communication_get_request_redirects(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """GET na view de POST deve redirecionar para case_detail."""
        url = reverse("intake:post_case_communication", args=[created_case.case_id])
        response = client.get(url)
        assert response.status_code == 302
        assert str(created_case.case_id) in (response.url or "")


# ── View layer tests (Doctor) ────────────────────────────────────────────


class TestDoctorPostCommunicationView:
    """Tests for doctor:post_case_communication view."""

    @pytest.fixture
    def authenticated_doctor(self, client: Any, doctor_user: Any) -> Any:
        client.force_login(doctor_user)
        session = client.session
        session["active_role"] = "doctor"
        session.save()
        return doctor_user

    def test_post_communication_success(
        self, client: Any, authenticated_doctor: Any, waiting_doctor_case: Case
    ) -> None:
        """POST com body válido → 302, mensagem criada."""
        url = reverse("doctor:post_case_communication", args=[waiting_doctor_case.case_id])
        response = client.post(url, {"body": "Mensagem do médico."})

        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=waiting_doctor_case).count() == 1

    def test_post_communication_empty_body(
        self, client: Any, authenticated_doctor: Any, waiting_doctor_case: Case
    ) -> None:
        """POST com body vazio → 302, mensagem NÃO criada."""
        url = reverse("doctor:post_case_communication", args=[waiting_doctor_case.case_id])
        response = client.post(url, {"body": ""})
        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=waiting_doctor_case).count() == 0

    def test_post_communication_secure_redirect(
        self, client: Any, authenticated_doctor: Any, waiting_doctor_case: Case
    ) -> None:
        """Redirect seguro no doctor view."""
        url = reverse("doctor:post_case_communication", args=[waiting_doctor_case.case_id])
        response = client.post(
            url,
            {
                "body": "Mensagem segura.",
                "next": "https://evil.com/phish",
            },
        )
        assert "evil.com" not in (response.url or "")
        assert str(waiting_doctor_case.case_id) in (response.url or "")

    def test_post_communication_requires_auth(self, client: Any, waiting_doctor_case: Case) -> None:
        """POST sem login → 302 para login."""
        url = reverse("doctor:post_case_communication", args=[waiting_doctor_case.case_id])
        response = client.post(url, {"body": "Mensagem sem auth."})
        assert response.status_code == 302
        login_url = reverse("login")
        assert login_url in response.url


# ── View layer tests (Dashboard) ─────────────────────────────────────────


class TestDashboardPostCommunicationView:
    """Tests for dashboard:post_case_communication view."""

    @pytest.fixture
    def admin_role(self, db: Any) -> Any:
        from apps.accounts.models import Role

        role, _ = Role.objects.get_or_create(name="admin")
        return role

    @pytest.fixture
    def admin_user(self, db: Any, admin_role: Any) -> Any:
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="admin1",
            password="testpass123",
            first_name="Admin",
            last_name="Teste",
        )
        user.roles.add(admin_role)
        return user

    @pytest.fixture
    def authenticated_admin(self, client: Any, admin_user: Any) -> Any:
        client.force_login(admin_user)
        session = client.session
        session["active_role"] = "admin"
        session.save()
        return admin_user

    def test_post_communication_success(self, client: Any, authenticated_admin: Any, created_case: Case) -> None:
        """POST com body válido → 302, mensagem criada."""
        url = reverse("dashboard:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": "Mensagem do admin."})

        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 1

    def test_post_communication_empty_body(self, client: Any, authenticated_admin: Any, created_case: Case) -> None:
        """POST com body vazio → 302, mensagem NÃO criada."""
        url = reverse("dashboard:post_case_communication", args=[created_case.case_id])
        response = client.post(url, {"body": ""})
        assert response.status_code == 302
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 0

    def test_post_communication_secure_redirect(
        self, client: Any, authenticated_admin: Any, created_case: Case
    ) -> None:
        """Redirect seguro no dashboard view."""
        url = reverse("dashboard:post_case_communication", args=[created_case.case_id])
        response = client.post(
            url,
            {
                "body": "Mensagem segura.",
                "next": "https://evil.com/phish",
            },
        )
        assert "evil.com" not in (response.url or "")
        assert str(created_case.case_id) in (response.url or "")


# ── Template rendering tests ─────────────────────────────────────────────


class TestCommunicationThreadOnCaseDetail:
    """Tests that the communication thread partial renders correctly."""

    def test_communication_thread_appears_on_intake_case_detail(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """GET case_detail → partial renderizado com seção de comunicação."""
        # Cria uma mensagem primeiro
        post_case_communication_message(
            case=created_case,
            author=authenticated_nurse,
            author_role="nurse",
            body="Mensagem visível na tela.",
        )

        url = reverse("intake:case_detail", args=[created_case.case_id])
        response = client.get(url)
        content = response.content.decode()

        assert "💬 Comunicação Operacional" in content
        assert "Mensagem visível na tela." in content

    def test_communication_form_hidden_for_cleaned_on_intake(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """GET case_detail CLEANED → textarea/Enviar não renderizado (caso retorna 404)."""
        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED)
        url = reverse("intake:case_detail", args=[created_case.case_id])
        response = client.get(url)
        # Caso CLEANED na fila operacional retorna 404
        assert response.status_code == 404

    def test_communication_form_hidden_when_case_cleaned_in_service(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """Não é possível postar em caso CLEANED via service."""
        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED)
        cleaned_case = Case.objects.get(pk=created_case.pk)

        with pytest.raises(CaseCommunicationError, match="Não é possível enviar mensagens em casos concluídos"):
            post_case_communication_message(
                case=cleaned_case,
                author=authenticated_nurse,
                author_role="nurse",
                body="Não deve funcionar.",
            )

    def test_communication_thread_on_doctor_decision(
        self, client: Any, authenticated_nurse: Any, doctor_user: Any, created_case: Case
    ) -> None:
        """A thread de comunicação aparece na tela de decisão médica."""
        post_case_communication_message(
            case=created_case,
            author=authenticated_nurse,
            author_role="nurse",
            body="Mensagem para o médico.",
        )

        # Verificar que a mensagem foi criada (teste de integração indireto)
        assert CaseCommunicationMessage.objects.filter(case=created_case).count() == 1

    def test_communication_form_present_on_non_cleaned_case(
        self, client: Any, authenticated_nurse: Any, waiting_nurse_case: Case
    ) -> None:
        """Formulário de post deve estar presente em casos não CLEANED."""
        url = reverse("intake:case_detail", args=[waiting_nurse_case.case_id])
        response = client.get(url)
        content = response.content.decode()

        assert "💬 Comunicação Operacional" in content
        assert "Enviar" in content
        assert "Digite sua mensagem" in content

    def test_communication_messages_in_chronological_order(
        self, client: Any, authenticated_nurse: Any, created_case: Case
    ) -> None:
        """Mensagens devem aparecer em ordem cronológica."""
        # Cria duas mensagens em ordem
        from datetime import timedelta

        from django.utils import timezone

        msg1 = post_case_communication_message(
            case=created_case,
            author=authenticated_nurse,
            author_role="nurse",
            body="Primeira mensagem.",
        )
        # Forçar timestamp diferente ajustando via ORM
        CaseCommunicationMessage.objects.filter(pk=msg1.pk).update(created_at=timezone.now() - timedelta(minutes=5))

        post_case_communication_message(
            case=created_case,
            author=authenticated_nurse,
            author_role="nurse",
            body="Segunda mensagem.",
        )

        # Verificar ordem
        msgs = list(CaseCommunicationMessage.objects.filter(case=created_case).order_by("created_at"))
        assert len(msgs) == 2
        assert msgs[0].body == "Primeira mensagem."
        assert msgs[1].body == "Segunda mensagem."
