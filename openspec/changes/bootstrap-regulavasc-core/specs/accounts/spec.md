# Spec: Accounts

## ADDED Requirements

### Requirement: Multi-role User
The system SHALL support users with multiple roles. Each user MUST have at least one role assigned by an admin. Roles are: `nurse`, `doctor`, `admin`.

#### Scenario: User with single role logs in
- **WHEN** user with role `nurse` authenticates
- **THEN** their active role is set to `nurse` automatically

#### Scenario: User with multiple roles selects active role
- **WHEN** user with roles `nurse` and `doctor` switches role via avatar menu
- **THEN** the active role changes and the UI updates to show that role's navigation and permissions

### Requirement: Authentication
The system SHALL use Django's built-in authentication (username + password). Users MUST authenticate before accessing any page except login and password reset.

#### Scenario: Valid login
- **WHEN** user submits valid credentials
- **THEN** they are redirected to their role-appropriate home page

#### Scenario: Invalid login
- **WHEN** user submits invalid credentials
- **THEN** they see an error message and remain on login page

### Requirement: Password Reset
The system SHALL allow users to reset their password via email. The flow MUST follow Django's built-in password reset (token-based, single-use links).

#### Scenario: User requests password reset
- **WHEN** user submits their email on the password reset form
- **THEN** system sends an email with a reset link

#### Scenario: User resets password with valid token
- **WHEN** user clicks reset link with valid token and submits new password
- **THEN** password is updated and user can login with new password

### Requirement: Profile Management
The system SHALL allow users to view and edit their profile (first name, last name, email). Users MAY have a professional council registration (CRM/COREN) that MUST be filled together (both council and number or neither).

#### Scenario: User edits profile
- **WHEN** user updates their first name and saves
- **THEN** the new name is reflected in the UI

### Requirement: Admin User Management
The system SHALL allow admin users to create, edit, block, and reset passwords of other users. Admin MUST be able to assign and remove roles.

#### Scenario: Admin creates a new doctor user
- **WHEN** admin fills user creation form with username, email, password and role `doctor`
- **THEN** the new user is created and can login

#### Scenario: Admin blocks a user
- **WHEN** admin sets a user's account_status to "blocked"
- **THEN** the blocked user cannot login

### Requirement: Role-Based Access Control
The system SHALL restrict access to views based on the user's active role using a `@role_required` decorator. Users without the required active role MUST be redirected with an error message.

#### Scenario: Nurse tries to access doctor queue
- **WHEN** user with active role `nurse` navigates to `/doctor/queue/`
- **THEN** they are redirected with a permission denied message

#### Scenario: Doctor accesses doctor queue
- **WHEN** user with active role `doctor` navigates to `/doctor/queue/`
- **THEN** they see the doctor queue page
