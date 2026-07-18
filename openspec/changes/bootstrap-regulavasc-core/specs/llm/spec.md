# Spec: LLM

## ADDED Requirements

### Requirement: PromptTemplate Versioning
The system SHALL store prompt templates with versioning. Each prompt has a unique name (e.g., `llm1_system`, `llm1_user`, `llm2_system`, `llm2_user`) and only one version is active per name at any time.

#### Scenario: Admin creates a new prompt version
- **WHEN** admin uploads a new version of `llm2_system`
- **THEN** the new version is saved with incremented version number; previous version is deactivated

#### Scenario: Pipeline resolves active prompt
- **WHEN** pipeline calls `PromptTemplate.get_active("llm1_system")`
- **THEN** the currently active version is returned

### Requirement: Vascular Prompt Seeds
The system SHALL seed the database with initial prompt templates adapted from the matrix-pdf-summarizer-bot's vascular surgery triage prompts. These MUST cover all four prompt names (llm1_system, llm1_user, llm2_system, llm2_user).

#### Scenario: Database is initialized
- **WHEN** `seed_prompts` management command runs
- **THEN** four active PromptTemplate records exist with version 1 and content ported from the bot's `medical_triage.txt`

### Requirement: Prompt Fallback
The system SHALL provide hardcoded fallback prompts if no active template exists in the database, ensuring the pipeline never crashes due to missing configuration.

#### Scenario: Pipeline runs before seeding
- **WHEN** no active `llm1_system` template exists in DB
- **THEN** pipeline uses a hardcoded default prompt and logs a warning
