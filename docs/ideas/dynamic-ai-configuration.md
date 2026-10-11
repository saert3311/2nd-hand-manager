# Dynamic AI Model & Prompt Configuration

## Problem Statement
How might we enable store managers to tune AI models, copywriting instructions, and language localization via Django Admin so marketplace listing conversion can be optimized without redeploying code or risking structured schema failures?

## Recommended Direction: Guarded Admin Registry (Direction A+)
Implement an `AIPromptConfiguration` database model in Django that decouples AI runtime parameters from application code:

1. **Configurable Parameters:**
   - `language`: `CharField` with choices (`es`, `en`, expandable to additional languages).
   - `model_name`: Free-form `CharField` (default `"gemini-2.5-flash"`) with help text listing recommended models (`gemini-2.5-flash`, `gemini-2.5-pro`). Free-form allows zero-migration testing of future Gemini model checkpoints.
   - `temperature`: `FloatField` (range `0.0` to `1.0`, default `0.3`).
   - `system_instruction`: `TextField` providing editable copywriting rules, platform style (Wallapop / eBay / Vinted), tone, and formatting instructions.
   - `is_active`: `BooleanField` indicating the active profile for that language.

2. **Deterministic Composition & Schema Protection:**
   The AI service separates the **editable marketing tone** from the **fixed technical envelope**:
   - The technical prompt wrapper guarantees output conforms strictly to `ProductListingSchema` (`title` and `description`) and always interpolates `product.raw_note`.
   - The user-configured `system_instruction` controls tone, marketplace focus, condition assessment emphasis, and bullet formatting.

3. **Resilient Fallback:**
   If no active database configuration exists for a given language, or if a database query fails, `inventory/services/ai_service.py` transparently falls back to the hardcoded default instructions and `gemini-2.5-flash`.

## Key Assumptions to Validate
- [ ] **Copy Quality:** Store managers can measurably improve marketplace listing conversion and appeal by iterating on Spanish and English guidelines in admin.
- [ ] **Model Agility:** A free-form model name field allows seamless upgrades to newer Gemini models (e.g., `gemini-2.5-pro` or upcoming releases) without schema changes or redeployments.
- [ ] **Schema Resilience:** Isolating technical JSON schema constraints from editable tone instructions prevents generation crashes caused by user prompt edits.

## MVP Scope
1. **Model & Migration (`inventory/models.py`):**
   - Create `AIPromptConfiguration` with `language`, `model_name`, `temperature`, `system_instruction`, `is_active`, and audit timestamps (`created_at`, `updated_at`).
   - Unique constraint or validation ensuring only one active config per language.
   - Data migration to pre-populate the initial active configs for `es` and `en` with existing production prompts.

2. **Admin Interface (`inventory/admin.py`):**
   - Register `AIPromptConfigurationAdmin` with `list_display`, `list_filter`, and field-level validation (e.g., temperature bounds 0.0–1.0).
   - Informative help texts displaying available context variables.

3. **Service Layer Integration (`inventory/services/ai_service.py`):**
   - Refactor `generate_product_listing(product, language=...)` to retrieve the active `AIPromptConfiguration` for `language`.
   - Dynamic selection of model name, temperature, and localized prompt instructions.
   - Graceful fallback to existing hardcoded constants if no record is found.

4. **Testing Suite:**
   - Unit tests verifying database configuration retrieval.
   - Unit tests verifying fallback behavior when no configuration exists in the database.
   - Verification that temperature and free-form model name are forwarded to `genai.Client`.

## Not Doing (and Why)
- **Full In-App Playground / Sandbox UI:** Avoid building custom preview/testing screens for the MVP; Django Admin handles authorization, validation, and editing out of the box.
- **Multi-Provider LLM Abstraction (OpenAI/Claude):** The app is standardized on Google GenAI (`google-genai` SDK); maintaining multi-vendor SDKs adds complexity without immediate business value.
- **Per-Item Prompt Customization at Intake:** Intake assistants need sub-45-second workflow velocity. Prompt governance belongs to managers at the catalog configuration level.

## Open Questions Resolved
- **Model Name Selection:** Resolved as **free-form text** with suggested defaults in help text, enabling immediate evaluation of new Gemini releases without code updates.
