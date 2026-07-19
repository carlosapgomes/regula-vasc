"""Views for authentication: login, logout, and role switching."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, RoleSelectForm


def login_view(request):
    """Handle GET (render form) and POST (authenticate) for login."""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)

                roles = list(user.roles.values_list("name", flat=True))

                if len(roles) == 0:
                    # Edge case: user without roles
                    return redirect("switch_role")
                elif len(roles) == 1:
                    # Single role: auto-select
                    request.session["active_role"] = roles[0]
                    return redirect("/")
                else:
                    # Multiple roles: let user pick
                    return redirect("switch_role")
            else:
                messages.error(request, "Usuário ou senha inválidos.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    """Logout and redirect to login page."""
    logout(request)
    return redirect("login")


@login_required
def switch_role_view(request):
    """Allow user to select an active role from their assigned roles."""
    user = request.user
    user_roles = list(user.roles.values_list("name", flat=True))

    if request.method == "POST":
        form = RoleSelectForm(request.POST)
        if form.is_valid():
            role_name = form.cleaned_data["role"]
            if role_name in user_roles:
                request.session["active_role"] = role_name
                return redirect("/")
            else:
                messages.error(request, "Papel inválido ou não atribuído.")
    else:
        form = RoleSelectForm()

    from .context_processors import ROLE_DISPLAY_NAMES

    roles_display = [{"name": role, "label": ROLE_DISPLAY_NAMES.get(role, role)} for role in user_roles]

    return render(
        request,
        "accounts/switch_role.html",
        {"roles": roles_display, "form": form},
    )


@login_required
def home_view(request):
    """Renderiza a home page para o usuário autenticado.

    Futuramente, cada app (intake, doctor, dashboard) terá sua própria
    home específica. Por enquanto, renderiza a landing page.
    """
    active_role = request.session.get("active_role")
    if not active_role:
        return redirect("/switch-role/")

    return render(request, "home.html")
