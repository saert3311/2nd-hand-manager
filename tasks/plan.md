# Implementation Plan: Secondhand Inventory & Staging App

## Overview
A lightweight Django web application enabling a two-actor secondhand reselling workflow:
1. Field assistants snap photos and write quick raw notes from a mobile-friendly intake screen.
2. Managers use a central dashboard to inspect items, trigger Gemini Multimodal Vision AI to generate marketplace listing copy, download photos in a single `.zip` bundle, copy text to clipboard, and track sales status and Euro (`€`) prices.

All uploaded photos are postprocessed on the server with Pillow to auto-orient, compress, and store as `.webp` files.

---

## Architecture Decisions
- **Django App Structure:** Single focused app `inventory/` alongside project configuration `config/`.
- **Image Pipeline:** Dedicated `services/image_service.py` encapsulates Pillow operations. Images are transformed to WebP in-memory before saving to `media/products/%Y/%m/`.
- **AI Integration:** Dedicated `services/ai_service.py` using `google-genai` (Gemini Flash multimodal vision). Accepts image file pointers and raw notes, requests structured JSON response (`title`, `description`).
- **Archive Generation:** Standard library `zipfile` streams in-memory ZIP responses (`io.BytesIO`) directly to the browser for instant photo downloads.
- **Frontend Approach:** Django Templates styled with Tailwind CSS via CDN. Responsive mobile-first design for `/intake/` and desktop-optimized staging workflow for `/products/<pk>/`. Vanilla JavaScript for thumbnail previews and clipboard copy.
- **Permissions:** Built-in Django auth with two groups: `assistants` (intake & catalog view) and `managers` (AI trigger, pricing, status edits, downloads, admin).
- **Internationalization (i18n):** Django `LocaleMiddleware` with `Accept-Language` header detection, falling back to English (`en`). Manual language switcher via `set_language`. Windows-portable `.po` to `.mo` compilation using `polib`. Localized Gemini prompts matching UI language.
- **Cloud Asset Storage:** Oracle Cloud Infrastructure (OCI) Object Storage bucket replaces local disk storage via `django-storages[boto3]` using OCI's S3-compatible API endpoint with OCI Customer Secret Keys. Zero local disk footprint via in-memory WebP processing.

---

## Phases & Checkpoints

### Phase 1: Foundation & Domain Layer
- **Task 1:** Virtual Environment & Project Scaffolding
- **Task 2:** Domain Models (`Product`, `ProductImage`), Migrations & Admin
- **Task 3:** Pillow WebP Image Postprocessing Service & Unit Tests
- **Checkpoint 1 (Foundation):** Migrations apply cleanly, image service correctly validates and converts images to WebP, tests pass.

### Phase 2: Authentication & Assistant Intake (Vertical Slice 1)
- **Task 4:** Authentication & Role-Based Access Control
- **Task 5:** Mobile-First Product Intake Flow (Multi-upload, client preview, raw note saving)
- **Checkpoint 2 (Intake):** Assistant can log in, take/upload photos and notes, and images are saved on disk in WebP format.

### Phase 3: Manager Dashboard & Photo ZIP Bundle (Vertical Slice 2)
- **Task 6:** Manager Catalog Dashboard (Filters, search, product cards)
- **Task 7:** Product Detail Staging View & In-Memory ZIP Download
- **Checkpoint 3 (Catalog & Assets):** Manager can browse inventory, filter active/sold items, inspect staging page, and download the full `.webp` photo zip.

### Phase 4: Gemini Multimodal AI & Sales Tracking (Vertical Slice 3)
- **Task 8:** Gemini Multimodal Vision Service (`ai_service.py`)
- **Task 9:** AI Generation UI, One-Click Copy, and Sales Price / Sold Status Controls
- **Checkpoint 4 (Complete Flow):** Full end-to-end user journey works: intake -> dashboard -> AI generate -> copy copy -> download zip -> mark sold.

### Phase 5: Multi-Language (i18n) Support
- **Task 10:** Django i18n Configuration & Windows-Friendly PO/MO Compiler
- **Task 11:** UI Translation Coverage (Templates, Forms, Views, Navbar Switcher & Spanish PO/MO Catalog)
- **Task 12:** Localized Gemini AI Prompting & i18n Automated Tests
- **Checkpoint 5 (i18n Complete):** Bilingual UI verified with browser language detection, manual switcher, and localized AI outputs.

