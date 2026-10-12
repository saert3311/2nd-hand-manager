# Product Requirements Document (PRD): Product Clarifications & Lifecycle States

## 1. Executive Summary
Introduce a structured product lifecycle state machine and an asynchronous clarification Q&A mechanism between Store Managers and Intake Assistants. When managers encounter ambiguous or missing product information during listing staging (e.g. unknown material, missing measurements, unconfirmed flaws, illegible tags), they can submit structured clarification requests. Assistants are notified via an attention badge in the top navigation bar and on the mobile intake screen, allowing them to answer directly from their phones. Resolved answers automatically feed into the Gemini Multimodal Vision AI prompt to generate accurate, high-converting marketplace listings without blocking workflow velocity.

---

## 2. Problem Statement
1. **Asynchronous Information Bottleneck:** Sourcing assistants quickly photograph and catalog dozens of secondhand garments per day. When a store manager stages items on desktop, critical listing details are frequently missing (e.g. pit-to-pit measurements, composition tags, working condition of zippers). Currently, there is no in-app mechanism to ask for details or flag missing information.
2. **Binary Product State Limitation:** Products currently only possess a binary `is_sold` flag (True/False). Items with doubts, unverified counterfeits, damaged goods, or items ready for publishing cannot be distinguished in catalog views or filtered effectively.
3. **AI Description Inaccuracy:** Without clarification data, the Gemini Multimodal Vision model either leaves gaps in the description or relies on guesses, leading to buyer questions or disputes on marketplaces like Wallapop, Vinted, or eBay.
4. **Lack of Visibility for Assistants:** Assistants spend their work hours in the mobile intake interface (`/intake/`). If a manager has questions about a cataloged product, there is no visual indicator or queue directing the assistant's attention to the specific item needing clarification.

---

## 3. User Personas & Scenarios

### Persona: Store Manager / Lister (User B)
- **Scenario 1 (Requesting Missing Measurements):** The manager reviews an oversized vintage bomber jacket. The intake note says "Chaqueta vintage". The manager creates a clarification under category *Medidas* asking: "Por favor, mide ancho de sisa a sisa y largo de manga". The product status transitions to `AWAITING_INFO`.
- **Scenario 2 (Reviewing Answers & Re-generating Copy):** The assistant submits the measurements. The product displays an indicator: *"✨ Nuevos datos disponibles — Regenerar descripción con IA"*. The manager clicks "Generate AI Listing", and Gemini generates a description explicitly highlighting the measured dimensions.
- **Scenario 3 (Flagging Unsellable / Damaged Goods):** The manager spots a torn lining or fake tag. They flag the product as `BLOCKED` with an explanation: "Forro interior desgarrado, no apto para reventa". The product is excluded from active listings and cannot be linked to marketplace sites.

### Persona: Sourcing Assistant (User A)
- **Scenario 4 (Discovering Pending Clarifications):** An assistant logs in on their phone. The top navigation bar displays a counter badge: `❓ Dudas (2)`. Tapping the badge opens the filtered dashboard showing the 2 items requiring answers.
- **Scenario 5 (Answering from Mobile):** The assistant inspects the physical garment on the rack, opens the product page, types the requested measurements in the reply box, and taps "Guardar respuesta". The clarification is marked resolved, and the counter badge decrements.

---

## 4. Scope & Functional Requirements

### 4.1 Product Lifecycle State Machine (`inventory/models.py`)

#### `ProductStatus` TextChoices
- `DRAFT`: Initial state upon assistant intake.
- `AWAITING_INFO`: Pending clarification questions from manager.
- `READY`: Reviewed and ready for marketplace publishing.
- `SOLD`: Item marked sold.
- `BLOCKED`: Item rejected, damaged, or unpublishable.

#### Model Enhancements (`Product`)
- `status`: `models.CharField(max_length=20, choices=ProductStatus.choices, default=ProductStatus.DRAFT, db_index=True)`
- Backward compatibility:
  - Property `is_sold`: returns `self.status == ProductStatus.SOLD`. Setter sets `self.status = ProductStatus.SOLD` if True, or `ProductStatus.READY` if False.
  - Legacy `is_sold` database column maintained in sync during `save()` to preserve existing external queries and test assertions.

### 4.2 Product Clarification Model (`ProductClarification`)

Stores structured Q&A items attached to products:
- `product`: `ForeignKey(Product, on_delete=models.CASCADE, related_name="clarifications")`
- `category`: `CharField(max_length=30, choices=ClarificationCategory.choices, default=ClarificationCategory.GENERAL)`
  - Categories:
    - `MEASUREMENTS` (*Medidas / Tallas*)
    - `TAG_COMPOSITION` (*Etiqueta / Composición / Marca*)
    - `FLAWS_CONDITION` (*Defectos / Desgaste / Manchas*)
    - `MATERIAL_AUTHENTICITY` (*Material / Autenticidad*)
    - `GENERAL` (*Consulta general*)
