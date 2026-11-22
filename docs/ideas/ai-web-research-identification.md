# AI Web Research & Grounded Product Identification

## Problem Statement
**How might we** help the Store Manager accurately identify obscure, white-label, or OEM liquidation pallet items (from AliExpress, Amazon, or manufacturer catalogs) and extract their real technical specifications and market pricing in `product_detail.html`—without slowing down standard 3-second AI generation for everyday items?

## Recommended Direction
Implement a **Two-Speed / On-Demand Web Research Mode (`🌐 Web Research`)** inside the Manager's Staging Workspace (`/products/<pk>/`) powered by **Gemini Multimodal Vision + Built-in Google Search Grounding** (`tools=[types.Tool(google_search=types.GoogleSearch())]`).

When the manager leaves the toggle off, `generate_product_listing()` runs the fast single-pass vision flow. When an item is unfamiliar or generic, the manager toggles on **`🌐 Web Research`** (and optionally types a model number, OEM code, or clue) before clicking **Generate with AI**. Gemini extracts visible model codes/labels from the photos, searches indexed AliExpress, Amazon, manufacturer pages, and European marketplaces, writes a spec-accurate listing, refreshes `estimated_retail_price` and `estimated_resale_price`, and persists a **Web Research Insights Card** (`Product.ai_research_data`) with the verified brand/model, technical specs, and clickable reference links.

## Key Assumptions to Validate
- [ ] **Visual/Textual Signal Sufficiency**: Photos, field notes, or an optional manager search hint contain enough signal (logo, packaging sticker, model/SKU code, or industrial design) for Gemini Vision to formulate a targeted web search query rather than a generic category query.
- [ ] **Model + Tool Compatibility**: Combining `tools=[types.Tool(google_search=types.GoogleSearch())]` with `response_mime_type="application/json"` works or self-heals gracefully across Gemini models (`generate_content_with_fallback()` retries with prompt-enforced JSON + Search Grounding and markdown-fence stripping if `400 INVALID_ARGUMENT` occurs).
- [ ] **Indexed Web Coverage**: Google Search Grounding chunks reliably surface AliExpress, Amazon, and manufacturer product pages without needing fragile direct HTML scrapers that hit anti-bot CAPTCHAs.

## MVP Scope
- **In Scope:**
  - On-demand `🌐 Web Research (AliExpress / Web)` toggle + optional `search_hint` input in `#aiCommandToolbar` on `inventory/templates/inventory/product_detail.html`.
  - Gemini Google Search Grounding integration in `inventory/services/compliance_service.py` and `inventory/services/ai_service.py` with self-healing JSON fallback and URL-validated (`http`/`https`) grounding source extraction.
  - Persistent `Product.ai_research_data` (`JSONField`) storing `used_web_search`, `search_hint`, `identified_brand`, `identified_model`, `technical_specs`, `search_queries`, `web_sources`, and `researched_at`, plus automatic refresh of `estimated_retail_price` and `estimated_resale_price`.
  - Responsive **Web Research Insights Card** (`#aiWebResearchCard`) on `product_detail.html` verified on desktop and OPPO A74 (`360×800` and `320×711`) viewports.
- **Not Doing (and Why):**
  - **No always-on web search during mobile `/intake/`:** Keeps mobile pallet scanning fast (`~3s`) and low-token for Sourcing Assistants.
  - **No direct AliExpress / Amazon HTML scraping or headless browser bots:** Direct scraping triggers anti-bot CAPTCHAs and fragile DOM breakage; Gemini Google Search Grounding queries Google's index cleanly with zero extra API keys.
  - **No automatic overwriting of an already-set `sale_price`:** Grounded retail/resale prices update only the advisory valuation benchmarks (`estimated_retail_price` / `estimated_resale_price`), leaving final pricing decisions with the Store Manager.

## Open Questions
- None — all scoping decisions confirmed by the user prior to implementation.
