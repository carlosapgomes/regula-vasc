"""Tests for receipt confirmation (nurse_ack → CLEANED)."""

from typing import Any

import pytest
from django.urls import reverse

from apps.cases.models import Case, CaseStatus

pytestmark = pytest.mark.django_db


class TestConfirmReceipt:
    """RED: POST with lock → status CLEANED."""

    def test_confirm_receipt_transitions_to_cleaned(
        self, client: Any, authenticated_nurse: Any, waiting_nurse_case: Case
    ) -> None:
        """POST com lock → status CLEANED."""
        # First visit detail to acquire lock
        detail_url = reverse("intake:case_detail", args=[waiting_nurse_case.case_id])
        detail_response = client.get(detail_url)
        assert detail_response.status_code == 200

        # Re-fetch case to get lock token
        case = Case.objects.get(pk=waiting_nurse_case.pk)
        lock_token = str(case.lock_token) if case.lock_token else None
        assert lock_token is not None, "Lock should be acquired"

        # Confirm receipt
        confirm_url = reverse("intake:confirm_receipt", args=[case.case_id])
        response = client.post(confirm_url, {"lock_token": lock_token})

        assert response.status_code == 302
        # Re-fetch (cannot use refresh_from_db with django-fsm)
        updated = Case.objects.get(pk=case.pk)
        assert updated.status == CaseStatus.CLEANED
        assert updated.nurse_ack_by == authenticated_nurse

    def test_confirm_receipt_without_lock_fails(
        self, client: Any, authenticated_nurse: Any, waiting_nurse_case: Case
    ) -> None:
        """POST sem token → warning."""
        confirm_url = reverse("intake:confirm_receipt", args=[waiting_nurse_case.case_id])
        response = client.post(confirm_url, {})

        assert response.status_code == 302
        updated = Case.objects.get(pk=waiting_nurse_case.pk)
        assert updated.status != CaseStatus.CLEANED

    def test_confirm_wrong_status_fails(self, client: Any, authenticated_nurse: Any, created_case: Case) -> None:
        """Tentar confirmar caso em status errado."""
        confirm_url = reverse("intake:confirm_receipt", args=[created_case.case_id])
        response = client.post(confirm_url, {"lock_token": "some-token"})

        assert response.status_code == 302
        updated = Case.objects.get(pk=created_case.pk)
        assert updated.status != CaseStatus.CLEANED
