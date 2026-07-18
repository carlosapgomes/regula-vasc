"""Password reset views using Django native views with custom templates."""

from django.contrib.auth import views as auth_views
from django.urls import reverse


class CustomPasswordResetView(auth_views.PasswordResetView):
    """PasswordResetView with custom template."""

    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    html_email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = "password_reset_done"
    from_email = None

    def get_success_url(self) -> str:
        return reverse(self.success_url)


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    """PasswordResetDoneView with custom template."""

    template_name = "accounts/password_reset_done.html"


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """PasswordResetConfirmView with custom template."""

    template_name = "accounts/password_reset_confirm.html"
    success_url = "password_reset_complete"

    def get_success_url(self) -> str:
        return reverse(self.success_url)


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """PasswordResetCompleteView with custom template."""

    template_name = "accounts/password_reset_complete.html"
