# Unified Forgiving & Multi-Field Product Search

## Problem Statement
How might we make product search across both the internal Staging Dashboard (`/dashboard/`) and the Public Storefront (`/tienda/`) forgiving of human input (uppercase/lowercase Unicode, Spanish accents, word order) and comprehensive across every product attribute—using only zero-dependency SQLite and Django primitives?

## Recommended Direction
Upgrade `inventory/services/search_service.py` into a unified, scope-aware search engine (`scope="internal"` vs. `scope="public"`) powered by a deterministic SQLite `like` function override (`sqlite_unaccent_like`) and multi-token `AND` parsing.

Every SQLite connection registers a deterministic `like` function (2-arg and 3-arg) via Django's `connection_created` signal using `unicodedata.normalize("NFKD", ...)` and `.casefold()`. This makes standard Django `__icontains`, `__istartswith`, `__iendswith`, and `__iexact` lookups 100% accent-insensitive (`camara` ↔ `cámara`) and Unicode case-insensitive (`CÁMARA` ↔ `cámara`, `NIÑO` ↔ `niño`).

Queries are tokenized so every word or phrase must match at least one searchable field on the product (`AND` across tokens, `OR` across fields), regardless of word order (`"taladro bosch"` matches `"Taladro percutor profesional Bosch 18V"`). Reverse 1-to-N relationships (`ProductClarification`, `ProductListingLink`) use `Exists(...)` subqueries so multi-token queries never multiply rows or skew pagination counts.

On the internal `/dashboard/`, the search engine also parses power shorthands (`#42` / `Ref. #0042` / `ref:42`, `pale:5` / `pallet:5`, price bounds like `<20`, `>50`, or `15..50`) and applies the active search filter to the status tab badge counts (`All`, `Ready`, `Published`, `Price Pending`, `Doubts`, `Sold`, `Blocked`, `Trash`) with a cross-tab recovery banner when matches exist in other tabs.

## Key Assumptions to Validate
- [x] **Unicode folding completeness:** Verify via unit tests that `sqlite_unaccent_like` folds all Spanish/European characters (`Á/á`, `É/é`, `Í/í`, `Ó/ó`, `Ú/ú`, `Ü/ü`, `Ñ/ñ`) symmetrically in both column values and query strings.
- [x] **Zero data leakage on `/tienda/`:** Verify via security tests that searching internal-only strings (`raw_note`, `provider.name`, `pallet.name`, `sold_channel_notes`, `clarifications.answer`) on `/tienda/?q=` returns 0 results.
- [x] **No duplicate rows on 1-to-N joins:** Verify that products with multiple `ProductClarification` or `ProductListingLink` records appear exactly once in paginated results and tab counts.

## MVP Scope

### In Scope
1. **Unicode Case & Accent Folding (`sqlite_unaccent_like`):**
   - Register deterministic 2-arg and 3-arg SQLite `like` functions on `connection_created` in `inventory/apps.py`.
2. **Multi-Word Tokenization (`AND` logic):**
   - Split multi-word queries (`"taladro bosch 18v"`) so each token must match across the product's searchable fields in any order, while preserving single-token structure when 1 token is entered.
3. **Comprehensive Field Coverage (Scoped):**
   - **Internal (`scope="internal"`):** `id` (`#42`, `Ref. #0042`, or bare integer), `ai_title`, `raw_note`, `ai_description`, `category__name`, `category__name_en`, `provider__name`, `pallet__number`, `pallet__name`, `pallet__notes`, `sold_channel_notes`, `sold_marketplace__name`, `clarifications` (`question`, `answer` via `Exists`), `listing_links` (`site__name`, `url` via `Exists`), plus date patterns (`YYYY-MM-DD`, `DD/MM/YYYY`, `YYYY-MM`, `YYYY`).
   - **Public (`scope="public"`):** `id` (`#42`, `Ref. #0042`, or bare integer), `ai_title`, `ai_description`, `category__name`, `category__name_en` (strictly excluding internal notes, origins, costs, sale notes, and clarifications).
4. **Manager Smart Shorthands (Internal):**
   - `#<id>` or `ref:<id>` or `Ref. #<id>` for exact Product ID lookup.
   - `pale:<n>` / `pallet:<n>` for quick pallet number filtering from the search bar.
   - `<price`, `<=price`, `>price`, `>=price`, or `min..max` / `min-max€` (e.g., `<25`, `15..50`) for quick price filtering.
5. **Search-Scoped Dashboard Tab Counts & Cross-Tab Zero-Result Recovery:**
   - Apply `build_search_query(search_query)` to `counts_qs` in `dashboard_view` so all status tab counters reflect the active search query.
   - When the current tab has 0 matches for `?q=` but other tabs have `> 0` matches, display an inline recovery link to jump to matching tabs.

## Not Doing (and Why)
- **SQLite FTS5 Virtual Tables & Triggers** — Introduces raw SQL trigger maintenance outside Django's standard model lifecycle.
- **Denormalized `search_document` Columns** — Requires schema migrations, backfill scripts, and cross-model signal synchronization that can drift out of sync.
- **Gemini AI Embeddings / Semantic Vector Search** — Adds external API latency, token costs, and network dependency to a core navigation action that must run in `<10ms` offline/locally.
- **Typo/Fuzzy Levenshtein Matching in SQL** — Can produce noisy false positives on short model numbers/SKUs; multi-word + accent-insensitivity solves the primary human-input failures cleanly.
