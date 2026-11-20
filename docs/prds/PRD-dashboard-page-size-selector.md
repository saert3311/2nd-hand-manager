# PRD: Dashboard Page Size Selector (20 / 50 / 100) — Phase 57

## 1. Objective

### Problem Statement
The internal staging dashboard (`/dashboard/`) currently hardcodes `PAGE_SIZE = 20` in `inventory/views.py`. When store managers or sourcing assistants review large pallet batches, recent intake sessions, or broad search results (50–100+ items), they are forced to paginate 20 items at a time. Conversely, raising the page size to 50 or 100 exposes an existing N+1 query bottleneck (`Product.primary_image` firing a query twice per card and `product.images.count` firing another query per card — roughly ~300 extra SQL queries on a 100-item page) alongside eager loading of 100 card thumbnails.

### Target Users & Scope
- **Target Users:** Both **Store Managers** (`is_manager`) and **Sourcing Assistants** (`is_assistant`) accessing the internal staging dashboard (`/dashboard/`, `inventory:dashboard`).
- **In Scope:** Server-side whitelisted page-size selection (`20`, `50`, `100`), Django session memory, filter/search composability, an above-grid compact results summary & segmented pill selector (`#dashboardResultsBar` / `#perPageSelector`), zero-N+1 image prefetching, lazy below-the-fold thumbnail loading, bilingual ES/EN labels, and responsive OPPO A74 (`360×800` & `320×711`) layout support.
- **Out of Scope:** The public storefront (`/tienda/`, `storefront/views.py`, `PUBLIC_PAGE_SIZE = 20`) remains strictly fixed at 20 items per page and untouched.

---

## 2. Tech Stack & Architectural Invariants

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database:** SQLite (zero schema migrations required; uses Django session storage + ORM `Prefetch`)
- **Frontend & Styling:** Django Templates + Tailwind CSS (OPPO A74 responsive baseline: `360×800` standard & `320×711` zoomed/low-DPI, zero horizontal overflow `scrollWidth <= clientWidth`, WCAG 2.1 AA contrast `>= 4.5:1`, no sub-12px micro-fonts)
- **Internationalization:** Bilingual ES/EN via Django `i18n` (`{% trans %}`, `gettext`) and `polib` (`python manage.py compile_locales`)
- **Constant Query Scaling:** SQL query count must remain constant (`O(1)`) whether rendering 20, 50, or 100 products per page.

---

## 3. Commands

Always run project commands via the workspace virtual environment (`.venv\Scripts\...`):

```powershell
# Lint & style check (Ruff)
.venv\Scripts\ruff.exe check .

# Django system check
.venv\Scripts\python.exe manage.py check

# Compile bilingual translation catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# Run targeted pagination, search, and dashboard tests
.venv\Scripts\python.exe manage.py test tests.test_pagination_search tests.test_dashboard

# Run full automated test suite
.venv\Scripts\python.exe manage.py test

# Start local development server
.venv\Scripts\python.exe manage.py runserver
```

---

## 4. Project Structure (Files Affected)

| File | Role in Phase 57 |
|---|---|
| `inventory/views.py` | Define `ALLOWED_PAGE_SIZES = (20, 50, 100)`, `DASHBOARD_PER_PAGE_SESSION_KEY = "dashboard_per_page"`, and `_resolve_dashboard_page_size(request)`; update `dashboard_view` pagination, context (`per_page`, `allowed_page_sizes`, `default_page_size`, `per_page_base_query`, sanitized `query_string`), and ordered `Prefetch("images", queryset=ProductImage.objects.order_by("order", "id"))`. |
| `inventory/models.py` | Update `Product.primary_image` property to read from `self._prefetched_objects_cache["images"]` when prefetched instead of issuing an uncached `.order_by(...).first()` query. |
| `inventory/templates/inventory/dashboard.html` | Render `#dashboardResultsBar` directly above the product grid (when `paginator.count > 0`) with the results counter and `#perPageSelector` (`20 | 50 | 100`), propagate `per_page` across filter forms/tabs/links when non-default, and optimize card images (`{% with primary_img=product.primary_image %}`, `{{ product.images.all|length }}`, `loading="lazy"` for `forloop.counter > 4`, `decoding="async"`). |
| `locale/es/LC_MESSAGES/django.po` (+ `.mo`) | Add Spanish translations for `"Products per page"`, `"Per page:"`, and `"Show %(count)d products per page"`. |
| `locale/en/LC_MESSAGES/django.po` (+ `.mo`) | Sync and compile English message catalog entries. |
| `tests/test_pagination_search.py` | Add comprehensive unit, integration, session, role, query-count (`assertNumQueries`), and bilingual tests. |
| `tests/test_oppo_a74_responsive.py` / `tests/test_dashboard_responsive.py` | Verify zero horizontal overflow and visibility of `#dashboardResultsBar` / `#perPageSelector` on `360×800` and `320×711` viewports. |

