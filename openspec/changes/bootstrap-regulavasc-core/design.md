# Design: Bootstrap RegulaVasc Core

## Context

O projeto `regula-vasc` é um sistema greenfield de apoio à regulação médica vascular. Dois projetos de referência informam as decisões:

- **`ats-web`** (Django SSR, 1755 testes, mesmo stack, fluxo EDA com 17 estados FSM): fornece a arquitetura base (Django apps, models, views, templates, FSM, pipeline LLM, lock system, auditoria). Vamos copiar e simplificar.
- **`matrix-pdf-summarizer-bot`** (Python, multi-provider LLM, prompts vasculares): fornece os prompts de triagem vascular e o padrão de LLM factory multi-provider.

O sistema será um monolito Django SSR (sem REST/SPA), Bootstrap 5.3 + Vanilla JS, com PWA para uso mobile e desktop. O banco é PostgreSQL 17 e as tasks assíncronas usam django-q2.

## Goals / Non-Goals

### Goals

1. Sistema web funcional com 3 papéis: enfermeiro, médico, administrador
2. Upload de PDF com pipeline LLM em 2 etapas (extração + parecer)
3. Suporte a dual-LLM (dois modelos rodando em paralelo para comparação)
4. Fluxo completo: upload → processamento → decisão médica → ciência do enfermeiro
5. Dashboard administrativo com métricas e encerramento de casos
6. Auditoria completa (CaseEvent append-only)
7. Comunicação intra-app por caso (thread de mensagens)
8. Anexos complementares
9. PWA funcional (installável, tema responsivo)
10. Multi-role com switch de papel ativo
11. TDD, quality gate (ruff + mypy + pytest)

### Non-Goals

- Sem agendamento/scheduler (não há agendamento de consulta)
- Sem scope gate (todo caso vai para o médico)
- Sem prior case lookup
- Sem post-schedule intercurrence
- Sem intranet guard
- Sem supervisor summaries
- Sem reenvio corrigido
- Sem menções/notificações na comunicação (MVP simples)
- Sem API REST / SPA
- Sem migração de dados do legado

## Decisions

### D1: Estrutura de Apps Django (7 apps)

Mesmo padrão do `ats-web`, simplificado:

```
config/          # settings (base/dev/prod), urls, wsgi
apps/
  accounts/      # User, Role, auth, perfil, switch-role
  cases/         # Case (FSM), CaseEvent, CaseAttachment, CaseCommunicationMessage
  llm/           # PromptTemplate versionado
  pipeline/      # LLM client, LLM1/LLM2 services, orchestrator, schemas
  intake/        # Enfermeiro: upload, meus casos, detalhe, ciência
  doctor/        # Médico: fila, decisão, presenter
  dashboard/     # Admin: métricas, fila completa, encerramento, gestão
templates/
static/
```

**Alternativa considerada:** 3 apps monolíticos (users, cases, processing). Rejeitada porque a separação por domínio funcional (atores + pipeline) facilita manutenção e espelha o padrão já validado no `ats-web`.

### D2: Máquina de Estados (9 estados)

Estados simplificados (vs 17 do ats-web):

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> EXTRACTING: start_extraction
    EXTRACTING --> LLM1_STRUCT: extraction_complete (success)
    EXTRACTING --> FAILED: extraction_complete (failure)
    LLM1_STRUCT --> LLM2_SUGGEST: llm1_complete (success)
    LLM1_STRUCT --> FAILED: llm1_complete (failure)
    LLM2_SUGGEST --> WAIT_DOCTOR: llm2_complete + ready_for_doctor
    LLM2_SUGGEST --> FAILED: llm2_complete (failure)
    WAIT_DOCTOR --> DOCTOR_ACCEPTED: doctor_decide (accept)
    WAIT_DOCTOR --> DOCTOR_DENIED: doctor_decide (deny)
    DOCTOR_ACCEPTED --> WAIT_NURSE_ACK: ready_for_nurse
    DOCTOR_DENIED --> WAIT_NURSE_ACK: ready_for_nurse
    WAIT_NURSE_ACK --> CLEANED: nurse_ack
    ANY(non-CLEANED) --> CLEANED: administratively_close
```

- Sem `ReturnState` (não precisamos de decisão condicional nas transições)
- `administratively_close` disponível de qualquer estado exceto CLEANED

### D3: Dual-LLM como feature nativa

O pipeline roda dois LLMs em paralelo desde o início:

- **LLM primário**: sempre roda, define `structured_data` e `suggested_action` padrão
- **LLM secundário**: opcional (admin habilita/desabilita), resultados salvos em campos separados
- Ambos rodam via `asyncio.gather` com timeout independente
- Falha de um não bloqueia o outro
- Médico vê ambos lado a lado (desktop) ou empilhados (mobile)
- Cada LLM pode ter provider, model, api_key e base_url diferentes

**Alternativa considerada:** Single-LLM com toggle. Rejeitada porque a comparação de modelos é requisito explícito do projeto e integrar depois seria mais caro.

### D4: Schemas Pydantic Vascular

O LLM1 extrai dados estruturados conforme o documento `RecomendacoesRelatoriosRegulacaoVascular_HMH.pdf`:

```
Llm1VascularResponse:
  patient: { name, age, sex }
  origin_context: { city, hospital, unit, state_uf }
  referral: { main_complaint, evolution_time_days, affected_limb, suspected_diagnosis }
  lesion: { exact_location, size_cm, depth, aspect, odor, larvae, gangrene_location, ... }
  pain: { has_pain, rest_pain, night_pain, improves_with_dangling, prior_claudication, sudden_onset }
  pulses: { femoral_r/l, popliteal_r/l, tibial_posterior_r/l, pedal_r/l }
  edema: { present, unilateral_bilateral, depressible, hardened, hot, cold }
  infection: { local_signs[], systemic_signs[] }
  history: { diabetes, smoking, hypertension, ckd, mi, stroke, arrhythmia, ... }
  labs: { hemoglobin, leukocytes, crp, glucose, creatinine, urea, potassium, lactate }
  imaging: { xray, duplex, angiotomography }
  acute_ischemia: { signs[], time_onset }
  extraction_quality: { confidence, missing_fields }
