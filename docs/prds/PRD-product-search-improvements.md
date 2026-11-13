# PRD: Unified Forgiving & Multi-Field Product Search (Phase 52)

## 1. Overview & Problem Statement
Currently, product search across both the internal Staging Dashboard (`/dashboard/?q=`) and the Public Storefront (`/tienda/?q=`) relies on single-substring `icontains` queries over a narrow subset of fields. Because SQLite's built-in `LIKE` operator only case-folds ASCII characters (`A–Z`) and does not fold diacritics:
1. **Spanish Accents & Non-ASCII Case Variants Fail:** Searching `"camara"`, `"CÁMARA"`, or `"NIÑO"` fails to match `"Cámara"`, `"cámara"`, or `"niño"`.
2. **Multi-Word Queries Are Brittle:** Searching `"taladro bosch"` fails when words are non-adjacent or reordered (e.g., `"Taladro percutor profesional Bosch 18V"`).
3. **Critical Catalog Attributes Are Unsearchable:** On `/dashboard/`, managers cannot search by Product `#ID` / `Ref. #0042` (and 4-digit IDs like `2025` are only treated as calendar years), Category name (`ES`/`EN`), Pallet number/name/notes, Sale/Ticket reference notes (`sold_channel_notes`), Clarification Q&A (`❓ Dudas` where measurements and serials live), or Marketplace site names/URLs.
4. **Dashboard Tab Counters Ignore Active Searches:** Status tab badges (`All`, `Ready to Publish`, `Published`, `Price Pending`, `Doubts`, `Sold`, `Blocked`, `Trash`) do not apply `search_query`, leaving managers blind to which status tab contains their search matches.

## 2. Goals & Success Criteria
1. **100% Case & Accent Forgiveness in SQLite:** Any combination of uppercase/lowercase ASCII or Unicode characters and accented/unaccented Spanish letters (`á/é/í/ó/ú/ü/ñ` ↔ `a/e/i/o/u/u/n`, `Á/É/Í/Ó/Ú/Ü/Ñ`) matches symmetrically across both `/dashboard/` and `/tienda/`.
2. **Multi-Token `AND` Matching:** Multi-word search queries require every token to match at least one searchable field on the product in any word order, while quoted phrases (`"..."`) match contiguously.
3. **Comprehensive, Scope-Isolated Field Coverage:**
   - **Internal (`scope="internal"`):** Searches `id` (`#42`, `Ref. #0042`, `ref:42`, or integer), `ai_title`, `raw_note`, `ai_description`, `category__name`, `category__name_en`, `provider__name`, `pallet__number`, `pallet__name`, `pallet__notes`, `sold_channel_notes`, `sold_marketplace__name`, `clarifications` (`question` & `answer` via `Exists`), `listing_links` (`site__name` & `url` via `Exists`), plus date patterns (`YYYY-MM-DD`, `DD/MM/YYYY`, `YYYY-MM`, `YYYY`).
   - **Public (`scope="public"`):** Strictly searches only `id` (`#42`, `Ref. #0042`, `ref:42`, or integer), `ai_title`, `ai_description`, `category__name`, and `category__name_en`. Zero leakage of `raw_note`, `provider`, `pallet`, `acquisition_cost`, `sold_channel_notes`, or `clarifications`.
4. **Manager Smart Shorthands:** Support `#<id>` / `ref:<id>`, `pale:<n>` / `pallet:<n>`, and price range operators (`<20`, `<=20`, `>50`, `>=50`, `15..50`) directly inside `/dashboard/?q=`.
5. **Search-Scoped Dashboard Tab Counts & Cross-Tab Recovery:** Scope `counts_qs` in `dashboard_view` to `search_query` and show one-click recovery pills in the empty state when results exist in other tabs (e.g., `Sold` or `Trash`).

## 3. Technical Architecture

### 3.1 SQLite Unicode Case & Diacritic Folding (`inventory/services/search_service.py` & `inventory/apps.py`)
- Implement `fold_search_text(text: str) -> str` using `unicodedata.normalize("NFKD", text.casefold())` with combining characters stripped (`not unicodedata.combining(c)`).
- Implement deterministic `sqlite_unaccent_like(pattern, value, escape=None) -> bool` with:
  - Fast path for standard `%substring%` patterns without wildcards inside the substring (`fold_search_text(inner) in fold_search_text(value)`).
  - Cached compiled regex path (`@lru_cache(maxsize=512)`) for patterns containing `_`, internal `%`, or escape sequences.
- Register `conn.create_function("like", 2, sqlite_unaccent_like, deterministic=True)` and `conn.create_function("like", 3, sqlite_unaccent_like, deterministic=True)` on every SQLite connection in `inventory/apps.py` via `connection_created`.

### 3.2 Unified `build_search_query(query_str: str, scope: str = "internal") -> Q`
- **Tokenization:** Extract quoted phrases (`"..."`) and whitespace-delimited tokens.
- **Special Token Parsing:**
  - **Exact Reference / ID (`#42`, `ref:42`, `ref.#0042`, `ref #42`):** Matches `Q(pk=42)`.
  - **Pallet Shorthand (`pale:5`, `palet:5`, `pallet:5`, `pale#5`, `pallet#5` — internal only):** Matches `Q(pallet__number=5)`.
  - **Price Shorthand (`<20`, `<=20`, `>50`, `>=50`, `10..50` — internal & public):** Filters `sale_price` accordingly.
  - **Date Patterns (`YYYY-MM-DD`, `DD/MM/YYYY`, `YYYY-MM`, `YYYY` — internal only):** Matches `created_at` or `sold_at` in `OR` with text/ID matches for that token.
  - **Bare Numbers (`42`, `2026`):** Matches `Q(pk=int(token))` (and `Q(pallet__number=int(token))` in internal scope) in `OR` with text/date matches.
- **Reverse 1-to-N Subqueries (Internal Scope):**
  - Use `Exists(ProductClarification.objects.filter(product=OuterRef("pk")).filter(Q(question__icontains=token) | Q(answer__icontains=token)))` and `Exists(ProductListingLink.objects.filter(product=OuterRef("pk"), is_active=True).filter(Q(site__name__icontains=token) | Q(url__icontains=token)))` so multi-word queries never duplicate rows.

### 3.3 Dashboard & Storefront Integration (`inventory/views.py`, `storefront/views.py`, `dashboard.html`)
- In `inventory/views.py` (`dashboard_view`):
  - Apply `search_q = build_search_query(search_query, scope="internal")` to both `products` and `counts_qs`.
  - When `products` is empty (`paginator.count == 0`) and `search_query` is non-empty, compute `search_other_tabs` (list of other tabs with `count > 0`, e.g., `All`, `Ready to Publish`, `Published`, `Price Pending`, `Doubts`, `Sold`, `Blocked`, `Trash` if manager) so `dashboard.html` renders clickable cross-tab recovery pills.
- In `storefront/views.py` (`catalog_view`):
  - Replace inline `icontains` filter with `qs = qs.filter(build_search_query(search_query, scope="public"))`.
- Preserve OPPO A74 (`360×800` and `320×711`) responsive layout rules (`flex-wrap`, `min-w-0`, `>= 16px` mobile inputs, zero horizontal overflow).