---

## 5. Functional & Non-Functional Requirements

### 5.1 Server-Side Page Size Resolution & Session Persistence (`inventory/views.py`)
- **Whitelisted Values:**
  - `PAGE_SIZE = 20` (default)
  - `ALLOWED_PAGE_SIZES = (20, 50, 100)`
  - `DASHBOARD_PER_PAGE_SESSION_KEY = "dashboard_per_page"`
- **Resolution Precedence (`_resolve_dashboard_page_size(request) -> int`):**
  1. Check `request.GET.get("per_page", "").strip()`. If it parses cleanly as an integer in `ALLOWED_PAGE_SIZES`, select that size and persist it in `request.session[DASHBOARD_PER_PAGE_SESSION_KEY]` (only writing to the session if the stored value differs).
  2. If `?per_page` is absent, non-numeric, or outside `ALLOWED_PAGE_SIZES` (e.g. `abc`, `0`, `-5`, `999`, `10000`), ignore the invalid parameter without raising an error; read `request.session.get(DASHBOARD_PER_PAGE_SESSION_KEY)` and return it if in `ALLOWED_PAGE_SIZES`, otherwise fall back to `PAGE_SIZE` (`20`).
- **Explicit Reset to 20:**
  - The `20` pill in `#perPageSelector` links explicitly to `?per_page=20...` so clicking `20` overwrites a previously stored session preference of `50` or `100`.
- **Page Reset on Size Change:**
  - Pill links construct their URL from `per_page_base_query` (`request.GET.copy()` with both `page` and `per_page` removed), ensuring changing page size always navigates to page 1 while preserving `status`, `q`, `platform`, `pallet`, `provider`, `channel`, `sync`, and `compliance`.
- **Clean Query Strings & Shareable URLs:**
  - Pagination links use `query_string` built from `request.GET.copy()` with `page` stripped and `per_page` normalized (set to `str(per_page)` when `per_page != PAGE_SIZE`, or stripped when `per_page == PAGE_SIZE` or malformed).
  - Status tabs, secondary filter forms (`search`, `platform`, `pallet`, `provider`), tertiary sub-filter pills (`sync`, `channel`), and `policy alerts` / `cross-tab recovery` links preserve `per_page` via session and include `per_page={{ per_page }}` / `<input type="hidden" name="per_page" value="{{ per_page }}">` whenever `per_page != default_page_size`.
- **"Clear filters" Behavior:**
  - Clicking **Clear filters** resets active filter parameters (`q`, `platform`, `pallet`, `provider`, `channel`, `compliance`) while preserving the active `per_page` preference (since page size is a display density preference, not a catalog filter). Having a non-default `per_page` active alone does **not** display the **Clear filters** button.

### 5.2 UI Placement, Segmented Pill Control & Responsiveness (`dashboard.html`)
- **Above-Grid Compact Results Bar (`#dashboardResultsBar`):**
  - Rendered directly above the product catalog grid whenever `products` is non-empty (`paginator.count > 0`), remaining visible even when all matching items fit on a single page (e.g., 35 products with `50` per page). Hidden when `paginator.count == 0`.
  - Follows `plugin:demolab` (`gemini-frontend-design`) workspace craft: styled as a clean hairline-separated utility strip (`border-b border-slate-200/80 pb-3`) on the page canvas with zero nested card-in-card clutter, `tabular-nums` alignment on counts and size numerals, sentence-case UI labels, `text-sm` (`14px`, >= `13px`) above-the-fold typography, and responsive stacking (`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3`).
  - **Left side:** Localized results summary (`Showing {{ start }} to {{ end }} of {{ total }} products`), avoiding duplicate summary clutter when only one bar is visible.
  - **Right side:** Compact connected segmented pill control (`#perPageSelector`, `role="group"`, `aria-label="{% trans 'Products per page' %}"`) featuring the sentence-case label `{% trans "Per page:" %}` and three 1-tap `<a>` pill segments (`20`, `50`, `100`).
    - Active option receives high-contrast highlight (`bg-white text-emerald-800 shadow-xs ring-1 ring-emerald-200 font-bold`) and `aria-current="true"`.
    - Inactive options render cleanly (`text-slate-700 hover:text-slate-900 hover:bg-slate-200/60`) with accessible `aria-label` and explicit CSS transition properties (`transition-[background-color,color,box-shadow] duration-150 ease-out motion-reduce:transition-none`, never `transition-all`).
    - Each pill maintains comfortable touch geometry (`min-h-[36px] min-w-[42px]`), `text-sm` (`14px`) typography, and WCAG 2.1 AA contrast (`>= 4.5:1`).
