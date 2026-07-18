# Spec: Dashboard

## ADDED Requirements

### Requirement: Dashboard Metrics
The system SHALL display aggregate metrics: total cases, accepted, denied, administratively closed, in progress, awaiting doctor, awaiting nurse. Metrics MUST be filterable by period (today, 7d, 30d, all).

#### Scenario: Admin views today's metrics
- **WHEN** admin loads dashboard with period "Hoje"
- **THEN** totals for cases created today are shown with breakdown by outcome

#### Scenario: Admin switches to 7-day period
- **WHEN** admin selects "7 dias"
- **THEN** metrics reflect cases from the last 7 days

### Requirement: All Cases Table
The system SHALL display a paginated, filterable, searchable table of all cases. Filters MUST include status and date range. Search MUST support patient name and agency record number (minimum 3 characters).

#### Scenario: Admin searches by patient name
- **WHEN** admin types 3+ characters of a patient name
- **THEN** table shows only matching cases

#### Scenario: Admin filters by status
- **WHEN** admin selects status filter "FAILED"
- **THEN** table shows only FAILED cases

### Requirement: Average Time Metrics
The system SHALL display average times for: upload to doctor decision, doctor decision to nurse acknowledgement, and total cycle time.

#### Scenario: Metrics display with data
- **WHEN** there are completed cases in the period
- **THEN** average times are displayed in human-readable format (e.g., "45 min", "2 h 15 min")

#### Scenario: Metrics display with no data
- **WHEN** there are no completed cases in the period
- **THEN** times show "—"

### Requirement: Administrative Closure
The system SHALL allow admin to close any non-CLEANED case with a mandatory reason selected from predefined choices plus optional free-text detail.

#### Scenario: Admin closes a WAIT_DOCTOR case
- **WHEN** admin clicks "Encerrar Administrativamente", selects reason "Caso duplicado", adds detail, and submits
- **THEN** case transitions to CLEANED, administrative closure metadata saved, CASE_ADMINISTRATIVELY_CLOSED event recorded, admin redirected to case detail

#### Scenario: Admin tries to close already CLEANED case
- **WHEN** admin attempts to close a CLEANED case
- **THEN** the button is not shown / operation is rejected

### Requirement: Attention Flag
The system SHALL flag cases that need attention: FAILED status, process stuck >30 minutes, or waiting human action >48 hours.

#### Scenario: Case processing stuck
- **WHEN** a case is in EXTRACTING for more than 30 minutes
- **THEN** it appears with attention flag in the dashboard

### Requirement: User Management
The system SHALL allow admin to list, create, edit, block/unblock users. Admin MUST be able to assign and revoke roles.

#### Scenario: Admin creates a new nurse
- **WHEN** admin fills user creation form with username, email, roles=["nurse"], and submits
- **THEN** new user is created with nurse role

### Requirement: Prompt Management
The system SHALL allow admin to list, view, and create new versions of prompt templates. Admin MUST be able to activate a specific version.

#### Scenario: Admin updates LLM2 system prompt
- **WHEN** admin creates a new version of `llm2_system` with updated criteria
- **THEN** the new version becomes active and pipelines use it immediately

### Requirement: LLM Configuration
The system SHALL allow admin to configure LLM providers (primary and secondary) including provider type, model, API key, and base URL. Admin MUST be able to enable/disable the secondary LLM.

#### Scenario: Admin enables secondary LLM
- **WHEN** admin sets `LLM_SECONDARY_ENABLED=true` and configures secondary provider
- **THEN** subsequent pipeline runs execute both primary and secondary LLMs

#### Scenario: Admin disables secondary LLM
- **WHEN** admin sets `LLM_SECONDARY_ENABLED=false`
- **THEN** subsequent pipeline runs execute only the primary LLM
