"""Views for the doctor app — medical queue, decision, and lock management."""

import logging
import uuid
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case as CaseAnnotation
from django.db.models import F, IntegerField, Q, Value, When
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseAttachment, CaseStatus
from apps.cases.services import (
    CASE_COMMUNICATION_MAX_LENGTH,
    CaseCommunicationError,
    assert_case_lock,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
    post_case_communication_message,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import DoctorDecisionForm
from .presenters import prepare_doctor_case_report

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────

STATUS_LABELS: dict[str, str] = {
    "NEW": "Novo",
    "EXTRACTING": "Extraindo dados",
    "LLM1_STRUCT": "Análise Automática (estrutura)",
    "LLM2_SUGGEST": "Análise Automática (sugestão)",
    "WAIT_DOCTOR": "Aguardando médico",
    "DOCTOR_ACCEPTED": "Aceito pelo médico",
    "DOCTOR_DENIED": "Recusado pelo médico",
    "WAIT_NURSE_ACK": "Aguardando confirmação",
    "FAILED": "Falha no processamento",
    "CLEANED": "Concluído",
}

STATUS_CSS_CLASS: dict[str, str] = {
    "NEW": "status-pending",
    "EXTRACTING": "status-progress",
    "LLM1_STRUCT": "status-progress",
    "LLM2_SUGGEST": "status-progress",
    "WAIT_DOCTOR": "status-progress",
    "DOCTOR_ACCEPTED": "status-accepted",
    "DOCTOR_DENIED": "status-denied",
    "WAIT_NURSE_ACK": "status-pending",
    "FAILED": "status-denied",
    "CLEANED": "status-done",
}

LOCK_CONTEXT = "doctor_decision"


# ── Queue views ────────────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def doctor_queue(request: HttpRequest) -> HttpResponse:
    """Fila médica: casos WAIT_DOCTOR (pendentes) + decididos hoje."""
    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])

    today = timezone.now().date()

    # Pending cases: WAIT_DOCTOR, ordered by regulation_days_on_screen DESC, created_at DESC
    pending_qs = (
        Case.objects.filter(status=CaseStatus.WAIT_DOCTOR)
        .select_related("created_by", "locked_by")
        .annotate(
            # Put nulls last for regulation_days_on_screen
            regulation_order=CaseAnnotation(
                When(regulation_days_on_screen__isnull=False, then=Value(0)),
                When(regulation_days_on_screen__isnull=True, then=Value(1)),
                output_field=IntegerField(),
            ),
        )
        .order_by("regulation_order", F("regulation_days_on_screen").desc(nulls_last=True), "-created_at")
    )

    # Decided today
    decided_today_qs = (
        Case.objects.filter(
            Q(doctor_decided_at__date=today),
            Q(status__in=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED, CaseStatus.WAIT_NURSE_ACK]),
        )
        .select_related("created_by", "doctor")
        .order_by("-doctor_decided_at")
    )

    pending_data = [
        {
            "case": c,
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "agency_record_number": c.agency_record_number,
            "regulation_days": c.regulation_days_on_screen,
            "created_at": c.created_at,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            **compute_lock_display(c, user=request.user),
        }
        for c in pending_qs
    ]

    decided_today_data = [
        {
            "case": c,
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "agency_record_number": c.agency_record_number,
            "decision": c.doctor_decision,
            "doctor_display": c.doctor_display if c.doctor else "—",
            "doctor_decided_at": c.doctor_decided_at,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
        }
        for c in decided_today_qs
    ]

    return render(
        request,
        "doctor/queue.html",
        {
            "pending_cases": pending_data,
            "decided_today_cases": decided_today_data,
            "today": today,
        },
    )


