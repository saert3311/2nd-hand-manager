# PRD: Product Detail Tabbed Workspace Redesign & Audit Log Deprioritization (Phase 50)

## 1. Executive Summary & Objective

As **2ndHand Staging Hub** evolved across 49 engineering phases—adding AI Multimodal Copywriting, Valuation Benchmarks, Marketplace Listing Links, Public Storefront Taxonomy & Analytics, Clarifications & Direct Notes, ClauseGuard Policy Compliance, and Lifecycle Audit Logs—the Product Detail view (`/products/<pk>/`) accumulated **7 vertically stacked cards** across two long columns.

While functionally comprehensive, displaying all 7 categories of information simultaneously creates high visual density, excessive vertical scrolling, and cognitive overload during rapid daily staging. Furthermore, the **Lifecycle Audit Trail** (`ProductStatusLog`) occupied a prominent card in the main layout despite being rarely consulted archival telemetry. Conversely, **Public Storefront & Taxonomy** controls were completely hidden on mobile viewports (`hidden lg:block`) to save vertical scroll space.

### Primary Objectives
1. **Category-Based Workspace Tabs (`#detailWorkspaceTablist`)**: Organize the product detail workspace into **4 focused, accessible tabs** (`Listing & Pricing`, `Channels & Storefront`, `Notes & Doubts`, and `Policy & Compliance`) with live status/counter badges, single-row horizontal scroll (`overflow-x-auto flex-nowrap whitespace-nowrap`) for narrow Android mobile viewports (`360×800` / `320×711` OPPO A74 baseline), keyboard roving focus, URL hash deep-linking, and `hidden="until-found"` Find-in-Page (`beforematch`) auto-switching.
2. **Deprioritize Lifecycle State Log (`#status-history-section`)**: Remove the Lifecycle Audit Trail from the primary 2-column workspace and relocate it to the bottom of the view as a quiet, collapsed-by-default native `<details id="status-history-disclosure">` footer drawer with a compact single-line-per-event log layout.
3. **Progressive Disclosure for Secondary Gallery Controls**: Collapse the "Add More Photos" dropzone inside an on-demand `<details id="detailAddPhotosDisclosure">` drawer whenever a product already has attached photos (auto-expanding on dragover or file selection), cutting left-column vertical height by ~45%.
4. **Unlock Mobile Storefront & Notes Access**: By moving `Public Storefront & Taxonomy` into `Tab 2 (Channels & Storefront)` and `Preserved Intake Notes` into `Tab 3 (Notes & Doubts)`, managers on smartphones gain full access to storefront visibility/taxonomy controls and intake notes without adding scroll clutter to the primary tab.
5. **High-Agency Staging UX Enhancements**:
   - **Listing Readiness Checklist Strip (`#listingReadinessChecklist`)**: At-a-glance status bar verifying the 4 publication pillars (`Photos`, `Title & Copy`, `Sale Price`, `Policy Check`) with 1-click tab navigation.
   - **1-Tap "Copy Full Listing Pack" (`#btnCopyFullListingPack`)**: Copies formatted `Title + Price + Description` in a single click for rapid external marketplace pasting.
   - **Live Character & Line Counters (`#titleCharCounter`, `#descCharCounter`)**: Real-time `font-mono tabular-nums` counters on Title and Description inputs.
   - **Unsaved Changes Indicator & `Ctrl+S` / `Cmd+S` Keyboard Save**: Tracks dirty form state across tabs and enables instant keyboard saving from any tab.

---

## 2. Information Architecture & Tab Structure

### 2.1. Left Column (`lg:col-span-5`): Visual Media & Quick Inspection
- **Photo Gallery Card**:
  - Featured Cover Photo preview (`#featuredImageWrapper`) with 1-click Cropper.js inspection modal.
  - 2-to-5 column responsive thumbnail strip (`#galleryThumbnailsGrid`) with async drag/button reordering (`#toggleReorderModeBtn`).
  - **Progressive Disclosure Upload Drawer (`#detailAddPhotosDisclosure`)**: Collapsed by default when `product.images.exists` is `True` (showing a compact summary bar with remaining slot count `{{ available_slots }}/10`), and open by default only when `product.images.count == 0`. Auto-expands whenever files are selected or dragged over the gallery card.

### 2.2. Right Column (`lg:col-span-7`): Tabbed Category Workspace (`#detailWorkspaceTabs`)
A sticky-capable, single-line horizontal tab bar (`role="tablist"`) with 4 semantic category tabs:

