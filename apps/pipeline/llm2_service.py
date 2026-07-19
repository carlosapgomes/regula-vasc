"""LLM2 Service — parecer de sugestão clínica para triagem vascular.

Chama o LLM2 com os dados estruturados do LLM1 e retorna
um parecer de aceite/recusa baseado nos critérios de cirurgia vascular.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from apps.pipeline.json_parser import decode_llm_json_object
from apps.pipeline.llm import LlmClient
from apps.pipeline.schemas.llm2 import Llm2VascularResponse

# ── Default prompts (vascular triage criteria) ─────────────────────────────

LLM2_DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente clínico especializado em triagem de cirurgia vascular. "
    "Sua função é analisar dados clínicos estruturados de um paciente e emitir "
    "um parecer de aceite (accept) ou recusa (deny) para cirurgia vascular, "
    "baseado estritamente nos critérios de triagem abaixo. "
    "Retorne APENAS JSON válido. Não inclua markdown, blocos de código ou "
    "chaves extras. Escreva todos os campos narrativos em português brasileiro (pt-BR)."
)

LLM2_DEFAULT_USER_PROMPT = (
    "Tarefa: analisar o caso abaixo e emitir seu parecer de triagem vascular.\n\n"
    "CRITÉRIOS DE ACEITAÇÃO (pelo menos um deve ser atendido):\n"
    "1. Lesão trófica em membro inferior com pulsos distais ausentes ou "
    "diminuídos (isquemia crítica)\n"
    "2. Gangrena de dedos ou antepé com pulso poplíteo palpável (possibilidade "
    "de amputação menor)\n"
    "3. Isquemia aguda Rutherford I ou IIa (viabilidade ameaçada mas recuperável)\n"
    "4. Infecção de pé diabético com isquemia associada (pé diabético isquêmico-infeccioso)\n"
    "5. Aneurisma arterial periférico com risco de ruptura\n\n"
    "CRITÉRIOS DE EXCLUSÃO (qualquer um implica recusa):\n"
    "1. Isquemia aguda Rutherford IIb ou III (necessita revascularização de urgência — "
    "fora do escopo da regulação)\n"
    "2. Paciente sem pulsos distais mas SEM lesão trófica (claudicação limitante "
    "— tratamento eletivo, não regulação de urgência)\n"
    "3. Sepse não controlada com instabilidade hemodinâmica\n"
    "4. Creatinina > 2.5 mg/dL sem diálise estabelecida\n"
    "5. IAM ou AVC há menos de 30 dias\n\n"
    "INSTRUÇÕES ADICIONAIS:\n"
    "- Pacientes com pulsos TODOS presentes e sem lesão: recusar (não é caso cirúrgico vascular)\n"
    "- Pacientes com comorbidades compensadas (DM, HAS controlada, DRC estável): aceitar\n"
    "- Na dúvida sobre viabilidade do membro, favorecer a avaliação presencial (accept)\n"
    "- Confiança alta: critérios claros e dados completos\n"
    "- Confiança média: alguns dados faltando mas critério maior preenchido\n"
    "- Confiança baixa: dados insuficientes para decisão segura\n"
)


@dataclass
class Llm2Result:
    """Result from LLM2 decision suggestion."""

    suggested_action: dict[str, object]


class Llm2Service:
    """Calls LLM2: suggests a clinical decision based on LLM1 structured data."""

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def run(
        self,
        *,
        llm1_structured_data: dict[str, object],
        system_prompt: str,
        user_prompt_template: str,
    ) -> Llm2Result:
        """Execute LLM2 suggestion.

        Args:
            llm1_structured_data: Structured data output from LLM1.
            system_prompt: System prompt for the LLM.
            user_prompt_template: Template with {llm1_structured_data} placeholder.

        Returns:
            Llm2Result with suggested_action dict.

        Raises:
            ValueError: If JSON parsing or schema validation fail.
        """
        llm1_json = json.dumps(llm1_structured_data, ensure_ascii=False)

        user_prompt = (
            f"{user_prompt_template}\n\n"
            f"Dados extraídos do paciente (JSON LLM1):\n{llm1_json}\n\n"
            "Retorne APENAS JSON válido com os campos: suggestion, recommendation_text, "
            "acceptance_criteria_met, exclusion_criteria_met, confidence, rationale."
        )

        raw_response = self._client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        decoded = decode_llm_json_object(raw_response)

        try:
            validated = Llm2VascularResponse.model_validate(decoded)
        except ValidationError as exc:
            raise ValueError(f"LLM2 schema validation failed: {exc}") from exc

        return Llm2Result(
            suggested_action=validated.model_dump(mode="json"),
        )
