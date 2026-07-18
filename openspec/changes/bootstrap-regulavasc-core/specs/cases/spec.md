# Spec: Cases

## ADDED Requirements

### Requirement: Case Model with FSM
The system SHALL have a `Case` model with a finite state machine managing its lifecycle through 10 states: NEW, EXTRACTING, LLM1_STRUCT, LLM2_SUGGEST, WAIT_DOCTOR, DOCTOR_ACCEPTED, DOCTOR_DENIED, WAIT_NURSE_ACK, CLEANED, FAILED.

#### Scenario: Case is created
- **WHEN** a nurse uploads a PDF
- **THEN** a Case is created with status NEW and a UUID case_id

#### Scenario: Case transitions through pipeline
- **WHEN** pipeline processes the case successfully
- **THEN** status transitions: NEW → EXTRACTING → LLM1_STRUCT → LLM2_SUGGEST → WAIT_DOCTOR

#### Scenario: Extraction fails
- **WHEN** PDF text extraction raises an error
- **THEN** status transitions to FAILED and a CaseEvent is recorded

### Requirement: Dual-LLM Result Storage
The system SHALL store results from both primary and secondary LLMs in separate JSON fields on the Case model for both LLM1 and LLM2 stages.

#### Scenario: Both LLMs process successfully
- **WHEN** primary and secondary LLM1 complete
- **THEN** `llm1_primary_result` and `llm1_secondary_result` are both populated

#### Scenario: Only primary LLM enabled
- **WHEN** secondary LLM is disabled and pipeline runs
- **THEN** only `llm1_primary_result` is populated; `llm1_secondary_result` remains null

### Requirement: Doctor Decision Fields
The system SHALL store the doctor's decision with mandatory reason on denial and optional observation.

#### Scenario: Doctor accepts a case
- **WHEN** doctor submits decision "accept" with an observation
- **THEN** `doctor_decision = "accept"`, `doctor_observation` is saved, `doctor = requesting user`, `doctor_decided_at = now`

#### Scenario: Doctor denies a case
- **WHEN** doctor submits decision "deny" with reason "Paciente necessita de revascularização"
- **THEN** `doctor_decision = "deny"`, `doctor_reason` is saved, `doctor_observation` is cleared

### Requirement: Nurse Acknowledgement
The system SHALL require the nurse to acknowledge receipt of the doctor's decision before the case is cleaned.

#### Scenario: Nurse confirms receipt
- **WHEN** nurse clicks "Confirmar Recebimento" on a WAIT_NURSE_ACK case
- **THEN** `nurse_ack_at = now`, `nurse_ack_by = requesting user`, status transitions to CLEANED

### Requirement: CaseEvent Audit Trail
The system SHALL record every state transition and significant action as an append-only `CaseEvent` with event_type, timestamp, actor, and optional payload.

#### Scenario: Case starts processing
- **WHEN** pipeline begins extraction
- **THEN** a CaseEvent with type "CASE_START_EXTRACTION" is created

#### Scenario: Doctor decides
- **WHEN** doctor submits decision
- **THEN** a CaseEvent with type "DOCTOR_ACCEPT" or "DOCTOR_DENY" is created with decision details in payload

### Requirement: CaseAttachment Support
The system SHALL support file attachments (PDF, JPEG, PNG) linked to a Case. Attachments MUST be suppressable (soft-delete) with audit trail.

#### Scenario: Nurse uploads an attachment
- **WHEN** nurse adds a JPEG file as supplementary attachment
- **THEN** a CaseAttachment is created with original_filename, content_type, size_bytes, sha256

#### Scenario: Nurse suppresses an attachment
- **WHEN** nurse suppresses an attachment with a reason
- **THEN** `is_suppressed = True`, suppression metadata is saved, a CaseEvent is recorded

### Requirement: Case Lock System
The system SHALL implement a lock mechanism to prevent concurrent work on the same case. Locks MUST expire after a configurable timeout.

#### Scenario: Doctor claims lock on WAIT_DOCTOR case
- **WHEN** doctor opens a decision form for an unlocked case
- **THEN** lock is acquired with token, context="doctor_decision", locked_until set

#### Scenario: Second doctor tries locked case
- **WHEN** second doctor tries to open the same case
- **THEN** they are redirected with a warning that the case is reserved

### Requirement: Administrative Closure
The system SHALL allow admin users to close any non-CLEANED case with a mandatory reason. This MUST record a CASE_ADMINISTRATIVELY_CLOSED event.

#### Scenario: Admin closes a WAIT_DOCTOR case
- **WHEN** admin submits closure with reason "Caso duplicado"
- **THEN** status transitions to CLEANED, administrative closure metadata is saved, event is recorded

### Requirement: Case Communication Messages
The system SHALL support an append-only thread of operational messages per Case, enabling communication between users without external messaging apps.

#### Scenario: Nurse posts a message
- **WHEN** nurse submits a message body on a case detail page
- **THEN** a CaseCommunicationMessage is created with author, author_role, and body; event recorded

#### Scenario: Post on CLEANED case is blocked
- **WHEN** user tries to post a message on a CLEANED case
- **THEN** the post is rejected with an error
