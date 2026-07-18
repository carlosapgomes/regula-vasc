# Spec: Intake

## ADDED Requirements

### Requirement: PDF Upload
The system SHALL allow nurse users to upload one or more regulation report PDFs. Each file MUST create a new Case and enqueue the pipeline. Supplementary attachments (PDF, JPEG, PNG) MAY be uploaded simultaneously.

#### Scenario: Nurse uploads a single PDF
- **WHEN** nurse selects a valid PDF and submits the form
- **THEN** a Case is created, the file is saved to MEDIA_ROOT, pipeline is enqueued, nurse is redirected to my_cases with success message

#### Scenario: Nurse uploads PDF with supplementary attachments
- **WHEN** nurse selects a PDF plus 3 JPEG files and submits
- **THEN** a Case is created with the PDF plus 3 CaseAttachment records linked to it

#### Scenario: Nurse uploads invalid file type
- **WHEN** nurse selects a .docx file
- **THEN** upload is rejected with warning message

### Requirement: My Cases List
The system SHALL show all operational cases (status != CLEANED) in a filterable, searchable list for nurses, regardless of who created the case (shift continuity).

#### Scenario: Nurse views case list
- **WHEN** nurse navigates to "Meus Casos"
- **THEN** they see cards for all non-CLEANED cases with patient name, status badge, agency record number, and creation time

#### Scenario: Nurse filters by status
- **WHEN** nurse selects status filter "WAIT_NURSE_ACK"
- **THEN** only cases with that status are shown

#### Scenario: Nurse searches by agency record number
- **WHEN** nurse types a regulation number in the search box
- **THEN** cases matching that number are displayed

### Requirement: Case Detail with Timeline
The system SHALL display a case detail page with: stepper showing progress, event timeline, embedded PDF viewer, structured data summary, doctor decision (if decided), and action buttons appropriate to the status.

#### Scenario: Nurse views case awaiting doctor
- **WHEN** nurse opens a WAIT_DOCTOR case
- **THEN** they see the stepper at "Avaliação Médica", timeline of events, PDF viewer, and no action buttons yet

#### Scenario: Nurse views case awaiting acknowledgement
- **WHEN** nurse opens a WAIT_NURSE_ACK case
- **THEN** they see the doctor's decision result and a "Confirmar Recebimento" button

### Requirement: Receipt Confirmation
The system SHALL allow nurses to confirm receipt of the final result, transitioning the case from WAIT_NURSE_ACK to CLEANED. A lock MUST be acquired first.

#### Scenario: Nurse confirms receipt
- **WHEN** nurse clicks "Confirmar Recebimento" with valid lock
- **THEN** case transitions to CLEANED, nurse_ack fields are populated, lock is released, success message shown

#### Scenario: Nurse tries to confirm without lock
- **WHEN** nurse submits confirmation without a valid lock token
- **THEN** they are warned that the reservation expired and must re-enter from the list

### Requirement: Supplementary Attachments
The system SHALL allow nurses to add supplementary attachments to a case before the doctor's decision. A justification note is mandatory.

#### Scenario: Nurse adds supplementary attachment
- **WHEN** nurse uploads a JPEG with justification "Raio-X adicional do pé"
- **THEN** a new CaseAttachment is created with upload_phase="supplemental", note is saved, success message shown

#### Scenario: Nurse tries to add attachment to CLEANED case
- **WHEN** nurse attempts to add attachment to a CLEANED case
- **THEN** operation is rejected

### Requirement: Attachment Suppression
The system SHALL allow nurses to suppress (soft-delete) attachments with a mandatory reason.

#### Scenario: Nurse suppresses wrong attachment
- **WHEN** nurse clicks "Suprimir" on an attachment and provides reason "Anexo errado"
- **THEN** attachment is marked as suppressed, suppression metadata saved, CaseEvent recorded
