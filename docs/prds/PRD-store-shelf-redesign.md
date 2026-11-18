# Product Requirements Document (PRD): Public Store Shelf Redesign (`rapidopackvalencia.es` Alignment)

## 1. Objective & Scope
Redesign the public-facing `storefront/` application so it serves directly as a clean, gallery-grade **"digital store shelf"** at `/` and `/tienda/`, visually synchronized with the external Astro landing page at **`https://rapidopackvalencia.es`**.

### Scope Boundary (Hard Invariant)
- **In Scope:** Public `storefront/` URLs, views, context processor, templates (`base_public.html`, `catalog.html`, `_product_card.html`, `product_detail.html`, `_purchase_box.html`, `_how_to_buy_modal.html`, `how_to_buy.html`, `legal_page.html`), bilingual `locale/` catalogs, and public storefront tests.
- **Strictly Out of Scope (Untouched):** All internal staff pages and logic under `inventory/` (`/panel/`, `/dashboard/`, `/intake/`, `/products/<pk>/`, `/pallets/`, `/login/`, `/admin/`, `inventory/models.py`, `inventory/views.py`, `inventory/forms.py`).

---

## 2. Core Requirements

### 2.1 Root Routing & Astro Frontpage Integration
- **Retire Django Corporate Landing (`home.html`):** Remove `storefront/templates/storefront/home.html` and delegate `home_view` (`/`, `storefront:home`) directly to `catalog_view` so the public root serves the Store Shelf immediately.
- **Preserve Existing Public Routes:** Keep `/tienda/` (`storefront:catalog`), `/tienda/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/p/<slug>-<pk>/`, `/como-comprar/`, `/go/whatsapp/`, `/go/whatsapp/<pk>/`, `/go/link/<link_pk>/`, `/sitemap.xml`, `/robots.txt`, and legal routes (`/aviso-legal/`, `/privacidad/`, `/cookies/`) backward-compatible.
- **Astro Navigation Links:** Expose `astro_landing_url` (`https://rapidopackvalencia.es`) via `storefront/context_processors.py`. Link `INICIO`, `PAQUETERÍA`, and `CONTACTO` in the header and footer back to `rapidopackvalencia.es` while highlighting `OUTLET / TIENDA` as the active surface.

### 2.2 Visual Identity & Design System (`rapidopackvalencia.es`)
- **Color Tokens:**
  - Surfaces: `#ffffff` base, `#f4f6f8` alternate/pedestal, `#e8eef3` / `#e2e8f0` subtle hairlines, `#111820` dark slate surface & primary dark ink.
  - Accent: `#059652` emerald primary (`#047842` hover/active ink, `#ecfdf5` mint wash, `#6ee7b7` mint highlight on dark surfaces).
  - High-contrast primary WhatsApp CTA (`bg-[#25D366] text-slate-950`) and Featured badge (`bg-amber-400 text-slate-950`) preserving WCAG AAA legibility.
- **Typography:**
  - Display & Prices: `Outfit` (`600`, `700`, `800`).
  - Body & UI Controls: `Plus Jakarta Sans` (`400`, `500`, `600`, `700`).
  - Technical Tags & References: `JetBrains Mono` (`500`, `600`) for `01 //`, `Ref. #0042`, `-XX% PVP`, hours, and counters.
  - Icons: `Material Symbols Outlined`.
- **Accessibility & Narrow Mobile (OPPO A74):**
  - Zero horizontal overflow (`scrollWidth <= clientWidth`) down to `360×800` and `320×711`.
  - No sub-12px micro-font classes (`text-[10px]`, `text-[11px]`).
  - Form inputs `>= 16px` on viewports `<= 640px`.

### 2.3 Minimalist Gallery Shelf & Decluttered Contact Flow
- **Compact Editorial Shelf Header (`01 // ESTANTERÍA ONLINE`):** Replaces bulky hero boxes with an eyebrow tag, item counter badge, concise `<h1>`, and inline trust pills so products render immediately above the fold.
- **Unified Search, Category Rail & Filter Bar:** Sticky/clean search input + sort selector, single-line horizontal scroll `#categoryRail`, and compact Price + Condition filters.
- **Button-Free Shelf Cards (`_product_card.html`):**
  - Zero WhatsApp or "Details" buttons repeated on cards in the grid.
  - Shows a `1:1` `#f4f6f8` pedestal photo, top-left status/`-XX% PVP` badge, top-right condition pill, subtle bottom-right marketplace indicators (`W`, `V`, `M` when `active_listing_links` exist), `JetBrains Mono` category + `Ref. #`, full-card link inside `<h3><a href="{{ product.get_public_url }}">...</a></h3>`, and clean `Outfit` price + strikethrough retail price + availability status dot.
- **Focused Conversion & External Store Access:**
  - **Product Detail Page (`_purchase_box.html`):** Features the primary WhatsApp inquiry/24h-hold button (`/go/whatsapp/<pk>/`) and outbound cards for active `ProductListingLink` entries (`/go/link/<link_pk>/`), with fallback profile links (`active_marketplace_sites`) when no item-specific link exists.
  - **Bottom Shelf Contact & Other Stores Banner (`02 // CONTACTO Y OTRAS TIENDAS`):** Dark `#111820` block below the shelf grid offering general WhatsApp inquiry, Google Maps / "Cómo comprar" access, and links to active external marketplace storefronts (`MarketplaceSite`).

---

## 3. Verification Criteria
- `ruff check .`, `manage.py check`, `manage.py compile_locales`, and 100% of `manage.py test` pass with zero errors.
- Visual browser inspection across desktop (`1440×900`) and mobile (`360×800`) confirms alignment with `rapidopackvalencia.es`, button-free shelf cards, working filters, primary WhatsApp + external store links on product detail, and zero horizontal overflow on `360×800` and `320×711`.