- `question`: `TextField` (question asked by manager)
- `asked_by`: `ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="asked_clarifications")`
- `answer`: `TextField(blank=True, default="")` (response from assistant)
- `answered_by`: `ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="answered_clarifications")`
- `status`: `CharField(max_length=20, choices=ClarificationStatus.choices, default=ClarificationStatus.PENDING)` (`PENDING` / `RESOLVED`)
- `created_at`: `DateTimeField(auto_now_add=True)`
- `answered_at`: `DateTimeField(null=True, blank=True)`

### 4.3 Notification & Discovery Layer

#### Context Processor (`inventory/context_processors.py`)
- Function `notifications(request)`:
  - Returns `{"pending_clarifications_count": ProductClarification.objects.filter(status="pending").count()}` for authenticated users.

#### Header Notification Badge (`inventory/templates/inventory/base.html`)
- Displays `❓ Dudas (X)` adjacent to navigation links when `pending_clarifications_count > 0`.
- Clicking navigates directly to `{% url 'inventory:dashboard' %}?status=awaiting_info`.

#### Mobile Intake Banner (`inventory/templates/inventory/intake.html`)
- High-contrast, dismissible alert banner displayed above the intake photo uploader when pending clarifications exist.

### 4.4 Dashboard Status Filtering & Counter Scoping (`inventory/views.py`)
- Expand status tabs:
  - `All` (`status=all`)
  - `Active` (`status=active`)
  - `Dudas pendientes` (`status=awaiting_info`)
  - `Sold` (`status=sold`)
  - `Blocked` (`status=blocked`)
- Status counters dynamically update to reflect `awaiting_info_count` and `blocked_count`, scoped to active platform filters and searches.

### 4.5 Product Staging UI (`inventory/templates/inventory/product_detail.html`)
- **Lifecycle Status Badge:** Prominently rendered in header with color coding:
  - `DRAFT`: Gray / Slate
  - `AWAITING_INFO`: Amber / Warning
  - `READY`: Emerald / Green
  - `SOLD`: Slate / Muted
  - `BLOCKED`: Rose / Red
- **Clarification Card:**
  - Manager: Form with category chip selectors, question textarea, and "Enviar pregunta" button.
  - Assistant: List of pending questions with prominent text inputs and "Enviar respuesta" button.
  - History of resolved questions with author timestamps.
  - AI Regeneration Pill: Highlighted when resolved clarifications exist that have not yet been incorporated into the current title/description.
- **Publishing Gate:** When status is `AWAITING_INFO` or `BLOCKED`, the Marketplace Links form displays an alert advising verification prior to publishing.

### 4.6 Gemini Multimodal AI Integration (`inventory/services/ai_service.py`)
- Query resolved clarifications for the product (`product.clarifications.filter(status="resolved")`).
- Format and append resolved questions and answers to the multimodal prompt instructions payload:
  ```text
  ADDITIONAL VERIFIED DETAILS & CLARIFICATIONS:
  - [Medidas / Tallas]: Ancho axila a axila 56cm, largo 68cm.
  - [Material]: 100% Piel ovina auténtica, forro en buen estado.
  ```
- Incorporate these details into the structured output JSON (`ProductListingSchema`).

### 4.7 Internationalization (i18n)
- Localize all new status choices, clarification categories, buttons, and badges in Spanish (`locale/es/LC_MESSAGES/django.po`) and English (`en`).

---

## 5. Edge Cases & Boundary Conditions
1. **Auto-Transition Logic:**
   - Asking a question on a product in `DRAFT` or `READY` immediately shifts its status to `AWAITING_INFO`.
   - When all open questions on a product are resolved, status automatically returns to `READY` (or `DRAFT`).
2. **Marking as Sold with Open Questions:**
   - If a manager marks an item as sold, status changes to `SOLD`, and open questions are marked resolved or archived.
3. **Assistant Access Controls:**
   - Assistants can answer questions on any product but cannot edit or delete manager questions or bypass product status to `READY` without answering.
4. **Zero-Clarification Products:**
   - Products without clarifications function completely as before with 0 regressions.

---

## 6. Success Criteria
1. Managers can ask categorized questions attached to any product, shifting status to `AWAITING_INFO`.
2. Assistants see pending questions via top navigation badge (`❓ Dudas (X)`) and mobile intake banner.
3. Assistants can submit answers directly from mobile on `/products/<pk>/`.
4. Resolved answers are appended to the Gemini Vision prompt, producing enriched title and description copy.
5. Dashboard provides dedicated filtering for items awaiting info (`?status=awaiting_info`).
6. All existing unit, integration, and e2e browser tests continue to pass (100% backward compatibility).
