# Spec: PWA

## ADDED Requirements

### Requirement: Web App Manifest
The system SHALL serve a valid manifest.json with app name "RegulaVasc", theme color `#0b4263`, icons in multiple sizes (72-512px), and display mode "standalone".

#### Scenario: Browser requests manifest
- **WHEN** GET `/static/manifest.json`
- **THEN** valid JSON is returned with name, short_name, icons, theme_color, and display properties

### Requirement: Service Worker
The system SHALL register a service worker that caches static assets (CSS, JS, icons) for offline access and provides a fallback page.

#### Scenario: Service worker installs
- **WHEN** user first visits the app
- **THEN** service worker is registered and caches static assets

#### Scenario: Offline access
- **WHEN** user is offline and navigates to a cached page
- **THEN** the page is served from cache

### Requirement: Mobile-First Responsive Design
The system SHALL use Bootstrap 5.3 responsive breakpoints. All pages MUST be usable on mobile devices (320px+ width). Navigation MUST collapse to hamburger menu on small screens.

#### Scenario: Mobile navigation
- **WHEN** viewport width < 992px
- **THEN** navbar shows hamburger toggle, role switch via avatar, and notification bell

#### Scenario: Desktop navigation
- **WHEN** viewport width >= 992px
- **THEN** navbar shows full inline menu with user identity, role, and navigation links

### Requirement: Installable PWA
The system SHALL meet PWA installability criteria: HTTPS (or localhost), valid manifest, registered service worker, and appropriate meta tags.

#### Scenario: Browser shows install prompt
- **WHEN** user visits the app multiple times on a supported browser
- **THEN** the browser offers to install the PWA

### Requirement: Hospital Theme
The system SHALL use a hospital-appropriate visual theme with dark blue primary color (`#0b4263`), readable fonts (Merriweather Sans for headings, Source Sans 3 for body), and adequate contrast for medical use.

#### Scenario: Theme applied globally
- **WHEN** any authenticated page loads
- **THEN** the navbar, buttons, badges, and cards use the hospital color palette defined in app.css

### Requirement: Mobile PDF Viewer
The system SHALL provide a mobile-friendly PDF viewer using PDF.js for viewing regulation PDFs on small screens.

#### Scenario: Nurse opens PDF on mobile
- **WHEN** nurse taps "Ver PDF" on a case detail page on mobile
- **THEN** a mobile-optimized PDF viewer opens with zoom and navigation controls
