# Product Requirements Document (PRD): Intake Mandatory Pre-Flight Identification Gate

## 1. Executive Summary
Enhance the mobile intake screen (`/intake/`) by introducing a client-side gating mechanism on the primary submission action: the "Guardar y catalogar siguiente producto" / "Save & Catalog Next Item" button (`#submitBtn`) is disabled by default and requires the sourcing assistant to run the initial AI identification (`#identifyBtn`) before saving. This guarantees that every product cataloged through the intake workflow benefits from AI appraisal benchmarks (MSRP and resale valuation), automated spec detection, and quality check tips before entering the staging catalog, while providing resilient fallbacks so warehouse operations are never blocked during network issues.

---

## 2. Problem Statement
1. **Skipped Pre-Flight Identification:** Although Gemini Multimodal Vision pre-flight identification and valuation benchmarks were implemented on the intake screen, assistants operating in rapid physical environments often bypass clicking "Identificar producto" and click "Save & Catalog Next Item" directly.
2. **Missing Catalog Benchmarks & Title Metadata:** When pre-flight identification is bypassed, products arrive in the staging dashboard without retail/resale valuation references, detected attribute tags, or suggested field notes. Store managers must then perform manual appraisal research or trigger full copywriting from scratch.
3. **Operational Balance:** While identification must be strongly encouraged and enforced in the UI, sourcing staff working in warehouse zones with intermittent connectivity must never be permanently locked out from saving physical inventory.

---

## 3. User Personas & Scenarios

### Persona: Sourcing Assistant (User A)
- **Scenario 1 (Standard Cataloging Flow):** The assistant snaps 3 photos of a vintage leather jacket. The Save button remains disabled with the notice *"Identifica el producto con IA para habilitar el guardado"* ("Identify product with AI to enable saving"). The assistant taps "Identificar producto". Gemini identifies the jacket, populates the suggested title, displays benchmark valuation (€450 MSRP / €140 resale), and unlocks the Save button. The assistant taps Save and moves to the next garment.
- **Scenario 2 (Photo Selection Reset):** The assistant snaps a photo, triggers identification, and then realizes the photo is blurry. They delete all photos. The form resets completely, and the Save button returns to the disabled state until new photos are captured and identified.
- **Scenario 3 (Network Timeout / Offline Blip):** The assistant is in a low-signal area. Tapping "Identificar producto" triggers an API timeout. The system displays an advisory notice (*"AI pre-check skipped / Network error"*) and gracefully unlocks the Save button with a fallback warning, ensuring the assistant can still persist the product without loss of captured photos.

---

## 4. Scope & Functional Requirements

### 4.1 Client-Side Intake State Machine (`inventory/templates/inventory/intake.html`)
1. **Initial State (Page Load / Reset):**
   - `#submitBtn` is initialized with `disabled = true`, reduced opacity (`opacity-50 cursor-not-allowed bg-slate-300 text-slate-500`), and `aria-disabled="true"`.
   - A descriptive guidance notice `#submitHelpText` renders below the Save button:
     `{% trans "Identify product with AI first to enable saving" %}`.
   - `#identifyBtn` is enabled as soon as at least 1 photo is selected (`selectedFiles.length > 0`).

2. **Identification State (`identifying`):**
   - Both `#identifyBtn` and `#submitBtn` are locked with animated spinners.

3. **Post-Identification Unlock:**
   - Once AI identification finishes (either successful response with specs/valuation OR handled error/timeout fallback):
     - An internal state flag `hasIdentified = true` is set.
     - `#submitBtn` transitions to fully enabled: `disabled = false`, `cursor-pointer`, full emerald styling (`bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white shadow-md`).
     - `#submitHelpText` displays a success confirmation or hides cleanly.

4. **Photo Modification & Reset Rules:**
   - **Adding/Removing Individual Photos:** If individual photos are added or deleted while `selectedFiles.length > 0`, `hasIdentified` remains `true` and the Save button remains unlocked.
   - **Removing All Photos:** If all photos are deleted (`selectedFiles.length === 0`), `hasIdentified` is reset to `false`, the advisory card hides, and `#submitBtn` is disabled again.

5. **Form Submission Guard:**
   - An event listener guard on the form's `submit` event strictly verifies `hasIdentified === true` and `selectedFiles.length > 0`. If triggered synthetically or via keyboard shortcut prior to identification, submission is blocked and an accessible inline warning alert is surfaced.

---

## 5. Non-Functional Requirements
- **Zero Regressions:** All existing automated tests (models, views, forms, signals, PWA, daily workflows) must pass 100%.
- **Bilingual Localization:** 100% of user-facing UI labels, tooltips, and warning notices must be translated into Spanish (`es`) and English (`en`) via `django.po`/`django.mo`.
- **Mobile First & Accessibility:** Conforms to WCAG 2.1 AA with `>= 16px` typography preventing iOS Safari auto-zoom, high-contrast states, and accessible `aria-disabled` attributes.