@login_required
@role_required("doctor")
def doctor_queue_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the doctor queue."""
    return render(request, "doctor/_queue_content.html", _queue_context(request))


def _queue_context(request: HttpRequest) -> dict[str, object]:
    """Build context for doctor queue rendering."""
    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_DOCTOR])

    today = timezone.now().date()

    pending_qs = (
        Case.objects.filter(status=CaseStatus.WAIT_DOCTOR)
        .select_related("created_by", "locked_by")
        .annotate(
            regulation_order=CaseAnnotation(
                When(regulation_days_on_screen__isnull=False, then=Value(0)),
                When(regulation_days_on_screen__isnull=True, then=Value(1)),
                output_field=IntegerField(),
            ),
        )
        .order_by("regulation_order", F("regulation_days_on_screen").desc(nulls_last=True), "-created_at")
    )

    decided_today_qs = (
        Case.objects.filter(
            Q(doctor_decided_at__date=today),
            Q(status__in=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED, CaseStatus.WAIT_NURSE_ACK]),
        )
        .select_related("created_by", "doctor")
        .order_by("-doctor_decided_at")
    )

    pending_data = [
        {
            "case": c,
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "agency_record_number": c.agency_record_number,
            "regulation_days": c.regulation_days_on_screen,
            "created_at": c.created_at,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            **compute_lock_display(c, user=request.user),
        }
        for c in pending_qs
    ]

    decided_today_data = [
        {
            "case": c,
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "agency_record_number": c.agency_record_number,
            "decision": c.doctor_decision,
            "doctor_display": c.doctor_display if c.doctor else "—",
            "doctor_decided_at": c.doctor_decided_at,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
        }
        for c in decided_today_qs
    ]

    return {
        "pending_cases": pending_data,
        "decided_today_cases": decided_today_data,
        "today": today,
    }


# ── Decision views ─────────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def doctor_decision(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """GET: Tela de decisão médica — formulário com relatório, dual-LLM, PDF, anexos.

    Adquire lock automaticamente no status WAIT_DOCTOR.
    """
    user = request.user

    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor", "locked_by"),
        case_id=case_id,
    )

    if case.status != CaseStatus.WAIT_DOCTOR:
        messages.warning(request, f"Este caso não está mais aguardando médico (status: {case.status}).")
        return redirect("doctor:queue")

    # Check if locked by another doctor
    lock_display = compute_lock_display(case, user=user)
    if lock_display["is_locked"] and not lock_display["is_locked_by_current_user"]:
        messages.warning(
            request,
            f"🔒 Caso está sendo avaliado por {lock_display['locked_by_display']}.",
        )
        return redirect("doctor:queue")

    # Acquire lock
    lock_token = None
    lock_held = False
    lock_error = ""

    result = claim_case_lock(
        case_id=case.case_id,
        user=user,
        expected_status=CaseStatus.WAIT_DOCTOR,
        context=LOCK_CONTEXT,
        role="doctor",
    )
    if result.acquired:
        lock_token = str(result.token)
        lock_held = True
        # Refresh case
        case = Case.objects.get(pk=case.case_id)
    else:
        lock_error = result.reason

    # Build presenter report
    structured_data = case.structured_data
    if isinstance(structured_data, dict):
        report_html = prepare_doctor_case_report(structured_data)
    else:
        report_html = ""

    # Dual-LLM configuration
    secondary_enabled = getattr(settings, "LLM_SECONDARY_ENABLED", False)

    # Prepare LLM2 suggestion cards
    llm2_primary = case.llm2_primary_result
    llm2_secondary = case.llm2_secondary_result if secondary_enabled else None

    primary_suggestion = _parse_llm2_suggestion(llm2_primary)
    secondary_suggestion = _parse_llm2_suggestion(llm2_secondary) if secondary_enabled else None

    # Check if primary and secondary diverge
    diverging = False
    if secondary_enabled and primary_suggestion and secondary_suggestion:
        p_decision = primary_suggestion.get("suggestion", "")
        s_decision = secondary_suggestion.get("suggestion", "")
        if p_decision and s_decision and p_decision != s_decision:
            diverging = True

    # Form
    form = DoctorDecisionForm()

    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    patient_name: str = case.patient_name

    return render(
        request,
        "doctor/decision.html",
        {
            "case": case,
            "patient_name": patient_name,
            "form": form,
            "report_html": report_html,
            # Dual-LLM
            "secondary_enabled": secondary_enabled,
            "primary_suggestion": primary_suggestion,
            "secondary_suggestion": secondary_suggestion,
            "diverging": diverging,
            # Lock
            "lock_token": lock_token or "",
            "lock_held": lock_held,
            "lock_error": lock_error,
            # PDF
            "pdf_url": reverse("doctor:serve_pdf", args=[case.case_id]),
            # Attachments
            "attachments": active_attachments,
            # Navigation
            "back_url": reverse("doctor:queue"),
            "back_label": "← Voltar para fila",
            # Communication
            "communication_messages": case.communication_messages.select_related("author").all(),
            "can_post_communication": case.status != CaseStatus.CLEANED,
            "communication_post_url": reverse("doctor:post_case_communication", args=[case.case_id]),
            "communication_next_url": request.get_full_path() + "#case-communication",
            "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
            # Status helpers
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            # Serve attachment base URL
            "serve_attachment_url_base": reverse(
                "doctor:serve_attachment", args=[case.case_id, "00000000-0000-0000-0000-000000000000"]
            ).replace("00000000-0000-0000-0000-000000000000", ""),
        },
    )


@login_required
@role_required("doctor")
def doctor_submit(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Processa a decisão médica (accept/deny).

    Valida lock, FSM transition, libera lock.
    """
    if request.method != "POST":
        return redirect("doctor:decision", case_id=case_id)

    user = request.user
    case = get_object_or_404(
        Case.objects.select_related("locked_by"),
        case_id=case_id,
    )

    if case.status != CaseStatus.WAIT_DOCTOR:
        messages.warning(request, f"Este caso não está mais aguardando médico (status: {case.status}).")
        return redirect("doctor:queue")

    # Validate lock
    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        messages.warning(request, "Token de reserva não encontrado. Abra o caso novamente pela fila.")
        return redirect("doctor:decision", case_id=case.case_id)

    try:
        assert_case_lock(
            case=case,
            user=user,
            token=token,
            context=LOCK_CONTEXT,
        )
    except PermissionError as exc:
        messages.warning(request, str(exc))
        return redirect("doctor:queue")

    # Validate form
    form = DoctorDecisionForm(request.POST)
    if not form.is_valid():
        # Return to decision page with form errors
        structured_data = case.structured_data
        report_html = prepare_doctor_case_report(structured_data) if isinstance(structured_data, dict) else ""

        secondary_enabled = getattr(settings, "LLM_SECONDARY_ENABLED", False)
        llm2_primary = case.llm2_primary_result
        llm2_secondary = case.llm2_secondary_result if secondary_enabled else None
        primary_suggestion = _parse_llm2_suggestion(llm2_primary)
        secondary_suggestion = _parse_llm2_suggestion(llm2_secondary) if secondary_enabled else None

        diverging = False
        if secondary_enabled and primary_suggestion and secondary_suggestion:
            p = primary_suggestion.get("suggestion", "")
            s = secondary_suggestion.get("suggestion", "")
            if p and s and p != s:
                diverging = True

        active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

        return render(
            request,
            "doctor/decision.html",
            {
                "case": case,
                "patient_name": case.patient_name,
                "form": form,
                "report_html": report_html,
                "secondary_enabled": secondary_enabled,
                "primary_suggestion": primary_suggestion,
                "secondary_suggestion": secondary_suggestion,
                "diverging": diverging,
                "lock_token": raw_token,
                "lock_held": True,
                "lock_error": "",
                "pdf_url": reverse("doctor:serve_pdf", args=[case.case_id]),
                "attachments": active_attachments,
                "back_url": reverse("doctor:queue"),
                "back_label": "← Voltar para fila",
                "communication_messages": case.communication_messages.select_related("author").all(),
                "can_post_communication": case.status != CaseStatus.CLEANED,
                "communication_post_url": reverse("doctor:post_case_communication", args=[case.case_id]),
                "communication_next_url": request.get_full_path() + "#case-communication",
                "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
                "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
                "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
                "serve_attachment_url_base": reverse(
                    "doctor:serve_attachment", args=[case.case_id, "00000000-0000-0000-0000-000000000000"]
                ).replace("00000000-0000-0000-0000-000000000000", ""),
            },
        )

    decision = form.cleaned_data["decision"]
    reason = form.cleaned_data.get("reason", "")
    observation = form.cleaned_data.get("observation", "")

    # Apply FSM transition
    from django.db import transaction

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.case_id)

        try:
            assert_case_lock(
                case=case,
                user=user,
                token=token,
                context=LOCK_CONTEXT,
            )
        except PermissionError as exc:
            messages.warning(request, str(exc))
            return redirect("doctor:queue")

        # Execute doctor_decide transition
        case.doctor_decide(decision=decision, user=user)
        case.doctor = user  # type: ignore[assignment]
        case.doctor_decision = decision
        case.doctor_reason = reason if decision == "deny" else ""
        case.doctor_observation = observation if decision == "accept" else observation
        case.doctor_decided_at = timezone.now()

        # Execute ready_for_nurse transition
        case.ready_for_nurse(user=user)
        case.save()

        # Release lock
        case.locked_by = None
        case.locked_at = None
        case.locked_until = None
        case.lock_token = None
        case.lock_context = ""
        case.lock_role = ""
        case.save(
            update_fields=[
                "status",
                "doctor",
                "doctor_decision",
                "doctor_reason",
                "doctor_observation",
                "doctor_decided_at",
                "locked_by",
                "locked_at",
                "locked_until",
                "lock_token",
                "lock_context",
                "lock_role",
            ]
        )

    if decision == "accept":
        messages.success(request, "✅ Caso aceito com sucesso. Seguirá para confirmação do enfermeiro.")
    else:
        messages.success(request, "❌ Caso recusado com sucesso. Seguirá para ciência do enfermeiro.")

    return redirect("doctor:queue")


