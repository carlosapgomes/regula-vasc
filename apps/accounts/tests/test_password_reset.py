"""Tests for password reset flow."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestLoginPageLinks:
    """Login page must link to password reset."""

    def test_login_page_links_to_password_reset(self, client) -> None:
        """GET /login/ contains link to password_reset."""
        response = client.get(reverse("login"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "password_reset" in content or "esqueci" in content.lower()


@pytest.mark.django_db
class TestPasswordResetPage:
    """Password reset form renders correctly."""

    def test_password_reset_page_renders(self, client) -> None:
        """GET password_reset returns 200 and renders form."""
        response = client.get(reverse("password_reset"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "email" in content.lower()

    def test_password_reset_email_sent(self, client) -> None:
        """POST email → email sent (mail.outbox in test)."""
        User.objects.create_user(
            username="exists@example.com",
            email="exists@example.com",
            password="oldpass123!",
        )

        response = client.post(
            reverse("password_reset"),
            {"email": "exists@example.com"},
        )
        assert response.status_code == 302
        done_url = reverse("password_reset_done")
        assert done_url in response.url

        # Email was sent
        assert len(mail.outbox) == 1
        assert "exists@example.com" in mail.outbox[0].to

    def test_password_reset_post_unknown_email_uses_same_response(self, client) -> None:
        """POST with unknown email: same redirect as existing email."""
        response = client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )
        assert response.status_code == 302
        done_url = reverse("password_reset_done")
        assert done_url in response.url

        # No email sent for unknown user
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestPasswordResetToken:
    """Token-based password change via native Django views."""

    def _get_reset_url_from_outbox(self, email_index=0):
        """Extract the password reset URL from the email body."""
        email_body: str = mail.outbox[email_index].body
        # Look for /reset/ path
        path_match = re.search(r"/reset/[^\s/]+/[^\s/]+/", email_body)
        if path_match:
            return path_match.group(0)
        return None

    def test_password_reset_token_allows_password_change(self, client) -> None:
        """Token-based reset allows setting a new password and logging in."""
        user = User.objects.create_user(
            username="resettoken@example.com",
            email="resettoken@example.com",
            password="oldpass123!",
        )

        # Request password reset
        client.post(reverse("password_reset"), {"email": "resettoken@example.com"})
        assert len(mail.outbox) == 1

        # Extract reset URL from email
        reset_path = self._get_reset_url_from_outbox()
        assert reset_path is not None, "No reset URL found in email"

        # GET the reset confirm page
        response = client.get(reset_path, follow=True)
        assert response.status_code == 200

        # POST new password at the confirm page
        confirm_path = response.redirect_chain[-1][0] if response.redirect_chain else reset_path
        response = client.post(
            confirm_path,
            {"new_password1": "NewStr0ng!Pass", "new_password2": "NewStr0ng!Pass"},
        )
        # Should redirect to password_reset_complete
        assert response.status_code == 302
        complete_url = reverse("password_reset_complete")
        assert complete_url in response.url

        # Login with new password works
        user.refresh_from_db()
        login_ok = client.login(username="resettoken@example.com", password="NewStr0ng!Pass")
        assert login_ok is True
