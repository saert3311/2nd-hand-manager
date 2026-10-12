# Changelog

All notable changes to the **2ndHand Staging Hub** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
