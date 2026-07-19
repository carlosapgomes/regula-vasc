"""Case lock service and administrative closure."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import Case, CaseAttachment, CaseCommunicationMessage, CaseEvent, CaseStatus


@dataclass(frozen=True)
class CaseLockResult:
    """Result of a lock claim operation."""

    acquired: bool
    token: uuid.UUID | None = None
    reason: str = ""
    locked_by_display: str = ""
    locked_until: datetime | None = None


def _get_lease_seconds(override: int | None = None) -> int:
    if override is not None:
        return override
    return getattr(settings, "CASE_LOCK_LEASE_SECONDS", 300)


def _build_lock_result(acquired: bool, case: Case | None = None, reason: str = "") -> CaseLockResult:
    """Helper to build a CaseLockResult."""
    if acquired and case:
        return CaseLockResult(
            acquired=True,
            token=case.lock_token,
            locked_by_display=case.locked_by.display_name if case.locked_by else "",
            locked_until=case.locked_until,
        )
    return CaseLockResult(acquired=False, reason=reason)


# ── Constants ────────────────────────────────────────────────────────

CASE_COMMUNICATION_MAX_LENGTH = 2000
"""Maximum length for a communication message body."""

ELIGIBLE_SUPPLEMENTAL_STATUSES = frozenset(
    {
        CaseStatus.NEW,
        CaseStatus.EXTRACTING,
        CaseStatus.LLM1_STRUCT,
        CaseStatus.LLM2_SUGGEST,
        CaseStatus.WAIT_DOCTOR,
    }
)
"""Statuses in which supplemental attachments can be added."""


# ── Helper functions ──────────────────────────────────────────────────


def _record_event(
    case: Case,
    event_type: str,
    user: Any,
    payload: dict[str, object] | None = None,
) -> None:
    CaseEvent.objects.create(
        case=case,
        event_type=event_type,
        actor=user,
        actor_type="human",
        payload=payload or {},
    )


def claim_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    expected_status: CaseStatus,
    context: str,
    role: str,
    lease_seconds: int | None = None,
) -> CaseLockResult:
    """Atomically claim a lease on a Case."""
    seconds = _get_lease_seconds(lease_seconds)
    now = timezone.now()
    token = uuid.uuid4()
    locked_until = now + timedelta(seconds=seconds)

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)

        # Status check
        if case.status != expected_status:
            return _build_lock_result(False, reason=f"Caso não está em {expected_status}")

        # Lock check
        previous_locked_by = None
        if case.locked_by is not None and case.locked_until is not None:
            if case.locked_until > now:
                # Active lock belongs to someone else
                if case.locked_by_id != user.pk:
                    return _build_lock_result(
                        False,
                        reason="Caso está reservado por outro usuário",
                    )
                # Same user — renew
                case.locked_at = now
                case.locked_until = locked_until
                case.lock_token = token
                case.lock_context = context
                case.lock_role = role
                case.save(update_fields=["locked_at", "locked_until", "lock_token", "lock_context", "lock_role"])
                _record_event(
                    case, "WORK_LOCK_CLAIMED", user, {"context": context, "role": role, "lease_seconds": seconds}
                )
                return _build_lock_result(True, case)
            # Expired lock
            previous_locked_by = {
                "id": str(case.locked_by_id),
                "display": case.locked_by.display_name if case.locked_by else "desconhecido",
            }

        # Acquire lock
        case.locked_by = user
        case.locked_at = now
        case.locked_until = locked_until
        case.lock_token = token
        case.lock_context = context
        case.lock_role = role
        case.save(update_fields=["locked_by", "locked_at", "locked_until", "lock_token", "lock_context", "lock_role"])

        if previous_locked_by:
            _record_event(case, "WORK_LOCK_EXPIRED", user, {"expired_locked_by": previous_locked_by})

        _record_event(case, "WORK_LOCK_CLAIMED", user, {"context": context, "role": role, "lease_seconds": seconds})

    return _build_lock_result(True, Case.objects.get(pk=case.pk))


LOCK_LOST_USER_MESSAGE = (
    "A reserva desta tela expirou ou foi liberada antes do envio. Volte à fila e abra o caso novamente."
)


def assert_case_lock(
    *,
    case: Case,
    user: Any,
    token: uuid.UUID,
    context: str,
) -> None:
    """Validate that the current user holds a valid lock on the case."""
    now = timezone.now()

    if case.locked_by is None:
        raise PermissionError(LOCK_LOST_USER_MESSAGE)
    if case.locked_by_id != user.pk:
        raise PermissionError(f"Lock pertence a outro usuário: {case.locked_by.display_name}")
    if case.lock_token is None or case.lock_token != token:
        raise PermissionError("Token de lock inválido.")
    if case.lock_context != context:
        raise PermissionError(f"Contexto de lock inválido: esperado '{context}', obtido '{case.lock_context}'")
    if case.locked_until is None or case.locked_until <= now:
        raise PermissionError(LOCK_LOST_USER_MESSAGE)


def release_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    token: uuid.UUID,
    context: str,
) -> bool:
    """Release a lock on a case."""
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)
        try:
            assert_case_lock(case=case, user=user, token=token, context=context)
        except PermissionError:
            return False

        _record_event(case, "WORK_LOCK_RELEASED", user, {"context": context})
        case.locked_by = None
        case.locked_at = None
        case.locked_until = None
        case.lock_token = None
        case.lock_context = ""
        case.lock_role = ""
        case.save(update_fields=["locked_by", "locked_at", "locked_until", "lock_token", "lock_context", "lock_role"])
    return True


def renew_case_lock(
    *,
    case_id: uuid.UUID,
    user: Any,
    token: uuid.UUID,
    context: str,
    lease_seconds: int | None = None,
) -> CaseLockResult:
    """Renew an existing lock (heartbeat)."""
    seconds = _get_lease_seconds(lease_seconds)
    now = timezone.now()
    locked_until = now + timedelta(seconds=seconds)

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case_id)

        if case.locked_by is None or case.locked_until is None:
            return _build_lock_result(False, reason="Caso não possui reserva ativa para renovar.")
        if case.locked_until <= now:
            return _build_lock_result(False, reason="Reserva expirou. Adquira uma nova reserva.")
        if case.locked_by_id != user.pk:
            return _build_lock_result(False, reason="Reserva pertence a outro usuário.")
        if case.lock_token is None or case.lock_token != token:
            return _build_lock_result(False, reason="Token de reserva inválido.")
        if case.lock_context != context:
            return _build_lock_result(
                False, reason=f"Contexto de reserva inválido: esperado '{context}', obtido '{case.lock_context}'."
            )

        case.locked_at = now
        case.locked_until = locked_until
        case.save(update_fields=["locked_at", "locked_until"])
    return _build_lock_result(True, Case.objects.get(pk=case.pk))


def compute_lock_display(case: Case, user: Any) -> dict[str, object]:
    """Compute lock display info for a case."""
    from django.utils import timezone

    now = timezone.now()
    if case.locked_by is None or case.locked_until is None or case.locked_until <= now:
        return {
            "is_locked": False,
            "is_locked_by_current_user": False,
            "locked_by_display": "",
            "locked_until": "",
            "lock_context": "",
        }
    return {
        "is_locked": True,
        "is_locked_by_current_user": case.locked_by_id == user.pk,
        "locked_by_display": case.locked_by.display_name if case.locked_by else "desconhecido",
        "locked_until": case.locked_until.isoformat() if case.locked_until else "",
        "lock_context": case.lock_context or "",
    }


def expire_stale_locks_for_statuses(
    *,
    statuses: list[CaseStatus],
) -> int:
    """Clear all expired locks for cases in the given statuses."""
    now = timezone.now()
    qs: QuerySet[Case] = Case.objects.filter(
        status__in=list(statuses),
        locked_by__isnull=False,
        locked_until__isnull=False,
        locked_until__lte=now,
    )
    count = qs.count()
    if count == 0:
        return 0
    qs.update(
        locked_by=None,
        locked_at=None,
        locked_until=None,
        lock_token=None,
        lock_context="",
        lock_role="",
    )
    return count


# ── Attachment supplementary operations ───────────────────────────────


class CaseCommunicationError(ValueError):
    """Error raised when posting a communication message fails."""


def add_supplemental_case_attachment(
    *,
    case: Case,
    uploaded_file: UploadedFile,
    user: Any,
    note: str,
) -> CaseAttachment:
    """Add a supplemental attachment to a case."""
    if case.status not in ELIGIBLE_SUPPLEMENTAL_STATUSES:
        raise ValueError(f"Não é possível adicionar anexos complementares no status {case.status}.")
    if case.doctor_decision:
        raise ValueError("Caso já foi decidido pelo médico.")

    import hashlib

    file_content = uploaded_file.read()
    sha256 = hashlib.sha256(file_content).hexdigest()
    file_name = uploaded_file.name or ""
    content_type = uploaded_file.content_type or "application/octet-stream"
    file_size = uploaded_file.size or len(file_content)

    uploaded_file.seek(0)

    attachment = CaseAttachment(
        case=case,
        file=uploaded_file,
        original_filename=file_name,
        content_type=content_type,
        size_bytes=file_size,
        sha256=sha256,
        uploaded_by=user,
        upload_phase="supplemental",
        uploaded_when_case_status=case.status,
        note=note,
    )
    attachment.save()

    CaseEvent.objects.create(
        case=case,
        event_type="CASE_ATTACHMENT_SUPPLEMENT_ADDED",
        actor=user,
        actor_type="human",
        payload={
            "attachment_id": str(attachment.attachment_id),
            "original_filename": file_name,
            "content_type": content_type,
            "size_bytes": file_size,
            "note": note,
        },
    )
    return attachment


def suppress_case_attachment(
    *,
    attachment: CaseAttachment,
    user: Any,
    reason: str,
) -> None:
    """Suppress (soft-delete) an attachment with a reason."""
    if attachment.is_suppressed:
        raise ValueError("Anexo já está suprimido.")

    from django.utils import timezone

    attachment.is_suppressed = True
    attachment.suppressed_at = timezone.now()
    attachment.suppressed_by = user
    attachment.suppression_reason = reason
    attachment.save(update_fields=["is_suppressed", "suppressed_at", "suppressed_by", "suppression_reason"])

    CaseEvent.objects.create(
        case=attachment.case,
        event_type="CASE_ATTACHMENT_SUPPRESSED",
        actor=user,
        actor_type="human",
        payload={
            "attachment_id": str(attachment.attachment_id),
            "original_filename": attachment.original_filename,
            "reason": reason,
        },
    )


def post_case_communication_message(
    *,
    case: Case,
    author: Any,
    author_role: str,
    body: str,
) -> CaseCommunicationMessage:
    """Post a communication message on a case."""
    body = (body or "").strip()
    if not body:
        raise CaseCommunicationError("Mensagem não pode estar em branco.")
    if len(body) > CASE_COMMUNICATION_MAX_LENGTH:
        raise CaseCommunicationError(f"Mensagem muito longa. Máximo de {CASE_COMMUNICATION_MAX_LENGTH} caracteres.")
    if case.status == CaseStatus.CLEANED:
        raise CaseCommunicationError("Não é possível enviar mensagens em casos concluídos.")
    if not author_role:
        raise CaseCommunicationError("Papel ativo não identificado.")

    msg = CaseCommunicationMessage.objects.create(
        case=case,
        author=author,
        author_role=author_role,
        body=body,
        message_type="user",
    )

    CaseEvent.objects.create(
        case=case,
        event_type="CASE_COMMUNICATION_MESSAGE_POSTED",
        actor=author,
        actor_type="human",
        payload={
            "message_id": str(msg.message_id),
            "author_role": author_role,
            "body_preview": body[:200],
        },
    )

    return msg


def administratively_close_case(
    *,
    case: Case,
    user: Any,
    reason_code: str,
    reason_text: str,
    active_role: str,
) -> Case:
    """Encerra um caso administrativamente."""
    if not reason_text.strip():
        raise ValueError("Motivo obrigatório: forneça uma descrição do encerramento.")
    if not reason_code:
        raise ValueError("Código de motivo obrigatório.")

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)
        if case.status == CaseStatus.CLEANED:
            raise ValueError("Caso já está encerrado (CLEANED).")

        previous_status = str(case.status)
        had_lock = case.locked_by is not None

        payload: dict[str, object] = {
            "previous_status": previous_status,
            "reason_code": reason_code,
            "reason_text": reason_text.strip(),
            "active_role": active_role,
            "had_lock": had_lock,
        }

        # Clear lock
        case.locked_by = None
        case.locked_at = None
        case.locked_until = None
        case.lock_token = None
        case.lock_context = ""
        case.lock_role = ""

        # Set admin closure metadata
        case.admin_closed_by = user
        case.admin_closed_at = timezone.now()
        case.admin_closure_reason_code = reason_code
        case.admin_closure_reason_text = reason_text.strip()

        case.administratively_close(user=user, payload=payload)
        case.save()

    return Case.objects.get(pk=case.pk)