### Phase 6: Oracle Cloud Infrastructure Object Storage Integration
- **Task 13:** Dependency Installation & OCI Storage Backend Configuration (`django-storages[boto3]`)
- **Task 14:** In-Memory WebP Image Pipeline & Storage Decoupling (Zero local disk persistence)
- **Task 15:** Storage Integration Tests & Test Mocking
- **Checkpoint 6 (OCI Complete):** Product images upload to OCI bucket, local disk remains untouched, and all 51+ tests pass.

### Phase 7: Catalog Pagination & Multi-Field Search (Vertical Slice 4)
- **Task 16:** Multi-Field Search Query & Date Parser Logic (Title, description, raw notes, created/sold dates)
- **Task 17:** Dashboard Server-Side Pagination & Query-Preserving UI Navigation Bar (Max 20 items per page)
- **Task 18:** i18n Translation & Comprehensive Unit/Integration Test Suite
- **Checkpoint 7 (Pagination & Search Complete):** Dashboard cleanly paginates at 20 items per page, retains search and filter query parameters across pages, parses multiple date formats, supports Spanish/English, and all tests pass.

### Phase 8: User Management & Django Admin Role Gating (Vertical Slice 5)
- **Task 19:** Custom `ManagerAdminSite` restricting `/admin/` access strictly to managers (`is_manager(user)`) with HTTP 403 enforcement.
- **Task 20:** Enhanced `CustomUserAdmin` with role badges, cataloging productivity counts, custom filters, and automatic `is_staff` synchronization on save and bulk actions.
- **Task 21:** i18n Translations and Comprehensive Unit/Integration Test Suite for Admin User Management.
- **Checkpoint 8 (User Management Complete):** Only managers can access `/admin/`; assistants are strictly blocked with 403; managers can add, modify, deactivate, and remove assistants; productivity counts display; Spanish and English translations pass; all tests pass.

### Phase 9: Dynamic AI Model & Prompt Configuration (Vertical Slice 6)
- **Task 22:** `AIPromptConfiguration` Domain Model, Migrations & Initial Data Seed.
- **Task 23:** Django Admin Registration & Form Validation (`AIPromptConfigurationAdmin`).
- **Task 24:** AI Service Integration (`ai_service.py`) with Dynamic Lookup & Resilient Fallback.
- **Task 25:** i18n Translations and Comprehensive Test Suite for Dynamic AI Configuration.
- **Checkpoint 9 (Dynamic AI Complete):** Managers can tune model names (free-form), temperature, and prompt copywriting instructions in Django Admin; changes apply immediately to listing generation; deactivation automatically cascades; service falls back gracefully when DB records are absent; all tests pass.

### Phase 10: Marketplace Sites & External Listing Links Tracking (Vertical Slice 7)
- **Task 26:** Marketplace Platforms & Listing Links Domain Models, Migrations & Initial Seed (`MarketplaceSite`, `ProductListingLink`).
- **Task 27:** Django Admin Integration (`MarketplaceSiteAdmin` & `ProductListingLinkInline`).
- **Task 28:** Product Detail Page Listing Links Management (Form handling, template UI, external links, copy buttons).
- **Task 29:** i18n Translations & Comprehensive Test Suite for Marketplace Tracking (`tests/test_marketplace_sites.py`).
- **Checkpoint 10 (Marketplace Tracking Complete):** Managers can configure resale sites in admin, seed data populates default platforms (Wallapop, Vinted, Milanuncios, eBay), product detail page displays links with direct navigation and one-click copy, link creation/update/deletion works seamlessly with manager gating, translations pass, and all automated tests pass.

### Phase 11: Dashboard Marketplace Platform Filter (Vertical Slice 6)
- **Task 30:** Backend Filtering & Dynamic Platform Aggregation in `dashboard_view` (Filter by platform slug, annotate active published product count, scope status counters to selected platform).
- **Task 31:** Dashboard Template UI for Platform Selector & Multi-Filter Composition (Tailwind dropdown, auto-submit on change, state preservation across status tabs, search bar, and pagination).
- **Task 32:** i18n Translations & Comprehensive Automated Test Suite for Platform Filter (Update Spanish catalogs, unit & integration tests covering dynamic platform query, filtering, counter scoping, and multi-filter retention).
- **Checkpoint 11 (Platform Filter Complete):** Platform selector displays only platforms with active published products, filters catalog instantly on change, retains status/search/page query state, scopes status counters accurately, and passes all automated tests.

