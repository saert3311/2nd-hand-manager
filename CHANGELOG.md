# Changelog

All notable changes to the **2ndHand Staging Hub** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.3.0] - 2026-10-29

### Fixed
- **Stuck `AWAITING_INFO` State Healing**: Fixed `Product.save()` so existing products transition out of `AWAITING_INFO` via `compute_lifecycle_status()` once clarification doubts are answered or deleted, instead of remaining locked in `AWAITING_INFO`. Removed hardcoded `ProductStatus.READY` overwrites in clarification views, refreshing lifecycle status accurately from database state and emitting status-congruent flash messages.
- **Action Confirmation Event Delegation & Modal Layering**: Switched `form[data-confirm-message]` binding in `inventory/templates/inventory/product_detail.html` to document-level submit event delegation so forms declared late in the DOM (such as `#deleteListingForm` in `#editListingModal`) trigger `#actionConfirmModal`. Raised `#actionConfirmModal` z-index to `z-[70]` so confirmation dialogs properly stack over parent modal dialogs without pointer event blockage.
- **Test Suite Alignment for Marketplace Links Redesign**: Updated `test_product_detail_renders_all_active_platforms`, `test_full_daily_workflow_in_real_chrome`, and `test_daily_workflow_with_accessibility_in_real_chrome` to navigate through `#openAddListingBtn`, `#addListingModal`, and `#editListingModal` reflecting the mobile-first active listing hub.

### Added
- **Ready to Publish Dashboard Filter & Automated Phase Transitions (Phase 43)**:
  - **`Ready to Publish` Filter & Badge**: Replaced the ambiguous `Active` filter in the dashboard status rail with `✨ Ready to Publish` (`#tab-ready`, `?status=ready`), backed by accurate aggregation (`ready_count`) and backward-compatible support for `?status=active`. Updated product card badges to `✨ Ready to Publish`.
  - **Deterministic Lifecycle State Transitions**: Hardened `Product.compute_lifecycle_status()` to require both title (`ai_title`) and listing description (`ai_description`), positive price (`sale_price > 0`), zero pending doubts, and zero marketplace listing links before reaching `READY`.
  - **Product Image Signals**: Connected post-save and post-delete signals on `ProductImage` to trigger `product.sync_lifecycle_status()`, keeping status synchronized as media is attached or removed.
  - **Bilingual Translations & Responsive Verification**: Added full Spanish translations (`Listo para publicar`) and verified zero horizontal tab overflow across low-DPI mobile viewports (`320×711` and `360×800`).
- **Marketplace Links Mobile Redesign: Active Listing Hub (Phase 42)**:
  - **Active Listing Tiles**: Replaced verbose marketplace cards with compact, tactile cards for each active listing displaying brand name, click count, 1-tap copy link button (`min-h-[40px]`), direct view button (`↗ Ver`), and settings button (`⚙️`).
  - **Progressive Disclosure & Zero-Height Inactive Rows**: Eliminated redundant pre-filled URL inputs and empty input cards for unlisted platforms. Added progressive disclosure `[ ➕ Add Marketplace Link ]` button when unlinked sites exist, and a compact empty state when no listings are active.
  - **Accessible Listing Modals**: Implemented accessible `#addListingModal` (site selector, URL input with clipboard paste button) and `#editListingModal` (edit URL or remove link) with ARIA dialog roles, focus management, and Escape key dismissal.
  - **Context Partitioning**: Supplied partitioned `active_listing_links` and `unlinked_sites` in `product_detail_view` without extra database queries.
  - **Bilingual Localization & Automated Tests**: Added Spanish and English translations in `locale/` and automated tests in `tests/test_marketplace_links_mobile.py` and `tests/test_oppo_a74_responsive.py`.
- **Streamlined Product Detail Mobile UI/UX & On-Demand Photo Editing**:
  - **In-Place Photo Crop & Rotate**: Added Cropper.js controls to the staging product detail workspace (`inventory/templates/inventory/product_detail.html`), enabling 90° rotation and freeform touch cropping for both saved gallery photos (via AJAX to new `product_edit_image_view` endpoint) and pending upload photos with WebP compression.
  - **2-Column Mobile Previews**: Switched saved gallery thumbnails and pending uploads from cramped 4-column layout to a finger-friendly 2-column mobile grid (`grid-cols-2 sm:grid-cols-4 md:grid-cols-5`) with touch-accessible crop and inspection buttons.
  - **Mobile Noise Reduction**: Hidden preserved intake field notes, lifecycle status audit history (`#status-history-section`), and public store taxonomy/visibility controls on viewports `< 1024px` (`hidden lg:block`), decluttering mobile staging flow.
  - **Mobile Visual Reordering**: Reordered staging content on mobile to place Gemini AI vision identification and listing copywriting/pricing details at the top (`order-1 lg:order-2`), followed by photo gallery and clarifications (`order-2 lg:order-1`).
  - **Decluttered Responsive Header Actions**: Refactored top action buttons ("View in Storefront", "Download All Photos (.ZIP)", "Move to Trash" / "Restore") into compact, touch-accessible flex buttons with abbreviated mobile labels, eliminating UI clutter and horizontal overflow down to 320px viewport width (tested against OPPO A74 baseline).
  - **Bilingual Localization & Automated Tests**: Added Spanish translations in `locale/es/` and comprehensive unit, permission, and Playwright responsive tests in `tests/test_product_detail_mobile_ux.py` and `tests/test_oppo_a74_responsive.py`.
- **On-Demand Mobile Photo Crop & Rotate in Intake (Phase 41)**:
  - Vendored **Cropper.js v1.6.2** locally in `inventory/static/inventory/vendor/` (`cropper.min.js` & `cropper.min.css`) for offline/PWA reliability.
  - Upgraded `#imagePreviewModal` in `inventory/templates/inventory/intake.html` with interactive freeform touch cropping (`autoCropArea: 1`, `viewMode: 1`), 90° left/right rotation controls (`#rotateLeftBtn`, `#rotateRightBtn`), a thumbnail edit shortcut button (`.photo-edit-btn` `✂️`), and in-place `.webp` (`max 2560px`, quality `0.82`) replacement via `#applyCropBtn`.
  - Added bilingual (`en`/`es`) localization and automated tests in `tests/test_intake_low_dpi.py`.

## [2.2.0] - 2026-10-27

