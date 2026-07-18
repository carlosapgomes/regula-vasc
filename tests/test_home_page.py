"""Tests for the home/landing page."""

from django.test import Client
from django.test.utils import override_settings


def test_home_page_returns_200(client: Client) -> None:
    """R6: Home page at / returns 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_home_page_uses_base_template(client: Client) -> None:
    """R4+R6: Home page extends base.html with PWA meta tags."""
    response = client.get("/")
    assert "base.html" in [t.name for t in response.templates]


def test_pwa_meta_tags_present(client: Client) -> None:
    """R4: base.html includes required PWA meta tags."""
    response = client.get("/")
    content = response.content.decode("utf-8")
    assert 'name="viewport"' in content
    assert 'name="theme-color"' in content
    assert 'name="apple-mobile-web-app-capable"' in content
    assert 'content="yes"' in content


@override_settings(DEBUG=True)
def test_static_files_served(client: Client) -> None:
    """R5: Static files are accessible in DEBUG mode."""
    manifest_response = client.get("/static/manifest.json")
    assert manifest_response.status_code == 200
    css_response = client.get("/static/css/app.css")
    assert css_response.status_code == 200
