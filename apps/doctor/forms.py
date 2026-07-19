"""Forms for the doctor app."""

from django import forms


class DoctorDecisionForm(forms.Form):
    """Form for the doctor's decision: accept or deny a case.

    - Accept: observation is optional.
    - Deny: reason is required, observation is optional.
    """

    DECISION_CHOICES = [
        ("accept", "Aceitar"),
        ("deny", "Recusar"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "btn-check", "data-decision-target": True}),
        error_messages={"required": "Selecione Aceitar ou Recusar."},
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Justificativa obrigatória para recusa..."}),
        max_length=2000,
    )
    observation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)..."}),
        max_length=500,
    )

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean() or {}
        decision = cleaned_data.get("decision")
        reason = cleaned_data.get("reason", "")

        if decision == "deny":
            if not reason or not reason.strip():
                self.add_error("reason", "Justificativa obrigatória para recusa.")
            elif len(reason.strip()) < 10:
                self.add_error("reason", "A justificativa deve ter pelo menos 10 caracteres.")

        return cleaned_data
