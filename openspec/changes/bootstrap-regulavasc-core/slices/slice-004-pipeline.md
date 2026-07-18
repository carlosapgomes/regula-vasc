# Slice 004 — Pipeline (LLM Client + Schemas + Extração + Orquestração)

## Handoff

Leia: `proposal.md`, `design.md` (D3, D4, D5, D6), `tasks.md`, `specs/pipeline/spec.md`.  
Referências: `../../ats-web/apps/pipeline/` (llm.py, llm1_service.py, llm2_service.py, orchestrator.py, tasks.py, schemas/llm1.py, schemas/llm2.py, json_parser.py), `../../ats-web/apps/intake/pdf_utils.py` (extração com pymupdf), `../../matrix-pdf-summarizer-bot/llm_factory.py` (multi-provider), `../../matrix-pdf-summarizer-bot/pdf_processor.py` (watermark removal).

**Estado atual:** Apps accounts, cases, llm funcionais. Nenhum pipeline de processamento.

## Objetivo

Criar o app `pipeline` com: cliente LLM multi-provider, schemas Pydantic vasculares (LLM1 + LLM2), serviços LLM1/LLM2, orquestrador com dual-LLM, extração de PDF, parser JSON, e tasks django-q2.

## Escopo funcional

**R1:** Protocolo `LlmClient` com `complete(system_prompt, user_prompt) -> str`  
**R2:** Implementações: `OpenAiLlmClient` (com json_schema strict), `AnthropicLlmClient`, `GenericOpenAiCompatibleClient`  
**R3:** Factory functions: `create_openai_llm1_client()`, `create_openai_llm2_client()` lendo de settings  
**R4:** Schema Pydantic `Llm1VascularResponse` com todos os campos do documento de recomendações vascular  
**R5:** Schema Pydantic `Llm2VascularResponse` com suggestion, recommendation_text, criteria, confidence  
**R6:** `Llm1Service.run()`: chama LLM1, valida resposta com Pydantic, retorna StructuredData  
**R7:** `Llm2Service.run()`: chama LLM2, valida resposta, retorna SuggestionData  
**R8:** `run_pipeline(case_id)`: orquestrador que executa extração → LLM1 (dual) → LLM2 (dual) → transições FSM  
**R9:** Dual-LLM: ambos rodam em `asyncio.gather`, falha de um não bloqueia o outro  
**R10:** `extract_pdf_text()` com pymupdf, `remove_watermark()`, `extract_agency_record_number()`, `extract_regulation_days_on_screen()`  
**R11:** `json_parser.py`: extrai JSON de respostas markdown (fallback)  
**R12:** `enqueue_pipeline(case_id)`: entry point django-q2  
**R13:** Tests com mocked LLM clients

## Arquivos esperados

```
apps/pipeline/
├── __init__.py, apps.py
├── llm.py              # LlmClient protocol, OpenAiLlmClient, AnthropicLlmClient, Generic client, factory functions
├── llm1_service.py     # Llm1Service com fallback system prompts
├── llm2_service.py     # Llm2Service com fallback system prompts
├── orchestrator.py     # run_pipeline(), _run_llm1_step(), _run_scope_and_llm2() adaptados
├── tasks.py            # enqueue_pipeline, execute_pipeline
├── pdf_utils.py        # extract_pdf_text, remove_watermark, extract_agency_record_number, extract_regulation_days_on_screen
├── json_parser.py      # extract_json_from_text
├── schemas/
│   ├── __init__.py
│   ├── llm1.py         # Llm1VascularResponse + todos os sub-models
│   └── llm2.py         # Llm2VascularResponse
└── tests/
    ├── __init__.py
    ├── test_llm_client.py
    ├── test_llm1_service.py
    ├── test_llm2_service.py
    ├── test_orchestrator.py
    ├── test_json_parser.py
    ├── test_pdf_utils.py
    └── test_dual_llm.py
```

Modificar: `config/settings/base.py` (INSTALLED_APPS, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, LLM1_PRIMARY_*, LLM1_SECONDARY_*, LLM2_PRIMARY_*, LLM2_SECONDARY_*, LLM_SECONDARY_ENABLED)

## TDD

**RED:**
- `test_llm1_service_extracts_valid_data`: mock client retorna JSON schema válido
- `test_llm1_service_rejects_invalid_json`: mock client retorna JSON inválido → ValidationError
- `test_llm2_service_returns_suggestion`: mock client retorna JSON válido com accept
- `test_orchestrator_happy_path`: mock clients → case avança NEW até WAIT_DOCTOR
- `test_orchestrator_handles_extraction_failure`: PDF inválido → FAILED
- `test_dual_llm_both_succeed`: ambos mocks retornam sucesso → ambos campos populados
- `test_dual_llm_secondary_fails`: mock secundário lança exceção → primário salvo, secundário com erro
- `test_pdf_extraction_removes_watermark`: texto com watermark → removido
- `test_extract_agency_record_number`: regex extrai número da regulação
- `test_json_parser_extracts_from_markdown`: texto com ```json...``` → extraído

## Checks

```bash
rg -n "class.*LlmClient\|def complete" apps/pipeline/llm.py
rg -n "model_validate\|ValidationError" apps/pipeline/llm1_service.py apps/pipeline/llm2_service.py
rg -n "asyncio.gather\|dual\|secondary" apps/pipeline/orchestrator.py
rg -n "pymupdf\|fitz\|extract_text" apps/pipeline/pdf_utils.py
rg -n "Llm1VascularResponse\|Llm2VascularResponse" apps/pipeline/schemas/
```

## Critérios de sucesso

- [ ] Pipeline feliz: NEW → WAIT_DOCTOR em < 2s (com mocks)
- [ ] LLM1 schema vascular validado com campos do documento de recomendações
- [ ] Dual-LLM: ambos resultados salvos quando habilitado
- [ ] Falha de LLM não quebra pipeline inteiro
- [ ] Extração de PDF funcional com pymupdf
- [ ] Watermark removido
- [ ] Agency record number e regulation days extraídos deterministicamente

---

Relatório: `/tmp/bootstrap-regulavasc-core-slice-004-report.md`
