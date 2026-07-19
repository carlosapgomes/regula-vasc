"""Forms for account authentication and role selection."""

from typing import Any

from django import forms


class LoginForm(forms.Form):
    """Formulário de login com username e senha."""

    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "nome de usuário", "autofocus": True}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Sua senha"}),
    )


class RoleSelectForm(forms.Form):
    """Formulário para seleção de papel ativo."""

    role = forms.CharField(max_length=20, widget=forms.HiddenInput())


class ProfileForm(forms.Form):
    """Formulário de edição de perfil (nome, email, registro profissional)."""

    first_name = forms.CharField(
        label="Nome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Sobrenome",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    professional_council = forms.ChoiceField(
        label="Conselho profissional",
        choices=[("", "---")],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    professional_council_number = forms.CharField(
        label="Número do conselho",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        from django import forms as django_forms

        from .models import ProfessionalCouncil

        super().__init__(*args, **kwargs)
        council_field = self.fields["professional_council"]
        assert isinstance(council_field, django_forms.ChoiceField)
        council_field.choices = [("", "---")] + list(ProfessionalCouncil.choices)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        council = cleaned_data.get("professional_council", "")
        number = cleaned_data.get("professional_council_number", "")
        has_council = bool(council)
        has_number = bool(number)
        if has_council != has_number:
            raise forms.ValidationError(
                "Os campos de conselho profissional devem ser preenchidos juntos ou ambos vazios."
            )
        return cleaned_data
