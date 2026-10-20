# Product Requirements Document (PRD) & Specification
# Intake AI Valuation & Reference Pricing ("New Retail Value & Used Resale Value")

## 1. Objective

Empower sourcing assistants and store managers with automated market appraisal benchmarks by expanding the **Intake Preflight AI Vision Scan** (`identify_intake_product`) to estimate:
1. **Estimated New Retail Value / Original MSRP (`estimated_retail_price`, €):** The approximate manufacturer retail price when the item was brand new.
2. **Estimated Secondhand Resale Market Value (`estimated_resale_price`, €):** The realistic secondhand resale market price for the item in its detected condition across major peer-to-peer marketplaces (Wallapop, Vinted, eBay).

These values are captured during the intake pre-flight identification, persisted to the `Product` domain model, and surfaced both in the mobile intake form and prominently on the staging product detail page (`/products/<pk>/`) directly alongside the manager's `Sale Price` input as a pricing reference benchmark.

---

### 1.1 Business & Operational Problems Solved

1. **Pricing Inconsistency & Guesswork:** Sourcing assistants and store managers currently price items without immediate market reference, leading to underpriced rare goods or overpriced stale inventory that fails to sell.
2. **Time Consuming Manual Research:** Managers currently must leave the staging hub, open Wallapop/Vinted/Google in a separate browser tab, search for the item model, and manually check used prices.
3. **High-Margin Discovery at Intake:** Sourcing assistants can immediately identify whether a physical item found in bulk lots or field sourcing is a high-value vintage piece or high-retail item before completing the intake.
4. **Permanent Appraisal Traceability:** Preserving the original estimated new MSRP and estimated used market value alongside the actual realized sale price gives long-term operational analytics into resale margins and discount-to-new ratios.

---

## 2. Tech Stack & Architecture Context

- **Runtime / Framework:** Python 3.13, Django 5.1+
- **AI Vision Model:** Google Gemini Multimodal Vision API (`google-genai` / `gemini-flash-latest` via `ai_service.py`)
- **Structured Output:** Pydantic schema validation (`IntakePreflightSchema`) returning JSON decimals
- **Database:** SQLite (local/dev) / PostgreSQL (production) with Django ORM
- **Frontend / Styling:** Django Templates (`intake.html`, `product_detail.html`), Tailwind CSS, Vanilla JavaScript
- **Internationalization (i18n):** Bilingual support (Spanish `es` default, English `en`) via Django `gettext`

---

## 3. Executable Commands

- **Run Dev Server:** `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
- **Create Migrations:** `.venv\Scripts\python.exe manage.py makemigrations inventory`
- **Apply Migrations:** `.venv\Scripts\python.exe manage.py migrate`
- **Run Targeted Tests:** `.venv\Scripts\python.exe manage.py test tests.test_ai_valuation`
- **Run Full Test Suite:** `.venv\Scripts\python.exe manage.py test`
- **Code Linter:** `.venv\Scripts\ruff.exe check .`
- **Compile Translations:** `.venv\Scripts\python.exe manage.py compile_locales`

---

## 4. Project Structure & Affected Modules

```
inventory/
├── models.py                     # Add estimated_retail_price & estimated_resale_price to Product model
├── migrations/
│   └── 0015_product_estimated_prices.py # Database migration adding the two decimal fields
├── forms.py                      # Add estimated fields to ProductIntakeForm & ProductUpdateForm
├── services/
│   └── ai_service.py             # Update IntakePreflightSchema and prompts for new & used value appraisal
├── views.py                      # Return estimated prices in intake_identify_view JSON response
├── templates/inventory/
│   ├── intake.html               # Add reference value pill/badge in AI advisory banner & near target price
│   └── product_detail.html       # Display reference values beside manager's Sale Price input in staging form
├── admin.py                      # Expose estimated prices in ProductAdmin list_display & fieldsets
locale/
├── es/LC_MESSAGES/django.po      # Spanish translations for estimated retail and resale labels
└── en/LC_MESSAGES/django.po      # English translations
tests/
└── test_ai_valuation.py          # Unit & integration tests for AI valuation schema, form, and UI rendering
```

---

## 5. Domain Model & Service Specification

### 5.1 `Product` Model Additions (`inventory/models.py`)

Add two nullable Decimal fields with Euro currency validation:

```python
estimated_retail_price = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    validators=[
        MinValueValidator(Decimal("0.00")),
        MaxValueValidator(Decimal("9999999.99")),
    ],
    verbose_name=_("Estimated Retail Price (€)"),
    help_text=_("Estimated original retail price when new (MSRP)"),
)

