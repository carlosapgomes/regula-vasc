"""Fixtures for intake tests."""

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.cases.models import Case


@pytest.fixture
def nurse_role(db: Any) -> Role:
    role, _ = Role.objects.get_or_create(name="nurse")
    return role


@pytest.fixture
def nurse_user(db: Any, nurse_role: Role) -> User:
    user = User.objects.create_user(
        username="nurse1",
        password="testpass123",
        first_name="Enfermeiro",
        last_name="Teste",
    )
    user.roles.add(nurse_role)
    return user


@pytest.fixture
def doctor_role(db: Any) -> Role:
    role, _ = Role.objects.get_or_create(name="doctor")
    return role


@pytest.fixture
def doctor_user(db: Any, doctor_role: Role) -> User:
    user = User.objects.create_user(
        username="doctor1",
        password="testpass123",
        first_name="Médico",
        last_name="Teste",
        professional_council="CRM",
        professional_council_number="12345",
    )
    user.roles.add(doctor_role)
    return user


def _pdf_content() -> bytes:
    return b"%PDF-1.4 fake pdf content for testing"


def _jpeg_content() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"


def make_pdf_file(name: str = "test.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=_pdf_content(),
        content_type="application/pdf",
    )


def make_jpeg_file(name: str = "test.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=_jpeg_content(),
        content_type="image/jpeg",
    )


def make_png_file(name: str = "test.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde",
        content_type="image/png",
    )


def make_docx_file(name: str = "test.docx") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"fake word content",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@pytest.fixture
def authenticated_nurse(client: Any, nurse_user: User) -> User:
    client.force_login(nurse_user)
    session = client.session
    session["active_role"] = "nurse"
    session.save()
    return nurse_user


@pytest.fixture
def created_case(db: Any, nurse_user: User) -> Case:
    """Create a Case in NEW status."""
    case = Case.objects.create(created_by=nurse_user)
    return case


@pytest.fixture
def waiting_doctor_case(db: Any, nurse_user: User) -> Case:
    """Create a Case in WAIT_DOCTOR status.

    Uses update() to bypass FSM (test setup only).
    """
    case = Case.objects.create(created_by=nurse_user)
    Case.objects.filter(pk=case.pk).update(status="WAIT_DOCTOR")
    return Case.objects.get(pk=case.pk)


@pytest.fixture
def waiting_nurse_case(db: Any, nurse_user: User, doctor_user: User) -> Case:
    """Create a Case in WAIT_NURSE_ACK status (decided by doctor)."""
    case = Case.objects.create(created_by=nurse_user)
    now = timezone.now()
    Case.objects.filter(pk=case.pk).update(
        status="WAIT_NURSE_ACK",
        doctor_id=doctor_user.pk,
        doctor_decision="accept",
        doctor_decided_at=now,
    )
    return Case.objects.get(pk=case.pk)
