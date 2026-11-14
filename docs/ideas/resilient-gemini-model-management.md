# Resilient Gemini Model Discovery, Effort Control & Self-Healing Routing

## Problem Statement
How might we let Store Managers dynamically discover and select the best available Gemini models (such as `gemini-4-hydrogen`, `gemini-3.8-flash`, or `gemini-3.5-flash-lite`) across all AI workflows while preventing both SDK/model 404/400 outages and excessive thinking-token costs?

## Recommended Direction
Extend `AIPromptConfiguration` and `inventory/services/compliance_service.py` with four interlocking capabilities:

1. **Unified Model Selector (`gemini-4-hydrogen` default) + Optional Per-Task Overrides (`AIPromptConfiguration`)**:
   - Upgrade `AIPromptConfiguration.model_name` default from `gemini-2.5-flash` to `gemini-4-hydrogen` (serving as the primary model and default for all tasks).
   - Add optional per-task override fields on `AIPromptConfiguration`: `intake_model_name`, `compliance_model_name`, and `policy_sync_model_name` (blank = inherit the primary `model_name`).
2. **Thinking Effort Control (`thinking_level` default `"low"`) + Model-Aware Clamping (`resolve_thinking_config`)**:
   - Add `thinking_level` (`minimal`, `low` [default], `medium`, `high`) to `AIPromptConfiguration`.
   - `gemini-4-hydrogen` defaults to `high` thinking in the upstream API (`908` thought tokens / `6.7s` on a 1-line intake note vs `343` thought tokens / `3.8s` at `low`). Setting the default to `low` cuts thinking token spend by >60% and nearly halves latency.
   - Implement `resolve_thinking_config(model_name, requested_level)`: automatically clamps `"minimal"` to `"LOW"` on models that do not support `"minimal"` (`gemini-4-*`, `gemini-3.8-flash`, `gemini-2.5-*`) so the API never raises `400 INVALID_ARGUMENT: Thinking level MINIMAL is not supported for this model`.
   - Force `"minimal"` (auto-clamped to `"low"` where unsupported) on ClauseGuard Stage 2 boolean pass/fail checks (`verify_product_compliance_ai`).
3. **Live Capability-Filtered Model Catalog in Django Admin**:
   - Implement `fetch_available_gemini_models(force_refresh=False)` in `inventory/services/compliance_service.py` (cached for 1 hour in Django cache with a static curated fallback list when offline or unconfigured).
   - Queries `client.models.list()` on `v1beta`, retains models supporting `generateContent`, and filters out non-JSON/specialized endpoints (`-tts`, `-image`, `nano-banana`, `lyria`, `transcribe`, `live`, `robotics`, `computer-use`, `deep-research`, `antigravity`, `gemma`).
   - Renders dynamic `<select>` dropdowns in `AIPromptConfigurationAdmin` plus an Admin action and top-bar button (`🔄 Refresh Gemini Models from API`) to force-refresh the live model catalog.
4. **Self-Healing Runtime Fallback Chain (`generate_content_with_fallback`)**:
   - Pin `v1beta` via `get_gemini_http_options()`.
   - Route all 4 Gemini call sites (`generate_product_listing`, `identify_intake_product`, `verify_product_compliance_ai`, and `_extract_clauses_with_gemini`) through `generate_content_with_fallback()`.
   - If the configured model fails with `404 NOT_FOUND` or `400 INVALID_ARGUMENT`, automatically retry down the deduplicated fallback chain (`[configured_model, "gemini-4-hydrogen", "gemini-3.8-flash", "gemini-flash-latest"]`) with model-clamped `ThinkingConfig` and log a warning.

## Key Assumptions Validated
- [x] `gemini-4-hydrogen`, `gemini-3.8-flash`, `gemini-3.5-flash-lite`, and `gemini-flash-latest` support `response_mime_type="application/json"` + Pydantic `response_schema` on `v1beta`.
- [x] `gemini-4-hydrogen` with `thinking_level="LOW"` reduces latency from `6.72s` to `3.87s` and reduces thought tokens by 62% (`908` → `343`), while `gemini-3.8-flash` with `thinking_level="LOW"` uses `0` thought tokens (`4.13s`).
- [x] Capability filtering on `client.models.list()` cleanly removes TTS/Image/Audio/Live models while retaining all multimodal text/JSON Gemini models.
- [x] Fallback retry triggers strictly on `404`/`400` model/parameter errors and does not multiply `429` quota or `401`/`403` auth errors.

## MVP Scope
- Pin `v1beta` via `get_gemini_http_options()`.
- Add `DEFAULT_MODEL_NAME = "gemini-4-hydrogen"`, ` DEFAULT_THINKING_LEVEL = "low"`, and `FALLBACK_MODEL_CHAIN = ("gemini-4-hydrogen", "gemini-3.8-flash", "gemini-flash-latest")`.
- Add `thinking_level`, `intake_model_name`, `compliance_model_name`, and `policy_sync_model_name` to `AIPromptConfiguration` + migration `0030` updating legacy unmodified `gemini-2.5-flash` defaults to `gemini-4-hydrogen`.
- Implement `fetch_available_gemini_models()`, `resolve_thinking_config()`, `resolve_task_model_and_thinking()`, and `generate_content_with_fallback()`.
- Upgrade `AIPromptConfigurationAdmin` with dynamic model `<select>` widgets, `thinking_level` selector, and live model refresh action/endpoint.

## Not Doing (and Why)
- **Not building a separate non-Admin settings UI** — Prompt and model configuration is a manager-only operation already housed in `AIPromptConfigurationAdmin`.
- **Not retrying on 429 Quota Exceeded or 5xx network timeouts across fallback models** — Retrying 3 models during a network outage or project-wide rate limit triples latency on mobile `/intake/`.
- **Not persisting raw `ListModels` entries in SQLite** — Caching in Django cache with a static fallback avoids stale DB rows and migrations when Google releases new models.
