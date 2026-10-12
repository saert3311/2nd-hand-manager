# Product Clarifications & Lifecycle States

## Problem Statement
How might we enable seamless, low-friction feedback between managers and assistants when secondhand product details are missing, so that listings are never blocked from publishing and Gemini AI descriptions achieve 100% accuracy without disrupting fast mobile intake?

## Recommended Direction
Implement a **Clarifications & Lifecycle State Engine** that formalizes product progression and establishes a direct, asynchronous Q&A channel attached to each product:

1. **Product Lifecycle State Machine:**
   - Transition `Product` from a binary `is_sold` model to a structured `status` enum:
     - `DRAFT` (Borrador / Intake recién catalogado)
     - `AWAITING_INFO` (Dudas pendientes / Esperando respuesta del asistente)
     - `READY` (Listo para publicar / Revisado y con IA generada)
     - `SOLD` (Vendido)
     - `BLOCKED` (No publicable / Falsificación, daño irreparable, piezas faltantes)
   - Maintain backward compatibility via property getters/setters and database synchronization for `is_sold`.

2. **Lightweight Q&A Model (`ProductClarification`):**
   - Each clarification record tracks `product`, `category` (Medidas, Etiqueta/Composición, Defectos/Desgaste, Material/Autenticidad, General), `question`, `asked_by`, `answer`, `answered_by`, `status` (`PENDING`, `RESOLVED`), and timestamps.
   - Quick-category chips on desktop allow managers to formulate questions in seconds.
   - Assistant interface on mobile allows 1-tap answering directly from the product page.

3. **High-Visibility Notification & Discovery:**
   - A lightweight Django context processor injects `pending_clarifications_count` globally into every template.
   - Top navigation renders an eye-catching badge: `❓ Dudas (X)` for assistants and managers, linking directly to the filtered dashboard view `?status=awaiting_info`.
   - The mobile intake screen (`/intake/`) displays a subtle, dismissible banner alerting assistants to pending questions so they can answer them when handling items in the store.

4. **Deterministic Gemini Multimodal AI Synergy:**
   - When generating or re-generating AI listing copy, `ai_service.py` combines the original `raw_note` with resolved `ProductClarification` items:
     ```text
     FIELD NOTES:
     Cazadora de cuero negra con tachuelas

     ADDITIONAL CLARIFICATIONS & MEASUREMENTS:
     - [Medidas]: Axila a axila: 56 cm, Largo: 68 cm
     - [Material]: 100% piel bovina legítima, cremallera YKK
     ```
   - When an assistant answers all open questions, the product displays a visual indicator for the manager: *"✨ Nuevos datos disponibles — Regenerar descripción con IA"*.

---

## Key Assumptions to Validate
- [ ] **Mobile Response Habit:** Assistants will check and respond to pending questions without leaving the web app when alerted by the top bar counter and intake screen banner.
- [ ] **Copywriting Quality Lift:** Supplying structured answers (measurements, exact fabric tags) to Gemini Vision measurably eliminates marketplace inquiries and return rates.
- [ ] **Backward Compatibility:** Preserving `is_sold` synchronization ensures 100% uptime and passes all 129 existing unit/integration/e2e tests without regressions.

---

## MVP Scope

### 1. Data Layer (`inventory/models.py`)
- `ProductStatus` TextChoices: `DRAFT`, `AWAITING_INFO`, `READY`, `SOLD`, `BLOCKED`.
- Add `status` field to `Product` with `db_index=True`, defaulting to `DRAFT`.
- Bi-directional sync between `status == SOLD` and legacy `is_sold` column.
- Model `ProductClarification` with `category`, `question`, `answer`, `status`, `asked_by`, `answered_by`, timestamps.

### 2. Global Notification Context (`inventory/context_processors.py`)
- `pending_clarifications_count`: Returns total count of unresolved questions.
- Header badge in `inventory/templates/inventory/base.html` displaying `❓ Dudas (X)`.

### 3. User Interface & Flow
- **Product Detail (`/products/<pk>/`):**
  - Clarification card with preset question categories (*Medidas*, *Etiqueta*, *Defectos*, *Material*, *General*).
  - Manager: Post new question, resolve/close question, change lifecycle status.
  - Assistant: Answer questions with responsive mobile textarea and submit button.
  - Callout banner when new answers are available to regenerate AI copy.
- **Intake (`/intake/`):**
  - Top alert banner notifying assistants if unresolved questions are waiting.
- **Dashboard (`/dashboard/`):**
  - New status filter tab: `Dudas pendientes` (`?status=awaiting_info`) with scoped counters.

### 4. AI Service Integration (`inventory/services/ai_service.py`)
- Automatically format and inject answered clarifications into the Gemini prompt payload alongside `raw_note`.

### 5. Internationalization (i18n)
- All new statuses, categories, badges, and notifications fully translated in Spanish (`locale/es/`) and English.

---

## Not Doing (and Why)
- **Live WebSocket / WebPush Chat:** Unnecessary operational overhead and infrastructure complexity for a two-person reselling team. Standard HTTP requests and navbar badges provide clean, reliable async coordination.
- **Arbitrary Nested Comment Threads:** Keeps conversations strictly bounded to a single question and single answer per issue. If further doubts arise, a new clarification item is created.
- **Third-Party Messaging Integrations (WhatsApp/Telegram Webhooks):** Out of scope for MVP; keeping all product context inside the staging dashboard avoids fragmented information.

---

## Open Questions Resolved
- **Lifecycle Transition Policy:** When a manager creates a clarification question, product status transitions to `AWAITING_INFO`. When the assistant answers all open questions, status automatically updates to `READY` (or `DRAFT`) with a visual recommendation to regenerate AI.
- **Status Coexistence with `is_sold`:** Handled cleanly with property encapsulation and model `save()` synchronization, guaranteeing backward compatibility.