```

O LLM2 emite parecer com:
```
Llm2VascularResponse:
  suggestion: accept | deny
  recommendation_text: str (markdown)
  acceptance_criteria_met: [str]
  exclusion_criteria_met: [str]
  confidence: alta | media | baixa
  rationale: str
```

### D5: Prompts

Os prompts são versionados em `PromptTemplate` (modelo `llm`), com seed inicial portado do `matrix-pdf-summarizer-bot`:

- `llm1_system`: instrui LLM a extrair dados estruturados no formato JSON do schema vascular. Inclui definições de cada campo, regras de inferência (ex: pulso poplíteo presente implica femoral presente), notação de pulsos (3+/2+/1+/0/-/?)
- `llm1_user`: "Extraia os dados estruturados do seguinte relatório de regulação vascular em PDF: {extracted_text}"
- `llm2_system`: adaptação literal do `medical_triage.txt` do bot — critérios de aceitação/exclusão para cirurgia vascular
- `llm2_user`: "Analise o caso abaixo e emita seu parecer: {structured_data_json}"

O admin pode editar prompts e criar novas versões. Apenas uma versão ativa por nome.

### D6: LLM Client Multi-Provider

Inspirado no `llm_factory.py` do bot Matrix, com adaptação para Django:

- Protocol `LlmClient` com método `complete(system_prompt, user_prompt) -> str`
- Implementações: `OpenAiLlmClient` (com json_schema strict mode), `AnthropicLlmClient`, `GenericOpenAiCompatibleClient`
- Configuração via `settings.py` (variáveis de ambiente):
  - `LLM1_PRIMARY_PROVIDER`, `LLM1_PRIMARY_MODEL`, `LLM1_PRIMARY_API_KEY`, `LLM1_PRIMARY_BASE_URL`
  - `LLM1_SECONDARY_PROVIDER`, `LLM1_SECONDARY_MODEL`, `LLM1_SECONDARY_API_KEY`, `LLM1_SECONDARY_BASE_URL`
  - Mesmo para LLM2
  - `LLM_SECONDARY_ENABLED` (bool)
- Admin pode reconfigurar via dashboard sem redeploy

### D7: Lock System

Mesmo padrão do `ats-web`:

- `claim_case_lock`: adquire lock com token UUID, contexto e papel. Timeout configurável (15 min default).
- `assert_case_lock`: valida lock atual (token + contexto)
- `renew_case_lock`: heartbeat (renova locked_until)
- `release_case_lock`: libera explícito
- `expire_stale_locks`: limpa locks expirados

Usado em:
- `WAIT_DOCTOR`: lock para médico decidir (evita 2 médicos no mesmo caso)
- `WAIT_NURSE_ACK`: lock para enfermeiro dar ciência (evita conflito)

### D8: Templates Compartilhados

O template `case_detail.html` será compartilhado entre intake, doctor e dashboard, parametrizado por:
- `show_intake_nav`, `show_doctor_nav`, `show_dashboard_nav`
- `can_confirm_receipt` (botão de ciência)
- `can_administratively_close` (botão admin)
- `back_url`, `back_label`
- `pdf_url` (rota protegida específica do papel)

### D9: PWA

- `manifest.json` com nome "RegulaVasc", theme-color `#0b4263`, ícones 72-512px
- Service worker (`sw.js`) com cache de estáticos e fallback offline
- Meta tags: `apple-mobile-web-app-capable`, `viewport`
- Tema hospitalar: paleta azul escuro (`#0b4263`), fontes Merriweather Sans + Source Sans 3

## Risks / Trade-offs

| Risco | Mitigação |
|-------|-----------|
| Complexidade do schema LLM1 vascular (30+ campos) pode gerar extrações ruins | Schema com campos opcionais; extraction_quality reporta baixa confiança; médico sempre vê o PDF original |
| Dual-LLM dobra custo de API | Admin pode desabilitar secundário; cada LLM tem timeout independente |
| FSM com 9 estados pode ter edge cases não capturados nos testes | Testes exaustivos de todas as transições; herança do padrão testado do ats-web |
| Django-Q2 requer worker separado (redis ou database) | Usar database broker (mais simples para MVP); documentar no docker-compose |
| PDFs escaneados (imagens) não terão texto extraível | Pipeline detecta texto vazio e registra FAILED; enfermeiro vê status de falha na fila |
| Múltiplos providers LLM podem ter comportamento inconsistente | Cada provider tem seu próprio client com interface comum; erros capturados individualmente |
