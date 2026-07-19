"""Views do app intake."""

import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.accounts.decorators import role_required
from apps.cases.models import Case, CaseAttachment, CaseStatus
from apps.cases.services import (
    CASE_COMMUNICATION_MAX_LENGTH,
    ELIGIBLE_SUPPLEMENTAL_STATUSES,
    CaseCommunicationError,
    add_supplemental_case_attachment,
    assert_case_lock,
    claim_case_lock,
    compute_lock_display,
    expire_stale_locks_for_statuses,
    post_case_communication_message,
    suppress_case_attachment,
)
from apps.cases.services import (
    release_case_lock as release_lock_service,
)
from apps.cases.services import (
    renew_case_lock as renew_lock_service,
)

from .forms import CaseUploadForm
from .services import process_uploaded_files, validate_attachment_file

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────

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

STEP_STATUS_INDEX: dict[str, int] = {
    CaseStatus.NEW: 0,
    CaseStatus.EXTRACTING: 1,
    CaseStatus.LLM1_STRUCT: 1,
    CaseStatus.LLM2_SUGGEST: 1,
    CaseStatus.WAIT_DOCTOR: 2,
    CaseStatus.DOCTOR_ACCEPTED: 2,
    CaseStatus.DOCTOR_DENIED: 2,
    CaseStatus.WAIT_NURSE_ACK: 3,
    CaseStatus.FAILED: 3,
    CaseStatus.CLEANED: 3,
}

STEPS: list[dict[str, str]] = [
    {"icon": "📄", "label": "Upload"},
    {"icon": "⚙️", "label": "Extração Automática"},
    {"icon": "🩺", "label": "Avaliação Médica"},
    {"icon": "✅", "label": "Resultado Final"},
]

EVENT_LABELS: dict[str, str] = {
    "CASE_CREATED": "Caso criado",
    "CASE_START_EXTRACTION": "Extração de dados iniciada",
    "CASE_EXTRACTION_OK": "Extração de dados concluída",
    "CASE_EXTRACTION_FAILED": "Falha na extração de dados",
    "LLM1_OK": "Análise Automática (estrutura) concluída",
    "LLM1_FAILED": "Falha na análise automática (estrutura)",
    "LLM2_OK": "Análise Automática (sugestão) concluída",
    "LLM2_FAILED": "Falha na análise automática (sugestão)",
    "CASE_READY_FOR_DOCTOR": "Caso enviado para avaliação médica",
    "DOCTOR_ACCEPT": "Aceito pelo médico",
    "DOCTOR_DENY": "Recusado pelo médico",
    "CASE_READY_FOR_NURSE": "Aguardando confirmação do enfermeiro",
    "CASE_NURSE_ACK": "Ciência confirmada pelo enfermeiro",
    "PIPELINE_FAILED": "Falha no processamento",
    "WORK_LOCK_CLAIMED": "Caso reservado",
    "WORK_LOCK_RELEASED": "Reserva liberada",
    "WORK_LOCK_EXPIRED": "Reserva expirada",
    "CASE_ATTACHMENT_ADDED": "Anexo adicionado",
    "CASE_ATTACHMENT_SUPPRESSED": "Anexo suprimido",
    "CASE_ATTACHMENT_SUPPLEMENT_ADDED": "Anexo complementar adicionado",
    "CASE_ADMINISTRATIVELY_CLOSED": "Encerrado administrativamente",
    "CASE_COMMUNICATION_MESSAGE_POSTED": "Mensagem operacional registrada",
}

EVENT_DOT_CSS: dict[str, str] = {
    "CASE_CREATED": "reception",
    "CASE_START_EXTRACTION": "system",
    "CASE_EXTRACTION_OK": "system",
    "CASE_EXTRACTION_FAILED": "system",
    "LLM1_OK": "system",
    "LLM1_FAILED": "system",
    "LLM2_OK": "system",
    "LLM2_FAILED": "system",
    "CASE_READY_FOR_DOCTOR": "system",
    "DOCTOR_ACCEPT": "doctor",
    "DOCTOR_DENY": "doctor",
    "CASE_READY_FOR_NURSE": "system",
    "CASE_NURSE_ACK": "nurse",
    "PIPELINE_FAILED": "system",
    "WORK_LOCK_CLAIMED": "system",
    "WORK_LOCK_RELEASED": "system",
    "WORK_LOCK_EXPIRED": "system",
    "CASE_ATTACHMENT_ADDED": "system",
    "CASE_ATTACHMENT_SUPPRESSED": "nurse",
    "CASE_ATTACHMENT_SUPPLEMENT_ADDED": "nurse",
    "CASE_ADMINISTRATIVELY_CLOSED": "system",
    "CASE_COMMUNICATION_MESSAGE_POSTED": "system",
}

