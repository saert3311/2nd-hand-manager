# Product Requirements Document (PRD): Multi-Language Support (i18n)

## 1. Executive Summary
Provide bilingual interface support (Spanish & English) across the entire 2ndHand Staging web application. The application will automatically detect the user's preferred language from their browser's `Accept-Language` headers, rendering the UI in Spanish (`es`) for Spanish-speaking users and falling back to English (`en`) for users with any other language.

---

## 2. Problem Statement
The application is currently hardcoded in English. However, sourcing assistants and managers operating in Spanish-speaking environments or cross-border markets need an intuitive, localized interface to speed up intake and reduce friction.

---

## 3. User Personas & Scenarios

### Persona 1: Field Sourcing Assistant (Spanish-speaking)
- **Scenario:** Opens `/intake/` on a mobile device configured in Spanish (`es-ES` / `es-419`).
- **Expectation:** The entire intake interface (labels, camera prompts, thumbnail counts, buttons, validation errors, and flash messages) displays in natural Spanish without requiring manual configuration.

### Persona 2: Manager / Lister (English or International)
- **Scenario:** Accesses the desktop dashboard from a browser configured in English or another language (e.g., French, German).
- **Expectation:** The interface defaults to English (`en`), providing clean navigation, status tabs, copy buttons, and staging controls.

---

## 4. Scope & Functional Requirements

### 4.1 Automatic Language Detection & Manual Override
- **Detection Order:**
  1. Explicit user language cookie/session (via manual switcher).
  2. Browser HTTP `Accept-Language` header via Django's `LocaleMiddleware`.
  3. Default fallback: English (`en`).
- **Supported Languages:**
  - `en` (English) — Default / fallback
  - `es` (Spanish) — Primary translated language
- **Manual Override:**
  - Header toggle component (`[🇬🇧 EN | 🇪🇸 ES]`) with Django's `set_language` redirect view, setting the `django_language` cookie so users can freely switch regardless of browser configuration.

### 4.2 Comprehensive UI Translation Coverage
All static UI text must be marked for translation:
- **Navigation & Layout:** Brand tags, "New Intake", "Dashboard", "Admin", "Sign Out", language switcher, footer text.
- **Authentication Pages:** Login header, username/password labels, placeholders, submit buttons, authentication error messages.
- **Mobile Intake (`/intake/`):** Instructions, file picker prompt, "X of 10 photos selected", field notes label, placeholders, help text, "Save & Catalog Next Item" button, recent uploads heading, and success banners.
- **Catalog Dashboard (`/dashboard/`):** Title, subtitles, filter tabs ("All", "Active", "Sold"), search input placeholder, product card metadata, date formatting, and empty state prompts.
- **Product Staging Detail (`/products/<pk>/`):** "Back to Dashboard", photo count, "Saved as WebP", "Download All Photos (.ZIP)", preserved notes title/badges, AI action banner, "Generate AI Listing", copy buttons ("Copy Title", "Copy Description", "Copied!"), pricing and sold toggle, and save buttons.
- **Backend Notifications & Validations:** Form validation messages (e.g. "Please attach at least one photo", "exceeds 10MB limit"), flash messages, model verbose names.

### 4.3 AI Generation Localization
- When the active session language is Spanish (`es`), Gemini Multimodal Vision prompt is instructed to generate Spanish marketplace titles and Spanish sales descriptions.
- When the active session language is English (`en`), Gemini generates English copy.

### 4.4 Data Boundaries (Out of Scope for i18n Translation)
- User-generated field notes (`raw_note`) remain preserved in whatever language the assistant typed.
- Currency formatting remains in Euro (`€`).


---

## 5. Non-Functional Requirements
- **Performance:** Negligible overhead (<5ms) added to request processing using compiled `.mo` binary catalogs.
- **Portability:** Compilation of translation files must work on Windows development environments without requiring external GNU gettext binaries installed on the OS path.

---

## 6. Success Metrics
- 100% of user-facing UI strings marked and translated into Spanish.
- Browsers requesting `es` receive Spanish UI; browsers requesting any other language receive English UI.
- All 39 existing unit/integration tests continue to pass, plus new tests verifying language negotiation and localized template output.
