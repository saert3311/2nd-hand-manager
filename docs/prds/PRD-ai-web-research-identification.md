# PRD: On-Demand AI Web Research & Grounded Product Identification — Phase 59

## 1. Objective

### Problem Statement
Items sourced from liquidation pallets (Amazon/AliExpress customer returns, OEM/white-label electronics, unbranded home appliances, or boxed items identified solely by an obscure model number) are often classified too generically by static LLM weights alone (e.g., *"Mini proyector LED"* instead of *"Magcubic HY300 Android 11 4K 200 ANSI Smart Projector"*). Without verified brand/model details and concrete specifications, listings convert worse and require the Store Manager to manually search AliExpress, Amazon, or manufacturer pages in separate browser tabs.

### Target Users & Scope
- **Primary User:** **Store Manager (`is_manager`)** working inside the Product Staging Workspace (`/products/<pk>/`).
- **In Scope:**
  - **Two-Speed Workflow in `#aiCommandToolbar` (`product_detail.html`)**:
    - Default **Fast Vision Mode** (`use_web_search` unchecked): preserves fast, single-pass copywriting generation (`~2–4s`).
    - On-demand **Web Research Mode** (`🌐 Web Research (AliExpress / Web)` checkbox checked, plus optional `search_hint` text input for model codes/clues): activates **Gemini Built-in Google Search Grounding** (`tools=[types.Tool(google_search=types.GoogleSearch())]`).
  - **Grounded Product Extraction & Listing Enrichment (`ai_service.py` & `compliance_service.py`)**:
    - OCR inspection of visible box labels, stickers, model numbers, barcodes/EANs, and ports across up to 5 attached product photos.
    - Live Google Search lookup across indexed AliExpress, Amazon, manufacturer pages, and European marketplaces.
    - Structured extraction of `identified_brand`, `identified_model`, up to 6 verified `technical_specs`, grounded `estimated_retail_price` (MSRP in €) and `estimated_resale_price` (€), and clickable `web_sources`.
    - Self-healing fallback when a Gemini model rejects combining `tools=[google_search]` with `response_mime_type="application/json"`.
  - **Persistent Research Storage (`Product.ai_research_data`)**:
    - Stores `used_web_search`, `search_hint`, `identified_brand`, `identified_model`, `technical_specs`, `search_queries`, `web_sources`, and `researched_at` in a non-destructive `JSONField` on `Product` (exposed read-only in `ProductAdmin`).
    - Refreshes `Product.estimated_retail_price` and `Product.estimated_resale_price` benchmarks when returned, **never** overwriting `Product.sale_price`.
  - **Web Research Insights Card (`#aiWebResearchCard`)**:
    - Renders persisted brand/model pills, technical specification tags, verified clickable source links (`target="_blank" rel="noopener noreferrer"`), and collapsible search query chips in Tab 1 (`Listing`) of `/products/<pk>/`.
- **Out of Scope:**
  - Running live web search during mobile `/intake/` (assistants keep fast mobile pre-flight scanning).
  - Direct HTML scraping of AliExpress/Amazon pages or custom third-party SERP API keys.
  - Auto-overwriting an existing `sale_price` set by the manager or assistant.
  - Exposing `ai_research_data` or internal research clues on the public `storefront` (strict internal firewall preserved).

---

## 2. Tech Stack & Architectural Invariants

- **Language & Framework:** Python 3.13+, Django 5.2 LTS (`inventory` app)
- **AI SDK:** `google-genai` (`types.Tool(google_search=types.GoogleSearch())` on `v1beta`)
- **Security & Input Sanitization:**
  - `search_hint` capped at 200 characters and enclosed in `<untrusted_search_hint>...</untrusted_search_hint>` with explicit prompt-injection guard directives.
  - Every extracted reference URL (from `grounding_metadata.grounding_chunks` or `reference_urls`) validated strictly via `HTTP_URL_VALIDATOR` (`schemes=["http", "https"]`), blocking `javascript:`, `data:`, and malformed URIs.
  - State-mutating `generate_ai_view` remains `@manager_required` and POST-only; Sourcing Assistants cannot trigger AI generation or view hidden hint/trigger controls.
- **Mobile & Low-DPI Compliance (OPPO A74 `360×800` & `320×711`):**
  - `#id_search_hint` uses `text-base sm:text-sm` (`>= 16px` on mobile) to prevent iOS Safari auto-zooming.
  - `#aiCommandToolbar`, `#aiForm`, and `#aiWebResearchCard` use `min-w-0`, `flex-wrap`, `break-words`, `>= 12px` typography, and WCAG 2.1 AA contrast (`>= 4.5:1`) with zero horizontal overflow (`scrollWidth <= clientWidth`).

---

## 3. Data Model (`Product.ai_research_data`)

`Product.ai_research_data` (`JSONField(default=dict, blank=True)`) stores:

```json
{
  "used_web_search": true,
  "search_hint": "HY300",
  "identified_brand": "Magcubic",
  "identified_model": "HY300",
  "technical_specs": [
    "Android 11 OS",
    "200 ANSI Lumens",
    "WiFi 6 & Bluetooth 5.0",
    "180° Rotatable Stand"
  ],
  "search_queries": ["Magcubic HY300 projector specs AliExpress"],
  "web_sources": [
    {
      "title": "Magcubic HY300 Pro Projector",
      "url": "https://www.aliexpress.com/item/1005006.html",
      "domain": "aliexpress.com"
    }
  ],
  "researched_at": "2026-11-22T12:00:00+00:00"
}
```

---

## 4. Acceptance Criteria & Verification

1. **Standard Mode Unchanged**: Generating with `use_web_search` unchecked sends no `tools` config to Gemini and leaves existing tests and latency unaffected.
2. **Grounded Research Flow**: Checking `#id_use_web_search` (and optionally supplying `#id_search_hint`) sends `tools=[types.Tool(google_search=types.GoogleSearch())]`, updates `ai_title`, `ai_description`, `estimated_retail_price`, `estimated_resale_price`, and `ai_research_data`, while preserving `sale_price`.
3. **Self-Healing Resilience**: Rejections of `tools` + `response_mime_type="application/json"` (`400 INVALID_ARGUMENT`) automatically recover via prompt-enforced JSON + Search Grounding and markdown fence stripping, without masking `429` or `401`/`403` errors.
4. **Permissions & URL Safety**: Assistants remain blocked from `/products/<pk>/generate-ai/`; unsafe `javascript:`/`data:` URLs are stripped from `web_sources`.
5. **Bilingual & Quality Gate**: Full ES/EN translations compiled via `compile_locales`; `manage.py check`, `ruff check .`, and 100% of `manage.py test` pass with zero errors or warnings.
