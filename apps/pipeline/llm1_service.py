"""LLM1 Service — extração de dados vasculares estruturados com Pydantic v2.

Chama o LLM1, valida a resposta contra o schema Llm1VascularResponse,
e retorna os dados estruturados.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError as PydanticValidationError

from apps.pipeline.json_parser import LlmJsonParseError, decode_llm_json_object
from apps.pipeline.llm import LlmClient
from apps.pipeline.schemas.llm1 import Llm1VascularResponse

# ── Default prompts (vascular triage) ──────────────────────────────────────

LLM1_DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente clínico especializado em triagem de cirurgia vascular. "
    "Retorne APENAS JSON válido que siga estritamente o schema de resposta vascular. "
    "Escreva todos os campos narrativos em português brasileiro (pt-BR). "
    "Não inclua markdown, blocos de código ou chaves extras. "
    "Não invente fatos; use null/unknown quando faltar informação. "
    "Extraia TODOS os campos listados no schema: patient, origin_context, "
    "referral, lesion, pain, pulses, edema, infection, history, labs, "
    "imaging, acute_ischemia, extraction_quality. "
    "Para pulsos, use a notação padrão: 3+ (amplo), 2+ (normal), "
    "1+ (diminuído), 0 (ausente sem Doppler), - (ausente ao Doppler), "
    "? (não avaliado). "
    "Inferência fisiológica: pulso poplíteo presente implica pulso femoral "
    "presente (mesmo que não explicitamente descrito). "
    "Classifique a síndrome de isquemia aguda segundo Rutherford (I, IIa, IIb, III) "
    "quando os sinais estiverem presentes. "
    "Extraia dados laboratoriais com valores numéricos sempre que disponíveis. "
    "Para comorbidades/antecedentes (history), use 'yes' apenas quando houver "
    "evidência textual explícita do diagnóstico; 'no' quando explicitamente negado; "
    "'unknown' quando não mencionado."
)

LLM1_DEFAULT_USER_PROMPT = (
    "Tarefa: extrair dados estruturados de um relatório de regulação vascular. "
    "Exigir evidência textual explícita para cada campo objetivo. "
    "Quando não houver evidência textual, retornar 'unknown' (para flags) "
    "ou null (para campos numéricos e textuais). "
    "Extraia TODOS os blocos do schema, incluindo: "
    "patient (nome, idade, sexo), "
    "origin_context (cidade, hospital, unidade, UF), "
    "referral (queixa principal, tempo de evolução, membro afetado, diagnóstico suspeito), "
    "lesion (localização exata, tamanho, profundidade, aspecto, odor, larvas, "
    "localização de gangrena, tipo de necrose, secreção purulenta), "
    "pain (dor, dor em repouso, dor noturna, melhora ao pendurar, claudicação prévia, "
    "início súbito), "
    "pulses (femoral D/E, poplíteo D/E, tibial posterior D/E, pedioso D/E), "
    "edema (presente, unilateral/bilateral, depressível, endurecido, quente, frio), "
    "infection (sinais locais, sinais sistêmicos), "
    "history (diabetes, tabagismo, HAS, DRC, IAM, AVC, arritmia, ICC, DPOC, "
    "amputação prévia, revascularização prévia, uso de anticoagulante, antiagregante), "
    "labs (hemoglobina, leucócitos, PCR, glicose, creatinina, ureia, potássio, lactato), "
    "imaging (raio-X, duplex, angiotomografia), "
    "acute_ischemia (sinais, tempo de início em horas, categoria Rutherford), "
    "extraction_quality (confiança: alta/média/baixa, campos faltantes)."
)


# ── Exceptions ──────────────────────────────────────────────────────────────


class Llm1ValidationError(RuntimeError):
    """LLM1 response failed Pydantic validation."""


# ── Result ──────────────────────────────────────────────────────────────────


@dataclass
class Llm1Result:
    """Validated and normalized LLM1 artifacts for persistence."""

    structured_data: dict[str, object]


# ── Service ─────────────────────────────────────────────────────────────────


class Llm1Service:
    """Execute LLM1 call, enforce vascular schema validation."""

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        extracted_text: str,
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm1Result:
        """Execute LLM1 extraction with full Pydantic v2 validation.

        Args:
            extracted_text: Raw text extracted from the medical report PDF.
            system_prompt: System prompt for the LLM.
            user_prompt_template: User prompt template (will be appended with the text).

        Returns:
            Llm1Result with structured_data (model_dump mode="json").

        Raises:
            Llm1ValidationError: If JSON parsing or schema validation fail.
        """
        # Build final user prompt
        user_prompt = f"{user_prompt_template}\n\nTexto clínico do relatório:\n{extracted_text}"

        # Call the LLM
        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Decode JSON, validate schema
        validated = _decode_and_validate(raw_response=raw_response)

        # Serialize to JSON-safe dict via model_dump
        structured = validated.model_dump(mode="json")

        return Llm1Result(structured_data=structured)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _decode_and_validate(*, raw_response: str) -> Llm1VascularResponse:
    """Decode LLM JSON, validate against vascular schema.

    Raises Llm1ValidationError on any failure.
    """
    try:
        decoded = decode_llm_json_object(raw_response)
    except LlmJsonParseError as error:
        raise Llm1ValidationError("LLM1 returned non-JSON payload") from error

    try:
        validated = Llm1VascularResponse.model_validate(decoded)
    except PydanticValidationError as error:
        raise Llm1ValidationError(f"LLM1 schema validation failed: {error}") from error

    return validated
