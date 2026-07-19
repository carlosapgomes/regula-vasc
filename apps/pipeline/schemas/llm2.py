"""Pydantic schema para o parecer de sugestão clínica (LLM2).

Schema simplificado para triagem vascular: accept/deny com critérios e confiança.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


class Llm2VascularResponse(StrictModel):
    """Schema da resposta LLM2 — parecer de triagem vascular."""

    suggestion: Literal["accept", "deny"]
    recommendation_text: str = Field(max_length=2000)
    acceptance_criteria_met: list[str] = Field(default_factory=list)
    exclusion_criteria_met: list[str] = Field(default_factory=list)
    confidence: Literal["alta", "media", "baixa"]
    rationale: str = Field(max_length=2000)
