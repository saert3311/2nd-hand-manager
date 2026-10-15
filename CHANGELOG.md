# Changelog

All notable changes to the **2ndHand Staging Hub** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
