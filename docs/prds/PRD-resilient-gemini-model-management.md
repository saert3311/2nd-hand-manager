# PRD: Resilient Gemini Model Discovery, Effort Control & Self-Healing Routing (Phase 53)

## 1. Objective & Background
Production experienced a `404 NOT_FOUND` failure on `/intake/identify/` (`models/gemini-flash-latest is not found for API version v1`) when `google-genai >= 3.0.0` switched the default Gemini Developer API endpoint from `v1beta` to `v1` (which neither exposes `-latest` aliases nor supports `response_mime_type="application/json"`). Furthermore, model names for Intake Vision, ClauseGuard Stage 2 Verification, and Policy Sync were hardcoded in Python, `AIPromptConfiguration.model_name` was seeded with the deprecating `gemini-2.5-flash` model as an unvalidated free-text field, and newer frontier models like `gemini-4-hydrogen` default to `high` thinking effort (`~908` billed thought tokens per simple JSON extraction unless constrained).

Phase 53 introduces a resilient, cost-controlled Gemini model management architecture across all 4 AI workflows.

## 2. Core Capabilities

### 2.1 Explicit `v1beta` Endpoint Pinning
- `GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1beta")` in `config/settings.py`.
- `get_gemini_http_options()` in `inventory/services/compliance_service.py` passes `types.HttpOptions(api_version="v1beta")` to every `genai.Client(...)` instantiation across `ai_service.py`, `compliance_service.py`, and `policy_sync_service.py`.

### 2.2 Unified Model Routing & Thinking Effort Control (`AIPromptConfiguration`)
- **Primary Model (`model_name`)**: Default upgraded from `"gemini-2.5-flash"` to `"gemini-4-hydrogen"`. Used for listing copywriting (`generate_product_listing`) and as the inherited default for all other AI tasks when their task-specific override is blank.
- **Optional Per-Task Model Overrides**:
  - `intake_model_name` (`CharField(max_length=64, blank=True, default="")`): Override for `/intake/identify/` (`identify_intake_product`). Blank = inherit `model_name`.
  - `compliance_model_name` (`CharField(max_length=64, blank=True, default="")`): Override for ClauseGuard Stage 2 (`verify_product_compliance_ai`). Blank = inherit `model_name`.
  - `policy_sync_model_name` (`CharField(max_length=64, blank=True, default="")`): Override for policy clause extraction (`sync_site_policy`). Blank = inherit `model_name`.
- **Thinking Effort Level (`thinking_level`)**:
  - `ThinkingLevel` (`TextChoices`):
    - `MINIMAL` (`"minimal"`): *Minimal / Near-Off (Fastest, Lowest Cost — auto-clamps to Low on Gemini 4 & 3.8)*
    - `LOW` (`"low"`, **Default**): *Low Effort — Fast & Cost-Efficient (Recommended)*
    - `MEDIUM` (`"medium"`): *Medium Effort — Balanced Reasoning*
    - `HIGH` (`"high"`): *High Effort — Deep Reasoning (Higher Token Cost)*
- **Model-Aware Thinking Clamping (`resolve_thinking_config(model_name, level)`)**:
  - Only `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, and `gemini-3-flash-preview` support `thinking_level="MINIMAL"`. For all other models (including `gemini-4-hydrogen`, `gemini-4-argon`, `gemini-4-carbon`, `gemini-3.8-flash`, `gemini-flash-latest`, and `gemini-2.5-*`), requesting `"minimal"` transparently clamps to `types.ThinkingConfig(thinking_level="LOW")` so the API never raises `400 INVALID_ARGUMENT`.
  - ClauseGuard Stage 2 pass/fail checks (`verify_product_compliance_ai`) always request `"minimal"` (clamped to `"LOW"` where unsupported) to avoid burning thought tokens on boolean classification.
- **Thought Token Telemetry**:
  - `_extract_token_count()` accounts for `thoughts_token_count` alongside prompt and candidate tokens when `total_token_count` is computed or reported.

### 2.3 Live Capability-Filtered Model Discovery in Manager Admin
- `fetch_available_gemini_models(force_refresh: bool = False) -> list[tuple[str, str]]`:
  - Calls `client.models.list()` on `v1beta`, caches results in Django cache (`gemini_available_models_v1`, 1-hour TTL), and always falls back to `STATIC_FALLBACK_MODELS` if `GEMINI_API_KEY` is missing or the network call fails.
  - Filters strictly for models where `"generateContent"` is in `supported_actions` and excludes incompatible/specialized model families (`-tts`, `-image`, `nano-banana`, `lyria`, `transcribe`, `live`, `robotics`, `computer-use`, `deep-research`, `antigravity`, `gemma`, `embedding`, `aqa`, `imagen`, `veo`, `learnlm`).
- `AIPromptConfigurationAdmin`:
  - Renders dynamic `<select>` dropdowns (`ModelChoiceWidget` / `AIPromptConfigurationAdminForm`) for `model_name`, `intake_model_name`, `compliance_model_name`, and `policy_sync_model_name` populated from `fetch_available_gemini_models()`, while preserving any custom model ID already saved on the instance.
  - Provides both a changelist Admin action and a one-click header button (`refresh-models/`) to force-refresh the cached model catalog from Google AI and display a localized confirmation banner.

### 2.4 Self-Healing Runtime Fallback Chain (`generate_content_with_fallback`)
- Centralizes all `client.models.generate_content(...)` invocations across `ai_service.py`, `compliance_service.py`, and `policy_sync_service.py`.
- Builds a deduplicated candidate chain starting with the resolved model followed by `FALLBACK_MODEL_CHAIN = ("gemini-4-hydrogen", "gemini-3.8-flash", "gemini-flash-latest")`.
- Re-computes `resolve_thinking_config(candidate_model, thinking_level)` on each attempt.
- Retries the next fallback model **only** when the exception is a model/parameter compatibility error (`404`, `NOT_FOUND`, `not found`, `400`, `INVALID_ARGUMENT`, `not supported`). Auth (`401`/`403`), quota (`429`/`RESOURCE_EXHAUSTED`), and network timeouts fail fast without multiplying requests.
