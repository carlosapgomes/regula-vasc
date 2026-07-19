"""Pipeline orchestrator — full LLM pipeline for vascular triage.

Flow: NEW → EXTRACTING → LLM1_STRUCT → LLM2_SUGGEST → WAIT_DOCTOR

Dual-LLM: both LLM1 and LLM2 stages run primary + secondary in parallel
via asyncio.gather. Failure of one does not block the other.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from django.conf import settings

from apps.cases.models import Case
from apps.llm.models import PromptTemplate
from apps.pipeline.llm import LlmClient
from apps.pipeline.llm1_service import (
    LLM1_DEFAULT_SYSTEM_PROMPT,
    LLM1_DEFAULT_USER_PROMPT,
    Llm1Result,
    Llm1Service,
    Llm1ValidationError,
)
from apps.pipeline.llm2_service import (
    LLM2_DEFAULT_SYSTEM_PROMPT,
    LLM2_DEFAULT_USER_PROMPT,
    Llm2Result,
    Llm2Service,
)
from apps.pipeline.pdf_utils import (
    extract_agency_record_number,
    extract_pdf_text_from_path,
    extract_regulation_days_on_screen,
    strip_watermark_and_extract_record,
)

logger = logging.getLogger(__name__)


def run_pipeline(
    case_id: uuid.UUID,
    *,
    primary_llm1_client: LlmClient | None = None,
    primary_llm2_client: LlmClient | None = None,
    secondary_llm1_client: LlmClient | None = None,
    secondary_llm2_client: LlmClient | None = None,
    llm1_system_prompt: str | None = None,
    llm1_user_template: str | None = None,
    llm2_system_prompt: str | None = None,
    llm2_user_template: str | None = None,
) -> None:
    """Orchestrate the full LLM pipeline for a case.

    FSM flow (happy path):
        NEW → EXTRACTING → LLM1_STRUCT → LLM2_SUGGEST → WAIT_DOCTOR
    On error at any step: → FAILED

    Dual-LLM: when secondary clients are provided, both primary and secondary
    run in parallel for each stage. Failure of secondary does not block.

    All injectable parameters default to production values (settings/DB).
    Override them in tests to avoid needing DB templates or real LLM calls.
    """
    case = Case.objects.get(case_id=case_id)

    # Resolve clients
    if primary_llm1_client is None:
        primary_llm1_client = _create_client_from_settings(prefix="LLM1_PRIMARY")
    if primary_llm2_client is None:
        primary_llm2_client = _create_client_from_settings(prefix="LLM2_PRIMARY")

    secondary_enabled = getattr(settings, "LLM_SECONDARY_ENABLED", False)
    if secondary_enabled and secondary_llm1_client is None:
        secondary_llm1_client = _create_optional_client(prefix="LLM1_SECONDARY")
    if secondary_enabled and secondary_llm2_client is None:
        secondary_llm2_client = _create_optional_client(prefix="LLM2_SECONDARY")

    try:
        # ── Step 1: PDF Extraction ──────────────────────────────
        _run_extraction_step(case)

        # ── Step 2: LLM1 Extraction (dual) ──────────────────────
        sp1 = llm1_system_prompt or _get_prompt_content("llm1_system", LLM1_DEFAULT_SYSTEM_PROMPT)
        ut1 = llm1_user_template or _get_prompt_content("llm1_user", LLM1_DEFAULT_USER_PROMPT)

        llm1_primary_result, llm1_secondary_result = asyncio.run(
            _run_dual_llm1(
                case=case,
                extracted_text=case.extracted_text,
                system_prompt=sp1,
                user_prompt_template=ut1,
                primary_client=primary_llm1_client,
                secondary_client=secondary_llm1_client,
            )
        )

        # Save LLM1 results
        if llm1_primary_result is not None:
            case.structured_data = llm1_primary_result.structured_data
            case.llm1_primary_result = llm1_primary_result.structured_data
        if llm1_secondary_result is not None:
            case.llm1_secondary_result = llm1_secondary_result.structured_data

        if llm1_primary_result is None:
            case.save()
            case._record_event("LLM1_FAILED", payload={"error": "LLM1 primary failed"})
            _try_fail_case(case)
            return

        case.save()
        case._record_event("LLM1_OK")
        case.llm1_complete(success=True, user=None)
        case.save()

        # ── Step 3: LLM2 Suggestion (dual) ──────────────────────
        sp2 = llm2_system_prompt or _get_prompt_content("llm2_system", LLM2_DEFAULT_SYSTEM_PROMPT)
        ut2 = llm2_user_template or _get_prompt_content("llm2_user", LLM2_DEFAULT_USER_PROMPT)

        llm2_primary_result, llm2_secondary_result = asyncio.run(
            _run_dual_llm2(
                case=case,
                llm1_structured_data=case.structured_data,  # type: ignore[arg-type]
                system_prompt=sp2,
                user_prompt_template=ut2,
                primary_client=primary_llm2_client,
                secondary_client=secondary_llm2_client,
            )
        )

        # Save LLM2 results
        if llm2_primary_result is not None:
            case.suggested_action = llm2_primary_result.suggested_action
            case.llm2_primary_result = llm2_primary_result.suggested_action
        if llm2_secondary_result is not None:
            case.llm2_secondary_result = llm2_secondary_result.suggested_action

        if llm2_primary_result is None:
            case.save()
            case._record_event("LLM2_FAILED", payload={"error": "LLM2 primary failed"})
            _try_fail_case(case)
            return

        case.save()
        case._record_event("LLM2_OK")
        case.llm2_complete(success=True, user=None)
        case.save()

        # ── Step 4: Ready for doctor ────────────────────────────
        case._record_event("CASE_READY_FOR_DOCTOR")

    except Exception as exc:
        logger.exception("Pipeline failed for case %s", case_id)
        try:
            case._record_event(
                "PIPELINE_FAILED",
                payload={"error": str(exc)},
            )
            case.save()
            _try_fail_case(case)
        except Exception:
            logger.exception("Failed to record pipeline failure for case %s", case_id)


# ── Step helpers ────────────────────────────────────────────────────────────


def _run_extraction_step(case: Case) -> None:
    """Extract text from PDF, clean watermarks, populate case fields."""
    if not case.pdf_file:
        raise ValueError("Case has no PDF file to extract")

    case.start_extraction(user=None)
    case.save()

    pdf_path = Path(case.pdf_file.path)
    raw_text = extract_pdf_text_from_path(str(pdf_path))

    if not raw_text.strip():
        case._record_event("CASE_EXTRACTION_FAILED", payload={"error": "Empty PDF text"})
        case.extraction_complete(success=False, user=None)
        case.save()
        raise ValueError("PDF extraction produced empty text")

    # Clean watermark and extract metadata
    cleaned_text, record_number = strip_watermark_and_extract_record(raw_text)
    agency_number = record_number or extract_agency_record_number(raw_text)
    days_on_screen = extract_regulation_days_on_screen(raw_text)

    case.extracted_text = cleaned_text
    case.agency_record_number = agency_number
    case.regulation_days_on_screen = days_on_screen
    case.save()

    case._record_event("CASE_EXTRACTION_OK")
    case.extraction_complete(success=True, user=None)
    case.save()


async def _run_dual_llm1(
    *,
    case: Case,
    extracted_text: str,
    system_prompt: str,
    user_prompt_template: str,
    primary_client: LlmClient,
    secondary_client: LlmClient | None,
) -> tuple[Llm1Result | None, Llm1Result | None]:
    """Run LLM1 (primary + optional secondary) in parallel."""

    async def _call_llm1(client: LlmClient, label: str) -> Llm1Result | None:
        try:
            service = Llm1Service(client)
            result = await asyncio.to_thread(
                service.run,
                extracted_text=extracted_text,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
            )
            logger.info("LLM1 %s: success", label)
            return result
        except Llm1ValidationError as exc:
            logger.warning("LLM1 %s: validation error: %s", label, exc)
            case._record_event(f"LLM1_{label.upper()}_FAILED", payload={"error": str(exc)})
            return None
        except Exception as exc:
            logger.exception("LLM1 %s: unexpected error", label)
            case._record_event(f"LLM1_{label.upper()}_FAILED", payload={"error": str(exc)})
            return None

    if secondary_client is not None:
        primary_task = _call_llm1(primary_client, "primary")
        secondary_task = _call_llm1(secondary_client, "secondary")
        results = await asyncio.gather(primary_task, secondary_task, return_exceptions=True)
        primary_result: Llm1Result | None = results[0] if not isinstance(results[0], BaseException) else None
        secondary_result: Llm1Result | None = results[1] if not isinstance(results[1], BaseException) else None
        return primary_result, secondary_result
    else:
        primary_result = await _call_llm1(primary_client, "primary")
        return primary_result, None


async def _run_dual_llm2(
    *,
    case: Case,
    llm1_structured_data: dict[str, object],
    system_prompt: str,
    user_prompt_template: str,
    primary_client: LlmClient,
    secondary_client: LlmClient | None,
) -> tuple[Llm2Result | None, Llm2Result | None]:
    """Run LLM2 (primary + optional secondary) in parallel."""

    async def _call_llm2(client: LlmClient, label: str) -> Llm2Result | None:
        try:
            service = Llm2Service(client)
            result = await asyncio.to_thread(
                service.run,
                llm1_structured_data=llm1_structured_data,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
            )
            logger.info("LLM2 %s: success", label)
            return result
        except ValueError as exc:
            logger.warning("LLM2 %s: validation error: %s", label, exc)
            case._record_event(f"LLM2_{label.upper()}_FAILED", payload={"error": str(exc)})
            return None
        except Exception as exc:
            logger.exception("LLM2 %s: unexpected error", label)
            case._record_event(f"LLM2_{label.upper()}_FAILED", payload={"error": str(exc)})
            return None

    if secondary_client is not None:
        primary_task = _call_llm2(primary_client, "primary")
        secondary_task = _call_llm2(secondary_client, "secondary")
        results = await asyncio.gather(primary_task, secondary_task, return_exceptions=True)
        primary_result: Llm2Result | None = results[0] if not isinstance(results[0], BaseException) else None
        secondary_result: Llm2Result | None = results[1] if not isinstance(results[1], BaseException) else None
        return primary_result, secondary_result
    else:
        primary_result = await _call_llm2(primary_client, "primary")
        return primary_result, None


# ── Prompt helpers ───────────────────────────────────────────────────────────


def _get_prompt_content(name: str, fallback: str) -> str:
    """Resolve prompt content from DB or return fallback."""
    template = PromptTemplate.get_active(name)
    if template is not None:
        return template.content
    logger.warning("PromptTemplate %r not found — using fallback", name)
    return fallback


# ── Client factories ────────────────────────────────────────────────────────


def _create_client_from_settings(*, prefix: str) -> LlmClient:
    """Create LLM client from Django settings using a prefix."""
    from apps.pipeline.llm import create_llm_client_from_settings

    return create_llm_client_from_settings(prefix=prefix)


def _create_optional_client(*, prefix: str) -> LlmClient | None:
    """Create an optional secondary LLM client. Returns None if not configured."""
    from apps.pipeline.llm import create_llm_client_from_settings

    try:
        return create_llm_client_from_settings(prefix=prefix)
    except (ValueError, KeyError, ImportError) as exc:
        logger.warning("Secondary LLM client %s not available: %s", prefix, exc)
        return None


# ── FSM helpers ─────────────────────────────────────────────────────────────


def _try_fail_case(case: Case) -> None:
    """Attempt to transition case to FAILED, best-effort.

    Tries llm2_complete first (most likely state when LLM2 fails),
    then llm1_complete as fallback (if the case hasn't progressed yet).
    """
    from django_fsm import TransitionNotAllowed

    for method in [case.llm2_complete, case.llm1_complete]:
        try:
            method(success=False, user=None)
            case.save()
            return
        except TransitionNotAllowed:
            continue

    case.save()
