# Product Requirements Document (PRD): Dashboard Marketplace Platform Filter

## 1. Executive Summary
Add a marketplace platform filter selector to the central inventory catalog dashboard (`/dashboard/`). This enables store managers and assistants to filter displayed inventory by the specific resale platform where each product is currently published (e.g. Wallapop, Vinted, eBay, Milanuncios, Vestiaire Collective). Crucially, the platform selector dynamically displays **only platforms that currently have at least one product published**, keeping the interface clean and preventing empty query dead-ends.

---

## 2. Problem Statement
Currently:
1. **No Marketplace Filtering on Dashboard:** Products published across different external marketplaces all appear mixed together in the general inventory dashboard. A store manager who wants to audit, review, or adjust pricing for items specifically live on Wallapop or Vinted must manually click into individual product pages one by one.
2. **Clutter from Unused Platforms:** If a marketplace platform is active in system configuration (e.g. eBay or Milanuncios) but the team has not yet published any products there, showing it in the filter dropdown creates visual noise and causes empty filter results.
3. **Loss of Filter State:** Users need filtering by platform to combine smoothly with existing status filters (`status=active`, `status=sold`, `status=all`), keyword/date searches (`q`), and server-side pagination (`page=2`) without resetting each other.

---

## 3. User Personas & Scenarios

### Persona: Store Manager / Lister (User B)
- **Scenario 1 (Auditing Active Wallapop Listings):** The manager wants to review all active items published on Wallapop to adjust discounts or answer platform messages. They open `/dashboard/`, choose "Wallapop" from the platform selector, and toggle the "Active" status tab. The dashboard displays only active items published on Wallapop.
- **Scenario 2 (Platform-Specific Sales Review):** The manager wants to see how many items sold specifically via Vinted. They select "Vinted" and click "Sold". The view updates with query parameters `?platform=vinted&status=sold`.
- **Scenario 3 (Dynamic Dropdown Cleanliness):** The store configures 10 resale platforms in Django Admin, but currently items are only published on Wallapop and Vinted. The platform dropdown shows only "All Platforms", "Wallapop", and "Vinted". Once an assistant publishes an item on eBay, "eBay" immediately appears in the selector.

### Persona: Field Sourcing Assistant (User A)
- **Scenario 4 (Checking Cross-Listed Items):** An assistant wants to see which items are already listed on a particular platform before processing new intake field notes. They use the platform dropdown to filter the catalog.

---

## 4. Scope & Functional Requirements

### 4.1 Filter Selector UX & UI (`inventory/templates/inventory/dashboard.html`)
- **Placement:** Placed within the dashboard filter toolbar adjacent to the status tabs and search bar.
- **Component Type:** Styled dropdown `<select>` element (or filter pill bar / dropdown) styled consistently with Tailwind CSS (rounded-xl, border-slate-200, focus:ring-emerald-500).
- **Default State:** "All Platforms" / "Todas las plataformas" selected by default (no platform filter applied).
- **Option Labels:** Display platform name and published product count, e.g.:
  - `Todas las plataformas` (default)
  - `Wallapop (12)`
  - `Vinted (8)`
  - `eBay (2)`
- **Interaction:** Selecting an option immediately navigates or submits the form to update the catalog view with `?platform=<slug>`.

### 4.2 Dynamic Platform Availability Query (`inventory/views.py`)
- Query active platforms that have at least one active listing link:
  ```python
  available_platforms = (
      MarketplaceSite.objects.filter(
          product_links__is_active=True,
          product_links__product__isnull=False,
      )
      .annotate(
          published_count=Count(
              "product_links__product",
              filter=Q(product_links__is_active=True),
              distinct=True,
          )
      )
      .filter(published_count__gt=0)
      .order_by("order", "name")
  )
  ```
- If a platform has 0 published products, it is strictly excluded from the selector options.
- If no platforms currently have any published products, the selector is either cleanly hidden or disabled with a helpful placeholder.

### 4.3 Query Parameter & Multi-Filter Composition
- URL parameter: `platform=<slug>` (e.g. `?platform=wallapop`).
- **Composition with Status Tabs:**
  - Status tab links preserve `platform`: `?status=active&platform=wallapop{% if search_query %}&q=...{% endif %}`.
- **Composition with Search Bar:**
  - Search form includes `<input type="hidden" name="platform" value="{{ platform_filter }}">` (when active) so submitting search queries retains the platform filter.
  - Clear search (`&times;`) preserves status and platform filter.
- **Composition with Pagination:**
  - Pagination links preserve `platform` parameter via `query_string` helper so navigating to page 2 stays on the selected platform.
- **Resetting Platform Filter:**
  - Selecting "All Platforms" clears the `platform` parameter.

### 4.4 Catalog Filtering Query
- When `platform` query parameter is provided:
  ```python
  if platform_filter:
      products = products.filter(
          listing_links__site__slug=platform_filter,
          listing_links__is_active=True,
      ).distinct()
  ```
- Uses `distinct()` to prevent duplicate product rows when multiple joins occur.

### 4.5 Status Counters Scoping
- **Scoped to Selected Platform:** When a platform filter is active (e.g. `?platform=wallapop`), the status counters ("All (X)", "Active (Y)", "Sold (Z)") dynamically update to reflect the counts of products published on that specific platform.
- When "All Platforms" is selected, the counters reflect total inventory across all products.

### 4.6 Internationalization (i18n)
- All new user-facing strings localized in Spanish (`locale/es/`) and English (`en`):
  - "All Platforms" -> "Todas las plataformas"
  - "Platform" / "Filter by platform" -> "Plataforma" / "Filtrar por plataforma"
  - "Published items" -> "Productos publicados"

---

## 5. Edge Cases & Boundary Conditions
1. **Invalid Platform Slug in URL:** If user enters `?platform=nonexistent`, query returns 0 results gracefully without 500 error; dropdown defaults to "All Platforms" or shows empty state.
2. **Deleting Last Link of a Platform:** If the only product link on a platform is removed, that platform immediately disappears from the selector on next page load.
3. **Deactivated Platform with Historical Links:** If `MarketplaceSite.is_active=False` but historical product links exist, define whether it should appear in the selector (recommend: only active sites or all sites with published products).
4. **Product with Multiple Links:** Product listed on both Wallapop and Vinted appears when filtering by Wallapop AND when filtering by Vinted.

---

## 6. Success Criteria
1. The dashboard displays a platform selector dropdown alongside status tabs and search bar.
2. Only marketplace platforms with at least 1 published product link are included in the selector.
3. Selecting a platform filters the product catalog to only items published on that platform.
4. Filter state is fully retained across status tabs ("Active", "Sold", "All"), keyword/date searches, and page navigation (Page 1, Page 2).
5. Selecting "All Platforms" returns to the unfiltered inventory catalog.
6. Spanish translations display seamlessly.
7. Full unit and integration test suite passes without regressions.
