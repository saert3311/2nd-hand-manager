# Product Requirements Document (PRD): Dynamic AI Model & Prompt Configuration

## 1. Executive Summary
Provide store managers and administrators with the ability to dynamically configure, tune, and test Google Gemini AI models, prompt instructions, sampling parameters (temperature), and language localization directly within the Django Administration panel (`/admin/`). This decouples AI copywriting and model selection from application deployments, empowering non-technical operators to optimize marketplace listing conversion across Wallapop, Vinted, and eBay while protecting structured JSON schema integrity and providing automatic fallback to reliable codebase defaults.

---

## 2. Problem Statement
Currently:
1. **Hardcoded Model & Prompts:** In [`inventory/services/ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py), the Gemini model (`gemini-2.5-flash`), temperature (`0.3`), and system prompts for Spanish and English are hardcoded into Python strings.
2. **Deployment Bottleneck for Prompt Tuning:** Any adjustment to listing tone, marketplace formatting guidelines, or model upgrades (e.g. testing `gemini-2.5-pro` or new Gemini releases) requires editing Python code, running tests, and executing a deployment.
3. **No Non-Technical Access:** Store managers—who understand secondhand marketplace merchandising, buyer psychology, and platform keywords best—cannot tweak prompt copy without developer intervention.
4. **Fragility of Ad-Hoc Prompting:** Allowing raw prompt editing without guardrails risks corrupting the required JSON schema output ([`ProductListingSchema`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py#L20-L23)) or omitting the intake assistant's field notes (`raw_note`).

---

## 3. User Personas & Scenarios

### Persona: Store Manager / Admin (User B)
- **Scenario 1 (Optimizing Spanish Copywriting for Wallapop & Vinted):** The manager wants Spanish listings to emphasize vintage authenticity, condition inspection, and bulleted tags for Wallapop. They log into `/admin/`, open the active Spanish AI Prompt Configuration, edit the copywriting instructions to add emphasis on flaws and vintage tags, and save. The next time any product listing is generated, the new copy instructions take effect immediately.
- **Scenario 2 (Upgrading / Testing a Newer Gemini Model):** Google releases a new model checkpoint or the manager wants to test `gemini-2.5-pro` on high-value items. The manager enters `gemini-2.5-pro` into the free-form `model_name` field in admin and saves.
- **Scenario 3 (Tuning Creativity / Determinism):** The manager notices listings are either too repetitive or too verbose. They adjust `temperature` from `0.3` to `0.2` or `0.5` directly via the admin form with slider/numeric validation.
- **Scenario 4 (Zero-Downtime Rollback):** If an experiment yields suboptimal copy, the manager can revert to standard instructions or deactivate the configuration, automatically falling back to system defaults.

### Persona: Field Sourcing Assistant (User A)
- **Scenario 5 (Zero Workflow Friction):** The intake assistant continues taking photos and recording rough field notes at `/intake/`. They are insulated from backend prompt changes, experiencing consistent, fast generation.

### Persona: Developer / DevOps
- **Scenario 6 (Resilient Fault Tolerance):** If the database is missing an active configuration, or if an unexpected database issue occurs, the AI service seamlessly falls back to hardcoded in-code defaults without throwing runtime exceptions.

---

## 4. Scope & Functional Requirements

### 4.1 Data Model: `AIPromptConfiguration`
A new Django model in `inventory.models`:
- **`language`:** `CharField(max_length=10, choices=[('es', _('Spanish')), ('en', _('English'))])`
- **`model_name`:** `CharField(max_length=64, default="gemini-2.5-flash", help_text=_("Gemini model identifier (e.g. gemini-2.5-flash, gemini-2.5-pro)"))`
- **`temperature`:** `FloatField(default=0.3, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], help_text=_("Sampling temperature between 0.0 and 1.0"))`
- **`system_instruction`:** `TextField(help_text=_("Editable copywriting guidelines, marketplace rules (Wallapop/Vinted/eBay), and tone instructions."))`
- **`is_active`:** `BooleanField(default=True, help_text=_("Whether this configuration is actively used for listing generation."))`
- **`created_at`:** `DateTimeField(auto_now_add=True)`
- **`updated_at`:** `DateTimeField(auto_now=True)`
- **Validation & Constraints:**
  - `clean()` enforces that only one active record exists per language code. If a record is saved with `is_active=True`, existing active records for the same language are either updated or an error is raised.
  - Temperature must be strictly within `[0.0, 1.0]`.

### 4.2 Django Admin Interface: `AIPromptConfigurationAdmin`
- Registered with the existing `ManagerAdminSite` (`admin.site`).
- Accessible strictly to store managers (`is_manager(user)`).
- **List Display:** `language`, `model_name`, `temperature`, `is_active`, `updated_at`.
- **List Filters:** `is_active`, `language`.
- **Search Fields:** `model_name`, `system_instruction`.
- **Form Layout:** Clear fieldsets separating Model Settings (`model_name`, `temperature`), Copywriting Instructions (`system_instruction`), and Activation Status (`is_active`).
- **In-Form Help & Placeholders:** Explicit guidance explaining that the system automatically appends the intake assistant's field notes and strictly enforces the title/description JSON format.

### 4.3 AI Service Layer Integration (`inventory/services/ai_service.py`)
- `generate_product_listing(product: Product, language: str = "en")` refactored:
  1. Resolves normalized language prefix (`es` vs `en`).
  2. Queries `AIPromptConfiguration.objects.filter(language=lang_prefix, is_active=True).first()`.
  3. **Dynamic Resolution:**
     - If an active configuration exists:
       - Uses `config.model_name`
       - Uses `config.temperature`
       - Combines `config.system_instruction` with the required system envelope (including `product.raw_note`).
     - If no active configuration exists or on DB error:
       - Uses fallback defaults: model `gemini-2.5-flash`, temperature `0.3`, and standard hardcoded instructions.
  4. Passes `temperature` into `types.GenerateContentConfig(temperature=..., response_mime_type="application/json", response_schema=ProductListingSchema)`.
  5. Passes model name into `client.models.generate_content(model=model_name, ...)`.

### 4.4 Data Migration & Initial Seeding
- Create a data migration (`000X_seed_ai_prompt_configurations.py`) that pre-populates initial records:
  - `es`: Active record with current Spanish instructions, `gemini-2.5-flash`, temperature `0.3`.
  - `en`: Active record with current English instructions, `gemini-2.5-flash`, temperature `0.3`.
- Ensures zero behavioral regression upon deployment.

### 4.5 Internationalization (i18n)
- All model field verbose names, help texts, and admin UI labels marked with `gettext_lazy` (`_`).
- Updated Spanish translation catalog (`locale/es/LC_MESSAGES/django.po`) and recompiled binary `.mo`.

---

## 5. Non-Functional Requirements
- **Reliability & Schema Safety:** Guarded architecture ensuring prompt instruction changes cannot circumvent Pydantic schema validation or break JSON parsing.
- **Performance:** Lightweight query (`.filter(...).first()`) on indexed/few-row table. No measurable latency added to AI generation.
- **Security:** Access restricted exclusively to authorized managers via `ManagerAdminSite`. Assistants cannot view or tamper with AI configuration.
- **Portability:** Portable across SQLite and PostgreSQL; translation compilation remains Python-native via `compile_locales`.

---

## 6. Success Criteria
1. Managers can view, create, and edit `AIPromptConfiguration` records in `/admin/`.
2. Updating `system_instruction`, `model_name`, or `temperature` in Django Admin immediately influences subsequent calls to `generate_product_listing`.
3. Setting `is_active=False` or deleting configuration records causes the AI service to transparently fall back to hardcoded defaults without raising errors.
4. Validations prevent invalid temperatures (< 0.0 or > 1.0) and prevent conflicting active configurations for the same language.
5. All new model fields and admin screens display in Spanish (`es`) when accessed by Spanish browsers.
6. 100% of automated unit tests pass, including new tests covering configuration lookup, fallback behavior, and model parameter forwarding.
