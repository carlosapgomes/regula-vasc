"""Tests for case_detail view."""

from typing import Any

import pytest
from django.urls import reverse

from apps.cases.models import Case

pytestmark = pytest.mark.django_db


class TestCaseDetailShowsTimeline:
    """RED: verificar que eventos aparecem na página."""

    def test_timeline_shows_events(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        """Eventos devem aparecer na timeline."""
        url = reverse("intake:case_detail", args=[created_case.case_id])
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "Timeline" in content or "Caso criado" in content

    def test_cleaned_case_returns_404(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        """Caso CLEANED deve retornar 404 na rota operacional."""
        from apps.cases.models import CaseStatus

        Case.objects.filter(pk=created_case.pk).update(status=CaseStatus.CLEANED)
        url = reverse("intake:case_detail", args=[created_case.case_id])
        response = client.get(url)
        assert response.status_code == 404

    def test_stepper_shown(self, client: Any, authenticated_nurse: Any, waiting_doctor_case: Case) -> None:
        """Stepper deve aparecer no detalhe."""
        url = reverse("intake:case_detail", args=[waiting_doctor_case.case_id])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Upload" in content
        assert "Extração" in content
        assert "Avaliação Médica" in content
        assert "Resultado" in content

    def test_waiting_nurse_shows_confirm_button(
        self, client: Any, authenticated_nurse: Any, waiting_nurse_case: Case
    ) -> None:
        """WAIT_NURSE_ACK deve mostrar botão de confirmação."""
        url = reverse("intake:case_detail", args=[waiting_nurse_case.case_id])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Confirmar Recebimento" in content
