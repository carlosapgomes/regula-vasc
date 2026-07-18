"""Tests for accounts views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestLoginView:
    """Tests for the login view."""

    def test_login_page_renders(self, client) -> None:
        """GET /login/ returns 200 and renders login form."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "entrar" in content.lower() or "login" in content.lower()

    def test_login_success(self, client) -> None:
        """POST valid credentials → redirect 302."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nurse@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nurse")
        user.roles.add(role)

        response = client.post(
            reverse("login"),
            {"username": "nurse@test.com", "password": "testpass123"},
        )

        assert response.status_code == 302

    def test_login_failure(self, client) -> None:
        """POST invalid credentials → 200 with error."""
        User.objects.create_user(username="real@test.com", password="correct123")

        response = client.post(
            reverse("login"),
            {"username": "real@test.com", "password": "wrongpass"},
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "inválid" in content.lower() or "alert-danger" in content.lower()

    def test_login_multiple_roles_redirects_to_switch(self, client) -> None:
        """User with multiple roles is redirected to /switch-role/."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role_nurse, _ = Role.objects.get_or_create(name="nurse")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role_nurse, role_doctor)

        response = client.post(
            reverse("login"),
            {"username": "multi@test.com", "password": "testpass123"},
        )

        assert response.status_code == 302
        assert response.url == reverse("switch_role")

    def test_login_single_role_auto_select(self, client) -> None:
        """User with exactly 1 role has active_role set in session."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="single@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)

        response = client.post(
            reverse("login"),
            {"username": "single@test.com", "password": "testpass123"},
        )

        assert response.status_code == 302
        assert response.url == "/"
        assert client.session["active_role"] == "doctor"

    def test_login_user_without_roles_redirects_to_switch(self, client) -> None:
        """User with no roles redirects to switch-role."""
        User.objects.create_user(username="norole@test.com", password="testpass123")

        response = client.post(
            reverse("login"),
            {"username": "norole@test.com", "password": "testpass123"},
        )

        assert response.status_code == 302
        assert response.url == reverse("switch_role")


@pytest.mark.django_db
class TestLogoutView:
    """Tests for the logout view."""

    def test_logout_redirects_to_login(self, client) -> None:
        """POST /logout/ logs out and redirects to /login/."""
        user = User.objects.create_user(username="logout@test.com", password="testpass123")
        client.force_login(user)

        response = client.post(reverse("logout"))

        assert response.status_code == 302
        assert response.url == reverse("login")


@pytest.mark.django_db
class TestSwitchRoleView:
    """Tests for the switch-role view."""

    def test_switch_role_page_renders(self, client) -> None:
        """GET /switch-role/ renders role selection page."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="switch@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        response = client.get(reverse("switch_role"))

        assert response.status_code == 200

    def test_switch_role_changes_active_role(self, client) -> None:
        """POST switch_role → session['active_role'] updated."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="valid@test.com", password="testpass123")
        role_nurse, _ = Role.objects.get_or_create(name="nurse")
        role_doctor, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role_nurse, role_doctor)
        client.force_login(user)

        response = client.post(reverse("switch_role"), {"role": "nurse"})

        assert response.status_code == 302
        assert response.url == "/"
        assert client.session["active_role"] == "nurse"

    def test_switch_role_invalid_role(self, client) -> None:
        """POST with role not assigned to user rejects."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="invalid@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)
        client.force_login(user)

        response = client.post(reverse("switch_role"), {"role": "nurse"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "inválido" in content.lower() or "erro" in content.lower()

    def test_switch_role_requires_login(self, client) -> None:
        """GET /switch-role/ without auth redirects to login."""
        response = client.get(reverse("switch_role"))

        assert response.status_code == 302
        assert "login" in response.url