# ── Decided detail ────────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def doctor_decided_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhes de um caso já decidido — consulta readonly."""
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )

    if case.status not in (
        CaseStatus.DOCTOR_ACCEPTED,
        CaseStatus.DOCTOR_DENIED,
        CaseStatus.WAIT_NURSE_ACK,
        CaseStatus.CLEANED,
    ):
        messages.warning(request, "Este caso não está disponível para consulta.")
        return redirect("doctor:queue")

    structured_data = case.structured_data
    report_html = prepare_doctor_case_report(structured_data) if isinstance(structured_data, dict) else ""

    secondary_enabled = getattr(settings, "LLM_SECONDARY_ENABLED", False)
    primary_suggestion = _parse_llm2_suggestion(case.llm2_primary_result)
    secondary_suggestion = _parse_llm2_suggestion(case.llm2_secondary_result) if secondary_enabled else None

    diverging = False
    if secondary_enabled and primary_suggestion and secondary_suggestion:
        p = primary_suggestion.get("suggestion", "")
        s = secondary_suggestion.get("suggestion", "")
        if p and s and p != s:
            diverging = True

    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    return render(
        request,
        "doctor/decision.html",
        {
            "case": case,
            "patient_name": case.patient_name,
            "form": None,
            "report_html": report_html,
            "readonly": True,
            "secondary_enabled": secondary_enabled,
            "primary_suggestion": primary_suggestion,
            "secondary_suggestion": secondary_suggestion,
            "diverging": diverging,
            "lock_token": "",
            "lock_held": False,
            "lock_error": "",
            "pdf_url": reverse("doctor:serve_pdf", args=[case.case_id]),
            "attachments": active_attachments,
            "back_url": reverse("doctor:queue"),
            "back_label": "← Voltar para fila",
            "communication_messages": case.communication_messages.select_related("author").all(),
            "can_post_communication": case.status != CaseStatus.CLEANED,
            "communication_post_url": reverse("doctor:post_case_communication", args=[case.case_id]),
            "communication_next_url": request.get_full_path() + "#case-communication",
            "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "serve_attachment_url_base": reverse(
                "doctor:serve_attachment", args=[case.case_id, "00000000-0000-0000-0000-000000000000"]
            ).replace("00000000-0000-0000-0000-000000000000", ""),
        },
    )