### Phase 12: Product Clarifications & Lifecycle States (Vertical Slice 8)
- **Task 33:** Domain Models & Migration for Lifecycle States & Clarifications (`ProductStatus` choices, `Product.status` field with legacy `is_sold` synchronization, `ProductClarification` model, Django admin registration).
- **Task 34:** Global Notification Context Processor, Top Nav Badge & Mobile Intake Banner (`notifications(request)` context processor, `pending_clarifications_count`, navbar `❓ Dudas (X)` attention badge, mobile `/intake/` alert banner).
- **Task 35:** Product Detail Staging Q&A UI & Clarification Interaction Flow (Lifecycle badge, Q&A card with category pills, manager question submission, assistant mobile reply form, auto-transition to `ready` upon resolution, AI regeneration callout, publishing gate warning).
- **Task 36:** Dashboard Status Filtering, Dynamic Status Counters & AI Prompt Integration (Dashboard filtering for `status=awaiting_info` and `status=blocked`, scoped status counters, Gemini multimodal vision prompt enrichment with resolved clarifications).
- **Task 37:** i18n Translations, Documentation & Regression Testing (Spanish translations in `locale/es/`, compilation, `CHANGELOG.md` update, full test suite execution, ruff linter verification).
- **Checkpoint 12 (Product Clarifications & Lifecycle States Complete):** Full lifecycle state machine active, managers can ask categorized questions, assistants receive badges and mobile alerts to answer, answered Q&A enriches Gemini descriptions, dashboard status filtering works, and all tests pass with 0 regressions.

### Phase 13: Cloudflare Turnstile Bot & Login Protection (Vertical Slice 9)
- **Task 38:** Configuration, Service & Context Processor (`config/settings.py`, `.env.example`, `inventory/services/turnstile_service.py`, `inventory/context_processors.py`, `tests/test_turnstile.py`).
- **Task 39:** Public Login Protection (`inventory/forms.py`, `inventory/views.py`, `inventory/templates/registration/login.html`, `tests/test_turnstile.py`).
- **Task 40:** Django Admin Login Protection (`inventory/forms.py`, `inventory/admin.py`, `inventory/templates/admin/login.html`, `tests/test_turnstile.py`).
- **Task 41:** i18n Translations, Documentation & Regression Testing (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `CHANGELOG.md`).
### Phase 14: SQLite Automated Cloud Backup & Disaster Recovery (Vertical Slice 10)
- **Task 42:** `DatabaseBackupLog` Domain Model & Migration (`inventory/models.py`, `inventory/migrations/`, `tests/test_backup.py`).
- **Task 43:** SQLite Hot-Backup, Compression & Cloud Upload Service (`inventory/services/backup_service.py`, `config/settings.py`, `.env.example`, `tests/test_backup.py`).
- **Task 44:** Django Management Command `backup_db` (`inventory/management/commands/backup_db.py`, `tests/test_backup.py`).
- **Task 45:** Django Admin Audit Log, Failure Alert Banner & On-Demand Backup Trigger (`inventory/admin.py`, `inventory/templates/admin/`, `tests/test_backup.py`).
- **Task 46:** i18n Translations, Documentation & Full Regression Suite (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `CHANGELOG.md`).
- **Checkpoint 14 (Automated SQLite Cloud Backup Complete):** Online hot backup creates uncorrupted snapshots during active writes, compressed `.sqlite3.gz` files upload to OCI Object Storage, retention prunes backups older than 30 days, managers can inspect audit logs and trigger backups in admin with failure banner alerting, and full test suite passes with 0 regressions.

### Phase 15: Smart Intake Pre-flight: On-Demand Item Identification, Advisory Guidance & Direct Pricing (Vertical Slice 11)
- **Task 47:** Optional Direct Sale Price on Intake Form (`inventory/forms.py`, `inventory/views.py`, `inventory/templates/inventory/intake.html`, `tests/test_views.py`).
- **Task 48:** AI Vision Pre-flight Service & Pydantic Schema (`inventory/services/ai_service.py`, `tests/test_ai_service.py`).
- **Task 49:** Asynchronous Pre-flight Endpoint (`inventory/views.py`, `inventory/urls.py`, `tests/test_views.py`).
- **Task 50:** Mobile Intake UI: On-Demand Identify Button, Loading State & Advisory Banner (`inventory/templates/inventory/intake.html`).
- **Task 51:** i18n Translations, Documentation & Full Regression Suite (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `CHANGELOG.md`).
- **Checkpoint 15 (Smart Intake Pre-flight & Direct Pricing Complete):** Assistants can trigger on-demand AI identification on `/intake/`, receive non-blocking advisory tips for missing details, apply suggested notes with smart append, enter optional sale prices in € that persist directly to the product, and pass all automated tests with 0 regressions.