- **Bottom Pagination Bar (`{% if page_obj.has_other_pages %}`):**
  - Remains below the product grid for `Previous`, elided page numbers, and `Next` navigation, preserving `query_string`.
- **OPPO A74 & Narrow Mobile Guardrails:**
  - Zero horizontal overflow (`document.documentElement.scrollWidth <= document.documentElement.clientWidth`) verified at `360×800` and `320×711` in both English and Spanish.

### 5.3 Performance Optimization for 100-Item Pages (`inventory/models.py`, `inventory/views.py`, `dashboard.html`)
- **Prefetch-Aware `Product.primary_image` (`inventory/models.py`):**
  - Check `self._prefetched_objects_cache` for `"images"` first and return the first cached item (`images_cache[0] if images_cache else None`), falling back to `self.images.order_by("order", "id").first()` only when `images` was not prefetched.
- **Ordered Image Prefetch (`inventory/views.py`):**
  - Prefetch `Prefetch("images", queryset=ProductImage.objects.order_by("order", "id"))` in `dashboard_view` so `images_cache[0]` matches `order_by("order", "id").first()` deterministically.
- **Template Query & Image Loading Hygiene (`dashboard.html`):**
  - Cache `{% with primary_img=product.primary_image %}` per card so `primary_image` is resolved once.
  - Replace `{{ product.images.count }}` with `{{ product.images.all|length }}` to use the prefetched list instead of issuing `COUNT(*)` per card.
  - Apply `{% if forloop.counter > 4 %}loading="lazy"{% endif %} decoding="async"` on dashboard card `<img>` tags to keep initial page paint fast and mobile memory usage controlled when displaying 50 or 100 cards.

### 5.4 Bilingual Localization (`es` / `en`)
Add and compile all new UI strings:
- `"Products per page"` → `"Productos por página"`
- `"Per page:"` → `"Por página:"`
- `"Show %(count)s products per page"` → `"Mostrar %(count)s productos por página"`

---

## 6. Code Style

Follow PEP 8, Ruff (`target-version = "py313"`, `line-length = 120`, rules `E, F, I, W`), and Python 3.13+ type annotations on view helpers:

```python
PAGE_SIZE = 20
ALLOWED_PAGE_SIZES: tuple[int, ...] = (20, 50, 100)
DASHBOARD_PER_PAGE_SESSION_KEY = "dashboard_per_page"


def _resolve_dashboard_page_size(request) -> int:
    """Resolve and persist a whitelisted dashboard page size from query params or session."""
    raw_per_page = request.GET.get("per_page", "").strip()
    if raw_per_page:
        try:
            requested = int(raw_per_page)
        except ValueError:
            requested = None
        if requested in ALLOWED_PAGE_SIZES:
            if request.session.get(DASHBOARD_PER_PAGE_SESSION_KEY) != requested:
                request.session[DASHBOARD_PER_PAGE_SESSION_KEY] = requested
            return requested

    saved = request.session.get(DASHBOARD_PER_PAGE_SESSION_KEY)
    if saved in ALLOWED_PAGE_SIZES:
        return saved
    return PAGE_SIZE
```

---

## 7. Testing Strategy