estimated_resale_price = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    validators=[
        MinValueValidator(Decimal("0.00")),
        MaxValueValidator(Decimal("9999999.99")),
    ],
    verbose_name=_("Estimated Resale Price (€)"),
    help_text=_("Estimated secondhand market resale value"),
)
```

### 5.2 AI Service Schema & Prompt Upgrade (`inventory/services/ai_service.py`)

Update `IntakePreflightSchema` to include the valuation fields:

```python
class IntakePreflightSchema(BaseModel):
    identified_title: str = Field(description="Detected product brand, model, and item type")
    category: str = Field(description="High-level product category")
    detected_attributes: list[str] = Field(default_factory=list, description="Visible attributes such as color, materials, logos")
    missing_or_recommended_info: list[str] = Field(default_factory=list, description="Actionable checklist of missing tags, size labels, flaws, or angles")
    suggested_note: str = Field(description="Draft summary suitable for intake notes")
    estimated_retail_price: Optional[float] = Field(
        default=None,
        description="Estimated original retail price when brand new in Euros (€). Null if impossible to estimate."
    )
    estimated_resale_price: Optional[float] = Field(
        default=None,
        description="Estimated realistic secondhand market resale value in Euros (€) considering condition. Null if impossible to estimate."
    )
```

#### Updated Prompt Instructions (Spanish & English)
Instruct Gemini to evaluate:
- **PVP Nuevo estimado (`estimated_retail_price`):** Estimación razonable del precio de venta al público original cuando el artículo era nuevo en tienda (MSRP).
- **Valor Reventa segunda mano (`estimated_resale_price`):** Estimación del valor de reventa en el mercado de segunda mano en España/Europa (Wallapop, Vinted, eBay) para el estado detectado.
- Si el objeto es de marca desconocida, artesanal o no tasable objetivamente, devolver `null`.

### 5.3 Intake Form Integration (`ProductIntakeForm`)

In `inventory/forms.py`:
- Include `estimated_retail_price` and `estimated_resale_price` as `HiddenInput` widgets in `ProductIntakeForm` (similar to `ai_title`).
- In `intake.html`, when `identifyBtn` receives JSON response from `/inventory/intake/identify/`:
  - Populate hidden fields: `id_estimated_retail_price.value` and `id_estimated_resale_price.value`.
  - When the assistant submits the form, both values are atomically saved to the `Product` instance.

---

## 6. User Interface Presentation

### 6.1 Mobile Intake Form (`inventory/templates/inventory/intake.html`)

1. **Inside the AI Advisory Card (`#aiAdvisoryBanner`):**
   Render an eye-catching valuation badge grid:
   ```html
   <div id="advisoryValuationContainer" class="hidden mt-3 pt-3 border-t border-indigo-200/60 grid grid-cols-2 gap-2 text-xs">
     <div class="bg-white/80 rounded-xl p-2.5 border border-indigo-100">
       <span class="text-slate-500 font-medium block text-[11px] uppercase tracking-wider">{% trans "Est. New Retail (MSRP)" %}</span>
       <span id="advisoryRetailPrice" class="font-extrabold text-slate-800 text-sm sm:text-base font-mono">--</span>
     </div>
     <div class="bg-white/80 rounded-xl p-2.5 border border-indigo-100">
       <span class="text-emerald-700 font-semibold block text-[11px] uppercase tracking-wider">{% trans "Est. Used Resale" %}</span>
       <span id="advisoryResalePrice" class="font-extrabold text-emerald-800 text-sm sm:text-base font-mono">--</span>
     </div>
   </div>
   ```

2. **Near the Target Sale Price Input (`#id_sale_price`):**
   Render dynamic reference pills directly beneath or above the input:
   - *"Ref. nuevo: €120.00"* | *"Ref. reventa: €45.00"*
   - A convenient button: *"Usar precio de reventa estimado"* that sets `id_sale_price.value = data.estimated_resale_price` if clicked.

### 6.2 Staging Product Detail View (`inventory/templates/inventory/product_detail.html`)

