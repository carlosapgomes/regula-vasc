"""Business logic for intake file processing."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.cases.models import (
    ACCEPTED_ATTACHMENT_CONTENT_TYPES,
    Case,
    CaseAttachment,
)

if TYPE_CHECKING:
    from apps.accounts.models import User as AccountsUser

logger = logging.getLogger(__name__)

# ── Validation errors ──────────────────────────────────────────────────


class FileValidationError(ValueError):
    """A single file failed validation."""


class BatchValidationError(ValueError):
    """The entire batch is invalid."""


class AttachmentValidationError(ValueError):
    """An attachment file failed validation."""


# ── PDF validation ─────────────────────────────────────────────────────


def validate_single_file(file: UploadedFile) -> None:
    """Validate a single uploaded PDF file.

    Raises ``FileValidationError`` if the file fails any check.
    """
    file_name = file.name or ""
    file_size = file.size or 0

    if not file_name.lower().endswith(".pdf"):
        raise FileValidationError(f'"{file_name}" não é um arquivo PDF.')

    max_file_size = settings.INTAKE_MAX_UPLOAD_BYTES_PER_FILE
    if file_size > max_file_size:
        raise FileValidationError(
            f'"{file_name}" excede o limite de {max_file_size // (1024 * 1024)} MB '
            f"({file_size / (1024 * 1024):.1f} MB)."
        )


def validate_batch(files: list[UploadedFile]) -> None:
    """Validate the entire batch before per-file processing."""
    if not files:
        raise BatchValidationError("Nenhum arquivo enviado.")

    max_files = settings.INTAKE_MAX_FILES_PER_BATCH
    if len(files) > max_files:
        raise BatchValidationError(f"Máximo de {max_files} arquivos por lote. Recebidos: {len(files)}.")

    total_bytes = sum(f.size or 0 for f in files)
    max_batch = settings.INTAKE_MAX_UPLOAD_BYTES_PER_BATCH
    if total_bytes > max_batch:
        raise BatchValidationError(
            f"Tamanho total do lote ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_batch // (1024 * 1024)} MB."
        )


# ── Attachment validation ────────────────────────────────────────────────


def validate_attachment_file(file: UploadedFile) -> None:
    """Validate a single attachment file.

    Raises ``AttachmentValidationError`` if the file fails any check.
    """
    file_name = file.name or ""
    file_size = file.size or 0
    content_type = (file.content_type or "").lower()

    ext = os.path.splitext(file_name)[1].lower()
    if ext not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise AttachmentValidationError(f'"{file_name}" formato não aceito. Use PDF, JPEG ou PNG.')

    if content_type and content_type not in ACCEPTED_ATTACHMENT_CONTENT_TYPES:
        raise AttachmentValidationError(f'"{file_name}" tipo de conteúdo não aceito: {content_type}.')

    max_size = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE
    if file_size > max_size:
        raise AttachmentValidationError(
            f'"{file_name}" excede o limite de {max_size // (1024 * 1024)} MB ({file_size / (1024 * 1024):.1f} MB).'
        )


def validate_attachments(attachments: list[UploadedFile], pdf_count: int) -> None:
    """Validate the full set of attachments before processing."""
    if not attachments:
        return

    if pdf_count != 1:
        raise AttachmentValidationError(
            "Anexos só são permitidos quando há exatamente 1 relatório principal. "
            "Remova os anexos ou envie apenas 1 PDF."
        )

    max_attachments = settings.INTAKE_MAX_ATTACHMENTS_PER_CASE
    if len(attachments) > max_attachments:
        raise AttachmentValidationError(f"Máximo de {max_attachments} anexos por caso. Recebidos: {len(attachments)}.")

    for att in attachments:
        validate_attachment_file(att)

    total_bytes = sum(f.size or 0 for f in attachments)
    max_total = settings.INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE
    if total_bytes > max_total:
        raise AttachmentValidationError(
            f"Tamanho total dos anexos ({total_bytes / (1024 * 1024):.1f} MB) "
            f"excede o limite de {max_total // (1024 * 1024)} MB."
        )


# ── Attachment creation ─────────────────────────────────────────────────


def create_case_attachment(
    *,
    case: Case,
    uploaded_file: UploadedFile,
    user: AccountsUser,
    upload_phase: str = "initial",
) -> CaseAttachment:
    """Create a CaseAttachment from an uploaded file."""
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
        upload_phase=upload_phase,
        uploaded_when_case_status=case.status,
    )
    attachment.save()
    return attachment


def record_attachment_event(attachment: CaseAttachment) -> None:
    """Record CASE_ATTACHMENT_ADDED audit event."""
    from apps.cases.models import CaseEvent

    CaseEvent.objects.create(
        case=attachment.case,
        event_type="CASE_ATTACHMENT_ADDED",
        actor=attachment.uploaded_by,
        actor_type="human",
        payload={
            "attachment_id": str(attachment.attachment_id),
            "original_filename": attachment.original_filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
            "sha256": attachment.sha256,
        },
    )


# ── Processing ──────────────────────────────────────────────────────────


def process_uploaded_files(
    files: list[UploadedFile],
    user: AccountsUser,
    attachments: list[UploadedFile] | None = None,
) -> tuple[list[Case], list[str]]:
    """Validate and process a batch of uploaded PDFs with optional attachments.

    Returns:
        A tuple ``(cases, errors)`` where ``cases`` is the list of
        successfully created ``Case`` instances and ``errors`` is a list
        of human-readable error messages.
    """
    cases: list[Case] = []
    errors: list[str] = []

    try:
        validate_batch(files)
    except BatchValidationError as exc:
        return [], [str(exc)]

    att_list = attachments or []
    attachment_error: str | None = None
    if att_list:
        try:
            validate_attachments(att_list, pdf_count=len(files))
        except AttachmentValidationError as exc:
            attachment_error = str(exc)
            if len(files) == 1:
                errors.append(str(exc))
                return [], errors

    for file in files:
        try:
            validate_single_file(file)
        except FileValidationError as exc:
            errors.append(str(exc))
            continue

        case = _create_case_from_file(file, user)
        cases.append(case)

    if attachment_error:
        errors.append(attachment_error)

    if cases and att_list and len(cases) == 1 and not attachment_error:
        case = cases[0]
        for att_file in att_list:
            try:
                attachment = create_case_attachment(
                    case=case,
                    uploaded_file=att_file,
                    user=user,
                    upload_phase="initial",
                )
                record_attachment_event(attachment)
            except Exception as exc:
                logger.exception("Failed to save attachment for case %s", case.case_id)
                errors.append(f"Erro ao salvar anexo: {exc}")

    return cases, errors


def _create_case_from_file(file: UploadedFile, user: AccountsUser) -> Case:
    """Create a single Case from an uploaded PDF file and enqueue pipeline."""
    case = Case.objects.create(created_by=user)
    case.pdf_file = file
    case.save()

    case.start_extraction(user=user)
    case.save()

    # Lazy import to avoid django-q2 dependency at module level
    from apps.pipeline.tasks import enqueue_pipeline

    enqueue_pipeline(case.case_id)

    return case