- **Framework & Location:** Django `TestCase` in `tests/test_pagination_search.py` and Playwright responsive checks in `tests/test_oppo_a74_responsive.py` / `tests/test_dashboard_responsive.py`.
- **Test Cases Required:**
  1. **Default 20/page preserved:** `/dashboard/` without params or session value renders 20 items per page.
  2. **20 / 50 / 100 switching:** With 105 products, `?per_page=50` renders 50 items across 3 pages and `?per_page=100` renders 100 items on page 1 and 5 on page 2.
  3. **Session persistence & reset to 20:** Visiting `?per_page=50` then visiting `/dashboard/` without `per_page` retains 50/page; visiting `?per_page=20` updates session back to 20/page.
  4. **Invalid `per_page` handling:** Non-numeric (`abc`), zero (`0`), negative (`-10`), and non-whitelisted (`999`) values fall back gracefully without 500 errors, do not overwrite valid session state, and never leak into pagination URLs.
  5. **Filter/search composability & page reset:** Changing page size preserves `status`, `q`, `platform`, `pallet`, `provider`, `channel`, `sync`, and `compliance`, resets pagination to page 1, and "Clear filters" preserves `per_page` without treating it as an active filter.
  6. **1-page visibility & 0-item hiding:** `#dashboardResultsBar` and `#perPageSelector` are rendered when 35 items fit on 1 page at `per_page=50`, and hidden when 0 items match.
  7. **Role access:** Both Manager and Assistant users can switch between 20, 50, and 100 items per page.
  8. **Constant query count (`assertNumQueries`):** Rendering 100 products with images executes the same number of SQL queries as rendering 20 products with images (zero N+1 growth).
  9. **Bilingual localization:** Spanish (`Accept-Language: es`) renders `"Por página:"` and `"Productos por página"`.
  10. **OPPO A74 responsive check:** Zero horizontal overflow (`scrollWidth <= clientWidth`) at `360×800` and `320×711` with `#dashboardResultsBar` visible.

---

## 8. Boundaries

- **Always:**
  - Strictly whitelist `(20, 50, 100)` server-side in `ALLOWED_PAGE_SIZES`.
  - Preserve all active dashboard filters and search queries across page-size switches.
  - Wrap every user-facing string in Django i18n and compile `.mo` catalogs with `manage.py compile_locales`.
  - Pass 100% of `ruff check .`, `manage.py check`, `manage.py compile_locales`, and `manage.py test`.
- **Ask First:**
  - Changing the public storefront (`/tienda/`) pagination size (`PUBLIC_PAGE_SIZE`).
  - Adding database models or user-profile schema migrations to store preferences across devices.
  - Adding page size options larger than `100` items per page.
  - Merging into `master` (explicit user approval mandatory per `AGENTS.md`).
- **Never:**
  - Pass unvalidated user-supplied `per_page` values directly into `Paginator(...)`.
  - Commit `.env`, secrets, or untracked browser verification screenshots.
  - Skip, delete, or relax existing tests to reach green.

---

## 9. Success Criteria

1. Default `/dashboard/` rendering without session or query overrides displays up to 20 products per page.
2. Users can switch cleanly between `20`, `50`, and `100` products per page via `#perPageSelector` inside `#dashboardResultsBar` above the product grid.
3. Selected page size persists via Django session across subsequent `/dashboard/` visits, and clicking `20` restores the 20-item default.
4. Invalid `?per_page=` query values never cause errors, never override valid preferences, and never propagate into links.
5. All active filters (`status`, `q`, `platform`, `pallet`, `provider`, `channel`, `sync`, `compliance`) remain intact when changing page size, page resets to 1, and "Clear filters" preserves the chosen page size.
6. `#dashboardResultsBar` stays visible even when the result set fits on 1 page (when `paginator.count > 0`) and hides cleanly on empty results (`paginator.count == 0`).
7. Rendering 100 products with attached `ProductImage` records performs constant `O(1)` SQL queries (zero N+1 queries) and applies `loading="lazy"` after the first 4 cards.
8. Zero horizontal overflow on OPPO A74 viewports (`360×800` and `320×711`) in both English and Spanish.
9. 100% of `ruff check .`, `manage.py check`, `manage.py compile_locales`, and `manage.py test` pass cleanly.

---

## 10. Open Questions

- **Resolved Design Decisions (Confirmed by User):**
  1. **Placement:** Compact results bar above the product grid (`#dashboardResultsBar`, visible whenever ≥1 product matches), keeping Previous / Elided Page Numbers / Next in the bottom pagination bar (`has_other_pages`).
  2. **Persistence:** URL query param (`?per_page=`) combined with Django session memory (`request.session["dashboard_per_page"]`).
  3. **Control Style:** Compact 1-tap segmented pill buttons (`20 | 50 | 100`).
- **Open Questions:** None remaining — ready for spec approval before proceeding to Phase 2 (Plan & Task Breakdown).