### Added
- **Comprehensive UI/UX Design System, Usability & WCAG 2.1 AA Accessibility Audit & Remediation (Phase 39)**:
  - **Skip Links & Landmark Semantics (`[A-01]`, `[A-02]`)**: Added keyboard-accessible skip links (`<a href="#main-content">`) and `<main id="main-content" tabindex="-1">` targets in both [`inventory/templates/inventory/base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html) and [`storefront/templates/storefront/base_public.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/base_public.html), plus explicit `aria-label` landmarks on primary navigation menus.
  - **Heading Hierarchy Normalization (`[V-01]`, `[V-02]`, `[V-03]`, `[U-05]`)**: Promoted the login heading to `<h1>` in [`login.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/registration/login.html), added a primary `<h1>` product title to [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html), demoted duplicate `<h1>` headings in [`dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html) and [`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html) to `<h2>`, and promoted modal dialog titles (`#how-to-buy-title`, `#lightbox-title`, `#deleteModalTitle`, `#actionConfirmModalTitle`) to `<h2>`.
  - **Relative `rem` Typography, `<meta name="text-scale">` & Sub-12px Elimination (`[V-05]`, `[V-06]`, `[V-07]`)**: Added `<meta name="text-scale" content="scale">` and converted all fixed `px` Tailwind font-size tokens in [`base_public.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/base_public.html) to relative `rem` units (`>= 0.75rem`). Eliminated all 27 occurrences of `text-[10px]`, `text-[11px]`, and invalid `py-0.2` across every template.
  - **WCAG 2.1 AA Contrast Remediation (`[V-08]`, `[V-09]`, `[V-10]`)**:
    - Upgraded WhatsApp CTAs across all storefront templates from `bg-[#25D366] text-white` (2.10:1) to `bg-[#25D366] hover:bg-[#20bd5a] text-slate-950 font-bold` (**9.4:1** AAA contrast).
    - Upgraded Featured (`⭐`) and Cover Photo badges from `bg-[#F59E0B]` / `bg-amber-500 text-white` (2.15:1) to `bg-amber-400 text-slate-950` (**10.2:1** AAA contrast).
    - Upgraded the brand wordmark `"Pack"` in [`base_public.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/base_public.html) from `#fe932c` (2.28:1) to `text-secondary` (`#904d00`, **5.92:1**) and `text-slate-400` metadata labels to `text-slate-500` (**4.6:1**).
  - **Accessible Modal Dialogs Replacing Native `confirm()` / `alert()` (`[U-02]`, `[A-04]`)**: Replaced all 4 native `confirm()` dialogs and 1 `alert()` call in [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html) with a reusable `#actionConfirmModal` (`role="dialog"`, `aria-modal="true"`, focus entry/restoration, `Escape` key handler) and inline clipboard feedback. Added focus management to `#photoModal` in [`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html).
  - **Complete Form Error Surfacing & Programmatic Label Association (`[U-03]`, `[A-03]`, `[A-06]`, `[A-07]`, `[A-08]`, `[A-09]`, `[A-10]`, `[A-11]`)**:
    - Rendered inline `role="alert"` field errors for `ai_title`, `ai_description`, `sale_price`, `status`, `raw_note`, and `non_field_errors` in [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html) and [`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html).
    - Associated all 10 unlabeled form controls via explicit `for`/`id` or `aria-label`, added `aria-controls` + `role="tabpanel"` to the Clarifications Hub tabs, added `aria-pressed`/`aria-expanded` to toggle buttons, added `role="button" tabindex="0"` keyboard support to gallery thumbnails, and added `aria-hidden="true"` to all decorative Material Symbols icons across 8 storefront templates.
  - **Automated UI & Accessibility Test Suite**: Added [`tests/test_ui_accessibility.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_ui_accessibility.py) verifying skip links, landmarks, heading hierarchy, inline `role="alert"` errors, ARIA tab/label semantics, and zero regressions on micro-fonts or native dialogs.


## [2.1.1] - 2026-10-27

### Added
- **Comprehensive Bilingual Localization Audit & Catalog Completeness (Phase 38)**:
  - **Template & Code English `msgid` Harmonization**: Standardized all source `msgid`s across public storefront templates ([`storefront/templates/storefront/home.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/home.html), [`base_public.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/base_public.html), [`how_to_buy.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/how_to_buy.html)), staging templates ([`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html), [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html)), and views ([`storefront/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/views.py)) to standard English strings. This resolves the root cause where visitors selecting English were served raw Spanish text due to Spanish `msgid`s without an English catalog.
  - **Complete Spanish Translation Catalog (`locale/es/LC_MESSAGES/django.po`)**: Audited all 859 unique translatable strings in the codebase and added 252 missing entries with verified Castilian Spanish phrasing covering public landing page sections, carrier descriptions, business hours, buying guide, legal disclosures, model field labels/help texts (`Category`, `StorefrontConfiguration`), forms, and image processing error messages.
  - **Complete English Translation Catalog (`locale/en/LC_MESSAGES/django.po`)**: Authored and compiled a dedicated 936-entry English translation catalog (`locale/en/LC_MESSAGES/django.po` and `.mo`), providing formal bilingual coverage for all project text.
  - **Zero-Missing Translation Quality Gate**: Verified 0 missing translations across the codebase via automated scanner and compiled both catalogs cleanly using `manage.py compile_locales`.
  - **Bilingual Automated Test Suite & Browser Verification**:
    - Added comprehensive bilingual tests in [`tests/test_i18n.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_i18n.py) verifying corporate landing page (`/`), how-to-buy (`/como-comprar/`), legal pages (`/aviso-legal/`, `/privacidad/`, `/cookies/`), and `compile_locales` management command in both `es` and `en`.
    - Added Playwright real Chrome browser test `test_browser_bilingual_language_switching_in_chrome` in [`tests/test_browser_daily_workflow.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_browser_daily_workflow.py) verifying live UI language switcher interaction, DOM text updates, and visual proof screenshots (`daily_bilingual_01_es.png` through `04_htb_es.png`).


### Fixed
- **CI Container Smoke Test Adaptation (Gate 6)**: Resolved smoke test expectation mismatch caused by the Phase 27 URL route restructuring (`/` -> corporate landing page, staff hub -> `/panel/`). Updated Gate 6 in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml) to independently smoke-test and verify:
  1. The public corporate landing page (`/`) and public catalog (`/tienda/`) for HTTP 200 and storefront identity content (`Rápido Pack`, paquetería, segunda mano).
  2. The internal staff staging portal (`/panel/` -> `/login/`) for branding (`2ndHand`) and footer compilation timestamp (`footer-build-time`).
- **CI Test Isolation for AI Services**: Decorated `test_ai_copywriting_prompt_formats_direct_notes` in [`tests/test_clarifications_hub.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_clarifications_hub.py) with `@override_settings(GEMINI_API_KEY="test-key")` to prevent failures in clean CI runner environments lacking local `.env` secrets. Hardened Gate 3 in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml) with a dummy fallback `GEMINI_API_KEY`.

### Added
- **Translation Catalog Quality Gate (Gate 2b)**: Integrated `python manage.py compile_locales` into the `quality-gates` job in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml), enforcing `AGENTS.md` Rule 5 zero-failure translation compilation in CI before unit tests run.
- **Semantic Version Resolution & Dockerfile Synchronization**: Added automated `app_version` resolution step in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml) to extract semantic version from `config/settings.py` (or release tag) during image builds instead of propagating branch names (`master`). Synchronized default `ARG APP_VERSION="2.1.1"` in [`Dockerfile`](file:///C:/Users/Jose/antigravity/epic-tesla/Dockerfile).
- **Release Tag Automation & GHCR Multi-Arch Publishing**: Expanded workflow triggers in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml) to listen on `tags: [ 'v*' ]`, enabling automated GHCR multi-arch container image builds and semantic tag publishing whenever a release tag is pushed.
- **Least-Privilege Security Hardening**: Added explicit `permissions: contents: read` to `quality-gates` and `docker-build-and-smoke-test` jobs in [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml).

## [2.1.0] - 2026-10-27

### Added
- **Corporate Business Landing Page (`/`), Revised Marketplace URLs (`/tienda/`) & Staff Router (`/panel/`) (Phase 37)**:
  - **Corporate Business Landing Page (`/`, `storefront:home`)**: Implemented [`storefront/templates/storefront/home.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/home.html) and `home_view` in [`storefront/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/views.py) based on the Stitch reference screen (`docs/stitch_references/landing_page.html`), featuring:
    1. Sticky header with corporate navigation (`Paquetería`, `Punto Pack`, `Tienda`, `Sobre nosotros`, `Contacto`) and direct WhatsApp CTA (`/go/whatsapp/`).
    2. Split Hero section with LCP-prioritized photo (`fetchpriority="high"` on `hero_counter.webp`), live business hours pill, and dual CTAs (`/tienda/`, `/#paqueteria`).
    3. Official carrier strip (`SEUR`, `GLS`, `InPost`, `Amazon Hub`, `Kanguro`, `DHL`, `Punto Pack Oficial`).
    4. 4 Parcel & Logistics service cards (`#paqueteria`, `#punto-pack`) + 3-step visual workflow.
    5. Brand Identity (*"Más que una tienda, tu punto de barrio"*, `#quienes-somos`) with lazy-loaded team photo (`shop_team.webp`) and 4 value pillars.
    6. Featured Products (*"Recién llegados"*) displaying the 4 newest available products (`is_sold=False, is_reserved=False`) via `_product_card.html` with strict `SAFE_PUBLIC_PRODUCT_FIELDS` projection.
    7. Trust Stats band, Alfafar Location & Contact card (`#contacto`), Final CTA banner, 4-column Footer, and `Schema.org/LocalBusiness` JSON-LD.
  - **Revised Public & Staff URL Architecture**:
    - `/` $\to$ `storefront:home` (Corporate Landing Page)
    - `/tienda/` $\to$ `storefront:catalog` (Marketplace Catalog, supporting Spanish query parameters `?estado=`, `?precio=`, `?orden=`, `?categoria=` alongside English aliases)
    - `/tienda/categoria/<slug:category_slug>/` $\to$ `storefront:category` (SEO Category Catalog)
    - `/tienda/producto/<slug:slug>-<int:pk>/` $\to$ `storefront:product_detail` (with **HTTP 301** permanent redirect on non-canonical slugs and legacy `/p/<slug>-<pk>/` URLs)
    - `/como-comprar/` $\to$ `storefront:how_to_buy` (Standalone shareable non-JS guide page [`storefront/templates/storefront/how_to_buy.html`](file:///C:/Users/Jose/antigravity/epic-tesla/storefront/templates/storefront/how_to_buy.html))
    - `/go/whatsapp/`, `/go/whatsapp/<int:pk>/`, `/go/link/<int:link_pk>/` $\to$ `storefront:go_whatsapp`, `storefront:go_whatsapp_product`, `storefront:go_listing`
    - `/aviso-legal/`, `/privacidad/`, `/cookies/` $\to$ `storefront:legal_notice`, `storefront:privacy`, `storefront:cookies`
    - `/panel/` $\to$ `inventory:root` (Staff entry router preserving `name="root"`)
    - Updated `/sitemap.xml` and `/robots.txt` (`Allow: /tienda/`, `Disallow: /panel/`).

## [2.0.0] - 2026-10-27

### Added
- **Public Marketplace Storefront Transformation — Rápido Pack (`rapidopack.es`, Phase 36)**:
  - **Domain Models & Official 12-Category Taxonomy**: Added `Category`, `StorefrontConfiguration` singleton (`get_solo()`), and `ProductCondition` (`new_with_tags`, `very_good`, `good`, `vintage`) in `inventory/models.py`, extended `Product` with `category`, `condition`, `is_public`, `is_featured`, `is_reserved`, `reserved_until`, `views_count`, and `whatsapp_clicks`, added `ProductListingLink.clicks_count`, and implemented `ProductQuerySet.public_visible()` with 7-day `SOLD` social proof retention. Seeded all 12 official Rápido Pack categories and default `StorefrontConfiguration` (`Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia`) in migration `0021_marketplace_storefront.py`.
  - **SQLite WAL Mode & Concurrency Tuning**: Enabled `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` on SQLite connections in `inventory/apps.py`.
  - **AI Taxonomy Auto-Classification & `classify_products` Command**: Extended `ProductListingSchema` and `IntakePreflightSchema` in `inventory/services/ai_service.py` with `category_slug` and `condition`, plus deterministic keyword fallback `infer_taxonomy_heuristically()`. Added `python manage.py classify_products` CLI command to classify existing products.
  - **Dedicated `storefront` Application & Stitch Design System**: Created `storefront/` app serving `/` (`storefront:catalog`), `/p/<slug>-<pk>/` (`storefront:product_detail`), `/go/whatsapp/<pk>/` (`storefront:go_whatsapp`), `/go/link/<link_pk>/` (`storefront:go_marketplace_link`), `/sitemap.xml`, `/robots.txt`, and RGPD/LSSI legal pages (`/legal/aviso-legal/`, `/legal/privacidad/`, `/legal/cookies/`). Moved internal staff root redirect to `/staff/` (`inventory:root`).
  - **Defense-in-Depth Public Data Firewall**: Enforced `.only(...)` SQL projection and `_sanitize_public_product()` in-memory clearing in `storefront/views.py` so `raw_note`, `ProductClarification`, and `created_by` are never exposed in public HTML, search, OpenGraph tags, JSON-LD, or sitemaps.
  - **Bilingual Localization & Automated Test Suite**: Updated `locale/es/LC_MESSAGES/django.po` and compiled `django.mo`. Added `tests/test_storefront.py` verifying visibility rules, 7-day sold retention, non-leak security firewall, catalog filters, click counters, SEO metadata, and AI taxonomy classification.

## [1.11.0] - 2026-10-26

### Added
- **Out-of-Sync Product Web Push Notifications (Phase 35)**:
  - **Real-Time Manager Alerts (`inventory/services/push_service.py`)**: Implemented `send_out_of_sync_notification(product)` dispatching encrypted Web Push notifications to active Store Managers (`ROLE_MANAGER` + active staff/superusers) via VAPID and `pywebpush` whenever published items undergo post-publication modifications.
  - **Edge-Transition State Guard (`inventory/models.py`)**: Instrumented `Product.__init__` and `Product.save()` with `_initial_needs_platform_sync` and `_previous_needs_platform_sync` to detect state transitions. Signal receiver `notify_managers_on_product_lifecycle_save` triggers strictly on `False -> True` edge transitions, preventing repetitive notification spam on subsequent edits.
  - **Notification Suppression Invariants**: Automatically suppresses notifications when platform sync is cleared via `product.mark_platform_synced()`, when editing draft/unpublished products, or when products are soft-deleted (`is_deleted=True`). A subsequent modification after clearance properly triggers a fresh alert.
  - **Actionable Deep-Linking & Tag Collapsing**: Formats notifications with direct URL `/products/<pk>/` leading directly to the workspace warning banner and 1-click clearance action, tagged with `product-out-of-sync-<pk>` to collapse repeated alerts in OS notification drawers.
  - **Bilingual Localization & Comprehensive Test Suite**: Added Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 16 automated tests in `tests/test_out_of_sync_notifications.py` with 100% pass rate.

## [1.10.0] - 2026-10-26

### Added
- **Detail View Photo Upload Component System (Phase 34)**:
  - **Component Parity with Intake Flow (`inventory/templates/inventory/product_detail.html`)**: Upgraded the 'Add More Photos' section in the Product Detail workspace from a raw file input into the full, mobile-first photo upload component system from `/intake/`.
  - **Interactive Dashed Dropzone (`#detailDropZone`)**: Desktop drag-and-drop file upload zone with visual dragover emerald highlights and click delegation to multi-file selector.
  - **Dual Mobile Action Triggers**: High-contrast, touch-friendly buttons for dedicated rear camera shooting (`#btnTriggerDetailCamera` triggering `#detailCameraInput` with `capture="environment"`) and multi-file gallery selection (`#btnTriggerDetailGallery` triggering `#detailImageInput`). Includes `stopPropagation()` handlers to prevent accidental double-invoking of file choosers on iOS and Android.
  - **Client-Side Canvas WebP Compression**: Automatic in-browser downscaling to max 2560px WebP (quality 0.82) with hardware EXIF orientation handling via `createImageBitmap` and `HTMLImageElement` fallback, eliminating mobile browser memory exhaustion (Android LMK crashes) and reducing network upload bandwidth by ~80-90%.
  - **Pre-Upload Queue & Interactive Preview Grid (`#detailPendingGrid`)**: Live thumbnail preview of newly selected photos prior to submission, with index badges (`+#`), individual photo discard buttons (✕), and a "Clear All" action (`#btnClearDetailPending`).
  - **Dynamic Slot Capacity Guardrail**: Automatically calculates remaining photo capacity (10 - N_existing), renders a live slot counter (`#detailUploadSlotCount`), and alerts managers when selection attempts exceed the 10-photo maximum ceiling.
  - **Context & Backend Synchronization (`inventory/views.py`)**: Enhanced `product_detail_view` to compute and expose `available_slots = max(0, 10 - product.images.count())` in template context, maintaining server-side 10-photo enforcement and `needs_platform_sync = True` triggering upon upload.
  - **Bilingual Localization & Automated Tests**: Added 10 Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 10 automated unit, view, permission, capacity, and localization tests in `tests/test_detail_photo_upload_component.py`.


## [1.9.0] - 2026-10-26

### Added
- **Published Product Modifications & External Platform Sync Tracking (Phase 33)**:
  - **Orthogonal Platform Synchronization Domain Model (`inventory/models.py`)**: Added `needs_platform_sync` (`BooleanField`, default `False`, indexed) and `last_platform_synced_at` (`DateTimeField`, null/blank) to `Product`. Preserves published lifecycle state (`PUBLISHED`) while tracking post-publication modifications without disrupting sales attribution, analytics, or external link navigation. Generated and applied migration `0020_product_platform_sync.py`.
  - **Automated Change-Detection Triggers**: Hooked change detection into `Product.save()` and clarification signals: modifications to `sale_price`, `ai_title`, or `ai_description`, as well as added or resolved `ProductClarification` questions/notes on published products, automatically flag `needs_platform_sync = True`. Reordering photos that alters the primary cover image (`#0`) also triggers out-of-sync tracking.
  - **Product Detail Staging Photo Management**: Enabled store managers to upload additional photos directly in the Photo Gallery card via `product_upload_images_view` (`POST /products/<pk>/images/upload/`), compressed to WebP with Pillow (up to 10 photos max). Implemented `product_delete_image_view` (`POST /products/<pk>/images/<image_id>/delete/`) with automatic order re-indexing ($0, 1, 2\dots$) while guaranteeing at least 1 photo remains. Both actions set `needs_platform_sync = True` on published items.
  - **1-Click Platform Sync Clearance Action**: Implemented `product_mark_platform_synced_view` (`POST /products/<pk>/mark-synced/`) and `Product.mark_platform_synced()`. Clears the sync flag, stamps `last_platform_synced_at`, and appends an immutable audit log entry in `ProductStatusLog` (`trigger="platform_sync_cleared"`).
  - **Accessible Warning Workspace Banner**: Added an amber warning banner `#platformSyncBanner` in `product_detail.html` notifying managers that external marketplace listings may be out of date, equipped with the 1-click `✅ Marcar plataformas como actualizadas` / `Mark Platforms as Updated` action.
  - **Catalog Dashboard Sub-Filtering & Live Badges (`inventory/templates/inventory/dashboard.html`)**: Added `?status=published&sync=out_of_sync` sub-filter with live counter under the "Publicados" tab, and rendered pulsing amber sync badges (`⚠️ Actualizar plataformas` / `⚠️ Update Platforms`) on product cards.
  - **Django Admin Visibility (`inventory/admin.py`)**: Added `needs_platform_sync_col` badge in `ProductAdmin.list_display` and `needs_platform_sync` in `list_filter`.
  - **Bilingual Localization & Comprehensive Test Suite**: Added 29 Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 21 automated unit, model, form, view, permission, and UI localization tests in `tests/test_published_platform_sync.py`.

## [1.8.1] - 2026-10-26

### Added
- **Low-DPI Intake Photo Miniatures & Delete Controls Optimization (Phase 32)**:
  - **High-Density Responsive Miniature Grid (`inventory/templates/inventory/intake.html`)**: Upgraded `#previewGrid` from `grid-cols-2` to `grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 sm:gap-2.5`. Compacts thumbnail cards to ~90px–115px square on viewports < 640px and low-DPI (1x) handheld warehouse scanners, eliminating vertical page hijacking and allowing assistants to view photo collections without displacing intake form controls.
  - **High-Contrast Unambiguous Delete ('X') Button**: Refactored the thumbnail delete control with a prominent white isolation ring (`ring-1 ring-white/90`), bold rose badge (`bg-rose-600 hover:bg-rose-700 active:bg-rose-800`), and heavy cross stroke (`stroke-width="3"`) to prevent subpixel blur, aliasing, and background blending on 1x DPI displays. Preserves an accessible 32x32px hit area positioned at `top-0.5 right-0.5` without obscuring photo content.
  - **Streamlined Cover & Sequence Badges**: Compacted cover badge (`⭐ #1`) and sequence pills (`#N`) with subtle contrast borders, preventing overlap with the delete button even on 90px cards.
  - **Compact Floating Reorder Bar**: Streamlined reorder arrows (`◀`, `▶`) and 1-click cover promotion (`⭐`) into a semi-transparent floating pill (`bg-slate-900/80 backdrop-blur-xs p-0.5 rounded-lg`), leaving over 70% of the thumbnail surface unobstructed.
  - **Tap-to-Inspect Lightbox Modal (`#imagePreviewModal`)**: Added an accessible full-screen photo inspection modal with semantic dialog markup (`role="dialog"`, `aria-modal="true"`), previous/next navigation buttons, dismiss handlers (`Escape` key, backdrop click, close button), and uncropped photo rendering so assistants can verify photo sharpness, barcode legibility, and condition before AI submission.
  - **Bilingual Localization & Comprehensive Test Suite**: Added Spanish translations for photo inspection, navigation, and zoom tooltips in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 9 automated tests in `tests/test_intake_low_dpi.py` verifying grid classes, delete button contrast attributes, lightbox modal presence, accessibility roles, and Spanish/English localization.

## [1.8.0] - 2026-10-26

### Added
- **Photo Reordering in Intake and Detail Workspaces (Phase 31)**:
  - **Backend Image Reordering API Endpoint**: Implemented `product_reorder_images_view` at `POST /products/<pk>/images/reorder/` in `inventory/views.py`. Strictly restricted to Store Managers (`@manager_required`, `@login_required`, `@require_POST`). Validates JSON payload, verifies all image IDs belong to the product, updates `ProductImage.order` atomically inside a single database transaction, and returns the updated primary cover image URL. Blocks assistants with HTTP 403 and rejects malformed or cross-product payloads with HTTP 400.
  - **Intake Form Hybrid Reordering (`inventory/templates/inventory/intake.html`)**: Added intuitive, touch-friendly tap controls (Move Left `◀`, Move Right `▶`, and 1-click "Set as Cover" `⭐`) on preview thumbnail cards alongside desktop HTML5 drag-and-drop handles. The #1 photo receives a prominent badge (`⭐ #1 Portada` / `⭐ #1 Cover`). Calling `syncFileInput()` on every reorder updates `imageInput.files` via `DataTransfer` so `request.FILES.getlist('images')` arrives pre-sorted for database persistence. Preserves pre-flight AI identification gate status if already run.
  - **Product Detail Staging Workspace Reordering (`inventory/templates/inventory/product_detail.html`)**: Added interactive photo reordering to the Photo Gallery Card for store managers. Features an accessible "Reorganizar fotos / Reorder" toggle, move left/right controls, 1-click "Set as Cover" button, and drag-and-drop handles. Saves changes asynchronously to the backend, updates the featured `#mainImage` preview dynamically, and renders accessible status notices. Sourcing assistants see a clean read-only gallery.
  - **Bilingual Localization & Comprehensive Test Suite**: Added Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 17 automated tests in `tests/test_photo_reordering.py` covering backend API authentication, assistant permission denial, atomic DB ordering, payload validation, intake UI elements, detail UI controls, and Spanish localization.

## [1.7.0] - 2026-10-26

### Added
- **Intake Mandatory Pre-flight Identification Gate (Phase 30)**:
  - **Save Button Gating & Initial State**: Modified `/intake/` in `inventory/templates/inventory/intake.html` so `#submitBtn` is initialized with `disabled` attribute, `aria-disabled="true"`, and disabled styling (`bg-slate-300 text-slate-500 cursor-not-allowed opacity-60`). Renders an accessible dynamic guidance hint `#submitHelpText` beneath the Save button informing the assistant: *"Identifica primero el producto con IA para habilitar el guardado"* / *"Identify product with AI first to enable saving"*.
  - **State Machine & Lifecycle Gating**: Added internal client tracking variable `hasIdentified` and helper `updateSubmitButtonState()`. Form state transitions (`identifying`, `submitting`, `idle`, and image optimization) strictly respect the gate. Running pre-flight AI identification unlocks the Save button with confirmation text (*"Producto identificado — listo para guardar"* / *"Product identified — ready to save"*).
  - **Photo Clearing Reset**: When all photos are deleted (`selectedFiles.length === 0`), `hasIdentified` automatically resets to `false` and `#submitBtn` is re-disabled until identification is executed again.
  - **Client-Side Submit Interception Guard**: Intercepts premature form submissions (e.g. Enter keypress in inputs) if `!hasIdentified`, displaying an inline accessible warning alert and drawing focus/highlight ring to the identification button.
  - **Non-Blocking Resilient Error Fallback**: If Gemini identification times out, encounters a network issue, or fails to recognize an item, the Save button is gracefully unlocked so warehouse sourcing staff are never blocked from saving intake items.
  - **Bilingual Localization & Comprehensive Test Suite**: Added Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 6 automated tests in `tests/test_intake_identification_gate.py` covering DOM attributes, Spanish localization, JS state machine presence, AI endpoint success/fallback handling, and backend persistence.

## [1.6.0] - 2026-10-26

### Added
- **Product Detail Clarifications Hub ("Direct Notes & Q&A Doubts") (Phase 29)**:
  - **Domain Model Extension**: Added `is_direct_note` (`BooleanField(default=False, db_index=True)`) to `ProductClarification` in `inventory/models.py`. Generated and applied database migration `0019_productclarification_is_direct_note.py`. Refactored post-save signals so direct clarification notes save in `RESOLVED` status without triggering `AWAITING_INFO` or dispatching assistant push notifications.
  - **Direct Clarification Endpoint & Multi-Role Permissions**: Implemented `product_add_direct_clarification_view` at `/products/<pk>/clarifications/add-note/` allowing both Store Managers and Sourcing Assistants to record immediate post-intake clarification notes (measurements, tags, condition, authenticity) without changing lifecycle status or creating blockers.
  - **AI Vision Copywriting Integration**: Updated Gemini listing prompt generator in `inventory/services/ai_service.py` to seamlessly format direct notes (`- [Category] Note: <content>`) alongside resolved Q&A doubt pairs.
  - **Frontend UI Engineering**: Redesigned `#clarifications-section` in the Left Column of `product_detail.html` directly below "Preserved Intake Notes". Features an accessible dual-mode tab switcher for managers (`📝 Añadir nota directa` vs `❓ Preguntar a asistente`), distinct badges and attributions for direct notes and doubts, mobile-safe typography (`text-base sm:text-sm` preventing iOS Safari auto-zoom), and manager deletion controls.
  - **Bilingual Localization & Comprehensive Test Suite**: Added Spanish translations in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 14 automated unit, model, form, view, permission, prompt, and UI localization tests in `tests/test_clarifications_hub.py`.

## [1.5.0] - 2026-10-26

### Added
- **Product Soft-Delete, Archival & Erased Trash Category (Phase 28)**:
  - **Domain Model Soft-Delete**: Added `is_deleted` (`BooleanField`, indexed, default `False`), `deleted_at` (`DateTimeField`), and `deleted_by` (`ForeignKey(User, null=True, on_delete=SET_NULL)`) to `Product` in `inventory/models.py`. Generated and applied database migration `0018_product_soft_delete.py`. Added helper methods `soft_delete()` and `restore()` which preserve original lifecycle status and append audit trail logs in `ProductStatusLog`.
  - **Protected Action Endpoints**: Implemented `product_soft_delete_view` and `product_restore_view` in `inventory/views.py` restricted to POST requests and store managers (`@manager_required`), registered at `/products/<pk>/delete/` and `/products/<pk>/restore/`. Non-managers attempting access are denied (HTTP 403), and assistants viewing soft-deleted products are safely redirected to the catalog.
  - **Product Detail Staging View UI**: Added an accessible "Move to Trash" trigger and `#deleteProductModal` confirmation dialog on `product_detail.html` for active items. For erased items, renders a prominent warning banner with an immediate 1-click "Restore Product" action.
  - **Dashboard Trash Category & Scoped Counters**: Added dedicated `?status=erased` ("🗑️ Eliminados" / "🗑️ Trash") tab pill on `dashboard.html` with an isolated `erased_count` badge. Excluded soft-deleted products from all default catalog views (`all`, `active`, `draft`, `ready`, `sold`, etc.) and standard status counter aggregations. Scoped multi-field search so global searches never return erased products, and searching within `status=erased` queries only erased inventory.
  - **Django Admin Integration**: Added `is_deleted_col` and `is_deleted` filter to `ProductAdmin`, with bulk admin actions `soft_delete_selected` and `restore_selected`.
  - **Bilingual Localization & Comprehensive Test Suite**: Updated Spanish translation catalogs in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 10 automated unit, view, admin, and localization tests in `tests/test_product_soft_delete.py`.

## [1.4.0] - 2026-10-25

### Added
- **Sale Channel Tracking & Multi-Channel Attribution (Phase 27)**:
  - **Domain Model Tracking**: Added `SaleChannelType` choices (`in_store`, `marketplace`, `other`), `sold_channel_type`, `sold_marketplace` (ForeignKey to `MarketplaceSite` with `SET_NULL` deletion protection), `sold_channel_notes` (`CharField(max_length=255)`), and computed property `sale_channel_display` to `Product` in `inventory/models.py`. Generated and applied database migration `0017_product_sale_channel.py`. Updated `mark_as_sold()` and `mark_as_unsold()` to manage channel state and audit logging in `ProductStatusLog`.
  - **Conditional Form Validation**: Updated `ProductUpdateForm` in `inventory/forms.py` with `sold_channel_type`, `sold_marketplace`, and `sold_channel_notes`. Implemented conditional business rules in `clean()`: channel type is mandatory whenever marked as sold; marketplace selection is mandatory when `sold_channel_type="marketplace"`; channel fields are cleanly reset to empty/null if reverted to an unsold status.
  - **Interactive Detail Staging UI**: Enhanced `inventory/templates/inventory/product_detail.html` with progressive disclosure `#soldChannelContainer` triggered automatically when status is set to Sold. Included 1-click quick-pick buttons for "In-Store / Tienda física" and active published marketplace links (e.g., Wallapop, Vinted), along with responsive status badge in the header displaying the sale channel.
  - **Dashboard Sub-Filtering & Channel Badges**: Updated `dashboard_view` in `inventory/views.py` with `channel` query filtering (`?status=sold&channel=in_store|marketplace|other`), live count aggregates (`channel_counts`), and `select_related("sold_marketplace")` to eliminate N+1 queries. Added tertiary filter navigation bar and card badges in `inventory/templates/inventory/dashboard.html`.
  - **Django Admin Integration**: Added `sale_channel_col` to `ProductAdmin.list_display` with status-aware color badges and registered `sold_channel_type` and `sold_marketplace` in `list_filter`.
  - **Bilingual Localization & Automated Test Suite**: Added Spanish translations to `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Authored 16 automated tests in `tests/test_sale_channel.py` covering model lifecycle methods, SET_NULL referential safety, form validation invariants, detail view quick-picks, dashboard sub-filtering, admin columns, and localization.

## [1.3.2] - 2026-10-24

### Fixed
- **Android Intake Native Camera Trigger Activation**:
  - **Native Label Element Activation**: Replaced synthetic JavaScript button click triggers with semantic `<label for="cameraInput">` and `<label for="imageInput">` elements. In Android Chrome and modern mobile browsers, user activation contexts are strictly enforced; native `<label>` binding initiates the OS camera capture intent (`MediaStore.ACTION_IMAGE_CAPTURE`) without programmatic click restrictions.
  - **Eliminated Event Bubbling to Gallery Trigger**: Bound `stopPropagation()` on `cameraInput` and `imageInput` click events and guarded the `#dropZone` click delegation handler against any child label, button, or input. Previously, clicking the camera button caused event bubbling up to `#dropZone`, which mistakenly fired the gallery `imageInput.click()` on top of the camera intent, opening the gallery instead of the camera.
  - **Keyboard Accessibility**: Implemented `role="button"`, `tabindex="0"`, and keydown listeners for `Space` and `Enter` on the dual action labels to maintain full accessibility.

## [1.3.1] - 2026-10-23

### Fixed
- **Mobile Intake Photo Capture & Low-Memory Out-of-Memory Crashes**:
  - **Decoupled Camera and Gallery Inputs**: Removed contradictory `capture="environment"` attribute from the multi-photo input in `inventory/templates/inventory/intake.html`, preventing Android's Low Memory Killer (LMK) from terminating background Chrome sessions during native camera execution (*"Unable to complete previous operation due to low memory"*).
  - **Dedicated Mobile Capture Buttons**: Added "📸 Tomar foto" (dedicated single-shot camera capture) and "🖼️ Elegir de la galería" (multi-photo selection) in the intake dropzone.
  - **Client-Side Canvas WebP Downscaling (2560px)**: Implemented on-device proportional resizing to max 2560px and WebP encoding (`image/webp` quality 0.82 with JPEG fallback), reducing decoded raster RAM from ~200MB down to ~3MB and file payload from ~15MB to ~400KB-700KB. Added inline spinner optimization indicator.
  - **Server-Side Decompression Safety**: Raised backend `MAX_DIMENSION` to 2560px and `Image.MAX_IMAGE_PIXELS` to 100,000,000 (100MP) in `inventory/services/image_service.py` to support modern 48MP/50MP mobile cameras without false-positive decompression bomb rejections.

## [1.3.0] - 2026-10-21

### Added
- **Consolidated Intake Session Notifications ("Debounced Manager Push Alerts") (Phase 26)**:
  - **Debounced Intake Sourcing Session Engine**: Created `IntakeBatchSession` model in `inventory/models.py` with `assistant`, `started_at`, `last_activity_at`, `product_count`, `is_notified`, and `closed_at`. Added foreign key `batch_session` on `Product` for complete operational auditability. Generated and applied database migration `0016_intake_batch_session.py`.
  - **Session Dispatcher & Configuration**: Implemented `inventory/services/intake_batch_service.py` with `record_product_intake()` and `process_pending_intake_batches()`. Added `INTAKE_SESSION_DEBOUNCE_MINUTES` setting in `config/settings.py` (default: 15 minutes, configurable via `.env`).
  - **Lifecycle Signal Refactoring**: Refactored `notify_managers_on_product_lifecycle_save` post-save signal in `inventory/models.py` to eliminate individual draft push alerts. When an assistant uploads products in draft, they are grouped under the assistant's active `IntakeBatchSession`. After 15 minutes of inactivity, a single consolidated push alert (`📦 Lote completado: %(count)s nuevos productos`) is dispatched to `ROLE_MANAGER` pointing to `/dashboard/?status=draft`.
  - **Urgent Alert Isolation**: Verified that urgent clarification doubts (`ProductClarification`) and price pending transitions (`PRICE_PENDING`) remain 100% instant and un-debounced.
  - **Management Command for CLI & Cron**: Built `python manage.py process_intake_batches` supporting `--debounce-minutes`, `--dry-run`, `--no-notify`, and `--quiet` options.
  - **Django Administration**: Registered `IntakeBatchSessionAdmin` in `manager_admin_site` with `BatchProductInline` displaying associated products, push status badges, and search by assistant.
  - **Bilingual Localization & Automated Tests**: Added Spanish catalog entries in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`. Added 11 unit and integration tests in `tests/test_intake_batch_notifications.py` covering debounce windows, grouping, idempotency, multi-assistant isolation, and admin permissions.

## [1.2.0] - 2026-10-21

### Fixed
- **Product Detail Staging View Sale Price Rendering & HTML5 Number Localization**:
  - **Root Cause Resolution**: Diagnosed and resolved the issue where a sale price entered during intake appeared in the dashboard list view but was missing/empty in the product detail view:
    1. *HTML5 Comma Sanitization*: In [`inventory/templates/inventory/product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html), the input field rendered `value="{{ form.sale_price.value|default:'' }}"`. Under the Spanish locale (`es`), Django's localization formats decimal values with a comma (e.g., `'35,50'`). According to the HTML5 specification, `<input type="number">` strictly requires an ASCII period floating-point representation; when given a value with a comma, web browsers (Chrome, Edge, Safari, Firefox) execute the value sanitization algorithm and reset the field to an empty string `""`.
    2. *Data Loss Risk on Update*: If a user submitted listing changes while the field was wiped by the browser, the empty string coerced the database `sale_price` to `None`.
    3. *Missing Visual Price Badges in Staging Detail*: Unlike the dashboard list view (which featured a prominent `€XX.XX` badge), the product detail page lacked a summary price badge in the header/breadcrumb bar and card header.
  - **HTML5 Input Unlocalization**: Loaded `l10n` in `product_detail.html` and applied `unlocalize` (`value="{{ form.sale_price.value|unlocalize|default:'' }}"`) to guarantee standard period-separated floating-point formatting (`35.50`) regardless of active user locale.
  - **Prominent Price Badges**: Added an eye-catching `#product-price-badge` badge (`€{{ product.sale_price|floatformat:2 }}`) to the breadcrumb top bar and staging card header in `product_detail.html`.
  - **Assistant Readonly Guard**: Added `readonly disabled` attributes and background styling to `#id_sale_price` for non-manager assistants viewing the staging detail page.
  - **Form Widget Attributes**: Added `placeholder="0.00"` and `inputmode="decimal"` to `ProductUpdateForm.sale_price` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py).
  - **Automated Regression Test Suite**: Added end-to-end assertions in [`tests/test_intake.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_intake.py) (`test_intake_sale_price_displays_in_dashboard_and_product_detail`) and [`tests/test_i18n.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_i18n.py) verifying that intake prices render properly across dashboard and detail views under both English and Spanish locales.

### Added
- **Intake AI Valuation & Reference Pricing (Phase 25)**:
  - **Domain Model Valuation Fields**: Added `estimated_retail_price` (estimated original retail value / MSRP in €) and `estimated_resale_price` (estimated realistic secondhand market resale value in €) as nullable `DecimalField`s with non-negative validation (`MinValueValidator(Decimal("0.00"))`) on `Product` in [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py). Generated and applied database migration `0015_product_estimated_prices.py`.
  - **Admin Registration**: Exposed `estimated_retail_price_display` and `estimated_resale_price_display` in `ProductAdmin.list_display` in [`inventory/admin.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/admin.py).
  - **AI Vision Preflight Appraisal Service**: Updated `IntakePreflightSchema` in [`inventory/services/ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py) with `estimated_retail_price` and `estimated_resale_price`. Updated `PREFLIGHT_ES_INSTRUCTION` and `PREFLIGHT_EN_INSTRUCTION` prompts to instruct Gemini Multimodal Vision to appraise original new retail MSRP and realistic secondhand market value in Spain/Europe (Wallapop, Vinted, eBay) in Euros (€) while returning `null` if unbranded or impossible to estimate objectively. Added sanitizing price parser `_clean_price()`.
  - **Mobile Intake Form & Benchmark UI Integration**:
    - Added hidden form fields `id_estimated_retail_price` and `id_estimated_resale_price` to `ProductIntakeForm` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py).
    - Rendered `#advisoryValuationContainer` inside `#aiAdvisoryBanner` in [`inventory/templates/inventory/intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html) displaying side-by-side cards for *PVP Nuevo (MSRP)* and *Reventa estimada*.
    - Rendered benchmark badges and `#btnUseEstimatedResale` button directly below the target sale price input (`#id_sale_price`), enabling assistants to adopt the estimated resale price with a single tap without overwriting unprompted.
  - **Staging Product Detail View Benchmark Badges**: In [`inventory/templates/inventory/product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html), rendered benchmark badges (`#ref-retail-price` and `#ref-resale-price`) beside the manager's `Sale Price (€)` input along with a one-click `Aplicar reventa (€YY.YY)` quick button for store managers.
  - **Bilingual Localization & 100% Test Coverage**: Localized all new valuation tokens in Spanish in [`locale/es/LC_MESSAGES/django.po`](file:///C:/Users/Jose/antigravity/epic-tesla/locale/es/LC_MESSAGES/django.po) and compiled to `django.mo`. Added 14 unit and integration tests in [`tests/test_ai_valuation.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_ai_valuation.py) validating schema parsing, fallback logic, model persistence, form binding, and UI rendering. The entire 337-test suite passes with 0 failures and 0 errors.
- **Compilation & Docker Image Build Timestamp Display (Phase 24)**:
  - **Version & Build Metadata Resolution Service**: Implemented [`inventory/services/version_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/version_service.py) with `get_build_info()`. Resolves build metadata through a hierarchical fallback: (1) environment variables (`APP_BUILD_TIME`, `APP_BUILD_COMMIT`, `APP_VERSION`, `APP_ENV`), (2) container baked files (`/app/build_date.txt` & `/app/build_commit.txt`), (3) Git fallback for local development (`git log -1` and `git rev-parse --short HEAD`), and (4) default development fallback with startup in-memory caching to eliminate runtime I/O overhead.
  - **Global Context Processor**: Added `build_info` context processor in [`inventory/context_processors.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/context_processors.py) and registered in [`config/settings.py`](file:///C:/Users/Jose/antigravity/epic-tesla/config/settings.py), exposing compilation timestamps, short Git commit SHA, environment labels, and styling badges across all application views.
  - **Docker Build & CI/CD Pipeline Automation**: Updated [`Dockerfile`](file:///C:/Users/Jose/antigravity/epic-tesla/Dockerfile) with `ARG BUILD_TIME`, `ARG BUILD_COMMIT`, `ARG APP_VERSION`, and an image compilation step that bakes `/app/build_date.txt` automatically during any `docker build`. Updated [`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml) in `docker-build-and-smoke-test` and `publish-image` to pass dynamic UTC timestamps and commit SHAs, adding container smoke test verification asserting `#footer-build-time` presence.
  - **Modernized Responsive Application Footer**: Refactored `<footer>` in [`inventory/templates/inventory/base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html) with accessible IDs (`#footer-build-time`, `#footer-build-sha`, `#footer-build-env`), semantic `role="contentinfo"`, and mobile-optimized flex wrapping (`text-[11px] sm:text-xs`) to prevent horizontal overflow on smartphone screens ($390 \times 844$).
  - **Bilingual Localization & Comprehensive Test Suite**: Localized all tokens in Spanish in [`locale/es/LC_MESSAGES/django.po`](file:///C:/Users/Jose/antigravity/epic-tesla/locale/es/LC_MESSAGES/django.po) and compiled to `django.mo`. Added 9 unit and integration tests in [`tests/test_build_info.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_build_info.py) covering all fallback tiers and template rendering.
- **Product State Change Tracking & Immutable Audit Trail (Phase 23)**:
  - **Audit Domain Model (`ProductStatusLog`)**: Added immutable `ProductStatusLog` model in [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py) tracking `product`, `from_status`, `to_status`, `changed_by` (`User`, nullable with `SET_NULL`), `trigger` (e.g. `intake`, `pricing`, `staging_update`, `clarification_opened`, `clarification_resolved`, `marketplace_link_added`, `marketplace_link_removed`, `marked_sold`, `reverted_unsold`), `notes`, and indexed `created_at`. Generated and applied database migration `0014_productstatuslog.py`.
  - **Thread-Safe Context Middleware (`CurrentUserMiddleware`)**: Implemented [`inventory/middleware.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/middleware.py) using `contextvars` to automatically capture `request.user` during web requests, safely resolving user attribution across both web traffic and CLI/automated tasks without thread leakage.
  - **Automated Lifecycle Transition Logging & Cascade Protection**: Hooked change detection into `Product.save()`, `mark_as_sold()`, `mark_as_unsold()`, `sync_lifecycle_status()`, and clarification/marketplace signals. Implemented thread-safe deletion tracking (`_deleting_product_pks` context variable) to eliminate orphan status logs during cascade deletions and satisfy SQLite foreign key integrity constraints.
  - **Read-Only Django Admin Changelist & Inline**: Registered `ProductStatusLogAdmin` and `ProductStatusLogInline` in [`inventory/admin.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/admin.py) with strictly revoked add, change, and delete permissions (`has_add_permission=False`, `has_change_permission=False`, `has_delete_permission=False`), providing color-coded status badges, trigger tags, search, and date filters.
  - **Responsive Detail Page Timeline Card ("Historial de Estados")**: Updated `product_detail_view` in [`inventory/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py) with optimized `Prefetch("status_logs")` and added an accessible, responsive vertical timeline card in [`inventory/templates/inventory/product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html) with actor role pills, localized timestamps, contextual badges, and a collapsible accordion toggle for histories exceeding 4 entries.
  - **Bilingual Localization & 100% Test Coverage**: Localized all model fields, triggers, and UI labels in Spanish in [`locale/es/LC_MESSAGES/django.po`](file:///C:/Users/Jose/antigravity/epic-tesla/locale/es/LC_MESSAGES/django.po) and compiled to `django.mo`. Added 14 unit and integration tests in [`tests/test_status_history.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_status_history.py); the entire 314-test suite passes with 0 failures and 0 warnings on `ruff check .`.
- **Mobile Typography & High-Readability Adaptation Across All Application Views**:
  - **Eliminated Arbitrary Sub-12px Font Sizes**: Replaced arbitrary Tailwind classes (`text-[10px]`, `text-[11px]`) and static unscaled `text-xs` (12px) across [`dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html), [`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html), [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html), [`login.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/registration/login.html), and [`base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html) with responsive, legible type scales (`text-xs sm:text-sm`, `text-sm sm:text-base`).
  - **iOS Safari Involuntary Auto-Zoom Prevention**: Upgraded all interactive text inputs, selects, and textareas across forms (`ProductIntakeForm`, `ProductUpdateForm`) and templates to render at `>= 16px` (`text-base sm:text-sm`) on mobile viewports with an explicit CSS safeguard:
    ```css
    @media (max-width: 640px) {
      input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea {
        font-size: 1rem !important; /* >= 16px prevents iOS Safari auto-zoom */
      }
    }
    ```
  - **WCAG 2.1 AA Zoom Compliance & OS Dynamic Type Scaling**: Removed `maximum-scale=1.0, user-scalable=no` from [`base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html), satisfying WCAG 2.1 AA (SC 1.4.4 Resize text) allowing standard 200% pinch-to-zoom. Added `<meta name="text-scale" content="scale">` to support OS accessibility font scaling preferences.
  - **Automated Playwright Typography Tests & Mobile Visual Captures**: Added `test_mobile_typography_and_input_font_sizes` in [`tests/test_dashboard_responsive.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_dashboard_responsive.py) asserting computed `fontSize >= 16px` on standard mobile viewports ($390 \times 844$) and generated visual audit captures: `mobile_login_390x844.png`, `mobile_intake_390x844.png`, and `mobile_product_detail_390x844.png`.
- **Dashboard Status Toolbar Modernization & Horizontal Scroll Rail (Elimination of Apilación)**:
  - **Architecture Decoupling**: Refactored [`inventory/templates/inventory/dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html) to decouple the status navigation tabs from the action/filter toolbar (search input and platform dropdown), preventing awkward vertical stacking/apilación on mobile and tablet devices.
  - **Single-Line Horizontal Scroll Rail**: Built a dedicated `<nav role="tablist">` container utilizing `overflow-x-auto`, `flex-nowrap`, and `whitespace-nowrap` with vendor-prefixed scrollbar suppression (`scrollbar-none`, `-webkit-overflow-scrolling: touch`), allowing all 7 lifecycle status tabs (*Todos*, *Activo*, *Precio pendiente*, *Listo para publicar*, *Dudas*, *Bloqueado*, *Vendido*) to sit on a clean, scrollable horizontal track without wrapping.
  - **WCAG 2.1 AA Touch Targets**: Upgraded all status tab links to full-height touch targets (minimum 36px–40px height on mobile / 32px on desktop) with prominent pill counters and focus indicators.
  - **Automated Playwright Multi-Viewport Verification**: Added `test_dashboard_responsive_tabs_no_apilation` in [`tests/test_dashboard_responsive.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_dashboard_responsive.py) executing real Chrome tests across 4 standard viewports (390px, 768px, 1024px, 1440px), verifying tab rail visibility, touch target heights, and strictly asserting that all tabs share the same vertical offset ($\Delta \le 4\text{px}$) with zero apilación. Captured visual audit screenshots in `browser_verification_screenshots/`.
- **Automated E2E Workday Verification Suite & Comprehensive Normal Day Workflows**:
  - Implemented comprehensive workday automated workflow script [`verify_workday_all_cases.py`](file:///C:/Users/Jose/antigravity/epic-tesla/verify_workday_all_cases.py) and test suite covering all cases and combinations: assistant login, intake preflight, clarification question creation, doubts filtering, assistant reply, auto-transition to ready, price pending staging, sale price assignment, external marketplace link management (Vinted, Wallapop), sold status marking, and unsold status reversal.
  - Captured full visual verification screenshots in `browser_verification_screenshots/`.
- **Installable PWA Support, VAPID Web Push Infrastructure & `.env`-Guarded Live Signal Triggers**:
  - **W3C Web App Manifest & Icons**: Added [`manifest_view`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py) serving `/manifest.json` (`display: standalone`, `scope: /`, `theme_color: #059669`, shortcuts for Intake, Dashboard, and Pending Doubts) and generated branded PNG icons (`icon-192.png`, `icon-512.png`, `apple-touch-icon.png`) under `inventory/static/inventory/icons/`.
  - **Root Pass-Through Service Worker (`/sw.js`)**: Added [`service_worker_view`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py) and [`inventory/templates/inventory/sw.js`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/sw.js) with `Service-Worker-Allowed: /`, zero-cache pass-through `fetch` handler (preventing stale HTML/CSRF tokens), `push` notification display with `tag` deduplication and `navigator.setAppBadge` support, and `notificationclick` deep-linking.
  - **VAPID Key Generator & Push Dispatcher Service**: Added [`generate_vapid_keys`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/management/commands/generate_vapid_keys.py) management command (`ECDSA P-256` Base64URL keypair) and [`inventory/services/push_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/push_service.py) (`send_push_to_subscription`, `send_push_to_user`, `send_push_to_group`) with automatic dead-endpoint pruning on HTTP `404`/`410 Gone`.
  - **`PushSubscription` Model, Admin & JSON Endpoints**: Added [`PushSubscription`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py) model (`0013_pushsubscription.py`), `PushSubscriptionAdmin` with `"Send test push notification"` action in [`inventory/admin.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/admin.py), and authenticated JSON routes `POST /api/push/subscribe/`, `POST /api/push/unsubscribe/`, and `POST /api/push/test/`.
  - **Navbar & Mobile Drawer Notification Toggles**: Updated [`inventory/templates/inventory/base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html) and [`inventory/context_processors.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/context_processors.py) (`pwa_push`) with desktop (`#push-toggle-btn`) and mobile (`#mobile-push-toggle-btn`) opt-in/out controls, test push trigger, and iOS Home Screen standalone guidance.
  - **`.env`-Controlled Live Workflow Signals (`PUSH_NOTIFICATIONS_LIVE_SIGNALS`)**: Added signal-driven push alerts in [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py) notifying `assistants` on new clarification doubts and notifying `managers` on answered doubts, new `DRAFT` intakes, and `PRICE_PENDING` transitions when `PUSH_NOTIFICATIONS_LIVE_SIGNALS=True`.
- **Refined Product Lifecycle State Machine & Automated State Transitions**:
  - Implemented automated state machine in [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py) (`compute_lifecycle_status()` and `sync_lifecycle_status()`):
    - `DRAFT`: Products lacking AI/final description (`not ai_description`).
    - `PRICE_PENDING`: Products with title and description, but no sale price (or `sale_price <= Decimal("0.00")`).
    - `READY`: Products with title, description, and price > 0, but no active external marketplace links.
    - `PUBLISHED`: Automatically assigned as soon as any active external marketplace listing link (`ProductListingLink`) is added.
    - `AWAITING_INFO` / `BLOCKED` / `SOLD`: Unsold or clarification resolution events dynamically re-evaluate the state machine.
  - Connected automated post-save and post-delete signals on `ProductListingLink` and `ProductClarification`.
  - Created and applied database migration `0012_add_lifecycle_states_and_sync.py`.
  - Added unit test suite [`tests/test_lifecycle.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_lifecycle.py) verifying all lifecycle permutations.
- **Intake Vision AI Model Upgrade (`gemini-flash-latest`) & Hidden Title Autofill**:
  - Upgraded [`identify_intake_product`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py) model constant to `gemini-flash-latest`.
  - Added hidden `ai_title` input to `ProductIntakeForm` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py) and [`inventory/templates/inventory/intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html).
  - Populated `#id_ai_title` automatically via client-side JavaScript upon pre-flight AI identification, eliminating generic `Producto #XX` placeholder titles without cluttering the assistant intake view.
- **Catalog Dashboard "Precio pendiente" Filter Tab & Status Badges**:
  - Added `status=price_pending` filter query handling and scoped `price_pending_count` aggregation in [`inventory/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py).
  - Added dedicated "Precio pendiente" tab with live count badge `({{ price_pending_count }})` in [`inventory/templates/inventory/dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html).
  - Added badge styling for `PRICE_PENDING` (amber) and `PUBLISHED` (cyan/blue) across dashboard cards and product detail views.
  - Added Spanish translations in `locale/es/LC_MESSAGES/django.po` compiled to `django.mo`.
- **End-to-End Real Chrome Lifecycle Verification Suite**:
  - Added [`tests/test_browser_lifecycle.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_browser_lifecycle.py) testing all 11 lifecycle stages in Google Chrome via Playwright.
  - Captured full visual verification screenshots in `screenshots/`.
- **Clarification Status Synchronization, Orphan Product Prevention & Dudas Badge Accuracy**:
  - **Root Cause Resolution**: Diagnosed and resolved the persistent active `❓ Dudas` navbar badge and phantom/orphan product behavior (`Product ID=81` with note `"Mobile Nav Test Jacket"`):
    1. *Inconsistent Product Status*: The test product had an unresolved clarification question (`"Check shoulder width?"`) but had its `Product.status` set to `draft` (rather than `awaiting_info`).
    2. *Query Discrepancy*: The navbar badge counted all pending clarification records (`pending_clarifications_count`), but the dashboard view filtered strictly by `Product.status == ProductStatus.AWAITING_INFO`. As a result, the badge showed 1 (or N+1), but clicking the button displayed 0 products in the list because the product was in `draft` state.
  - **Model Signal Synchronization**: Implemented `post_save` and `post_delete` signals on `ProductClarification` in [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py):
    - Automatically sets `Product.status = AWAITING_INFO` whenever a clarification is created or marked `PENDING` (unless the product is sold).
    - Automatically transitions `Product.status` to `READY` when all pending clarifications on a product are resolved or deleted.
  - **Context Processor Exclusions**: Updated `notifications(request)` in [`inventory/context_processors.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/context_processors.py) to exclude sold items (`product__is_sold=False` and `.exclude(product__status=ProductStatus.SOLD)`).
  - **Dashboard Filter Hardening**: Updated `dashboard_view` in [`inventory/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py) so filtering by `status=awaiting_info` and tab counts evaluate `Q(status=ProductStatus.AWAITING_INFO) | Q(clarifications__status=ClarificationStatus.PENDING, is_sold=False)`. This ensures any product with unresolved doubts is never orphaned or invisible when clicking the doubts button.
  - **Form Validation Guard**: Added validation to `ProductUpdateForm` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py) preventing products from being manually marked as `Ready to Publish` while unresolved clarifications remain.
  - **Data Migration**: Added `inventory/migrations/0011_sync_product_clarification_status.py` healing existing mismatched records across environments.
  - **Automated Regression Test Suite**: Added `ClarificationLifecycleSynchronizationAndOrphanPreventionTests` in [`tests/test_clarifications.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_clarifications.py) verifying signal transitions, sold item exclusion, form validation, and dashboard inclusion.
- **Production Role Groups Seeding, Docker Initialization & CustomGroupAdmin**:

  - **Root Cause Resolution**: Identified and resolved the two underlying causes preventing Django user groups (`assistants`, `managers`) from being available in production Docker containers:
    1. *Missing Migration Data Seeding*: Docker's production entrypoint runs `python manage.py migrate --noinput`. Previously, groups were only created manually via `setup_roles` or local superuser scripts. No data migration existed to initialize the `auth_group` table on clean database volumes.
    2. *Django Admin Permission Gating*: `Group` was registered with Django's default `GroupAdmin`, which requires superuser privileges or `auth.view_group` permissions. Standard store managers (`is_staff=True, is_superuser=False, groups=['managers']`) were denied module access (HTTP 403 Forbidden) and groups were completely hidden from their admin index.
  - **Automatic Data Migration**: Created `inventory/migrations/0010_seed_default_groups.py` ensuring `assistants` and `managers` groups are idempotently seeded whenever migrations are applied.
  - **Post-Migrate Signal (Defense-in-Depth)**: Connected `ensure_default_role_groups` to the `post_migrate` signal in [`inventory/apps.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/apps.py) guaranteeing groups exist across all environments, CI runs, and database resets.
  - **Production Entrypoint Hardening**: Updated [`docker/entrypoint.sh`](file:///C:/Users/Jose/antigravity/epic-tesla/docker/entrypoint.sh) to execute `python manage.py setup_roles --no-demo-users` during container boot, verifying and logging role initialization to stdout.
  - **CustomGroupAdmin Implementation**: Implemented `CustomGroupAdmin` in [`inventory/admin.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/admin.py) inheriting from `GroupAdmin`, overriding permission hooks (`has_module_permission`, `has_view_permission`, `has_change_permission`, `has_add_permission`, `has_delete_permission`) to grant store managers full access, and adding a members count column (`user_count`) annotated via `Count("user")`.
  - **Automated Regression Test Suite**: Added test coverage in [`tests/test_admin_user_management.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_admin_user_management.py) verifying group access for store managers, group visibility in admin index, member count displays, and strict HTTP 403 denial for non-manager assistants.
- **Intake Photo Preview Management, Deletion & FileList Synchronization**:
  - Implemented client-side photo state management in [`inventory/templates/inventory/intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html) tracking chosen files in an in-memory array `selectedFiles: File[]`.
  - Added cumulative photo capture: selecting files or taking pictures with a smartphone camera appends newly selected valid files to `selectedFiles` up to the 10-image maximum rather than replacing previous selections.
  - Built synchronization engine `syncFileInput()` utilizing standard HTML5 `DataTransfer` to keep `imageInput.files` perfectly synchronized with `selectedFiles` whenever photos are added or deleted.
  - Implemented interactive preview cards in `#previewGrid` with index badges (`#1`, `#2`, ...) and accessible top-right delete buttons ("✕") providing a minimum 44×44px interactive touch target meeting WCAG 2.1 AA.
  - Added single photo deletion: tapping "✕" prevents event propagation, removes the photo from `selectedFiles`, resynchronizes `imageInput.files`, dynamically re-indexes remaining badges, and updates the counter text (`X / 10 selected`).
  - Added form state guarding: all delete buttons are disabled (`pointer-events-none opacity-50 cursor-not-allowed`) during `'identifying'` and `'submitting'` states.
  - Retained active AI pre-flight identification advisory banner when deleting individual photos, resetting only if all photos are removed.
  - Added Spanish translations in `locale/es/LC_MESSAGES/django.po` compiled to `django.mo`.
  - Added comprehensive test coverage in [`tests/test_intake.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_intake.py) and verified full end-to-end user workflows using real Google Chrome via Playwright (`verify_intake_photo_management_browser.py`).
- **Responsive Mobile Navigation Header & Collapsible Hamburger Drawer**:

  - Refactored top navigation header in [`inventory/templates/inventory/base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html) with responsive Tailwind breakpoint (`md:` / 768px), keeping full horizontal navigation on desktop while simplifying mobile headers.
  - Decluttered mobile viewports (< 768px) down to the brand logo, urgent doubts badge `❓ (X)`, and a prominent 44×44px hamburger toggle button (`#mobile-menu-button`).
  - Added an accessible mobile collapsible drawer (`#mobile-menu`) styled as a sticky dropdown accordion (`bg-white border-b border-slate-200 shadow-lg`) directly beneath the header.
  - Provided vertical hierarchy in mobile drawer: user profile card with role badge, highlighted New Intake button, Dashboard link, Doubts link, conditional Administration Panel link (managers only), full-width segmented bilingual switcher (`🇬🇧 English` / `🇪🇸 Español`), and isolated Sign Out button.
  - Built vanilla JavaScript interaction handling: animated SVG icon toggle (☰ to ✕), `aria-expanded` updates, keyboard `Escape` dismissal returning focus to button, outside-click close, and auto-reset when viewport is resized to `≥ md`.
  - Added Spanish translation strings (`Open menu`, `Close menu`, `Mobile navigation`, `Administration Panel`) to `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
  - Added test suite `MobileNavigationTests` in [`tests/test_views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_views.py) and end-to-end browser automation script in Playwright (`verify_mobile_nav_browser.py`) testing mobile iPhone 14 viewport (390×844) and desktop switching.
- **Intake Form Async Protection, Double-Submit Prevention & Client-Side Validation**:
  - Implemented client-side tri-state machine (`idle`, `identifying`, `submitting`) in [`inventory/templates/inventory/intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html) managing user interaction during asynchronous operations and network requests.
  - Added asynchronous operation blocking: clicking "Identificar producto" sets `formState = 'identifying'`, disables the submit button (`#submitBtn`) with reduced opacity and informative tooltip (*"Espera a que finalice el análisis con IA..."*), and locks the photo dropzone (`pointer-events-none opacity-70`) to prevent race conditions or mutating photos mid-analysis.
  - Implemented double-submit prevention with a synchronous boolean latch (`isSubmitting = true`), disabling the submit button, showing an animated SVG spinner, updating label to *"Guardando producto..."*, and setting `pointer-events-none` on form controls. Repeated taps or accidental double-clicks during in-flight submissions are intercepted and rejected, completely eliminating duplicate POST requests and duplicate product records in the database.
  - Replaced native browser `window.alert()` popups with an accessible inline alert banner (`#intakeClientAlert`) adhering to WCAG 2.1 AA (`role="alert"`, `aria-live="polite"`).
  - Added client-side zero-photos validation on submission, displaying an accessible warning message, applying a temporary warning ring (`border-rose-400 ring-2 ring-rose-200 bg-rose-50/40`) to `#dropZone`, and scrolling smoothly to the dropzone.
  - Added pre-upload file guards inspecting image selection: rejecting batches >10 photos and inspecting `file.size > 10MB` client-side with explicit filename and MB size feedback before network transmission starts.
  - Configured automatic clearing of the dropzone error ring and alert banner as soon as at least one valid image is selected.
  - Added graceful recovery handling on network fetch errors, timeouts, and browser BFCache history navigation (`pageshow` event).
  - Added Spanish translations in `locale/es/LC_MESSAGES/django.po` compiled to `django.mo`.
  - Added comprehensive test coverage in [`tests/test_intake.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_intake.py) and verified full end-to-end user workflows using real Google Chrome via Playwright.
- **Smart Intake Pre-flight: On-Demand Item Identification, Advisory Guidance & Direct Pricing**:
  - Implemented `identify_intake_product()` and `IntakePreflightSchema` in [`inventory/services/ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py) querying Google Gemini Multimodal Vision API (`gemini-2.5-flash`) with structured output.
  - Capped multimodal image payload to the first 3 photos (`images_bytes[:3]`) with in-memory MIME detection to minimize upload payload and latency on mobile connections.
  - Built asynchronous endpoint `POST /inventory/intake/identify/` (`intake_identify_view` in [`inventory/views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/views.py)) gated by `@login_required` with image count/format validation.
  - Integrated mobile intake UI in [`inventory/templates/inventory/intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html):
    - Added "🔍 Identificar producto" button toggling enabled state on photo selection with animated spinner and loading feedback.
    - Added non-blocking advisory alert banner above field notes displaying identified product name, category, detected attributes, and actionable inspection checklists (size tags, sole wear, flaws).
    - Added one-click "Añadir sugerencia a notas" smart append button populating or appending to `raw_note`.
    - Added direct manual `sale_price` capture on `ProductIntakeForm` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py) persisting directly to `product.sale_price` in Euro (`€`).
  - Added complete Spanish translations in `locale/es/LC_MESSAGES/django.po` compiled to `django.mo`.
  - Added unit and integration tests across [`tests/test_ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_ai_service.py), [`tests/test_views.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_views.py), and [`tests/test_intake.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_intake.py).
- **SQLite Automated Cloud Backup to OCI Object Storage**:
  - Implemented automated, zero-downtime hot backups using SQLite's native online backup API (`sqlite3.Connection.backup()`), guaranteeing database consistency without table locks or risk of WAL torn pages during active writes.
  - Added in-memory `gzip` compression pipeline (`.sqlite3.gz`), reducing backup storage volume by ~80-90% before transmission.
  - Built direct cloud upload to Oracle Cloud Infrastructure (OCI) Object Storage bucket under `backups/db/%Y/%m/` via project storage abstraction (`django-storages[boto3]`).
  - Added automated lifecycle retention pruning deleting snapshots older than 30 days (`DB_BACKUP_RETENTION_DAYS`) after each backup run.
  - Created Django management command `python manage.py backup_db` with CLI options (`--retention-days`, `--no-compress`, `--local-only`, `--dry-run`, `--quiet`) returning exit codes 0/1 for cron scheduling.
  - Created `DatabaseBackupLog` audit log model and `DatabaseBackupLogAdmin` in `ManagerAdminSite` with read-only metrics, color-coded status badges, and formatted file sizes.
  - Built on-demand "Crear copia de seguridad ahora" confirmation flow in Django Administration allowing store managers to trigger immediate cloud snapshots with flash feedback.
  - Added prominent failure alert banner (`backup-failure-alert`) rendered across Django administration pages whenever the most recent backup attempt fails.
  - Added complete Spanish translations in `locale/es/LC_MESSAGES/django.po` and 34 comprehensive tests in `tests/test_backup.py`.
- **Cloudflare Turnstile Bot & Login Protection**:
  - Integrated Cloudflare Turnstile smart challenge protection across all authentication entry points: public staff login (`/login/` / `CustomLoginView`) and Django administration login (`/admin/login/` / `ManagerAdminSite`).
  - Implemented `verify_turnstile_token` in [`inventory/services/turnstile_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/turnstile_service.py) with a 5.0s timeout and fail-closed security policy against credential stuffing and brute-force bot attacks.
  - Built `TurnstileValidationMixin` in [`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py) executing challenge verification prior to password hashing, conserving server CPU during attack bursts.
  - Added `TurnstileAuthenticationForm` to `CustomLoginView` and `TurnstileAdminAuthenticationForm` to `ManagerAdminSite.login_form`.
  - Created global `turnstile` context processor in [`inventory/context_processors.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/context_processors.py) injecting `TURNSTILE_SITE_KEY` and `TURNSTILE_ENABLED` into templates.
  - Updated [`login.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/registration/login.html) and created [`admin/login.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/admin/login.html) with responsive light-theme widgets (`data-theme="light"`), async script loading, and clear non-field error reporting.
  - Added support for Cloudflare official test dummy keys and automated bypass when `TURNSTILE_ENABLED=False` for offline dev and CI workflows.
  - Localized challenge validation messages in Spanish and added 25 automated tests in [`tests/test_turnstile.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_turnstile.py).
- **Production Containerization (Docker & Docker Compose)**:
  - Created production-grade [`Dockerfile`](file:///C:/Users/Jose/antigravity/epic-tesla/Dockerfile) based on `python:3.13-slim-bookworm` configured with an unprivileged non-root user (`appuser:appgroup`, UID 10001) for least-privilege security.
  - Added Gunicorn (`gunicorn>=23.0.0`) production WSGI HTTP server with 3 sync workers and a 120s request timeout to support AI multimodal requests.
  - Configured WhiteNoise (`whitenoise>=6.8.0`) to compress, hash, and serve static assets directly from `/app/staticfiles`, eliminating the need for a separate Nginx container in simple deployments.
  - Built an automated startup entrypoint script ([`docker/entrypoint.sh`](file:///C:/Users/Jose/antigravity/epic-tesla/docker/entrypoint.sh)) that handles database migrations and static collection automatically on container boot.
  - Added native container healthcheck polling the root endpoint via `curl` with 30s intervals.
  - Provided multi-container orchestration via [`docker-compose.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/docker-compose.yml) with persistent volumes for SQLite data (`secondhand_data`) and user photos (`secondhand_media`), plus an optional PostgreSQL profile (`--profile postgres`).
  - Added [`README.md`](file:///C:/Users/Jose/antigravity/epic-tesla/README.md) with comprehensive container and local setup documentation.

### CI/CD & Automation
- **GitHub Actions Quality Gates & GHCR Publishing ([`.github/workflows/ci.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/.github/workflows/ci.yml))**:
  - Implemented automated Shift-Left quality gates on every pull request and push to `master`:
    1. *Gate 1*: Code linting and style compliance via `ruff check .`.
    2. *Gate 2*: Django system and deployment security checks via `python manage.py check`.
    3. *Gate 3*: Full automated test suite execution (`python manage.py test`, 162 tests).
    4. *Gate 4*: Docker container image build with GitHub Actions layer caching.
    5. *Gate 5*: Container non-root execution verification (`id -u != 0`).
    6. *Gate 6*: Container boot smoke test, polling healthcheck and verifying expected HTML application response.
    - Added automated `publish-image` job pushing production multi-architecture Docker images (`linux/amd64` and `linux/arm64`) to **GitHub Container Registry (GHCR)** via QEMU emulation (`ghcr.io/saert3311/2nd-hand-manager:latest` and SHA tag) upon successful master builds.
- **Production Container Orchestration & CD ([`docker-compose.prod.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/docker-compose.prod.yml))**:
  - Configured standalone production compose using pre-built GHCR image with persistent volumes (`secondhand_data`, `secondhand_media`) and fallback `build` context for native ARM/local builds.
  - Added Watchtower service for continuous hands-free deployment: automatically pulls new GHCR images, gracefully restarts the container, and prunes old images.
  - Added attachment to external Docker network `supabase-net` enabling private ingress via Cloudflare Tunnel (`cloudflared`) without exposing container ports to the public internet.
  - Added Django reverse proxy headers (`SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST`) and configurable `CSRF_TRUSTED_ORIGINS` in [`config/settings.py`](file:///C:/Users/Jose/antigravity/epic-tesla/config/settings.py) for secure HTTPS routing behind Cloudflare.

### Security & Hardening
- **Multi-Axis Quality Review & Input Boundary Hardening**:
  - Conducted five-axis review (Correctness, Readability, Architecture, Security, Performance) and threat analysis across intake, staging, AI generation, and marketplace publishing flows.
  - Hardened `ProductListingLink.url` and `MarketplaceSite.base_url` models with `HTTP_URL_VALIDATOR` (`schemes=["http", "https"]`), preventing execution of `javascript:`, `data:`, and non-HTTP URL schemes at model, form, and admin boundaries.
  - Enforced server-side length limits on clarification models and forms (`ProductClarificationForm.question` capped at 2,000 chars, `ProductClarificationAnswerForm.answer` capped at 3,000 chars).
  - Hardened upload validation pipeline in `inventory/services/image_service.py` with explicit rejection of 0-byte/empty files, safe error conversion for truncated/corrupted images, rejection of polyglot/SVG files, and sanitization of filenames against directory traversal exploits (`clean_stem`).
  - Implemented defensive clamping on AI-generated listing titles (`[:255]`) in `inventory/views.py` to prevent database overflow from unexpectedly long LLM responses.
  - Verified 100% safe rendering without XSS across all templates (`product_detail.html`, `dashboard.html`, `intake.html`, `base.html`), ensuring complete HTML escaping and secure `escapejs` attribute passing.
  - Added 11 automated security tests in `tests/test_security.py` bringing the test suite to 162 passing tests.

## [1.1.0] - 2026-10-12

### Added
- **Product Clarification Feedback Loop & Granular Lifecycle States (`ProductStatus`, `ProductClarification`)**:
  - Transitioned product domain model from binary `is_sold` to a structured lifecycle state machine: `DRAFT`, `AWAITING_INFO`, `READY`, `SOLD`, and `BLOCKED` with bidirectional synchronization and 100% backward compatibility for legacy `is_sold` queries and tests.
  - Added `ProductClarification` model supporting categorized questions (*Medidas*, *Etiqueta*, *Defectos*, *Material*, *General*) asked by store managers and answered by sourcing assistants.
  - Global `notifications` context processor surfacing pending clarification counters via a high-visibility animated navbar badge (`❓ Dudas (X)`) and an intake banner alert alerting mobile assistants to open doubts.
  - Dedicated staging Q&A card on `/products/<pk>/` with category selectors, manager question creation/dismissal, and assistant mobile answer submissions.
  - Auto-state transition: answering all pending questions on a product automatically shifts its lifecycle status to `READY` and displays a visual callout (`ai-regeneration-callout`) prompting the manager to re-run Gemini Vision.
  - Marketplace publishing caution gate (`publishing-gate-caution`) warning managers if a product has unresolved doubts or is blocked before publishing external links.
  - AI Prompt Enrichment: `generate_product_listing` dynamically formats and appends resolved clarification Q&As into the Gemini Multimodal Vision prompt for higher accuracy listings.
  - Catalog Dashboard Filtering: Added `status=awaiting_info` and `status=blocked` filter tabs with dynamic status counter badges scoped to active search and marketplace platform filters.
  - Full Spanish translation catalog and 22 new unit & integration tests in `tests/test_clarifications.py`.
- **Dashboard Marketplace Platform Filter**:
  - Dynamic platform selector on the inventory dashboard (`/dashboard/`) displaying only resale platforms that currently have at least one active product link (`product_links__is_active=True`), annotated with their published product count (e.g. `Wallapop (12)`, `Vinted (8)`). Platforms with 0 published items are strictly omitted.
  - Seamless auto-submission on selection (`onchange="this.form.submit()"`) with full filter state preservation across status tabs (`status=active`, `status=sold`, `status=all`), unified search queries (`q`), and pagination (`page`).
  - Dynamic status counters scoping: when a platform filter is active, dashboard counters ("All", "Active", "Sold") dynamically update to reflect the counts of products published on that specific platform.
  - Visual platform badges on product catalog cards displaying live published channels.
  - Complete Spanish localization for all selector labels and accessibility strings.
  - 10 new unit and integration tests added to `tests/test_marketplace_sites.py` covering dynamic aggregation, platform filtering, status scoping, search combinations, invalid slugs, and pagination (129 total passing tests).
- **Marketplace Sites & Product Listing Links Tracking (`MarketplaceSite`, `ProductListingLink`)**:
  - Configurable `MarketplaceSite` model managed in Django administration (`ManagerAdminSite`), enabling store managers to add, reorder (`order`), and toggle active status for resale platforms (Wallapop, Vinted, Milanuncios, eBay, Vestiaire Collective, Etsy, etc.).
  - Automatic database seed migration populating default active platforms: Wallapop, Vinted, Milanuncios, and eBay.
  - `ProductListingLink` model tracking external listing URLs per product with a database-level `UniqueConstraint(fields=['product', 'site'])` enforcing exactly one live ad link per platform per product.
  - Dedicated "Marketplace Listing Links" card on the product detail page (`/products/<pk>/`) displaying all active platforms with direct external link navigation (`target="_blank" rel="noopener noreferrer"`), one-click copy URL button, and manager-only link save/update/remove actions (with read-only view for assistants).
  - Django administration integration with `MarketplaceSiteAdmin` (list display, search, slug prepopulation) and `ProductListingLinkInline` on `ProductAdmin`.
  - Full Spanish localization across model fields, admin forms, and product detail templates.
  - Comprehensive automated test suite in `tests/test_marketplace_sites.py` covering model constraints, admin permissions, product page CRUD, and URL validation (119 total passing tests).
- **Dynamic AI Model & Prompt Configuration (`AIPromptConfiguration`)**: Database-backed configuration model registered in Django administration allowing store managers to configure Gemini model identifiers (free-form text, e.g. `gemini-2.5-flash`, `gemini-2.5-pro`), sampling temperature (`0.0`–`1.0`), and custom copywriting instructions per language (`es`, `en`).
- **Resilient AI Service Fallback & Schema Protection**: Decoupled prompt architecture in `inventory/services/ai_service.py` that merges custom marketing tone instructions into an immutable JSON schema envelope (`ProductListingSchema`) and assistant field notes (`product.raw_note`). Automatically falls back to code defaults if database records are missing or on database errors.
- **Automatic Configuration Demotion**: Unique active configuration enforcement ensuring that saving a new active configuration for a language automatically demotes any previously active configuration for that language.
- **Bilingual AI Configuration Admin**: Full Spanish translation for all model field names, admin fieldsets, status badges, and help texts.
- **Automated AI Configuration Test Suite**: Added comprehensive test coverage in `test_models.py` and `test_ai_service.py` validating database overrides, temperature forwarding, demotion logic, fallback resilience, and schema stability (101 total passing tests).
- **Manager-Only Django Admin Gating (`ManagerAdminSite`)**: Strict role-based boundary restricting `/admin/` access exclusively to managers (`is_manager(user)`). Authenticated assistants attempting to access the administration site receive an explicit HTTP 403 Forbidden response.
- **User Management & Visual Role Badging**: Custom `UserAdmin` displaying color-coded role badges (Superuser in purple, Manager in emerald, Assistant in blue), role filtering (`RoleListFilter`), and cataloging productivity metrics (`cataloged_items_count`) linking directly to filtered product listings with zero N+1 queries.
- **Role Actions & Safe Offboarding**: Administrative actions to promote/demote between Manager and Assistant (automatically synchronizing `is_staff`), safely deactivate user accounts (`is_active = False`) to revoke login while preserving product authorship on `Product.created_by`, and reactivate users with self-deactivation protection.
- **Manager Operational Delegation**: Model permission overrides enabling store managers to add, update, and manage users and products without requiring superuser credentials.
- **Server-Side Catalog Pagination**: Paginated `/dashboard/` catalog listing capped at 20 products per page (`PAGE_SIZE = 20`) via Django `Paginator`.
- **Query-Preserving Pagination Navigation**: Responsive pagination controls with Previous/Next buttons, item summary counter ("Showing X to Y of Z products"), and elided page numbering retaining active status filters and search terms across pages.
- **Multi-Field & Date Search**: Unified search engine supporting text containment across `ai_title`, `raw_note`, and `ai_description`, along with automatic parsing of date strings (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM`, and `YYYY`) matched against `created_at` and `sold_at`.
- **Spanish Localization & Admin Translations**: Full bilingual translation coverage for all admin site titles, role badges, action messages, pagination counters, and search placeholders.
- **Comprehensive Automated Tests**: Expanded test suite to 93 passing tests with 23 new unit, integration, and security tests covering pagination boundaries, query retention, multi-format date searches, and admin role gating/permissions.

## [1.0.0] - 2026-10-10

### Added
- **Mobile-First Product Intake**: Instant camera capture and upload of up to 10 photos with client-side live preview thumbnails and field notes capture.
- **In-Memory WebP Processing**: Automated EXIF orientation correction and high-efficiency WebP compression via Pillow without local disk persistence.
- **Oracle Cloud Infrastructure (OCI) Object Storage**: Direct S3-compatible cloud storage integration for all product images with S3 payload signing and checksum compatibility fixes.
- **Manager Catalog Dashboard**: Central inventory overview featuring search across titles/notes, status filter tabs (All, Active, Sold), and fast single-query SQL aggregation.
- **Product Staging & Photo ZIP Bundles**: Detailed staging page with interactive photo gallery and single-click in-memory streaming ZIP archive download (`.zip`).
- **Gemini Multimodal Vision AI**: Automated drafting of SEO-friendly marketplace titles and bulleted sales copy from photos and notes via Google Gemini Flash.
- **One-Click Clipboard Copy**: One-click copying for generated listing titles and descriptions with instant visual feedback.
- **Sales & Pricing Tracking**: Euro (`€`) sale price validation and marking items as Sold with recorded timestamps.
- **Multi-Language (i18n) Localization**: Automatic browser language detection (`Accept-Language: es`), manual navbar language switcher (`🇬🇧 EN` / `🇪🇸 ES`), complete Spanish translation catalog, localized Gemini prompting, and portable `compile_locales` management command using `polib`.
- **Security & Hardening**:
  - Safe DOM element construction eliminating client-side `innerHTML` XSS vectors.
  - URL-encoded search query links preventing attribute breakouts.
  - Model and form validation enforcing non-negative prices `[0.00, 9999999.99]` and 5,000 character limit on field notes.
  - Pixel flood / decompression bomb defense with `Image.MAX_IMAGE_PIXELS` cap and format whitelisting (`JPEG`, `PNG`, `WEBP`, `GIF`, `TIFF`, `BMP`, `MPO`).
  - HTTP security headers (`X-Frame-Options: DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`, `HttpOnly`, `SameSite=Lax`).
- **Comprehensive Automated Test Suite**: 70 offline unit, integration, and security tests covering domain models, auth, intake, dashboard, ZIP downloads, Gemini AI, localization, cloud storage, and XSS/input security.
- **Real Browser End-to-End Verification**: Automated Chrome Playwright workflow verifying multi-language intake, cloud uploads, thumbnail rendering, interactive gallery switching, ZIP extraction, and sales status updates.