| Tab ID | Label (EN / ES) | Live Badge / Indicator | Contents |
| :--- | :--- | :--- | :--- |
| `tab-listing` *(Default)* | **Listing & Pricing** / **Ficha y Precio** | Readiness ratio (`4/4` or `⚠️`) | Compact AI Vision Action Bar, Unapplied Clarifications Callout, Listing Readiness Checklist, Title + Live Char Counter, Description + Live Char/Line Counter, 1-Tap Copy Full Pack, Sale Price + Valuation Benchmarks (`MSRP` / `Resale`), Lifecycle Status, Origin Pallet, Sold Channel Attribution. |
| `tab-channels` | **Channels & Storefront** / **Canales y Tienda** | Active links count (`{{ active_listing_links\|length }}`) + Sync dot | External Marketplace Listing Links (`#marketplaceLinksCard`), 1-tap Copy/View tiles, Add/Edit modals, **Public Storefront & Taxonomy (`Rápido Pack`)** (`category`, `condition`, `is_public`, `is_featured`, `is_reserved`), Conversion KPIs (`Public Views`, `WhatsApp Clicks`, `Platform Clicks`). |
| `tab-notes` | **Notes & Doubts** / **Notas y Dudas** | Pending doubts count (`{{ pending_clarifications.count }}` in amber) or total notes | Product Clarifications & Notes Hub (`#clarifications-section`), Pending Doubts inline answer forms, Resolved Clarifications & Direct Notes, Manager Dual-Mode Switcher (`Direct Note` vs `Ask Doubt`), **Preserved Intake Field Notes (`#intakeNotesCard`)**. |
| `tab-compliance` | **Policy & Compliance** / **Políticas (ClauseGuard)** | Verdict icon (`✅`/`⚠️`/`🚫`) + Risk Score (`X/100`) | ClauseGuard Policy Compliance Card (`#clauseGuardCard`), Stage & Token Economics Bar, Per-Platform Compatibility Matrix (`#clauseGuardPlatformMatrix`), Flagged Policy Clauses (`#clauseGuardCitationsList`), Auto-Sanitized Copy Notes, On-Demand AI Verification (`#verifyComplianceBtn`). |

> **Unified Form Invariant (`#productStagingForm`)**: Tab 1 (`Listing & Pricing`) and Tab 2 (`Channels & Storefront`) share the single `<form method="post" id="productStagingForm">` wrapper and a shared persistent Save footer bar (`#stagingFormSaveBar`). Toggling between Tab 1 and Tab 2 preserves all in-progress input values without requiring intermediate saves.

### 2.3. Bottom Footer Disclosure: Deprioritized Lifecycle Audit Trail (`#status-history-section`)
- Positioned below the main 12-column grid as a full-width, low-contrast `<details id="status-history-disclosure">` element.
- **Collapsed State (Default)**: Renders a single compact bar (`py-2.5 px-4 bg-slate-100/80 text-slate-600 rounded-xl border border-slate-200/80`) displaying `📜 Lifecycle Audit Trail` and `{{ status_logs|length }} changes`.
- **Expanded State**: Displays a compact, high-density timeline list of state transitions with `font-mono` timestamps, `from_status → to_status` pills, actor attribution, and trigger tags.

---

## 3. Accessibility, Modern Web Standards & Mobile Ergonomics

1. **WCAG 2.1 AA Tablist Semantics (`modern-web-guidance: tabs`)**:
   - Uses `<button type="button" role="tab" aria-selected="...">` inside `<div role="tablist" aria-label="...">`.
   - Active tab is indicated via both color and a 2px bottom border indicator (`border-b-2 border-emerald-600`), never color alone (WCAG 1.4.1).
   - Supports keyboard `ArrowLeft`, `ArrowRight`, `Home`, and `End` navigation across tabs.
2. **Searchable Hidden Panels (`modern-web-guidance: search-hidden-content`)**:
   - Inactive tab panels use `hidden="until-found"` (with a clean child wrapper for padding/borders) and listen for the `beforematch` event so native browser Find-in-Page (`Ctrl+F`) automatically activates the matching tab.
3. **OPPO A74 Narrow Mobile Viewport (`360×800` & `320×711`)**:
   - Zero horizontal overflow (`scrollWidth <= clientWidth`).
   - Tab rail scrolls horizontally in a single row (`overflow-x-auto flex-nowrap whitespace-nowrap no-scrollbar`) with `flex-none` tabs.
   - All form controls maintain `>= 16px` font size on mobile (`<= 640px`) to prevent iOS Safari auto-zoom.
