# Spec: Doctor

## ADDED Requirements

### Requirement: Doctor Queue
The system SHALL display a queue of cases awaiting doctor decision (WAIT_DOCTOR), ordered by regulation_days_on_screen descending (most urgent first), then by created_at. A secondary tab SHALL show today's decided cases.

#### Scenario: Doctor views pending queue
- **WHEN** doctor navigates to doctor queue
- **THEN** they see cards for all WAIT_DOCTOR cases with patient info, wait time, and suggested action summary

#### Scenario: Empty queue
- **WHEN** no cases are in WAIT_DOCTOR
- **THEN** doctor sees an empty state message

### Requirement: Doctor Decision Form
The system SHALL present a decision form with: full patient structured data (presenter-formatted), dual-LLM suggestions side-by-side (if both enabled), embedded PDF viewer, attachment list, and decision form (accept/deny with mandatory reason on denial and optional observation).

#### Scenario: Doctor opens decision with dual-LLM enabled
- **WHEN** doctor opens a case and secondary LLM is enabled
- **THEN** they see two cards: "Parecer Primário" and "Parecer Secundário" with each LLM's recommendation and rationale

#### Scenario: Doctor opens decision with only primary LLM
- **WHEN** doctor opens a case and secondary LLM is disabled
- **THEN** they see a single card with the primary LLM's recommendation

### Requirement: Accept Decision
The system SHALL allow the doctor to accept a case with an optional observation. The case MUST transition to DOCTOR_ACCEPTED then WAIT_NURSE_ACK.

#### Scenario: Doctor accepts with observation
- **WHEN** doctor selects "Aceitar", writes "Paciente elegível para debridamento" in observation, and submits
- **THEN** `doctor_decision = "accept"`, `doctor_observation` saved, FSM transitions to WAIT_NURSE_ACK

### Requirement: Deny Decision
The system SHALL allow the doctor to deny a case with mandatory justification. The reason field MUST not be empty. The case MUST transition to DOCTOR_DENIED then WAIT_NURSE_ACK.

#### Scenario: Doctor denies without reason
- **WHEN** doctor selects "Recusar" with empty reason field and submits
- **THEN** form validation fails, error message displayed

#### Scenario: Doctor denies with reason
- **WHEN** doctor selects "Recusar", writes "Necessita revascularização — viola critério de exclusão" and submits
- **THEN** `doctor_decision = "deny"`, `doctor_reason` saved, FSM transitions to WAIT_NURSE_ACK

### Requirement: Doctor Lock
The system SHALL acquire a lock when doctor enters the decision form. The lock MUST be renewable (heartbeat) and released on submit or explicitly.

#### Scenario: Lock acquired on entry
- **WHEN** doctor clicks on a case from the queue
- **THEN** a lock is acquired with context "doctor_decision" and doctor is redirected to decision form

#### Scenario: Lock prevents double access
- **WHEN** second doctor tries to open an already-locked case
- **THEN** they are redirected to queue with a warning

### Requirement: Vascular Report Presenter
The system SHALL format structured data into a readable clinical report with sections: Patient Data, Chief Complaint & Evolution, Lesion Description, Pain Assessment, Pulse Exam, Medical History, Labs & Imaging, Infection Signs, Edema.

#### Scenario: Presenter formats structured data
- **WHEN** structured_data contains a complete vascular report
- **THEN** presenter generates HTML with all sections populated from the JSON fields

#### Scenario: Presenter handles missing optional fields
- **WHEN** structured_data has no imaging data
- **THEN** presenter shows "Imagem: não realizada" without breaking layout
