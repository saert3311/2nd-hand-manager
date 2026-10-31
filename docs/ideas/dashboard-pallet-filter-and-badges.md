# Dashboard Pallet Filter & Visual Card Attribution

## Problem Statement
How might we empower store managers to filter the staging dashboard by liquidation pallet and instantly identify which pallet each cataloged item belongs to, without cluttering the mobile layout or disrupting existing status and marketplace filters?

## Recommended Direction
Incorporate a dedicated Pallet selector into the Secondary Filter Bar on the staging dashboard (`dashboard.html`), positioned alongside the existing Platform and Search controls. The selector includes "All Pallets", each recorded pallet (`Pallet #X (YYYY-MM-DD) [count]`), and "Standalone / No Pallet" to isolate unassigned inventory.

On the product cards, render a distinct, compact badge (`📦 Pallet #X`) in the card photo's top badge overlay row, matching the established visual language of the Product Detail view.

Keep the interface clean and minimal without full-width pallet summary banners, ensuring seamless composition with status tabs, search queries, pagination, and low-DPI mobile viewports (OPPO A74 baseline).

## Key Assumptions to Validate
- [ ] **Zero N+1 Query Overhead**: Dashboard query already uses `select_related("pallet")`, so rendering pallet badges across 20 products per page introduces zero extra database queries.
- [ ] **Mobile Toolbar Wrapping**: Adding the pallet dropdown beside search and platform controls wraps fluidly on narrow Android viewports (`360×800` and `320×711`) without clipping or horizontal overflow.
- [ ] **Strict Financial Confidentiality**: Sourcing assistants viewing the dashboard see pallet labels (`Pallet #X`) without any financial amounts (`purchase_price` / `estimated_value`) exposed in DOM attributes or text.
- [ ] **Filter Composability**: Pallet filter composes seamlessly with `status`, `platform`, `channel`, `q`, and pagination query parameters.

## MVP Scope

### 1. Backend Query & Filter Handling (`inventory/views.py`)
- Parse `request.GET.get("pallet", "").strip()`:
  - `""` (default): All products.
  - `"none"`: Filter products where `pallet__isnull=True`.
  - `<id>`: Filter products where `pallet_id=pallet_filter`.
- Scope status tab counts (`counts_qs`) to the active pallet filter (identical to `platform_filter` scoping).
- Supply `available_pallets` (annotated with active item counts and ordered by `-number`) and `unassigned_products_count` in the context.
- Maintain `pallet_filter` in context for form binding and query string propagation.

### 2. Secondary Filter Bar UI (`inventory/templates/inventory/dashboard.html`)
- Add a Pallet Selector form adjacent to the Platform Selector in the Secondary Filter Bar:
  - Options:
    1. `{% trans "All Pallets" %}`
    2. `{% trans "— Standalone / No Pallet —" %} ({{ unassigned_count }})`
    3. `{% for p in available_pallets %}Pallet #{{ p.number }} ({{ p.received_date|date:"Y-m-d" }}) ({{ p.products_count }}){% endfor %}`
  - Auto-submits on change (`onchange="this.form.submit()"`).
  - Preserves active `status`, `q`, `platform`, and `channel` via hidden inputs.
- Update "Clear All Filters" button condition to check `pallet_filter`.
- Preserve `pallet` in status tab links and pagination links.

### 3. Visual Card Attribution (`inventory/templates/inventory/dashboard.html`)
- In the product card's photo badge overlay row (alongside status, marketplace, and featured badges):
  - Render a compact, tactile badge:
    `📦 Pallet #{{ product.pallet.number }}`
    styled with `text-indigo-900 bg-indigo-50 border border-indigo-200/90 shadow-xs`.
  - When a product is standalone (`pallet is None`), no badge is rendered, preserving clean card visuals.

### 4. Bilingual Localization & Tests
- Spanish translation entries in `locale/es/LC_MESSAGES/django.po` compiled to `django.mo`.
- Unit and integration tests covering:
  - Pallet filtering (`all`, specific pallet ID, and `none`).
  - Filter composability with status tabs, search queries, and platform filters.
  - Badge rendering on dashboard cards.
  - Zero financial data leakage to assistants.
  - Low-DPI mobile responsive verification (`360×800` & `320×711`).

## Not Doing (and Why)
- **No full-width pallet summary banner** — Confirmed by user: keep the dashboard minimal and uncluttered; deep pallet details and financial management live on `/pallets/`.
- **No financial metric badges on cards** — Purchase cost and estimated resale margin remain strictly confidential in the manager-only Pallet Hub.
- **No inline pallet assignment dropdown on cards** — Reassigning or unassigning pallets is performed inside the Staging Product Detail view (`/products/<pk>/`) or Django Admin to avoid accidental touch triggers in the scrollable grid.
- **No public storefront exposure** — Pallet metadata is strictly internal inventory staging data and is not surfaced on rapidopack.es.

## Open Questions
- None. Requirements and scope are fully clarified.
