# Product Requirements Document (PRD): Smart Intake Pre-flight: On-Demand Item Identification, Advisory Guidance & Direct Pricing

## 1. Executive Summary
Enhance the mobile-first intake experience (`inventory:intake`) by providing sourcing assistants with an on-demand AI identification tool, real-time advisory guidance on missing details, and an optional sale price field. 

While the assistant is physically holding the product and selecting photos, they can tap **"Identificar producto"**. The system invokes Google Gemini Vision (`gemini-2.5-flash`) via an asynchronous endpoint (`/inventory/intake/identify/`) to inspect the selected photos. It detects the item's brand/category and highlights missing details (such as missing size tags, uninspected sole wear, or care label absence) in a friendly, non-blocking advisory banner directly above the field notes. The assistant can immediately verify the physical item, add notes or extra photos, set an optional price in Euro (€), and submit without disrupting cataloging velocity.

---

## 2. Problem Statement
1. **Downstream Clarification Bottlenecks:** Assistants photograph products and submit them quickly with sparse notes. Later, when managers review items on the staging dashboard, they notice that crucial attributes (garment size, fabric composition, serial number, flaw details) are missing. Managers must open a clarification inquiry (`AWAITING_INFO`), forcing the assistant to locate the physical item on warehouse racks hours or days later.
2. **Missing Real-Time Feedback During Intake:** Assistants often don't know which specific details a manager or resale platform requires for a particular item type (e.g., shoe sole photos vs. leather authenticity stamps vs. electronics model stickers).
3. **No Direct Price Capture at Intake:** Some intake items arrive with fixed shop price tags or agreed purchase prices. Currently, assistants cannot record this price during intake; managers must manually enter it later on the staging screen.

---

## 3. User Personas & Scenarios

### Persona 1: Sourcing Assistant (User A)
- **Scenario 1 (Real-Time Missing Tag Alert):** The assistant snaps 3 photos of a vintage leather jacket and taps "Identificar producto". Within 2 seconds, the AI identifies it as a "Vintage Schott Perfecto Leather Jacket" and displays an advisory banner: *"💡 No se aprecia la etiqueta de talla ni el estado del forro interior"*. The assistant checks the jacket, notices the size 42 label, snaps a 4th photo of the tag, and types "Size 42, inner lining clean" into notes.
- **Scenario 2 (Known Price Intake):** Sourcing an item with an existing store sticker (€45.00), the assistant fills in the new optional `Precio (€)` field on the intake screen. When saved, the product immediately reflects `sale_price = 45.00`, saving the manager a manual step.
- **Scenario 3 (Zero Delay / Offline Fallback):** In a hurry or on a slow connection, the assistant skips the identify button or if the AI times out, the form remains completely functional and allows immediate submission without blocking.

### Persona 2: Store Manager / Lister (User B)
- **Scenario (Higher First-Pass Yield):** Products arrive in the staging dashboard with higher quality photos, complete tags, fewer missing flaws, and pre-filled prices. The manager spends less time opening `ProductClarification` inquiries and can generate AI listings and publish immediately.

---

## 4. Scope & Functional Requirements

### 4.1 On-Demand Product Identification API (`/inventory/intake/identify/`)
- **HTTP Method:** `POST`
- **Authentication:** Gated by `@login_required` (available to both Assistants and Managers).
- **Request Payload:** `multipart/form-data` containing:
  - `images`: 1 to 10 image files (selected in client file input).
  - `raw_note`: Optional current text from the raw notes field.
- **AI Processing:**
  - Extracts image bytes in-memory (downscaling client-side or processing directly).
  - Resolves active `AIPromptConfiguration` for language and model fallback (`gemini-2.5-flash`).
  - Calls Gemini Multimodal Vision API using a structured Pydantic schema:
    ```python
    class IntakePreflightSchema(BaseModel):
        identified_title: str
        category: str
        detected_attributes: list[str]
        missing_or_recommended_info: list[str]
        suggested_note: str
    ```