# ── Views ──────────────────────────────────────────────────────────────


@login_required
@role_required("nurse")
def intake_home(request: HttpRequest) -> HttpResponse:
    """Dashboard do enfermeiro — formulário de upload + casos recentes."""
    user = request.user
    assert user.is_authenticated

    if request.method == "POST":
        form = CaseUploadForm(request.POST, request.FILES)
        files = request.FILES.getlist("pdf_files")
        attachments = request.FILES.getlist("attachment_files")
        cases, errors = process_uploaded_files(files, user, attachments=attachments or None)

        for error in errors:
            messages.warning(request, error)

        if cases:
            count = len(cases)
            msg = (
                f"{count} encaminhamento{'s' if count > 1 else ''} recebido{'s' if count > 1 else ''} "
                f"com sucesso. O processamento continuará em background."
            )
            messages.success(request, msg)
            return redirect("intake:my_cases")
        elif not errors:
            messages.warning(request, "Nenhum arquivo enviado.")
    else:
        form = CaseUploadForm()

    recent_cases = Case.objects.filter(created_by=user).exclude(status=CaseStatus.CLEANED).order_by("-created_at")[:10]

    recent_cases_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
        }
        for c in recent_cases
    ]

    return render(
        request,
        "intake/intake_home.html",
        {
            "form": form,
            "recent_cases": recent_cases_data,
        },
    )


