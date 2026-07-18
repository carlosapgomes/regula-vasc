# Spec: Pipeline

## ADDED Requirements

### Requirement: PDF Text Extraction
The system SHALL extract text from uploaded PDF files using pymupdf. It MUST detect empty extractions and handle errors gracefully.

#### Scenario: Valid PDF with text
- **WHEN** a PDF with extractable text is processed
- **THEN** `case.extracted_text` is populated with the full text content

#### Scenario: Scanned PDF with no text
- **WHEN** a scanned/image-only PDF is processed
- **THEN** `case.extracted_text` is empty and case transitions to FAILED

### Requirement: LLM1 Structured Extraction
The system SHALL run LLM1 to extract structured data from the report text using a Pydantic schema. The schema MUST cover patient demographics, clinical data (lesion, pain, pulses, infection, edema), medical history, labs, imaging, and origin context.

#### Scenario: LLM1 extracts data successfully
- **WHEN** LLM1 receives report text and the system prompt
- **THEN** it returns JSON matching `Llm1VascularResponse` schema, validated by Pydantic

#### Scenario: LLM1 returns invalid JSON
- **WHEN** LLM1 response does not match the Pydantic schema
- **THEN** pipeline catches ValidationError, records LLM1_FAILED event, transitions to FAILED

### Requirement: LLM2 Suggestion
The system SHALL run LLM2 to generate an acceptance recommendation (accept/deny) based on the structured data and vascular surgery triage criteria from the prompts.

#### Scenario: LLM2 recommends acceptance
- **WHEN** structured data meets acceptance criteria (e.g., palpable femoral pulse, creatinine ≤ 1.4)
- **THEN** LLM2 returns `suggestion: "accept"` with acceptance criteria explicitly listed

#### Scenario: LLM2 recommends denial
- **WHEN** structured data violates exclusion criteria (e.g., requires revascularization)
- **THEN** LLM2 returns `suggestion: "deny"` with violated criteria listed

### Requirement: Dual-LLM Parallel Execution
The system SHALL run primary and secondary LLMs in parallel using asyncio.gather when both are configured. Failure of one MUST NOT block the other.

#### Scenario: Both LLMs succeed
- **WHEN** primary and secondary LLM2 are both enabled and called
- **THEN** both results are saved in `llm2_primary_result` and `llm2_secondary_result`

#### Scenario: Secondary LLM fails
- **WHEN** primary LLM2 succeeds but secondary LLM2 raises an exception
- **THEN** `llm2_primary_result` is populated, `llm2_secondary_result` contains error info, pipeline does not fail

### Requirement: Multi-Provider LLM Client
The system SHALL support multiple LLM providers (OpenAI, Anthropic, Ollama/generic) through a common `LlmClient` protocol. Configuration MUST come from Django settings.

#### Scenario: OpenAI provider used
- **WHEN** `LLM1_PRIMARY_PROVIDER=openai`
- **THEN** an OpenAI client is created with the configured API key and model

#### Scenario: Generic/Ollama provider used
- **WHEN** `LLM1_PRIMARY_PROVIDER=generic` with a base_url
- **THEN** a generic OpenAI-compatible client is created pointing to the custom endpoint

### Requirement: Pipeline Orchestration
The system SHALL orchestrate the complete pipeline: enqueue task via django-q2, run extraction, LLM1, LLM2 sequentially, transition FSM at each stage. On any failure, the case MUST transition to FAILED.

#### Scenario: Happy path pipeline
- **WHEN** a case is created and pipeline is enqueued
- **THEN** the case flows through all states: NEW → EXTRACTING → LLM1_STRUCT → LLM2_SUGGEST → WAIT_DOCTOR

#### Scenario: Pipeline failure mid-way
- **WHEN** LLM1 API call fails
- **THEN** case transitions to FAILED with LLM1_FAILED and PIPELINE_FAILED events recorded

### Requirement: Agency Record Number Extraction
The system SHALL extract the regulation agency record number from the PDF text using deterministic regex patterns (as done in ats-web).

#### Scenario: PDF contains agency record number
- **WHEN** PDF text contains a regulation number matching known patterns
- **THEN** `case.agency_record_number` is populated

### Requirement: Regulation Days on Screen Extraction
The system SHALL extract "Dias em tela: N" from regulation PDFs and store it on the Case for queue prioritization.

#### Scenario: PDF contains days on screen
- **WHEN** PDF text contains "Dias em tela: 15"
- **THEN** `case.regulation_days_on_screen = 15`