### Phase 16: Intake Form Async Protection, Double-Submit Prevention & Client-Side Validation (Vertical Slice 12)
- **Task 52:** Accessible Client-Side File Validations (0 photos, >10 count, >10MB individual size) & Price Bounds without `alert()` (`inventory/templates/inventory/intake.html`, `tests/test_views.py`).
- **Task 53:** Form State Machine & Async Blocking (Disable submit button and dropzone during AI identification) (`inventory/templates/inventory/intake.html`, `tests/test_views.py`).
- **Task 54:** Double-Submit Prevention & Submit Loading State (`inventory/templates/inventory/intake.html`, `tests/test_views.py`).
- **Task 55:** i18n Spanish Translations, Unit/Integration Tests & Browser Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake.py`, `tests/test_views.py`, `CHANGELOG.md`).
- **Checkpoint 16 (Intake Form Async Protection & Client-Side Validation Complete):** Double-clicking submit button never triggers duplicate submissions; AI pre-flight locks submit and dropzone until finished; client validation alerts user of missing photos, >10 images, or >10MB files without browser `alert()`; error ring auto-clears on valid selection; full test suite and Playwright browser verification pass with 0 regressions.

---

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Large mobile image uploads causing memory bloat | High | Enforce max 10 images / 10MB per file; process images sequentially in memory using Pillow. |
| Gemini API downtime or missing API key | Medium | Graceful error handling in `ai_service.py` with friendly user alerts; support manual editing fallback. |
| Mobile browser camera compatibility | Medium | Use standard HTML5 `<input type="file" accept="image/*" capture="environment" multiple>` for maximum compatibility. |
| EXIF orientation bugs on mobile uploads | Low | Use `PIL.ImageOps.exif_transpose` during WebP conversion to normalize orientation. |
| Missing GNU gettext tools on Windows | High | Provide Python-native `compile_locales` management command using `polib` to compile binary `.mo` files without external tools. |
| Tests failing due to missing OCI cloud credentials | High | Keep default storage configurable with in-memory / local fallback in test runner so CI/local tests remain fast and offline. |
| Unsafe search queries or parameter injection | Medium | Parameterize all text queries and date lookups using Django ORM `Q` filters; escape query strings in templates with `|urlencode`. |
| Loss of active filter/search when clicking pagination links | Medium | Pass active query string parameters (`status`, `q`) to template context and append to page URLs. |
| Assistant gaining access to Django admin via direct URL | High | Subclass `admin.AdminSite` with custom `has_permission` returning 403 if not `is_manager(request.user)`. |
| Dangling products if assistant user is hard deleted | Medium | `Product.created_by` uses `on_delete=models.SET_NULL`; provide safe deactivation (`is_active=False`) action to preserve historical attribution. |
| Non-technical managers breaking prompt schema or deleting variables | High | Isolate user copywriting instructions from immutable JSON schema envelope; enforce automatic fallback on any DB error. |
| Multiple active configurations created for the same language | Medium | Automatic demotion on `save()`: activating a configuration automatically sets any other configuration for that language to `is_active=False`. |
| Malformed or unsafe external URLs input for marketplace links | Medium | Validate all URLs with Django `URLValidator` requiring `http` or `https` schemes; render external links with `rel="noopener noreferrer"`. |
| N+1 queries when loading marketplace links for products | Low | Prefetch related links and sites (`prefetch_related("listing_links__site")`) on product detail view. |
| Duplicate links created for the same platform on a product | Low | Enforce database-level `UniqueConstraint(fields=['product', 'site'])` and handle `IntegrityError` in form validation. |
| Empty or invalid platform slug causing empty results or crashes | Low | Gracefully validate platform slug against database; use `.distinct()` on product querysets when filtering across joins. |
| Platforms without published products cluttering the dropdown | Low | Filter `available_platforms` to only include `MarketplaceSite` rows where `product_links__is_active=True` count > 0. |
| Cloudflare Turnstile API timeout or network failure | High | Implement fail-closed policy (Option A) with a strict 5.0s timeout to protect against bypass during attacks, with clear retry feedback. |
| Turnstile breaking local development or headless CI | High | Automatically bypass verification when `TURNSTILE_ENABLED=False` or keys omitted; support official Cloudflare test dummy keys. |
| Bot attacks bypassing public login and hitting admin login | High | Apply Turnstile protection uniformly to both `/login/` and `/admin/login/` (Option B). |
| Database corruption from backing up active SQLite file | High | Use SQLite native online backup API (`conn.backup()`) rather than filesystem copying, ensuring atomic consistency during active writes. |
| Unbounded cloud storage growth from daily snapshots | Medium | Enforce automated retention pruning after each backup, deleting snapshots older than 30 days. |
| Backup failure going unnoticed until disaster recovery | High | Record every attempt in `DatabaseBackupLog` and display a prominent warning banner in Django Administration when the last backup failed. |
| Backups failing in offline dev or CI environments | High | Support `--local-only` mode and mock S3 storage in tests so test suite runs 100% offline without credentials. |
| Mobile latency during intake AI identification | Medium | Slice image inputs to the first 3 photos max (Option A) and target ≤2.0s response time with `gemini-2.5-flash`. |
| AI identification failure blocking item intake | High | Enforce strictly non-blocking design: UI banner is advisory only, and form submit button remains functional at all times. |
| Double form submission creating duplicate product records | High | Latch `isSubmitting = true` synchronously and disable `#submitBtn` with loading spinner upon initial valid submit. |
| Race condition between AI pre-flight and form submission | High | Implement client-side `formState` machine: lock submit button and dropzone (`pointer-events-none`) while identify fetch is in flight. |
| Browser `alert()` halting execution and degrading mobile UX | Medium | Replace all `alert()` calls with accessible inline alert banner (`role="alert"`, `aria-live="polite"`). |
| Assistant uploading files >10MB wasting mobile bandwidth | Medium | Inspect `file.size` before upload starts; reject batch with explicit filename and MB size if limit exceeded. |