def _my_cases_context(request: HttpRequest) -> dict[str, object]:
    """Build context for full and HTMX nurse case-list renders."""
    user = request.user
    assert user.is_authenticated

    expire_stale_locks_for_statuses(statuses=[CaseStatus.WAIT_NURSE_ACK])

    qs = (
        Case.objects.exclude(status=CaseStatus.CLEANED)
        .select_related("doctor", "created_by", "locked_by")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    search = request.GET.get("q", "")
    if search:
        qs = qs.filter(agency_record_number__icontains=search)

    case_data = [
        {
            "case": c,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            "patient_name": c.patient_name,
            "patient_age": c.patient_age,
            "created_by_other_nurse": c.created_by_id != user.pk,
            "created_by_display": c.created_by.get_full_name() or c.created_by.username,
            **(
                compute_lock_display(c, user=user)
                if c.status == CaseStatus.WAIT_NURSE_ACK
                else {
                    "is_locked": False,
                    "is_locked_by_current_user": False,
                    "locked_by_display": "",
                    "locked_until": "",
                    "lock_context": "",
                }
            ),
        }
        for c in qs
    ]

    query_string = request.META.get("QUERY_STRING", "")
    partial_url = "/intake/my-cases/partial/"
    if query_string:
        partial_url = f"{partial_url}?{query_string}"

    return {
        "case_data": case_data,
        "status_filter": status_filter,
        "search": search,
        "status_labels": STATUS_LABELS,
        "status_css": STATUS_CSS_CLASS,
        "my_cases_partial_url": partial_url,
    }


@login_required
@role_required("nurse")
def my_cases(request: HttpRequest) -> HttpResponse:
    """Lista 'Meus Casos' do enfermeiro — cards com filtros."""
    return render(request, "intake/my_cases.html", _my_cases_context(request))


@login_required
@role_required("nurse")
def my_cases_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial for polling the nurse case list."""
    return render(request, "intake/_my_cases_content.html", _my_cases_context(request))


@login_required
@role_required("nurse")
def case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhes de um caso para o enfermeiro — timeline, stepper e PDF inline."""
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("Caso concluído não está disponível na fila operacional.")

    events = case.events.all()
    current_step_idx = STEP_STATUS_INDEX.get(case.status, 0)
    steps = STEPS

    if case.doctor_decision == "deny":
        steps = STEPS
        current_step_idx = len(steps) - 1

    enriched_events = []
    for e in events:
        enriched_events.append(
            {
                "event": e,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
            }
        )

    # Lock acquisition for WAIT_NURSE_ACK
    user = request.user
    lock_token = None
    lock_locked_by_display = None
    can_confirm = case.status == CaseStatus.WAIT_NURSE_ACK
    lock_held = False

    if case.status == CaseStatus.WAIT_NURSE_ACK:
        result = claim_case_lock(
            case_id=case.case_id,
            user=user,
            expected_status=CaseStatus.WAIT_NURSE_ACK,
            context="nurse_receipt",
            role="nurse",
        )
        if result.acquired:
            lock_token = str(result.token)
            case = Case.objects.get(pk=case.case_id)
            lock_held = True
        elif result.locked_by_display:
            lock_locked_by_display = result.locked_by_display
            can_confirm = False
        else:
            can_confirm = False

    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    # Lock info for supplemental attachments
    supplemental_lock_blocked_by = ""
    if case.status == CaseStatus.WAIT_DOCTOR:
        lock_display = compute_lock_display(case, user=user)
        if lock_display["is_locked"]:
            raw_blocked = lock_display["locked_by_display"]
            supplemental_lock_blocked_by = str(raw_blocked) if raw_blocked else ""

    # Result info
    result_info = None
    if case.status in (CaseStatus.WAIT_NURSE_ACK, CaseStatus.CLEANED):
        if case.doctor_decision == "deny":
            result_info = {
                "type": "doctor_denied",
                "reason": case.doctor_reason,
                "doctor_display": case.doctor_display,
            }
        elif case.doctor_decision == "accept":
            result_info = {
                "type": "doctor_accepted",
                "observation": case.doctor_observation,
                "doctor_display": case.doctor_display,
            }
    elif case.status == CaseStatus.FAILED:
        result_info = {"type": "failed"}

    # Eligibility for supplemental attachment
    can_add_supplemental = (
        case.status not in (CaseStatus.CLEANED,)
        and not case.doctor_decision
        and case.status in ELIGIBLE_SUPPLEMENTAL_STATUSES
    )

    patient_name: str = ""
    if case.structured_data and isinstance(case.structured_data, dict):
        patient = case.structured_data.get("patient", {})
        if isinstance(patient, dict):
            raw_name = patient.get("name")
            patient_name = str(raw_name) if raw_name else ""

    return render(
        request,
        "intake/case_detail.html",
        {
            "case": case,
            "events": enriched_events,
            "steps": steps,
            "current_step_idx": current_step_idx,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "can_confirm_receipt": can_confirm,
            "lock_token": lock_token or "",
            "lock_locked_by_display": lock_locked_by_display or "",
            "lock_held": lock_held,
            "result_info": result_info,
            "patient_name": patient_name,
            # Parametrização para template compartilhado
            "show_intake_nav": True,
            "show_doctor_nav": False,
            "show_dashboard_nav": False,
            "back_url": reverse("intake:my_cases"),
            "back_label": "← Voltar para lista",
            "pdf_url": reverse("intake:serve_pdf", args=[case.case_id]),
            "attachments": active_attachments,
            "can_add_supplemental": can_add_supplemental,
            "supplemental_lock_blocked_by": supplemental_lock_blocked_by,
            "can_administratively_close": False,
            # Comunicação operacional
            "communication_messages": case.communication_messages.select_related("author").all(),
            "can_post_communication": case.status != CaseStatus.CLEANED,
            "communication_post_url": reverse("intake:post_case_communication", args=[case.case_id]),
            "communication_next_url": request.get_full_path() + "#case-communication",
            "communication_max_length": CASE_COMMUNICATION_MAX_LENGTH,
        },
    )


# ── PDF and attachment serving ─────────────────────────────────────────


def _get_nurse_attachment_or_404(case_id: uuid.UUID, attachment_id: uuid.UUID) -> tuple[Case, CaseAttachment]:
    """Busca e autoriza anexo para o enfermeiro."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("Anexo de caso concluído não está disponível na fila operacional.")

    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case=case,
        is_suppressed=False,
    )
    return case, attachment


@login_required
@role_required("nurse")
@xframe_options_sameorigin
def serve_pdf(request: HttpRequest, case_id: uuid.UUID) -> HttpResponseBase:
    """Serve o PDF original do caso para visualização inline."""
    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("PDF de caso concluído não está disponível na fila operacional.")
    if not case.pdf_file:
        raise Http404("PDF não encontrado para este caso.")

    response = FileResponse(case.pdf_file.open("rb"), content_type="application/pdf")
    response["Cache-Control"] = "no-store"
    return response


@login_required
@role_required("nurse")
@xframe_options_sameorigin
def serve_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """Serve um anexo protegido para visualização."""
    _, attachment = _get_nurse_attachment_or_404(case_id, attachment_id)

    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
    )
    response["Cache-Control"] = "no-store"
    return response


# ── Receipt confirmation ──────────────────────────────────────────────


@login_required
@role_required("nurse")
def confirm_receipt(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Confirma recebimento do resultado final e conclui o caso."""
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)

    if case.status != CaseStatus.WAIT_NURSE_ACK:
        messages.warning(request, "Este caso não está aguardando confirmação de recebimento.")
        return redirect("intake:case_detail", case_id=case.case_id)

    raw_token = request.POST.get("lock_token", "")
    try:
        token = uuid.UUID(raw_token) if raw_token else None
    except (ValueError, AttributeError):
        token = None

    if token is None:
        messages.warning(
            request,
            "Token de reserva não encontrado. Volte para a lista e tente novamente.",
        )
        return redirect("intake:case_detail", case_id=case.case_id)

    try:
        assert_case_lock(
            case=case,
            user=request.user,
            token=token,
            context="nurse_receipt",
        )
    except PermissionError as exc:
        messages.warning(request, str(exc))
        return redirect("intake:case_detail", case_id=case.case_id)

    # Execute FSM transition: WAIT_NURSE_ACK → CLEANED
    case.nurse_ack(user=request.user)
    from typing import cast
    from apps.accounts.models import User as AccountsUser

    case.nurse_ack_by = cast(AccountsUser, request.user)

    from django.utils import timezone

    case.nurse_ack_at = timezone.now()
    case.save()

    # Clear lock
    case.locked_by = None
    case.locked_at = None
    case.locked_until = None
    case.lock_token = None
    case.lock_context = ""
    case.lock_role = ""
    case.save(
        update_fields=[
            "locked_by",
            "locked_at",
            "locked_until",
            "lock_token",
            "lock_context",
            "lock_role",
            "nurse_ack_by",
            "nurse_ack_at",
        ]
    )

    messages.success(request, "Recebimento confirmado. Caso concluído.")
    return redirect("intake:my_cases")


