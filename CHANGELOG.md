# Changelog

All notable changes to the **2ndHand Staging Hub** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-10-22

### Added
- **Public Marketplace Storefront Transformation — Rápido Pack (`rapidopack.es`, Phase 27)**:
  - **Domain Models & Official 12-Category Taxonomy**: Added `Category`, `StorefrontConfiguration` singleton (`get_solo()`), and `ProductCondition` (`new_with_tags`, `very_good`, `good`, `vintage`) in `inventory/models.py`, extended `Product` with `category`, `condition`, `is_public`, `is_featured`, `is_reserved`, `reserved_until`, `views_count`, and `whatsapp_clicks`, added `ProductListingLink.clicks_count`, and implemented `ProductQuerySet.public_visible()` with 7-day `SOLD` social proof retention. Seeded all 12 official Rápido Pack categories and default `StorefrontConfiguration` (`Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia`) in migration `0017_marketplace_storefront.py`.
  - **SQLite WAL Mode & Concurrency Tuning**: Enabled `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` on SQLite connections in `inventory/apps.py`.
  - **AI Taxonomy Auto-Classification & `classify_products` Command**: Extended `ProductListingSchema` and `IntakePreflightSchema` in `inventory/services/ai_service.py` with `category_slug` and `condition`, plus deterministic keyword fallback `infer_taxonomy_heuristically()`. Added `python manage.py classify_products` CLI command to classify existing products.
  - **Dedicated `storefront` Application & Stitch Design System**: Created `storefront/` app serving `/` (`storefront:catalog`), `/p/<slug>-<pk>/` (`storefront:product_detail`), `/go/whatsapp/<pk>/` (`storefront:go_whatsapp`), `/go/link/<link_pk>/` (`storefront:go_marketplace_link`), `/sitemap.xml`, `/robots.txt`, and RGPD/LSSI legal pages (`/legal/aviso-legal/`, `/legal/privacidad/`, `/legal/cookies/`). Moved internal staff root redirect to `/staff/` (`inventory:root`).
  - **Defense-in-Depth Public Data Firewall**: Enforced `.only(...)` SQL projection and `_sanitize_public_product()` in-memory clearing in `storefront/views.py` so `raw_note`, `ProductClarification`, and `created_by` are never exposed in public HTML, search, OpenGraph tags, JSON-LD, or sitemaps.
  - **Bilingual Localization & Automated Test Suite**: Updated `locale/es/LC_MESSAGES/django.po` and compiled `django.mo`. Added `tests/test_storefront.py` verifying visibility rules, 7-day sold retention, non-leak security firewall, catalog filters, click counters, SEO metadata, and AI taxonomy classification.

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