- **Response Format:** JSON:
  ```json
  {
    "success": true,
    "identified_title": "Nike Air Max 90 Infrared",
    "category": "Sneakers / Footwear",
    "detected_attributes": ["White/Grey/Infrared colorway", "Visible Air cushioning"],
    "missing_or_recommended_info": [
      "Size tag inside tongue is not clearly visible",
      "Underside sole tread wear is not shown"
    ],
    "suggested_note": "Nike Air Max 90 Infrared, condition good. Check tongue tag for US/EU size."
  }
  ```
- **Error Resilience:** Returns `{ "success": false, "error": "User-friendly error message" }` on network failure, API timeout, or invalid image input without crashing.

### 4.2 Mobile Intake UI Enhancements (`inventory/templates/inventory/intake.html`)
- **"Identificar producto" Action Button:**
  - Located directly below the photo upload preview area.
  - Disabled with clear helper text when 0 photos are selected (`"Selecciona fotos primero"`).
  - Active once ≥1 photo is chosen.
  - Shows an animated spinner and text *"Analizando fotos con IA..."* during the request.
- **Advisory Guidance Alert Banner:**
  - Appears smoothly above the `raw_note` field upon successful identification.
  - Displays detected item title with an icon.
  - Highlights missing detail tips as bulleted badges (amber/blue style).
  - Provides a one-click button: *"Añadir sugerencia a notas"* (appends or sets `suggested_note` in `raw_note`).
- **Strictly Non-Blocking:**
  - The banner is purely advisory. The "Guardar producto" button is never disabled or blocked.
- **Optional Sale Price Field:**
  - Added to the intake card layout between field notes and submit button.
  - Currency input formatted with prefix `€`, numeric keypad on mobile (`inputmode="decimal"`), step `0.01`.

### 4.3 Form & Model Integration (`ProductIntakeForm` & `Product`)
- Update `ProductIntakeForm` in `inventory/forms.py`:
  - Add `sale_price` field (`forms.DecimalField(required=False, min_value=Decimal("0.00"), max_value=Decimal("9999999.99"))`).
- Update `product_intake_view` in `inventory/views.py`:
  - If `form.cleaned_data.get("sale_price")` is present, assign it to `product.sale_price`.

### 4.4 Internationalization (i18n)
- All new UI strings marked with `{% trans %}` / `gettext_lazy`:
  - "Identify Item" / "Identificar producto"
  - "Analyzing photos with AI..." / "Analizando fotos con IA..."
  - "Suggested Details to Verify" / "Detalles sugeridos a verificar"
  - "Apply suggestion to notes" / "Añadir sugerencia a notas"
  - "Sale Price (€)" / "Precio de venta (€)"
  - "Optional target sale price in Euro" / "Precio de venta opcional en euros"
- Spanish message catalog updated in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.

---

## 5. Non-Functional Requirements
- **Latency:** Vision pre-flight call target response time ≤ 3.0 seconds under standard 4G/WiFi conditions.
- **Payload Optimization:** Client JavaScript resizes or compresses images before AJAX transmission if total size exceeds 4MB to maintain rapid mobile upload speed.
- **Security:** CSRF token verification enforced on the AJAX endpoint. File type validation and authentication required.
- **Graceful Degradation:** If Gemini is unavailable, rate-limited, or disabled, the identification button displays a gentle toast/error without blocking normal intake.

---

## 6. Success Metrics & Acceptance Criteria
1. Assistants can trigger photo identification in 1 tap from the intake screen.
2. AI accurately detects the product category and surfaces missing attribute tips.
3. Assistants can enter an optional sale price in € that persists correctly to `product.sale_price`.
4. The intake form remains 100% functional and submittable whether the identification button is used or ignored.
5. All tests pass with zero regressions and complete Spanish i18n coverage.
