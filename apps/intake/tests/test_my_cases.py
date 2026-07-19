"""Tests for my_cases list view."""

from typing import Any

import pytest
from django.urls import reverse

from apps.cases.models import Case

pytestmark = pytest.mark.django_db


class TestMyCasesShowsAllNonCleaned:
    """RED: criar 3 casos → listagem mostra 3."""

    def test_shows_all_non_cleaned_cases(self, client: Any, authenticated_nurse: Any, nurse_user: Any) -> None:
        for i in range(3):
            Case.objects.create(created_by=nurse_user)

        url = reverse("intake:my_cases")
        response = client.get(url)

        assert response.status_code == 200
        assert Case.objects.exclude(status="CLEANED").count() == 3

    def test_excludes_cleaned_cases(self, client: Any, authenticated_nurse: Any, nurse_user: Any) -> None:
        from apps.cases.models import CaseStatus

        case = Case.objects.create(created_by=nurse_user)
        # Use update() which bypasses FSM protection
        Case.objects.filter(pk=case.pk).update(status=CaseStatus.CLEANED.value)

        url = reverse("intake:my_cases")
        response = client.get(url)

        assert response.status_code == 200
        assert Case.objects.filter(status=CaseStatus.CLEANED.value).count() == 1
        assert Case.objects.exclude(status=CaseStatus.CLEANED.value).count() == 0

    def test_filter_by_status(self, client: Any, authenticated_nurse: Any, nurse_user: Any) -> None:
        Case.objects.create(created_by=nurse_user)  # NEW
        from apps.cases.models import CaseStatus

        case2 = Case.objects.create(created_by=nurse_user)
        Case.objects.filter(pk=case2.pk).update(status=CaseStatus.WAIT_DOCTOR)

        url = reverse("intake:my_cases") + "?status=WAIT_DOCTOR"
        response = client.get(url)

        assert response.status_code == 200

    def test_search_by_agency_record_number(self, client: Any, authenticated_nurse: Any, nurse_user: Any) -> None:
        Case.objects.create(created_by=nurse_user, agency_record_number="REG-12345")
        Case.objects.create(created_by=nurse_user, agency_record_number="REG-67890")

        url = reverse("intake:my_cases") + "?q=REG-12345"
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert "REG-12345" in content
