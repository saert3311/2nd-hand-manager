# PRD: Dashboard Pallet Filter & Visual Card Attribution (Phase 47)

## 1. Objective

### Problem Statement
In **2ndHand Staging Hub**, Phase 46 introduced liquidation pallet tracking, sticky intake session attribution, and dedicated pallet management on `/pallets/`. However, on the primary staging dashboard (`/dashboard/`):
1. **No Pallet Filter**: Store managers cannot filter the product grid by pallet to review all items originating from a specific shipment (e.g. "Review all items from Pallet #3").
2. **No Unassigned Filter**: Managers have no direct way to isolate standalone or walk-in items that have no pallet assigned (`pallet is None`).
3. **No Card Attribution Badge**: In the product grid, cards do not visually display which pallet an item belongs to, requiring managers to click through to each product's detail workspace to discover its origin pallet.

### Target Users & Goals
- **Store Managers (`managers` group / `is_staff` / `is_superuser`)**:
  - Filter the staging dashboard by any recorded liquidation pallet or by unassigned ("Standalone / No Pallet") items via a clean select dropdown in the Secondary Filter Bar beside the Platform and Search controls.
  - Dynamically scope dashboard status tab counts (`Ready`, `Published`, `Draft`, `Sold`, etc.) to the selected pallet, mirroring the platform filter behavior.
  - Instantly identify each item's pallet on the product cards in the grid via a tactile badge (`📦 Pallet #X`) in the photo overlay badge row.
  - Composable filtering: Combine pallet filtering with status tabs, search queries, channel filters, and marketplace platform filters.
- **Sourcing Assistants (`assistants` group / `is_assistant`)**:
  - View pallet badges on dashboard cards for physical workshop identification without leaking confidential commercial financial metrics (`purchase_price`, `estimated_value`).

---

## 2. Tech Stack & Architectural Invariants

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database:** SQLite with zero-downtime online backup
- **Frontend:** Django Templates + Tailwind CSS (OPPO A74 responsive baseline `320×711` & `360×800`)
- **Localization:** Bilingual (`es` / `en`) via Django `i18n` and `polib` (`manage.py compile_locales`)
- **Testing:** Automated unit, integration, permission, and Playwright responsive tests (`manage.py test`)
- **Zero N+1 Query Overhead:** Dashboard query already pre-fetches `select_related("pallet")`.
- **Financial Confidentiality:** Pallet choices and badges render solely numbers and dates, never purchase or estimated amounts.

---

## 3. Scope & Requirements

### 3.1 Backend Query & Filter Handling (`inventory/views.py`)
- Parse GET parameter `pallet = request.GET.get("pallet", "").strip()` in `dashboard_view`.
- Handle filter states:
  - `""` (default): All products.
  - `"none"`: `products = products.filter(pallet__isnull=True)`
  - `<id>` (numeric): `products = products.filter(pallet_id=pallet_filter)`
- Update status aggregation (`counts_qs`):
  - If `pallet_filter == "none"`: `counts_qs = counts_qs.filter(pallet__isnull=True)`
  - Else if `pallet_filter.isdigit()`: `counts_qs = counts_qs.filter(pallet_id=pallet_filter)`
- Populate template context:
  - `pallet_filter`: Active filter value string.
  - `available_pallets`: `Pallet.objects.annotate(products_count=Count("products", filter=Q(products__is_deleted=False))).order_by("-number")`
  - `unassigned_products_count`: `Product.objects.filter(is_deleted=False, pallet__isnull=True).count()`

### 3.2 Secondary Filter Bar UI (`inventory/templates/inventory/dashboard.html`)
- Position a Pallet Selector form directly adjacent to the Platform Selector form in the Secondary Filter Bar:
  - Options:
    1. `{% trans "All Pallets" %}` (`value=""`)
    2. `{% trans "— Standalone / No Pallet —" %} ({{ unassigned_products_count }})` (`value="none"`)
    3. `{% for p in available_pallets %}Pallet #{{ p.number }} ({{ p.received_date|date:"Y-m-d" }}) ({{ p.products_count }}){% endfor %}` (`value="{{ p.id }}"`)
  - Auto-submits on change (`onchange="this.form.submit()"`).
  - Preserves active `status`, `q`, `platform`, and `channel` via hidden inputs.
- Update Platform Selector form and Search form to preserve `pallet` via hidden inputs.
- Update "Clear All Filters" button condition:
  `{% if search_query or platform_filter or channel_filter or pallet_filter %}`
- Preserve `pallet` in status tab links and pagination links.

### 3.3 Product Card Visual Attribution (`inventory/templates/inventory/dashboard.html`)
- In the top badge overlay on the card photo:
  ```html
  {% if product.pallet %}
  <span class="text-xs font-bold px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-900 border border-indigo-200/90 shadow-xs flex items-center gap-1 backdrop-blur-xs">
    <span>📦</span> Pallet #{{ product.pallet.number }}
  </span>
  {% endif %}
  ```
- Standalone items (`product.pallet is None`) show no extra badge, avoiding visual noise.

### 3.4 Responsive Design & Accessibility
- Fluid wrapping in the Secondary Filter Bar: Search input, Platform dropdown, and Pallet dropdown wrap neatly across small viewports (`flex-col sm:flex-row flex-wrap`).
- Verified zero horizontal overflow on OPPO A74 mobile viewports (`360×800` & `320×711`).
- Accessible `aria-label="{% trans 'Filter by pallet' %}"` on select element.

---

## 4. Verification & Testing

1. **Unit & Integration Suite (`tests/test_pallet_tracking.py`)**:
   - Verify filtering by `all`, `none` (unassigned), and specific pallet ID.
   - Verify composability with `status`, `platform`, `channel`, and `q`.
   - Verify tab count scoping when a pallet filter is active.
   - Verify pallet badge presence on product card.
   - Verify no financial data exposure in HTML.
2. **Quality Gates**:
   - `ruff check .`
   - `python manage.py check`
   - `python manage.py compile_locales`
   - `python manage.py test tests.test_pallet_tracking`
   - Full test suite execution: `python manage.py test`
