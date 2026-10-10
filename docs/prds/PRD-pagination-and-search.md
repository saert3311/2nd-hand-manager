# Product Requirements Document (PRD): Catalog Pagination & Multi-Field Search

## 1. Executive Summary
Enhance the inventory catalog dashboard (`/dashboard/`) with robust server-side pagination (maximum 20 products per page) and comprehensive multi-field search across product title, description, raw intake notes, and creation/sale dates. This ensures optimal page load performance, predictable layout rendering as the inventory grows, and effortless item discovery for store managers and listers.

---

## 2. Problem Statement
As the product catalog expands beyond initial testing to dozens or hundreds of secondhand items:
1. **Unbounded Queries:** Loading all items and their prefetched image sets in a single HTTP response degrades database efficiency, increases memory consumption, and increases initial page render latency (LCP).
2. **Limited Search Capabilities:** The existing search only checks text containment on `ai_title`, `raw_note`, and `ai_description`. Managers frequently need to locate items cataloged on a specific sourcing day or marked sold on a specific date (e.g., `"2026-10-10"`, `"10/10/2026"`), which currently returns zero results.
3. **Navigation Friction:** Without pagination controls, users cannot link to or share specific result subsets or review archived inventory in bite-sized batches.

---

## 3. User Personas & Scenarios

### Persona: Manager / Lister (User B)
- **Scenario 1 (Browsing large catalog):** Sourcing assistants catalog 50+ items over a weekend. The manager opens the dashboard. The interface renders the first 20 items quickly, showing clear pagination ("Showing 1 to 20 of 55 products", "Page 1 of 3"). The manager clicks "Next" or page "2" without losing the active filter (`status=active`).
- **Scenario 2 (Date-based search):** The manager wants to find items sourced during yesterday's sourcing run (e.g., `2026-10-09`). Typing `2026-10-09` into the search box returns all items cataloged on that date.
- **Scenario 3 (Title & Description search):** Typing "Carhartt jacket" finds products with matching AI title, generated description, or raw field notes.
- **Scenario 4 (Combined search & pagination):** Searching for "jacket" returns 25 results. Page 1 displays 20 items, and page 2 displays the remaining 5 items while preserving `?q=jacket` in the navigation links.

---

## 4. Scope & Functional Requirements

### 4.1 Server-Side Pagination
- **Target Views:** Primary catalog dashboard (`/dashboard/`).
- **Items Per Page:** Default of **20 items per page** (`PAGE_SIZE = 20`) via Django's built-in `django.core.paginator.Paginator`.
- **Page Validation:**
  - If `page` parameter is not an integer (e.g. `?page=abc`), cleanly serve the first page.
  - If `page` parameter exceeds available pages (e.g. `?page=9999`), cleanly serve the last page (using `Paginator.get_page(page_number)`).
- **Pagination Navigation Component:**
  - "Showing X to Y of Z products" summary counter.
  - Previous and Next buttons (disabled with accessible visual styles when at boundaries).
  - Elided page numbering (e.g. `1 ... 4 5 6 ... 12`) using `Paginator.get_elided_page_range()`.
  - Full preservation of query parameters: clicking page numbers or next/previous preserves existing `status` and `q` parameters in the URL (`?status=sold&q=vintage&page=2`).
  - Mobile responsive: Compact layout on mobile screens (`< sm`), full elided range on tablet/desktop.

### 4.2 Multi-Field Search (Title, Description, Date)
- **Unified Search Bar:**
  The top search input will match across three primary dimensions:
  1. **Title:**
     - `ai_title__icontains=search_query`
     - Fallback matching on intake raw notes when `ai_title` is not yet generated.
  2. **Description:**
     - `ai_description__icontains=search_query`
     - `raw_note__icontains=search_query`
  3. **Date (Intelligent Date Parser):**
     - When the search term matches common date formats:
       - ISO format: `YYYY-MM-DD` (e.g. `2026-10-10`)
       - European slash/hyphen: `DD/MM/YYYY`, `DD-MM-YYYY` (e.g. `10/10/2026`)
       - US slash/hyphen: `MM/DD/YYYY`, `MM-DD-YYYY`
       - Year-Month: `YYYY-MM` (e.g. `2026-10`)
       - 4-digit Year: `YYYY` (e.g. `2026`)
     - Matches `created_at__date` (intake date) OR `sold_at__date` (date sold).
     - Combined with `Q` objects so text searches and date searches work seamlessly through the same search box.
- **Search Feedback:**
  - Clear search button (`×`) to reset the search while retaining the current `status` filter.
  - Active search term display in empty state message with "clear search" prompt.

### 4.3 Multi-Language (i18n) Localization
- All pagination and search terms fully localized in Spanish (`es`) and English (`en`):
  - "Showing %(start)d to %(end)d of %(total)d products" -> "Mostrando %(start)d a %(end)d de %(total)d productos"
  - "Previous" -> "Anterior"
  - "Next" -> "Siguiente"
  - "Page %(current)d of %(total)d" -> "Página %(current)d de %(total)d"
  - "Search title, description, or date (YYYY-MM-DD)..." -> "Buscar por título, descripción o fecha (AAAA-MM-DD)..."
- `.po` catalogs updated and compiled to `.mo` via `python manage.py compile_locales`.

---

## 5. Non-Functional Requirements
- **Performance:** Database query must use `LIMIT 20 OFFSET X` with `prefetch_related("images")` so only 20 records and their associated images are loaded per request.
- **Security:** Search query sanitized, no SQL injection (Django ORM parameterized `Q` queries only), URL parameter escaping in templates via `|urlencode`.
- **Accessibility:** Accessible ARIA attributes (`aria-label="Pagination"`, `aria-current="page"`, keyboard tab order).

---

## 6. Success Criteria
1. When more than 20 items exist in the catalog, `/dashboard/` renders exactly 20 items on page 1, with a pagination toolbar.
2. Navigating to page 2 displays items 21 through 40 while retaining active status filters and search terms.
3. Entering a date query (e.g., `2026-10-10`) correctly filters items created or sold on that date.
4. Entering a text query filters items matching title, generated description, or raw field note.
5. All 70+ existing automated tests remain green, and new comprehensive unit tests for pagination and search pass with 100% success.
6. Multi-language toggle switches pagination and search labels between Spanish and English cleanly.
