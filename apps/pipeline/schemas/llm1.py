"""Pydantic schema para extração estruturada de dados vasculares (LLM1).

Schema baseado no documento RecomendacoesRelatoriosRegulacaoVascular_HMH.pdf.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceFlag = Literal["yes", "no", "unknown"]
BrazilStateUf = Literal[
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]
PulseNotation = Literal["3+", "2+", "1+", "0", "-", "?"]
PulseNotationNullable = PulseNotation | None


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid")


# ── Patient ─────────────────────────────────────────────────────────────────


class Llm1Patient(StrictModel):
    """Identidade e dados demográficos do paciente."""

    name: str | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    sex: Literal["M", "F", "Outro"] | None = None


# ── Origin Context ─────────────────────────────────────────────────────────


class Llm1OriginContext(StrictModel):
    """Contexto de origem: cidade, hospital, unidade, UF."""

    city: str | None = None
    hospital: str | None = None
    unit: str | None = None
    state_uf: BrazilStateUf | None = None


# ── Referral ───────────────────────────────────────────────────────────────


class Llm1Referral(StrictModel):
    """Dados de encaminhamento / queixa principal."""

    main_complaint: str | None = None
    evolution_time_days: int | None = Field(default=None, ge=0)
    affected_limb: Literal["left", "right", "bilateral", "unknown"] = "unknown"
    suspected_diagnosis: str | None = None


# ── Lesion ─────────────────────────────────────────────────────────────────


class Llm1Lesion(StrictModel):
    """Descrição detalhada da lesão vascular."""

    exact_location: str | None = None
    size_cm: float | None = Field(default=None, ge=0)
    depth: Literal["superficial", "profunda", "expondo_osso", "expondo_tendao", "unknown"] = "unknown"
    aspect: str | None = None  # descritivo: "necrótica", "granulação", etc.
    odor: EvidenceFlag = "unknown"
    larvae: EvidenceFlag = "unknown"
    gangrene_location: str | None = None  # "dedos", "antepé", etc.
    necrosis_type: Literal["seca", "umida", "gasosa", "none", "unknown"] = "unknown"
    purulent_secretion: EvidenceFlag = "unknown"


# ── Pain ───────────────────────────────────────────────────────────────────


class Llm1Pain(StrictModel):
    """Avaliação de dor e claudicação."""

    has_pain: EvidenceFlag = "unknown"
    rest_pain: EvidenceFlag = "unknown"
    night_pain: EvidenceFlag = "unknown"
    improves_with_dangling: EvidenceFlag = "unknown"
    prior_claudication: EvidenceFlag = "unknown"
    sudden_onset: EvidenceFlag = "unknown"


# ── Pulses ─────────────────────────────────────────────────────────────────


class Llm1Pulses(StrictModel):
    """Avaliação de pulsos arteriais por membro.

    Notação: 3+ (amplo), 2+ (normal), 1+ (diminuído),
    0 (ausente não Doppler), - (ausente ao Doppler), ? (não avaliado).
    """

    femoral_r: PulseNotationNullable = None
    femoral_l: PulseNotationNullable = None
    popliteal_r: PulseNotationNullable = None
    popliteal_l: PulseNotationNullable = None
    tibial_posterior_r: PulseNotationNullable = None
    tibial_posterior_l: PulseNotationNullable = None
    pedal_r: PulseNotationNullable = None
    pedal_l: PulseNotationNullable = None


# ── Edema ──────────────────────────────────────────────────────────────────


class Llm1Edema(StrictModel):
    """Avaliação de edema nos membros inferiores."""

    present: EvidenceFlag = "unknown"
    unilateral_bilateral: Literal["unilateral", "bilateral", "none", "unknown"] = "unknown"
    depressible: EvidenceFlag = "unknown"
    hardened: EvidenceFlag = "unknown"
    hot: EvidenceFlag = "unknown"
    cold: EvidenceFlag = "unknown"


# ── Infection ──────────────────────────────────────────────────────────────


class Llm1Infection(StrictModel):
    """Sinais de infecção locais e sistêmicos."""

    local_signs: list[str] = Field(default_factory=list)
    systemic_signs: list[str] = Field(default_factory=list)


# ── History / Antecedentes ─────────────────────────────────────────────────


class Llm1History(StrictModel):
    """Antecedentes patológicos e fatores de risco vascular."""

    diabetes: EvidenceFlag = "unknown"
    smoking: EvidenceFlag = "unknown"
    hypertension: EvidenceFlag = "unknown"
    ckd: EvidenceFlag = "unknown"  # chronic kidney disease (DRC)
    mi: EvidenceFlag = "unknown"  # myocardial infarction (IAM)
    stroke: EvidenceFlag = "unknown"  # AVC
    arrhythmia: EvidenceFlag = "unknown"
    heart_failure: EvidenceFlag = "unknown"  # ICC
    copd: EvidenceFlag = "unknown"  # DPOC
    prior_amputation: EvidenceFlag = "unknown"
    prior_revascularization: EvidenceFlag = "unknown"
    anticoagulation_use: EvidenceFlag = "unknown"
    antiplatelet_use: EvidenceFlag = "unknown"


# ── Labs ───────────────────────────────────────────────────────────────────


class Llm1Labs(StrictModel):
    """Exames laboratoriais relevantes."""

    hemoglobin: float | None = Field(default=None, ge=0)
    leukocytes: int | None = Field(default=None, ge=0)
    crp: float | None = Field(default=None, ge=0)  # PCR
    glucose: int | None = Field(default=None, ge=0)
    creatinine: float | None = Field(default=None, ge=0)
    urea: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)
    lactate: float | None = Field(default=None, ge=0)


# ── Imaging ────────────────────────────────────────────────────────────────


class Llm1Imaging(StrictModel):
    """Exames de imagem realizados e seus achados principais."""

    xray: str | None = None  # descrição do achado
    duplex: str | None = None
    angiotomography: str | None = None


# ── Acute Ischemia ─────────────────────────────────────────────────────────


class Llm1AcuteIschemia(StrictModel):
    """Sinais de isquemia aguda (Rutherford)."""

    signs: list[str] = Field(default_factory=list)
    time_onset_hours: int | None = Field(default=None, ge=0)
    rutherford_category: Literal["I", "IIa", "IIb", "III", "unknown"] = "unknown"


# ── Extraction Quality ─────────────────────────────────────────────────────


class Llm1ExtractionQuality(StrictModel):
    """Metadados de qualidade da extração."""

    confidence: Literal["alta", "media", "baixa"]
    missing_fields: list[str] = Field(default_factory=list)


# ── Top-level Response ─────────────────────────────────────────────────────


class Llm1VascularResponse(StrictModel):
    """Schema completo da resposta LLM1 — extração vascular estruturada."""

    patient: Llm1Patient = Field(default_factory=Llm1Patient)
    origin_context: Llm1OriginContext = Field(default_factory=Llm1OriginContext)
    referral: Llm1Referral = Field(default_factory=Llm1Referral)
    lesion: Llm1Lesion = Field(default_factory=Llm1Lesion)
    pain: Llm1Pain = Field(default_factory=Llm1Pain)
    pulses: Llm1Pulses = Field(default_factory=Llm1Pulses)
    edema: Llm1Edema = Field(default_factory=Llm1Edema)
    infection: Llm1Infection = Field(default_factory=Llm1Infection)
    history: Llm1History = Field(default_factory=Llm1History)
    labs: Llm1Labs = Field(default_factory=Llm1Labs)
    imaging: Llm1Imaging = Field(default_factory=Llm1Imaging)
    acute_ischemia: Llm1AcuteIschemia = Field(default_factory=Llm1AcuteIschemia)
    extraction_quality: Llm1ExtractionQuality = Field(
        default_factory=lambda: Llm1ExtractionQuality(
            confidence="media",
            missing_fields=[],
        )
    )
