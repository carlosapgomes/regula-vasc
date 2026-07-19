"""Case, CaseEvent, CaseAttachment, and CaseCommunicationMessage models."""

import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django_fsm import FSMField, transition


class ReturnState:
    """Target callable for django-fsm that resolves target from return value."""

    def get_state(self, instance, transition, result: str, args, kwargs) -> str:
        return result


class CaseStatus(models.TextChoices):
    """Estados do caso (10 estados)."""

    NEW = "NEW", "New"
    EXTRACTING = "EXTRACTING", "Extracting"
    LLM1_STRUCT = "LLM1_STRUCT", "LLM1 Struct"
    LLM2_SUGGEST = "LLM2_SUGGEST", "LLM2 Suggest"
    WAIT_DOCTOR = "WAIT_DOCTOR", "Wait Doctor"
    DOCTOR_ACCEPTED = "DOCTOR_ACCEPTED", "Doctor Accepted"
    DOCTOR_DENIED = "DOCTOR_DENIED", "Doctor Denied"
    WAIT_NURSE_ACK = "WAIT_NURSE_ACK", "Wait Nurse Ack"
    FAILED = "FAILED", "Failed"
    CLEANED = "CLEANED", "Cleaned"


class Case(models.Model):
    """Caso de triagem vascular — entidade central do sistema."""

    case_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # FSM Status
    status = FSMField(
        max_length=30,
        choices=CaseStatus.choices,
        default=CaseStatus.NEW,
        protected=True,
    )

    # Origin / PDF
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cases_created",
    )
    pdf_file = models.FileField(upload_to="pdfs/%Y/%m/", blank=True, null=True)
    extracted_text = models.TextField(blank=True)
    agency_record_number = models.CharField(max_length=20, blank=True)
    regulation_days_on_screen = models.PositiveIntegerField(null=True, blank=True)

    # LLM artifacts
    structured_data = models.JSONField(blank=True, null=True)
    # Dual-LLM results for LLM1 (extraction)
    llm1_primary_result = models.JSONField(blank=True, null=True)
    llm1_secondary_result = models.JSONField(blank=True, null=True)
    # Dual-LLM results for LLM2 (suggestion)
    llm2_primary_result = models.JSONField(blank=True, null=True)
    llm2_secondary_result = models.JSONField(blank=True, null=True)
    suggested_action = models.JSONField(blank=True, null=True)

    # Doctor decision
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases_decided",
    )
    doctor_decision = models.CharField(max_length=10, blank=True)
    doctor_reason = models.TextField(blank=True)
    doctor_observation = models.CharField(max_length=500, blank=True)
    doctor_decided_at = models.DateTimeField(null=True, blank=True)

    # Nurse acknowledgement
    nurse_ack_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases_nurse_acknowledged",
    )
    nurse_ack_at = models.DateTimeField(null=True, blank=True)

    # Administrative closure
    admin_closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases_admin_closed",
    )
    admin_closed_at = models.DateTimeField(null=True, blank=True)
    admin_closure_reason_code = models.CharField(max_length=40, blank=True)
    admin_closure_reason_text = models.TextField(blank=True)

    # Lock / Lease fields
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases_locked",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    lock_token = models.UUIDField(null=True, blank=True)
    lock_context = models.CharField(max_length=40, blank=True)
    lock_role = models.CharField(max_length=30, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "locked_until"]),
        ]

    def __str__(self) -> str:
        return f"Case {self.case_id} [{self.status}]"

    @property
    def patient_name(self) -> str:
        sd = self.structured_data
        if isinstance(sd, dict):
            patient = sd.get("patient", {})
            if isinstance(patient, dict):
                name = patient.get("name")
                if name:
                    return str(name)
        return "Paciente"

    @property
    def patient_age(self) -> str:
        sd = self.structured_data
        if isinstance(sd, dict):
            patient = sd.get("patient", {})
            if isinstance(patient, dict):
                age = patient.get("age", "")
                return str(age) if age else ""
        return ""

    @property
    def doctor_display(self) -> str:
        if not self.doctor:
            return ""
        registration = self.doctor.professional_registration_display
        if registration:
            return f"{self.doctor.display_name} — {registration}"
        return self.doctor.display_name

    # ── FSM Transitions ──────────────────────────────────────────────────

    @transition(field=status, source=CaseStatus.NEW, target=CaseStatus.EXTRACTING)
    def start_extraction(self, user=None):
        self._record_event("CASE_START_EXTRACTION", user=user)

    @transition(field=status, source=CaseStatus.EXTRACTING, target=ReturnState())
    def extraction_complete(self, success: bool, user=None):
        if not success:
            self._record_event("CASE_EXTRACTION_FAILED", user=user)
            return CaseStatus.FAILED
        self._record_event("CASE_EXTRACTION_OK", user=user)
        return CaseStatus.LLM1_STRUCT

    @transition(field=status, source=CaseStatus.LLM1_STRUCT, target=ReturnState())
    def llm1_complete(self, success: bool, user=None):
        self._record_event("LLM1_OK" if success else "LLM1_FAILED", user=user)
        return CaseStatus.FAILED if not success else CaseStatus.LLM2_SUGGEST

    @transition(field=status, source=CaseStatus.LLM2_SUGGEST, target=ReturnState())
    def llm2_complete(self, success: bool, user=None):
        self._record_event("LLM2_OK" if success else "LLM2_FAILED", user=user)
        return CaseStatus.FAILED if not success else CaseStatus.WAIT_DOCTOR

    @transition(field=status, source=CaseStatus.WAIT_DOCTOR, target=ReturnState())
    def doctor_decide(self, decision: str, user=None):
        self._record_event(
            f"DOCTOR_{decision.upper()}",
            user=user,
            payload={"decision": decision},
        )
        return CaseStatus.DOCTOR_DENIED if decision == "deny" else CaseStatus.DOCTOR_ACCEPTED

    @transition(
        field=status,
        source=[CaseStatus.DOCTOR_ACCEPTED, CaseStatus.DOCTOR_DENIED],
        target=CaseStatus.WAIT_NURSE_ACK,
    )
    def ready_for_nurse(self, user=None):
        self._record_event("CASE_READY_FOR_NURSE", user=user)

    @transition(field=status, source=CaseStatus.WAIT_NURSE_ACK, target=CaseStatus.CLEANED)
    def nurse_ack(self, user=None):
        self._record_event("CASE_NURSE_ACK", user=user)

    # Administrative close from any non-CLEANED state
    @transition(
        field=status,
        source=[
            CaseStatus.NEW,
            CaseStatus.EXTRACTING,
            CaseStatus.LLM1_STRUCT,
            CaseStatus.LLM2_SUGGEST,
            CaseStatus.WAIT_DOCTOR,
            CaseStatus.DOCTOR_ACCEPTED,
            CaseStatus.DOCTOR_DENIED,
            CaseStatus.WAIT_NURSE_ACK,
            CaseStatus.FAILED,
        ],
        target=CaseStatus.CLEANED,
    )
    def administratively_close(self, *, user=None, payload=None):
        self._record_event("CASE_ADMINISTRATIVELY_CLOSED", user=user, payload=payload or {})

    def _record_event(
        self,
        event_type: str,
        *,
        user=None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self._pending_event = {
            "event_type": event_type,
            "actor": user,
            "actor_type": "human" if user else "system",
            "payload": payload or {},
        }


class CaseEvent(models.Model):
    """Trilha de auditoria append-only."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_type = models.CharField(max_length=10)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    event_type = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["case", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
        ]

    def __str__(self) -> str:
        return f"CaseEvent {self.event_type} @ {self.timestamp}"


ACCEPTED_ATTACHMENT_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
CONTENT_TYPE_EXTENSION_MAP: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _extension_for_content_type(content_type: str) -> str:
    return CONTENT_TYPE_EXTENSION_MAP.get(content_type, ".bin")


def case_attachment_upload_to(instance: "CaseAttachment", filename: str) -> str:
    ext = _extension_for_content_type(instance.content_type)
    return os.path.join(
        "case_attachments",
        str(instance.case_id),
        f"{instance.attachment_id}{ext}",
    )


class CaseAttachment(models.Model):
    """Anexo clínico vinculado a um Case."""

    attachment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=case_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="case_attachments_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Suppression fields
    is_suppressed = models.BooleanField(default=False, db_index=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    suppressed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="case_attachments_suppressed",
    )
    suppression_reason = models.TextField(blank=True)

    # Upload phase
    upload_phase = models.CharField(max_length=20, default="initial")
    uploaded_when_case_status = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["case", "created_at"]),
        ]

    def clean(self) -> None:
        if self.content_type not in ACCEPTED_ATTACHMENT_CONTENT_TYPES:
            raise ValidationError(
                f"Tipo de arquivo '{self.content_type}' não aceito. "
                f"Aceitos: {', '.join(sorted(ACCEPTED_ATTACHMENT_CONTENT_TYPES))}"
            )

    def __str__(self) -> str:
        sup = " (suprimido)" if self.is_suppressed else ""
        return f"CaseAttachment {self.attachment_id} [{self.original_filename}]{sup}"


class CaseCommunicationMessage(models.Model):
    """Mensagem de comunicação operacional vinculada a um Case."""

    message_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="communication_messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="case_communication_messages",
    )
    author_role = models.CharField(max_length=30, blank=True)
    body = models.TextField()
    message_type = models.CharField(max_length=20, default="user")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["case", "created_at"])]

    def clean(self) -> None:
        if self.message_type == "user":
            if self.author is None:
                raise ValidationError("Mensagens manuais (message_type='user') exigem author.")
            if not self.author_role:
                raise ValidationError("Mensagens manuais (message_type='user') exigem author_role.")
        if self.message_type not in ("user", "system"):
            raise ValidationError(f"message_type inválido: '{self.message_type}'. Use 'user' ou 'system'.")

    def __str__(self) -> str:
        return f"CaseCommunicationMessage {self.message_id} [{self.author_role}]"
