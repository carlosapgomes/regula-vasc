"""Profile and password change views."""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ProfileForm


@login_required
def profile_view(request):
    """Render and handle profile editing."""
    user = request.user
    roles = list(user.roles.values_list("name", flat=True))
    active_role = request.session.get("active_role", "")

    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.email = form.cleaned_data["email"]
            user.professional_council = form.cleaned_data.get("professional_council", "")
            user.professional_council_number = form.cleaned_data.get(
                "professional_council_number", ""
            )
            user.save()
            from django.contrib import messages

            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("profile")
    else:
        form = ProfileForm(
            initial={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "professional_council": user.professional_council,
                "professional_council_number": user.professional_council_number,
            }
        )

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "user_roles": roles,
            "active_role": active_role,
        },
    )


class HospitalPasswordChangeForm(PasswordChangeForm):
    """PasswordChangeForm com widgets aderentes ao estilo Bootstrap."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field_name in ("old_password", "new_password1", "new_password2"):
            self.fields[field_name].widget.attrs.setdefault("class", "")
            classes = self.fields[field_name].widget.attrs["class"]
            if "form-control" not in classes:
                self.fields[field_name].widget.attrs["class"] = (
                    classes + " form-control"
                ).strip()


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    """PasswordChangeView with custom template and session preservation."""

    template_name = "accounts/password_change_form.html"
    form_class = HospitalPasswordChangeForm
    success_url = "password_change_done"

    def get_success_url(self) -> str:
        return reverse(self.success_url)
