# Idea One-Pager: Store Shelf Redesign & Astro Frontpage Alignment

## Problem Statement
> **How Might We** transform the Django public storefront into a clean, editorial **"digital store shelf"** at `/` and `/tienda/` that feels like a native extension of the Astro corporate landing page on **`rapidopackvalencia.es`**, retiring the redundant Django landing page and decluttering the product grid so browsing is effortless while WhatsApp and external marketplace links (Wallapop, Vinted, Milanuncios) remain one tap away when a shopper is ready to act?

## Recommended Direction
1. **Retire the Duplicate Django Landing Page (`home.html`) & Serve the Store Shelf at `/` and `/tienda/`:**
   - Route `/` (`storefront:home`) and `/tienda/` (`storefront:catalog`) directly to `catalog_view` (the Store Shelf).
   - Connect header and footer navigation links (`INICIO`, `PAQUETERÍA`, `CONTACTO`) seamlessly back to `https://rapidopackvalencia.es` while keeping `TIENDA · OUTLET` active on the Django storefront.
2. **Synchronize Visual Language with `rapidopackvalencia.es`:**
   - Adopt the live Astro design tokens: clean `#ffffff` / `#f4f6f8` surfaces (replacing the old `#faf8ff` lavender tint), `#e2e8f0` subtle borders, `#111820` deep slate dark surfaces/headings, `#059652` primary emerald green (`#047842` hover, `#ecfdf5` mint wash, `#6ee7b7` mint accent on dark), and `Outfit` + `Plus Jakarta Sans` + `JetBrains Mono` typography.
   - Use the `3px` solid emerald top accent bar, frosted white navbar, and dark `#111820` footer.
3. **Minimalist Gallery Shelf Grid (Zero Per-Card Button Clutter):**
   - Replace the oversized hero + stacked metric/trust boxes with a compact `01 // ESTANTERÍA ONLINE` editorial header, unified search + category rail, and single-row filter bar so shelf items appear immediately above the fold (including on OPPO A74 `360×800` and `320×711` viewports).
   - Remove the repetitive green WhatsApp and "Details" buttons from every product card (`_product_card.html`). Each shelf item shows a `1:1` `#f4f6f8` image pedestal, `-XX% PVP` / `FEATURED` / `RESERVED` / `SOLD` status badge, condition pill, subtle external platform indicators (`W`, `V`, `M`), `JetBrains Mono` category + `Ref. #`, 2-line title, and crisp `Outfit` price + availability dot — clicking anywhere on the card navigates to the product detail page.
4. **Focused Contact & External Store Links Architecture:**
   - **Product Detail Page (`_purchase_box.html`):** Holds the primary WhatsApp inquiry/24h-reservation CTA (`/go/whatsapp/<pk>/`) and dedicated outbound cards for the item's active external store listings (`Wallapop`, `Vinted`, `Milanuncios`, etc., via `/go/link/<link_pk>/`), with fallback profile links when no per-item link is set.
   - **Store-Wide Contact & Other Stores Bar:** Keep one clean WhatsApp CTA in the top header and a sleek dark `#111820` banner at the bottom of the shelf (`02 // CONTACTO Y OTRAS TIENDAS`) linking to WhatsApp for general inquiries and to active `MarketplaceSite` storefronts.
5. **Strict Scope Boundary:**
   - Only public-facing `storefront/` routes, templates, context, docs, translations, and storefront tests change. Internal `inventory/` workflows (`/panel/`, `/dashboard/`, `/intake/`, `/products/<pk>/`, `/pallets/`) remain 100% untouched.

## Key Assumptions to Validate
- [ ] **Visual Continuity:** Shoppers moving between `rapidopackvalencia.es` and the Django Store Shelf experience one cohesive brand identity (`Outfit`, `Plus Jakarta Sans`, `JetBrains Mono`, `#059652`, `#111820`).
- [ ] **Scannability Without Conversion Loss:** Removing repeated WhatsApp/Details buttons from grid cards reduces visual noise on mobile while preserving clear access to WhatsApp and external marketplace links on the product detail view and bottom shelf bar.
- [ ] **Above-the-Fold Inventory Density:** Compressing top header chrome ensures products are visible immediately on `1440×900` desktop and `360×800` mobile viewports without horizontal overflow down to `320×711`.

## MVP Scope
- Retire `home.html` and route `/` (`storefront:home`) + `/tienda/` (`storefront:catalog`) to the Store Shelf (`catalog_view`).
- Align `base_public.html` (header, palette, fonts, dark `#111820` footer), `catalog.html`, `_product_card.html`, `product_detail.html`, `_purchase_box.html`, `_how_to_buy_modal.html`, `how_to_buy.html`, and `legal_page.html`.
- Keep all legacy URL aliases (`/tienda/`, `/tienda/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/p/<slug>-<pk>/`, `/como-comprar/`, `/go/whatsapp/`, `/go/whatsapp/<pk>/`, `/go/link/<link_pk>/`), SEO JSON-LD, bilingual ES/EN translations, and strict internal data firewall intact.

## Not Doing (and Why)
- **Not maintaining a duplicate Django corporate landing page** — `rapidopackvalencia.es` (Astro) is the sole owner of the corporate/parcel landing page.
- **Not putting WhatsApp or external store buttons on every grid card** — creates repetitive clutter on list/shelf views.
- **Not modifying any internal `inventory/` pages or models** — internal intake, staging dashboard, and staff tooling are explicitly out of scope.
- **Not building an in-app shopping cart or checkout gateway** — conversions remain WhatsApp-first + external marketplace escrow links.