# ── PDF and attachment serving ─────────────────────────────────────────────


@login_required
@role_required("doctor")
@xframe_options_sameorigin
def serve_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve the original PDF for the doctor."""
    case = get_object_or_404(Case, case_id=case_id)
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    response = FileResponse(case.pdf_file.open("rb"), content_type="application/pdf")
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("doctor")
@xframe_options_sameorigin
def serve_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """Serve a protected attachment for the doctor."""
    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case__case_id=case_id,
        is_suppressed=False,
    )
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
    )
    response["Cache-Control"] = "no-store"
    return response


# ── Lock renew/release ────────────────────────────────────────────────────


@login_required
@role_required("doctor")
def lock_renew(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Renova a reserva do médico (heartbeat)."""
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    result = renew_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context=LOCK_CONTEXT,
    )

    if result.acquired:
        return JsonResponse(
            {
                "success": True,
                "locked_until": result.locked_until.isoformat() if result.locked_until else None,
            }
        )
    return JsonResponse({"success": False, "error": result.reason}, status=200)


@login_required
@role_required("doctor")
def lock_release(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Libera a reserva do médico explicitamente."""
    if request.method != "POST":
        raise Http404

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        return JsonResponse({"success": False, "error": "Token de reserva não fornecido."}, status=200)

    released = release_lock_service(
        case_id=case_id,
        user=request.user,
        token=token,
        context=LOCK_CONTEXT,
    )

    return JsonResponse({"success": released})


# ── Communication ─────────────────────────────────────────────────────────


@login_required
def post_case_communication(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Cria uma mensagem de comunicação operacional no caso."""
    if request.method != "POST":
        return redirect("doctor:decision", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)
    active_role: str = str(request.session.get("active_role", ""))
    body = request.POST.get("body", "")

    try:
        post_case_communication_message(
            case=case,
            author=request.user,
            author_role=active_role,
            body=body,
        )
        messages.success(request, "Mensagem enviada com sucesso.")
    except CaseCommunicationError as exc:
        messages.warning(request, str(exc))
    except Exception:
        logger.exception("Erro inesperado ao postar mensagem de comunicação.")
        messages.warning(request, "Erro inesperado ao enviar mensagem. Tente novamente.")

    next_url = request.POST.get("next", "")
    if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
        next_url = reverse("doctor:decision", args=[case.case_id])
    return redirect(next_url)


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_llm2_suggestion(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Parse LLM2 result into a display-friendly dict, or None if unavailable."""
    if not result or not isinstance(result, dict):
        return None

    suggestion = result.get("suggestion", "")
    acceptance = result.get("acceptance_criteria_met", []) or []
    exclusion = result.get("exclusion_criteria_met", []) or []
    confidence = result.get("confidence", "")
    rationale = result.get("rationale", "")
    recommendation = result.get("recommendation_text", "")

    return {
        "suggestion": suggestion,
        "acceptance_criteria_met": acceptance if isinstance(acceptance, list) else [],
        "exclusion_criteria_met": exclusion if isinstance(exclusion, list) else [],
        "confidence": confidence,
        "rationale": rationale,
        "recommendation_text": recommendation,
    }
