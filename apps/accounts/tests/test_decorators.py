"""Tests for @role_required decorator."""

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.decorators import role_required

User = get_user_model()


@pytest.mark.django_db
class TestRoleRequiredDecorator:
    """Tests for the @role_required decorator."""

    def _make_request(self, user, active_role):
        """Create a request with proper session and user for decorator testing.

        Uses RequestFactory but manually patches _messages to avoid
        AttributeError when the decorator calls messages.error().
        """
        from django.contrib.sessions.backends.base import SessionBase

        factory = RequestFactory()
        request = factory.get("/test/")
        request.user = user
        session = SessionBase()
        session["active_role"] = active_role
        request.session = session

        # Patch _messages to avoid AttributeError when messages.error() is called
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_role_required_allows_correct_role(self) -> None:
        """User with role doctor can access view decorated with @role_required('doctor')."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="doc@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="doctor")
        user.roles.add(role)

        def sample_view(request):
            return HttpResponse("OK")

        wrapped_view = role_required("doctor")(sample_view)

        request = self._make_request(user, "doctor")

        response = wrapped_view(request)
        assert response.status_code == 200

    def test_role_required_blocks_wrong_role(self) -> None:
        """User with role nurse accessing @role_required('doctor') → redirect."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nurse@test.com", password="testpass123")
        role_nurse, _ = Role.objects.get_or_create(name="nurse")
        user.roles.add(role_nurse)

        def sample_view(request):
            return HttpResponse("OK")

        wrapped_view = role_required("doctor")(sample_view)

        request = self._make_request(user, "nurse")

        response = wrapped_view(request)
        assert response.status_code == 302

    def test_role_required_multiple_roles_allowed(self) -> None:
        """User with role nurse can access @role_required('nurse', 'doctor')."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="multi@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nurse")
        user.roles.add(role)

        def sample_view(request):
            return HttpResponse("OK")

        wrapped_view = role_required("nurse", "doctor")(sample_view)

        request = self._make_request(user, "nurse")

        response = wrapped_view(request)
        assert response.status_code == 200

    def test_role_required_blocks_nurse_from_admin(self) -> None:
        """User with role nurse accessing @role_required('admin') → redirect."""
        from apps.accounts.models import Role

        user = User.objects.create_user(username="nursea@test.com", password="testpass123")
        role, _ = Role.objects.get_or_create(name="nurse")
        user.roles.add(role)

        def sample_view(request):
            return HttpResponse("OK")

        wrapped_view = role_required("admin")(sample_view)

        request = self._make_request(user, "nurse")

        response = wrapped_view(request)
        assert response.status_code == 302