In the Pricing & Status section of the listing staging form, right beside the manager's `Sale Price (€)` input:
- Add a dedicated benchmark card or badge row displaying:
  - **PVP Nuevo (MSRP):** `€{{ product.estimated_retail_price|floatformat:2|default:"—" }}`
  - **Reventa estimada:** `€{{ product.estimated_resale_price|floatformat:2|default:"—" }}`
  - A subtle discount-to-new calculation (e.g. `product.sale_price` vs `product.estimated_retail_price`, `-62% dto. sobre nuevo`).
- If can_manage is true, a quick click pill: *"Aplicar reventa (€XX.XX)"* that fills the sale price input.

---

## 7. Testing Strategy

1. **Unit Tests (`tests/test_ai_valuation.py`)**:
   - `test_preflight_schema_includes_valuation_fields`: Test Pydantic schema validation with valid floats, integer values, nulls, and missing fields.
   - `test_identify_intake_product_parses_valuation`: Mock Gemini client returning `estimated_retail_price` and `estimated_resale_price` and verify dictionary output.
   - `test_intake_form_saves_estimated_prices`: Test `ProductIntakeForm` binds and saves `estimated_retail_price` and `estimated_resale_price` to `Product`.
   - `test_product_detail_view_renders_valuation_reference`: Test GET `/products/<pk>/` renders `#ref-retail-price` and `#ref-resale-price` with localized currency.
   - `test_null_valuation_handling`: Test behavior when Gemini cannot appraise an item (`None`); verify no crashes and graceful fallback display (`—`).
2. **Regression Verification**:
   - Full test suite execution: All 323 existing tests pass with 0 regressions.
   - Linter execution: `ruff check .` with 0 warnings.

---

## 8. Boundaries

- **Always Do:**
  - Support `None` / `null` gracefully when an item is unbranded or impossible to value.
  - Enforce decimal validation (`max_digits=10`, `decimal_places=2`, non-negative) preventing malformed numbers.
  - Preserve assistant autonomy: the estimated resale price is a reference suggestion; the user can freely choose any target price.
  - Maintain mobile responsiveness on smartphone screens ($390 \times 844$) without horizontal overflow.
- **Ask First:**
  - Automatically changing the lifecycle status based on estimated price.
- **Never Do:**
  - Block intake saving if Gemini is unable to estimate prices.
  - Hardcode currencies other than Euro (`€`).

---

## 9. Success Criteria

- [ ] Gemini preflight identification returns `estimated_retail_price` and `estimated_resale_price` in JSON response.
- [ ] `Product` model persists both decimal fields with database migration `0015_product_estimated_prices.py`.
- [ ] Intake mobile view displays reference valuation badges and allows one-click adoption into target sale price.
- [ ] Product detail staging view renders both reference prices alongside the manager's sale price input.
- [ ] Django Admin displays estimated prices in `ProductAdmin`.
- [ ] Full bilingual support (`es`/`en`) with compiled `django.mo`.
- [ ] 100% test pass rate with 0 regressions across existing 323 tests.
- [ ] `ruff check .` passes cleanly.

---

## 10. Open Questions for User Alignment

1. **Intake Sale Price Adoption Pattern:**
   - **Option A (Recommended — Reference Pills + One-Click "Usar reventa" Button):** Display the reference values clearly; if the assistant taps "Usar reventa estimada", it fills the sale price input. Otherwise, it remains a passive reference so manual notes or custom prices are not overwritten.
   - **Option B (Auto-Fill Empty Sale Price):** If the assistant has left the sale price field blank, automatically populate it with the estimated resale price upon identification.

2. **Manager Detail Page Interaction:**
   - **Option A (Recommended — Prominent Reference Badges + "Aplicar" Pill):** Display the values as reference benchmarks directly next to the manager's `Sale Price (€)` input with an optional "Aplicar" button that sets the manager's input.
   - **Option B (Fully Editable Fields in Staging Form):** Allow the manager to modify the reference `estimated_retail_price` and `estimated_resale_price` directly in the form inputs.

3. **Handling of Valuation Ranges (e.g. €40 - €50):**
   - **Option A (Recommended — Single Representative Point Estimate Decimal):** Gemini returns a single representative decimal price (e.g. €45.00), making it clean to store in standard database `DecimalField` and easily set as `sale_price`.
   - **Option B (Price Range Decimals):** Store min and max resale fields (`estimated_resale_min`, `estimated_resale_max`).
