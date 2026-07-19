"""Views for the dashboard app — admin metrics, case management, user/prompt/LLM config."""

import logging
import uuid
from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, DurationField, ExpressionWrapper, F, Q, QuerySet
from django.db.models.functions import Now
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.decorators import role_required
from apps.accounts.models import Role, User
from apps.cases.models import Case, CaseStatus
from apps.cases.services import administratively_close_case
from apps.llm.models import PromptTemplate

from .models import LlmProviderConfig

logger = logging.getLogger(__name__)


# ── Shared constants ───────────────────────────────────────────────────────

PAGE_SIZE = 20

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

ADMIN_CLOSE_REASON_CHOICES = [
    ("DUPLICATE", "Caso duplicado"),
    ("PATIENT_TRANSFERRED", "Paciente transferido"),
    ("PATIENT_DECEASED", "Paciente falecido"),
    ("PATIENT_DISCHARGED", "Paciente recebeu alta"),
    ("OUT_OF_SCOPE", "Fora do escopo vascular"),
    ("DATA_ENTRY_ERROR", "Erro de digitação/cadastro"),
    ("OTHER", "Outro motivo"),
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

# ── Helper functions ───────────────────────────────────────────────────────


def _period_filter_kwargs(period: str) -> dict[str, object]:
    """Build created_at__gte filter based on period string."""
    now = timezone.now()
    if period == "today":
        return {"created_at__date": now.date()}
    elif period == "7d":
        return {"created_at__gte": now - timedelta(days=7)}
    elif period == "30d":
        return {"created_at__gte": now - timedelta(days=30)}
    return {}  # 'all' or unknown


def _compute_metrics(period: str) -> dict[str, Any]:
    """Compute dashboard metric cards for a given period."""
    filters = _period_filter_kwargs(period)
    base_qs = Case.objects.filter(**filters)

    total = base_qs.count()
    accepted = base_qs.filter(doctor_decision="accept").count()
    denied = base_qs.filter(doctor_decision="deny").count()
    admin_closed = base_qs.filter(status=CaseStatus.CLEANED, admin_closed_by__isnull=False).count()
    pending = base_qs.filter(status=CaseStatus.WAIT_DOCTOR).count()
    wait_doctor = base_qs.filter(status=CaseStatus.WAIT_DOCTOR).count()
    wait_nurse = base_qs.filter(status=CaseStatus.WAIT_NURSE_ACK).count()
    failed = base_qs.filter(status=CaseStatus.FAILED).count()

    return {
        "total": total,
        "accepted": accepted,
        "denied": denied,
        "admin_closed": admin_closed,
        "pending": pending,
        "wait_doctor": wait_doctor,
        "wait_nurse": wait_nurse,
        "failed": failed,
    }


def _compute_avg_times(period: str) -> dict[str, Any]:
    """Compute average processing times in seconds."""
    filters = _period_filter_kwargs(period)
    base_qs = Case.objects.filter(**filters)

    # upload → doctor decision (cases that have been decided)
    decided_qs = base_qs.filter(doctor_decided_at__isnull=False)
    upload_to_decision = decided_qs.annotate(
        diff=ExpressionWrapper(
            F("doctor_decided_at") - F("created_at"),
            output_field=DurationField(),
        )
    ).aggregate(avg=Avg("diff"))

    # doctor decision → nurse ack (cases that have been acknowledged)
    acked_qs = base_qs.filter(nurse_ack_at__isnull=False, doctor_decided_at__isnull=False)
    decision_to_ack = acked_qs.annotate(
        diff=ExpressionWrapper(
            F("nurse_ack_at") - F("doctor_decided_at"),
            output_field=DurationField(),
        )
    ).aggregate(avg=Avg("diff"))

    # total cycle: upload → cleaned (cases that reached CLEANED)
    cleaned_qs = base_qs.filter(status=CaseStatus.CLEANED)
    total_cycle = cleaned_qs.annotate(
        diff=ExpressionWrapper(
            Now() - F("created_at"),
            output_field=DurationField(),
        )
    ).aggregate(avg=Avg("diff"))

    def _seconds(td: Any) -> int | None:
        if td is None:
            return None
        if isinstance(td, timedelta):
            return int(td.total_seconds())
        return None

    return {
        "upload_to_decision_avg": _seconds(upload_to_decision.get("avg")),
        "decision_to_ack_avg": _seconds(decision_to_ack.get("avg")),
        "total_cycle_avg": _seconds(total_cycle.get("avg")),
    }


def _compute_attention_cards() -> dict[str, list[dict[str, Any]]]:
    """Compute attention cards for cases needing attention."""
    now = timezone.now()

    # FAILED cases (newest first)
    failed_cases = list(
        Case.objects.filter(status=CaseStatus.FAILED).select_related("created_by").order_by("-created_at")[:10]
    )

    # Stuck processing: cases in EXTRACTING/LLM1_STRUCT/LLM2_SUGGEST for >30min
    stuck_threshold = now - timedelta(minutes=30)
    stuck_processing = list(
        Case.objects.filter(
            Q(status__in=[CaseStatus.EXTRACTING, CaseStatus.LLM1_STRUCT, CaseStatus.LLM2_SUGGEST]),
            updated_at__lt=stuck_threshold,
        )
        .select_related("created_by")
        .order_by("updated_at")[:10]
    )

    # Human wait >48h: WAIT_DOCTOR or WAIT_NURSE_ACK for >48h
    wait_threshold = now - timedelta(hours=48)
    human_wait = list(
        Case.objects.filter(
            Q(status=CaseStatus.WAIT_DOCTOR) | Q(status=CaseStatus.WAIT_NURSE_ACK),
            updated_at__lt=wait_threshold,
        )
        .select_related("created_by")
        .order_by("updated_at")[:10]
    )

    def _case_to_dict(c: Case) -> dict[str, Any]:
        return {
            "case_id": str(c.case_id),
            "patient_name": c.patient_name,
            "agency_record_number": c.agency_record_number,
            "status": c.status,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "created_by_display": c.created_by.get_full_name() or c.created_by.username if c.created_by else "—",
        }

    return {
        "failed": [_case_to_dict(c) for c in failed_cases],
        "stuck_processing": [_case_to_dict(c) for c in stuck_processing],
        "human_wait": [_case_to_dict(c) for c in human_wait],
    }


def _build_case_table_query(
    request: HttpRequest,
    period: str,
) -> tuple[QuerySet[Case], str]:
    """Build and return the filtered/sorted Case queryset for the table.

    Returns (queryset, search_term).
    """
    filters: Q = Q()
    period_filters = _period_filter_kwargs(period)
    if period_filters:
        filters &= Q(**period_filters)

    # Status filter
    status_filter = request.GET.get("status", "")
    if status_filter and status_filter in dict(CaseStatus.choices):
        filters &= Q(status=status_filter)

    # Search (server-side, min 3 chars)
    search = request.GET.get("q", "").strip()
    if len(search) >= 3:
        filters &= Q(agency_record_number__icontains=search) | Q(admin_closure_reason_text__icontains=search)
        # We also try to search by patient name via structured_data (JSON)
        # This is approximate but works for basic search
        filters |= Q(structured_data__patient__name__icontains=search)

    qs = Case.objects.filter(filters).select_related("created_by", "doctor", "admin_closed_by").order_by("-created_at")

    return qs, search


# ── Dashboard Index ────────────────────────────────────────────────────────


@login_required
@role_required("admin")
def dashboard_index(request: HttpRequest) -> HttpResponse:
    """Dashboard principal: métricas, cards de atenção, tabela de casos."""
    period = request.GET.get("period", "today")

    metrics = _compute_metrics(period)
    avg_times = _compute_avg_times(period)
    attention = _compute_attention_cards()

    case_qs, search = _build_case_table_query(request, period)

    paginator = Paginator(case_qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    case_rows = [
        {
            "case": c,
            "patient_name": c.patient_name,
            "agency_record_number": c.agency_record_number,
            "status_label": STATUS_LABELS.get(c.status, c.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(c.status, "status-pending"),
            "created_by_display": c.created_by.get_full_name() or c.created_by.username if c.created_by else "—",
            "doctor_display": c.doctor_display if c.doctor else "—",
            "created_at": c.created_at,
            "doctor_decided_at": c.doctor_decided_at,
        }
        for c in page_obj
    ]

    return render(
        request,
        "dashboard/index.html",
        {
            "period": period,
            "metrics": metrics,
            "avg_times": avg_times,
            "attention": attention,
            "case_rows": case_rows,
            "page_obj": page_obj,
            "search": search,
            "status_filter": request.GET.get("status", ""),
            "status_labels": STATUS_LABELS,
            "active_tab": "index",
        },
    )


# ── Case Detail & Administrative Close ─────────────────────────────────────


@login_required
@role_required("admin")
def dashboard_case_detail(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """Detalhe de qualquer caso para o admin, com botão de encerramento."""
    case = get_object_or_404(
        Case.objects.select_related("created_by", "doctor", "admin_closed_by"),
        case_id=case_id,
    )

    events = case.events.all()
    enriched_events = [
        {
            "event": e,
            "label": EVENT_LABELS.get(e.event_type, e.event_type),
            "dot_css": EVENT_DOT_CSS.get(e.event_type, "system"),
        }
        for e in events
    ]

    active_attachments = list(case.attachments.filter(is_suppressed=False).order_by("created_at"))

    patient_name: str = case.patient_name

    can_administratively_close = case.status != CaseStatus.CLEANED

    return render(
        request,
        "dashboard/index.html",  # Reuses the template with tab switching
        {
            "case": case,
            "case_detail_mode": True,
            "events": enriched_events,
            "status_label": STATUS_LABELS.get(case.status, case.get_status_display()),
            "status_css": STATUS_CSS_CLASS.get(case.status, "status-pending"),
            "patient_name": patient_name,
            "can_administratively_close": can_administratively_close,
            "attachments": active_attachments,
            "back_url": reverse("dashboard:index") + "?" + request.GET.urlencode()
            if request.GET
            else reverse("dashboard:index"),
            "back_label": "← Voltar para Dashboard",
            # Communication
            "communication_messages": case.communication_messages.select_related("author").all(),
            "can_post_communication": case.status != CaseStatus.CLEANED,
            "communication_post_url": reverse("dashboard:post_case_communication", args=[case.case_id]),
            "communication_next_url": request.get_full_path() + "#case-communication",
            "communication_max_length": 10000,
            "admin_close_reason_choices": ADMIN_CLOSE_REASON_CHOICES,
            "active_tab": "case_detail",
        },
    )


@login_required
@role_required("admin")
def dashboard_administrative_close(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Encerra um caso administrativamente."""
    if request.method != "POST":
        return redirect("dashboard:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)

    if case.status == CaseStatus.CLEANED:
        messages.warning(request, "Este caso já está encerrado (CLEANED).")
        return redirect("dashboard:case_detail", case_id=case_id)

    reason_code = request.POST.get("reason_code", "")
    reason_text = request.POST.get("reason_text", "")

    if not reason_code:
        messages.warning(request, "Selecione um código de motivo para o encerramento.")
        return redirect("dashboard:case_detail", case_id=case_id)

    if not reason_text.strip():
        messages.warning(request, "Descreva o motivo do encerramento.")
        return redirect("dashboard:case_detail", case_id=case_id)

    try:
        active_role = str(request.session.get("active_role", "admin"))
        administratively_close_case(
            case=case,
            user=request.user,
            reason_code=reason_code,
            reason_text=reason_text,
            active_role=active_role,
        )
        messages.success(request, "✅ Caso encerrado administrativamente com sucesso.")
    except ValueError as exc:
        messages.warning(request, str(exc))
    except Exception:
        logger.exception("Erro ao encerrar caso administrativamente.")
        messages.warning(request, "Erro inesperado ao encerrar o caso.")

    return redirect("dashboard:case_detail", case_id=case_id)


# ── User CRUD ─────────────────────────────────────────────────────────────


@login_required
@role_required("admin")
def dashboard_user_list(request: HttpRequest) -> HttpResponse:
    """Lista de usuários com opções de criar/editar."""
    users = User.objects.prefetch_related("roles").order_by("username")
    all_roles = Role.objects.all()

    user_data = [
        {
            "user": u,
            "role_names": ", ".join(r.name for r in u.roles.all()) if u.roles.exists() else "—",
            "is_active": u.is_account_active,
            "account_status": u.account_status,
        }
        for u in users
    ]

    return render(
        request,
        "dashboard/user_list.html",
        {
            "users": user_data,
            "all_roles": all_roles,
            "active_tab": "users",
        },
    )


@login_required
@role_required("admin")
def dashboard_user_create(request: HttpRequest) -> HttpResponse:
    """Cria um novo usuário."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")
        role_ids = request.POST.getlist("roles")
        professional_council = request.POST.get("professional_council", "")
        professional_council_number = request.POST.get("professional_council_number", "").strip()

        # Validation
        errors: list[str] = []
        if not username:
            errors.append("Nome de usuário é obrigatório.")
        if User.objects.filter(username=username).exists():
            errors.append("Nome de usuário já existe.")
        if not password:
            errors.append("Senha é obrigatória.")
        if password != password_confirm:
            errors.append("Senhas não conferem.")
        if not role_ids:
            errors.append("Selecione ao menos um papel.")
        if professional_council and not professional_council_number:
            errors.append("Número do conselho profissional obrigatório quando conselho é informado.")
        if professional_council_number and not professional_council:
            errors.append("Conselho profissional obrigatório quando número é informado.")

        if errors:
            for err in errors:
                messages.warning(request, err)
            all_roles = Role.objects.all()
            return render(
                request,
                "dashboard/user_form.html",
                {
                    "form_mode": "create",
                    "user_obj": None,
                    "all_roles": all_roles,
                    "selected_role_ids": [int(r) for r in role_ids],
                    "form_data": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "professional_council": professional_council,
                        "professional_council_number": professional_council_number,
                    },
                    "active_tab": "users",
                },
            )

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            professional_council=professional_council,
            professional_council_number=professional_council_number,
        )
        if role_ids:
            user.roles.set(Role.objects.filter(pk__in=role_ids))
        user.save()

        messages.success(request, f"✅ Usuário '{username}' criado com sucesso.")
        return redirect("dashboard:user_list")

    all_roles = Role.objects.all()
    return render(
        request,
        "dashboard/user_form.html",
        {
            "form_mode": "create",
            "user_obj": None,
            "all_roles": all_roles,
            "selected_role_ids": [],
            "form_data": {},
            "active_tab": "users",
        },
    )


@login_required
@role_required("admin")
def dashboard_user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    """Edita um usuário existente."""
    user_obj = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")
        role_ids = request.POST.getlist("roles")
        account_status = request.POST.get("account_status", "active")
        professional_council = request.POST.get("professional_council", "")
        professional_council_number = request.POST.get("professional_council_number", "").strip()

        errors: list[str] = []
        if not username:
            errors.append("Nome de usuário é obrigatório.")
        if User.objects.filter(username=username).exclude(pk=user_id).exists():
            errors.append("Nome de usuário já existe.")
        if password and password != password_confirm:
            errors.append("Senhas não conferem.")
        if not role_ids:
            errors.append("Selecione ao menos um papel.")
        if professional_council and not professional_council_number:
            errors.append("Número do conselho profissional obrigatório quando conselho é informado.")
        if professional_council_number and not professional_council:
            errors.append("Conselho profissional obrigatório quando número é informado.")

        if errors:
            for err in errors:
                messages.warning(request, err)
            all_roles = Role.objects.all()
            return render(
                request,
                "dashboard/user_form.html",
                {
                    "form_mode": "edit",
                    "user_obj": user_obj,
                    "all_roles": all_roles,
                    "selected_role_ids": [int(r) for r in role_ids] if role_ids else [],
                    "form_data": {
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "professional_council": professional_council,
                        "professional_council_number": professional_council_number,
                        "account_status": account_status,
                    },
                    "active_tab": "users",
                },
            )

        user_obj.username = username
        user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.email = email
        user_obj.account_status = account_status
        user_obj.professional_council = professional_council
        user_obj.professional_council_number = professional_council_number

        if password:
            user_obj.set_password(password)

        user_obj.save()

        if role_ids:
            user_obj.roles.set(Role.objects.filter(pk__in=role_ids))
        else:
            user_obj.roles.clear()

        messages.success(request, f"✅ Usuário '{username}' atualizado com sucesso.")
        return redirect("dashboard:user_list")

    all_roles = Role.objects.all()
    selected_ids = list(user_obj.roles.values_list("pk", flat=True))
    return render(
        request,
        "dashboard/user_form.html",
        {
            "form_mode": "edit",
            "user_obj": user_obj,
            "all_roles": all_roles,
            "selected_role_ids": selected_ids,
            "form_data": {
                "username": user_obj.username,
                "first_name": user_obj.first_name,
                "last_name": user_obj.last_name,
                "email": user_obj.email,
                "professional_council": user_obj.professional_council,
                "professional_council_number": user_obj.professional_council_number,
                "account_status": user_obj.account_status,
            },
            "active_tab": "users",
        },
    )


# ── Prompt Management ──────────────────────────────────────────────────────


@login_required
@role_required("admin")
def dashboard_prompt_list(request: HttpRequest) -> HttpResponse:
    """Lista de prompts com opção de criar nova versão."""
    prompt_names = PromptTemplate.objects.values_list("name", flat=True).distinct().order_by("name")

    prompts_grouped: list[dict[str, Any]] = []
    for name in prompt_names:
        versions = list(PromptTemplate.objects.filter(name=name).order_by("-version"))
        active_version = next((v for v in versions if v.is_active), None)
        prompts_grouped.append(
            {
                "name": name,
                "versions": versions,
                "active_version": active_version,
                "latest_version": versions[0] if versions else None,
            }
        )

    return render(
        request,
        "dashboard/prompt_list.html",
        {
            "prompts_grouped": prompts_grouped,
            "active_tab": "prompts",
        },
    )


@login_required
@role_required("admin")
def dashboard_prompt_create(request: HttpRequest) -> HttpResponse:
    """Cria uma nova versão de um prompt."""
    prompt_name = request.GET.get("name", "")
    existing = PromptTemplate.objects.filter(name=prompt_name).order_by("-version").first()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        content = request.POST.get("content", "").strip()
        activate = request.POST.get("activate") == "on"

        if not name:
            messages.warning(request, "Nome do prompt é obrigatório.")
            return redirect("dashboard:prompt_list")
        if not content:
            messages.warning(request, "Conteúdo do prompt é obrigatório.")
            return redirect(reverse("dashboard:prompt_create") + f"?name={name}")

        latest = PromptTemplate.objects.filter(name=name).order_by("-version").first()
        new_version = (latest.version + 1) if latest else 1

        if activate:
            PromptTemplate.objects.filter(name=name, is_active=True).update(is_active=False)

        PromptTemplate.objects.create(
            name=name,
            version=new_version,
            content=content,
            is_active=activate,
        )

        messages.success(request, f"✅ Prompt '{name}' v{new_version} criado com sucesso.")
        return redirect("dashboard:prompt_list")

    # Pre-fill from existing if available
    initial_content = existing.content if existing else ""
    next_version = (existing.version + 1) if existing else 1

    return render(
        request,
        "dashboard/prompt_create.html",
        {
            "prompt_name": prompt_name,
            "initial_content": initial_content,
            "next_version": next_version,
            "has_existing": existing is not None,
            "active_tab": "prompts",
        },
    )


# ── LLM Config ────────────────────────────────────────────────────────────


@login_required
@role_required("admin")
def dashboard_llm_config(request: HttpRequest) -> HttpResponse:
    """Configuração dos providers LLM."""
    config = LlmProviderConfig.get_singleton()

    if request.method == "POST":
        config.llm1_primary_provider = request.POST.get("llm1_primary_provider", "openai")
        config.llm1_primary_model = request.POST.get("llm1_primary_model", "")
        config.llm1_primary_api_key = request.POST.get("llm1_primary_api_key", "")
        config.llm1_primary_base_url = request.POST.get("llm1_primary_base_url", "")

        config.llm1_secondary_provider = request.POST.get("llm1_secondary_provider", "openai")
        config.llm1_secondary_model = request.POST.get("llm1_secondary_model", "")
        config.llm1_secondary_api_key = request.POST.get("llm1_secondary_api_key", "")
        config.llm1_secondary_base_url = request.POST.get("llm1_secondary_base_url", "")

        config.llm2_primary_provider = request.POST.get("llm2_primary_provider", "openai")
        config.llm2_primary_model = request.POST.get("llm2_primary_model", "")
        config.llm2_primary_api_key = request.POST.get("llm2_primary_api_key", "")
        config.llm2_primary_base_url = request.POST.get("llm2_primary_base_url", "")

        config.llm2_secondary_provider = request.POST.get("llm2_secondary_provider", "openai")
        config.llm2_secondary_model = request.POST.get("llm2_secondary_model", "")
        config.llm2_secondary_api_key = request.POST.get("llm2_secondary_api_key", "")
        config.llm2_secondary_base_url = request.POST.get("llm2_secondary_base_url", "")

        config.secondary_enabled = request.POST.get("secondary_enabled") == "on"
        config.save()

        messages.success(request, "✅ Configuração LLM atualizada com sucesso.")
        return redirect("dashboard:llm_config")

    return render(
        request,
        "dashboard/index.html",
        {
            "config": config,
            "llm_config_mode": True,
            "active_tab": "llm_config",
        },
    )


# ── Communication (delegate to existing service) ─────────────────────────


@login_required
@role_required("admin")
def post_case_communication(request: HttpRequest, case_id: uuid.UUID) -> HttpResponse:
    """POST: Cria uma mensagem de comunicação operacional no caso."""
    if request.method != "POST":
        return redirect("dashboard:case_detail", case_id=case_id)

    case = get_object_or_404(Case, case_id=case_id)
    active_role: str = str(request.session.get("active_role", ""))
    body = request.POST.get("body", "")

    try:
        from apps.cases.services import CaseCommunicationError, post_case_communication_message

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
        next_url = reverse("dashboard:case_detail", args=[case.case_id])
    return redirect(next_url)
