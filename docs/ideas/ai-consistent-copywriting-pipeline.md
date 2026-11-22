# AI Consistent Copywriting & Research-Then-Write Pipeline

## Problem Statement
**How might we** guarantee that every AI-generated product listing in `/products/<pk>/` strictly follows the Store Manager's `AIPromptConfiguration` prompt template, section order, and tone—and produces repeatable results across re-runs—whether generated in Fast Mode or with live Web Research?

## Recommended Direction
Adopt a **Research-Then-Write Two-Stage Pipeline** (Direction B) with **native system-role enforcement and Run-1/Run-2 input stability** across `inventory/services/ai_service.py` and `inventory/services/compliance_service.py`:

1. **Pass 1 — Fact Researcher (runs only when `use_web_search=True`):**
   Calls Gemini Vision + Google Search Grounding with a facts-only schema (`WebResearchFactsSchema`: `identified_brand`, `identified_model`, `technical_specs`, `estimated_retail_price`, `estimated_resale_price`, `reference_urls`). Because Pass 1 writes zero listing copy and runs zero ClauseGuard checks, web search noise can never hijack copywriting rules. If Google Search is unavailable, Pass 1 signals `web_search_fallback=True` and hands off smoothly to Pass 2.
2. **Pass 2 — Strict Copywriter (always runs, identical path for Fast Mode & Web Research Mode):**
   - Sends `AIPromptConfiguration.system_instruction` through Gemini's native `config.system_instruction` channel instead of burying it inside the user prompt `contents[0]`.
   - Passes a deterministic per-product `seed` (with `400` self-healing if a fallback model rejects `seed`) and lowers default fallback temperature to `0.1` (while respecting the Admin-configured `temperature` and guiding `0.0–0.1` in Admin help text).
   - Eliminates the **Run-2 ClauseGuard prompt drift** by computing Stage 1 top-3 clauses strictly from immutable source facts (`raw_note` + resolved `clarifications`, ignoring prior `ai_title`/`ai_description`), so Run 1 and Run 2 receive identical prompts.
   - Feeds verified product facts—either freshly returned by Pass 1 or persisted in `product.ai_research_data`—as a neutral `<verified_product_facts>` data block (zero competing style directives), and keeps `ProductListingSchema` descriptions style-neutral so `system_instruction` is the sole authority on formatting, emojis, tone, and length.

## Key Assumptions to Validate
- [ ] **Admin Prompt & Temperature Alignment:** Active `AIPromptConfiguration` uses low `temperature` (`0.0`–`0.1`) and non-contradictory rules — validated by running generation twice on the same product and inspecting prompt invariance.
- [ ] **Gemini API Compatibility for `system_instruction` & `seed`:** Models on `v1beta` accept `config.system_instruction` and `config.seed` — protected by automatic `seed`-strip self-healing in `generate_content_with_fallback()`.
- [ ] **Acceptable Two-Pass Latency for Opt-In Web Research:** Adding ~2–4s only when `use_web_search=True` (while Fast Mode stays 1 fast call reusing locked `ai_research_data`) is a worthwhile trade-off for strict template compliance.

## MVP Scope
- **In Scope:**
  - `generate_content_with_fallback()` support for native `system_instruction` and `seed` (with `400` self-healing on unsupported `seed`).
  - Split `WebResearchFactsSchema` (Pass 1) from lean, style-neutral `ProductListingSchema` (Pass 2).
  - Decouple Pass 2 Stage 1 ClauseGuard prompt input from prior `ai_title`/`ai_description` so Run 1 and Run 2 prompts are identical.
  - Reuse persisted `product.ai_research_data` inside `<verified_product_facts>` during Fast Mode regenerations.
  - Admin `temperature` help text hint (`0.0–0.1`) with zero database migrations; unit/integration tests covering determinism, `seed` fallback, Run-1/Run-2 invariance, and two-stage web research.
- **Not Doing (and Why):**
  - **No new DB columns (`few_shot_example` / `fixed_footer`) yet** — Zero-migration implementation keeps rollouts instant; golden examples and footers can already live in `AIPromptConfiguration.system_instruction`.
  - **No silent overwriting of existing Admin `temperature` rows** — Preserves manager-tuned configurations while advising `0.0–0.1` in Admin UI.
  - **No changes to mobile `/intake/identify/`** — Keeps mobile pallet scanning fast and decoupled from staging copywriting templates.