---

## Open Questions / Notes
- Approved: Date search auto-detected via unified search input (Option A).
- Approved: Pagination applies strictly to the catalog dashboard (`/dashboard/`).
- Approved: Prioritize user deactivation over hard deletion in admin.
- Approved: Explicit HTTP 403 Forbidden when assistant attempts to access `/admin/`.
- Approved: Free-form text input for Gemini model names with helpful admin suggestions.
- Approved: Option A for active configuration uniqueness (automatic deactivation of previous active config on save).
- Approved: Manager-only editing for listing links on product detail page; assistants have read-only visibility (Option A).
- Approved: Strict 1 link per platform per product via database `UniqueConstraint` (Option A).
- Approved: Deletion behavior: clearing link or clicking remove deletes the `ProductListingLink` record (Option A).
- Approved: Platform-filtered status counters scoping: status counters ("All", "Active", "Sold") dynamically update to reflect products on that specific platform (Option A).
- Approved: Dropdown option representation: platform name with item count (`Wallapop (12)`) (Option A).
- Approved: Platform filter submission: instant auto-submit (`onchange="this.form.submit()"`) (Option A).
- Approved: Turnstile failure mode: Fail-closed (Option A).
- Approved: Turnstile protection scope: Protect all login forms, including `/login/` and `/admin/login/` (Option B).
- Approved: Turnstile widget theme: Explicit light theme (`data-theme="light"`) (Option A).
- Approved: Backup retention window: 30 days daily retention (Option A).
- Approved: On-demand backup trigger in admin: Prominent top bar button with confirmation view (Option A).
- Approved: Failure notification: Django Admin warning banner + structured audit log (Option A).
- Approved: Suggested notes application: Append / smart fill preserving existing notes (Option A).
- Approved: Pre-flight photo sample size: First 3 photos for speed and minimal mobile payload (Option A).
- Approved: Action on oversized files (>10MB): Reject entire selection, reset input, and alert user which file was oversized (Option A).
- Approved: Dropzone error ring reset timing: Auto-clear on file selection as soon as at least one valid image is chosen (Option A).