# ── Attachment management ─────────────────────────────────────────────


@login_required
@role_required("nurse")
def suppress_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> HttpResponseBase:
    """POST: Suprime um anexo ativo de forma auditável."""
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )
    if case.status == CaseStatus.CLEANED:
        raise Http404("Anexo de caso concluído não está disponível na fila operacional.")

    attachment = get_object_or_404(
        CaseAttachment,
        attachment_id=attachment_id,
        case=case,
        is_suppressed=False,
    )

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.warning(request, "Informe o motivo da supressão do anexo.")
        return redirect("intake:case_detail", case_id=case.case_id)

    try:
        suppress_case_attachment(
            attachment=attachment,
            user=request.user,
            reason=reason,
        )
        messages.success(request, "Anexo suprimido com sucesso.")
    except ValueError as exc:
        messages.warning(request, str(exc))

    return redirect("intake:case_detail", case_id=case.case_id)


@login_required
@role_required("nurse")
def add_supplemental_attachment(
    request: HttpRequest,
    case_id: uuid.UUID,
) -> HttpResponse:
    """POST: Adiciona anexo(s) complementar(es) a um caso."""
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

    case = get_object_or_404(
        Case.objects.select_related("created_by"),
        case_id=case_id,
    )

    note = request.POST.get("note", "").strip()
    if not note:
        messages.warning(request, "Justificativa obrigatória para anexo complementar.")
        return redirect("intake:case_detail", case_id=case.case_id)

    files = request.FILES.getlist("attachment_files")
    if not files:
        messages.warning(request, "Selecione ao menos um arquivo para anexar.")
        return redirect("intake:case_detail", case_id=case.case_id)

    for f in files:
        try:
            validate_attachment_file(f)
        except ValueError as exc:
            messages.warning(request, str(exc))
            return redirect("intake:case_detail", case_id=case.case_id)

    existing_count = case.attachments.filter(is_suppressed=False).count()
    max_attachments = settings.INTAKE_MAX_ATTACHMENTS_PER_CASE
    if existing_count + len(files) > max_attachments:
        messages.warning(
            request,
            f"Máximo de {max_attachments} anexos por caso. Já existem {existing_count} anexo(s).",
        )
        return redirect("intake:case_detail", case_id=case.case_id)

    success_count = 0
    for f in files:
        try:
            add_supplemental_case_attachment(
                case=case,
                uploaded_file=f,
                user=request.user,
                note=note,
            )
            success_count += 1
        except ValueError as exc:
            messages.warning(request, str(exc))
            return redirect("intake:case_detail", case_id=case.case_id)

    if success_count > 0:
        msg = f"{success_count} anexo(s) complementar(es) adicionado(s) com sucesso."
        messages.success(request, msg)

    return redirect("intake:case_detail", case_id=case.case_id)


# ── Communication ─────────────────────────────────────────────────────


@login_required
def post_case_communication(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Cria uma mensagem de comunicação operacional no caso."""
    if request.method != "POST":
        return redirect("intake:case_detail", case_id=case_id)

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
    if not next_url:
        next_url = reverse("intake:case_detail", args=[case.case_id])
    return redirect(next_url)


# ── Lock renew/release ────────────────────────────────────────────────


@login_required
@role_required("nurse")
def lock_renew(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Renova a reserva do enfermeiro (heartbeat)."""
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
        context="nurse_receipt",
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
@role_required("nurse")
def lock_release(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Libera a reserva do enfermeiro explicitamente."""
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
        context="nurse_receipt",
    )

    return JsonResponse({"success": released})
