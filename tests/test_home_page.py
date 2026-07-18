"""Tests for the home/landing page."""

import pytest
from django.test import Client
from django.test.utils import override_settings


def test_home_page_redirects_to_login_when_unauthenticated(client: Client) -> None:
    """Home page at / redirects to login when not authenticated."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_home_page_returns_200_for_authenticated_user(client: Client) -> None:
    """Home page at / returns 200 for authenticated user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="testpass123")

    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name="nurse")
    user.roles.add(role)

    client.force_login(user)
    session = client.session
    session["active_role"] = "nurse"
    session.save()

    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_pwa_meta_tags_present_in_base(client: Client) -> None:
    """base.html includes required PWA meta tags."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="testuser2", password="testpass123")

    from apps.accounts.models import Role

    role, _ = Role.objects.get_or_create(name="nurse")
    user.roles.add(role)

    client.force_login(user)
    session = client.session
    session["active_role"] = "nurse"
    session.save()

    response = client.get("/")
    content = response.content.decode("utf-8")
    assert 'name="viewport"' in content
    assert 'name="theme-color"' in content
    assert 'name="apple-mobile-web-app-capable"' in content
    assert 'content="yes"' in content


@override_settings(DEBUG=True)
def test_static_files_served(client: Client) -> None:
    """Static files are accessible in DEBUG mode."""
    manifest_response = client.get("/static/manifest.json")
    assert manifest_response.status_code == 200
    css_response = client.get("/static/css/app.css")
    assert css_response.status_code == 200
