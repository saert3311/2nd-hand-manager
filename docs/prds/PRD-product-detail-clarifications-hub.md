# Product Requirements Document (PRD): Product Detail Clarifications Hub

## 1. Executive Summary
Expand the product detail workspace (`/products/<pk>/`) to introduce a unified **Product Clarifications Hub** situated directly beneath the intake field notes. While the initial Q&A system allowed managers to ask questions when data was missing, users need the ability to add **direct clarification notes** (e.g., measurements, fabric composition, uncataloged flaws, authenticity details) after the initial intake form without forcing the product into a blocking `AWAITING_INFO` state. Both sourcing assistants and store managers can post direct clarifications, while store managers retain exclusive authority to open pending doubt inquiries for assistants. All resolved clarifications and direct notes seamlessly integrate into the Gemini Multimodal Vision prompt for listing copywriting.

---

## 2. Problem Statement
1. **Post-Intake Information Gap:** Intake assistants rapidly inspect and photograph secondhand products. Often, crucial details (measurements, zipper condition, composition labels, original accessories) are discovered or remembered immediately *after* submitting the intake form.
2. **Rigid Q&A Constraint:** In the existing system, adding clarification data required a store manager to create a question, transitioning the product status to `AWAITING_INFO`, and an assistant to respond. Assistants could not proactively add notes or observations on an existing product, and managers could not record immediate discoveries without creating artificial questions.
3. **UI Placement & Workflow Context:** Clarification tools must be intuitively situated in the product detail layout, immediately following the preserved intake notes, so staff have a single cohesive factual baseline (photos + intake notes + supplemental clarifications) before moving to marketplace copywriting, pricing, and publishing.

---

## 3. User Personas & Scenarios

### Persona 1: Sourcing Assistant (User A)
- **Scenario 1 (Proactive Post-Intake Measurement):** After submitting a vintage jacket via `/intake/`, the assistant measures the chest width (54 cm) and length (70 cm). They open the product detail view, select category *Medidas*, enter the measurements, and click "Añadir aclaración". The note is instantly saved as an active clarification without changing product status or creating artificial blocker states.
- **Scenario 2 (Resolving Manager Doubts):** An assistant sees a pending doubt from the manager asking about the wash tag. They inspect the garment, submit the answer, and the pending doubt transitions to resolved.

### Persona 2: Store Manager / Lister (User B)
- **Scenario 3 (Adding Discovery During Listing Review):** The manager inspects the product photos, notices a branded engraving on the zipper, and records a direct clarification under *Material / Autenticidad*.
- **Scenario 4 (Issuing an Inquiry):** The manager notices an ambiguous stain and switches to "Preguntar a Asistente" (Q&A mode) under *Defectos*. The product transitions to `AWAITING_INFO` and notifies the assistant.
- **Scenario 5 (Copywriting Integration):** When generating AI listing copy, Gemini reads the preserved intake note PLUS all direct clarifications and resolved answers, creating rich, accurate descriptions.

---

## 4. Scope & Functional Requirements

### 4.1 Domain Model Enhancements (`inventory/models.py`)
- Extend `ProductClarification`:
  - `is_direct_note`: `BooleanField(default=False, db_index=True, verbose_name=_("Direct Note"))`
  - When `is_direct_note=True`:
    - `status` defaults to `ClarificationStatus.RESOLVED`.
    - `question` stores a standardized descriptor (e.g. `_("Direct Clarification Note")` or user-defined note topic) or is made optional/custom.
    - `answer` stores the detailed clarification text.
    - `asked_by` and `answered_by` are set to `request.user`.
    - `answered_at` is set to `timezone.now()`.
    - Does NOT trigger `AWAITING_INFO` status transition or blocking lifecycle changes.
  - When `is_direct_note=False` (Standard Manager Doubt):
    - Retains existing behavior: `status=PENDING`, triggers `AWAITING_INFO`, triggers Web Push notification to assistants.

### 4.2 Permission & Security Matrix (`inventory/permissions.py`)
| Action | Store Manager | Sourcing Assistant | Anonymous |
| :--- | :--- | :--- | :--- |
| **View Clarifications** | Allowed | Allowed (Active products only) | Denied (Redirect to login) |
| **Add Direct Clarification Note** | Allowed | Allowed | Denied (HTTP 403 / Redirect) |
| **Create Pending Q&A Doubt** | Allowed | Denied (HTTP 403) | Denied |
| **Answer Pending Q&A Doubt** | Allowed | Allowed | Denied |
| **Delete / Dismiss Clarification** | Allowed | Denied (HTTP 403) | Denied |

### 4.3 Service & Copywriting Integration (`inventory/services/ai_service.py`)
- In `generate_product_listing`:
  - Include both direct clarification notes and resolved Q&A items:
    - Direct note format: `- [Categoría] Nota: <contenido>`
    - Q&A format: `- [Categoría] Pregunta: <pregunta> -> Respuesta: <respuesta>`
  - Retain the unapplied clarifications callout indicator (`has_unapplied_clarifications`) so managers know when newly added direct notes or answers have not yet been reflected in the current listing copy.

### 4.4 Frontend UI Engineering (`inventory/templates/inventory/product_detail.html`)
- **Location**: Positioned in the Left Column (`lg:col-span-5`), immediately below "Preserved Intake Notes" and above "Lifecycle Audit Trail".
- **Visual Design**:
  - Clean card container `#clarifications-section` matching existing Tailwind styling (`bg-white rounded-2xl shadow-sm border border-slate-200 p-5`).
  - Header with icon `💡`, title `{% trans "Product Clarifications & Notes" %}`, and count badges (`X pending`, `Y resolved`).
  - **Manager Mode Switcher**:
    - Accessible tab/toggle for managers:
      1. `📝 Añadir nota directa` (Direct Clarification Note - instant, no blocking state).
      2. `❓ Preguntar a asistente` (Ask Assistant Doubt - flags `AWAITING_INFO`).
  - **Assistant Interface**:
    - Directly exposes the `📝 Añadir nota directa` form so assistants can record measurements or details anytime.
    - Displays pending doubts with prominent reply inputs.
  - **Clarification List Items**:
    - Pending items: High-contrast amber styling (`bg-amber-50/80 border-amber-200`).
    - Resolved items: Clean emerald styling (`bg-emerald-50/50 border-emerald-200`) with distinct badges for `Direct Note` vs `Resolved Q&A`.
    - Attribution footer: Author avatar/name, role badge (*Manager* / *Assistant*), and timestamp.
  - **Mobile Ergonomics**:
    - `<input>` and `<textarea>` elements styled with `text-base sm:text-sm` to guarantee iOS Safari does not trigger zoom.
    - Minimum button touch targets of 44px.

---

## 5. Non-Functional Requirements
- **Zero Regressions:** 100% of existing unit and E2E tests must pass.
- **Bilingual Support:** 100% of strings wrapped in `gettext` / `{% trans %}` with Spanish translations compiled in `django.po`/`django.mo`.
- **Database Safety:** Migration generated via `makemigrations` and non-destructive.
- **Linting:** Zero warnings or errors in `ruff check .`.
