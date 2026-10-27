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

### Phase 17: Responsive Mobile Navigation & Collapsible Hamburger Drawer (Vertical Slice 13)
- **Task 56:** Accessible Mobile Hamburger Button & Sticky Header Refactor (`inventory/templates/inventory/base.html`, `tests/test_views.py`).
  - Add Tailwind responsive breakpoint `md:` to separate desktop horizontal navbar from mobile header.
  - Implement 44×44px `#mobile-menu-button` with dynamic SVG switching between hamburger (☰) and close (✕) icons.
  - Render compact doubts attention badge pill `❓ (X)` directly in the mobile bar next to the button when `pending_clarifications_count > 0` (Decision 27).
- **Task 57:** Collapsible Mobile Menu Drawer & Keyboard/Touch Interaction (`inventory/templates/inventory/base.html`, `tests/test_views.py`).
  - Build vertical collapsible drawer `#mobile-menu` directly below sticky header (`bg-white border-b border-slate-200 shadow-lg`) (Decision 28).
  - Include user identity card, Intake link, Dashboard link, Doubts link, conditional Admin link (for managers), segmented bilingual language switcher (`🇬🇧 English` / `🇪🇸 Español`), and isolated Sign Out action.
  - Implement accessible vanilla JavaScript toggle handling `aria-expanded`, keyboard `Escape` dismissal, outside-click close, and auto-reset on viewport resize.
  - Maintain DOM presence of all legacy test invariants (`badge-pending-clarifications`, `set_language`, `name="language"`, `value="en"`, `value="es"`, `"Sign Out"`).
- **Task 58:** i18n Spanish Translations, Comprehensive Unit/Integration Test Suite & Browser Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_views.py`, `tests/test_i18n.py`, `CHANGELOG.md`).
  - Add new Spanish translation strings (`Open menu`, `Close menu`, `Mobile navigation`, `Signed in as`, `English`, `Spanish`).
  - Compile catalogs using `compile_locales`.
  - Add test assertions in `tests/test_views.py` and `tests/test_i18n.py` verifying mobile menu structure, ARIA attributes, and language forms.
  - Run real browser automation on iPhone 14 mobile viewport (390×844) validating toggle, link clicking, outside click, and `Escape` key.
- **Checkpoint 17 (Responsive Mobile Navigation Complete):** Mobile header is uncluttered and clean; hamburger button toggles accessible drawer with smooth SVG transitions; doubts notification pill alerts assistants on mobile; keyboard and click-outside close cleanly; desktop viewports retain the full horizontal bar; all 243+ tests and browser tests pass with 0 regressions.

### Phase 18: Intake Photo Preview Management, Deletion & FileList Synchronization (Vertical Slice 14)
- **Task 59:** Client-Side Photo State Management & Cumulative File Capture (`inventory/templates/inventory/intake.html`, `tests/test_views.py`).
  - Introduce in-memory array `selectedFiles: File[]` managing the active photo set on `/intake/`.
  - Implement cumulative photo capture: selecting or snapping photos appends valid images to `selectedFiles` up to the 10-image maximum rather than replacing the batch (Decision 31).
  - Implement `syncFileInput()` utilizing standard HTML5 `DataTransfer` to mutate `imageInput.files = dt.files` whenever photos are added or deleted.
  - Dynamically update counter text (`#photoCount`: `X / 10 selected`) and toggle "Identificar producto" button state.
- **Task 60:** Interactive Preview Thumbnail Card & Accessible Deletion (`inventory/templates/inventory/intake.html`, `tests/test_views.py`).
  - Render preview cards in `#previewGrid` with index badges (`#1`, `#2`, ...) and accessible delete buttons ("✕").
  - Meet WCAG 2.1 AA with minimum 44×44px interactive touch target, 28×28px visual rose button, and localized `aria-label="Remove photo #N"`.
  - Handle click events: stop propagation and prevent default (preventing file picker opening), splice file from `selectedFiles`, synchronize `imageInput.files` via `DataTransfer`, and re-index remaining preview cards.
  - Reset dropzone and hide previews when all photos are deleted (`selectedFiles.length === 0`).
  - Preserve active AI pre-flight identification advisory banner when deleting photos unless all photos are removed (Decision 32).
  - Enforce form state guarding: disable delete buttons (`pointer-events-none opacity-50 cursor-not-allowed`) during `'identifying'` and `'submitting'` states.
- **Task 61:** i18n Spanish Translations, Automated Tests & Real Browser Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake.py`, `tests/test_views.py`, `CHANGELOG.md`).
  - Add Spanish translation strings (`Remove photo` -> `Eliminar foto`) in `locale/es/LC_MESSAGES/django.po` and compile via `python manage.py compile_locales`.
  - Update and expand unit/integration tests in `tests/test_views.py` and `tests/test_intake.py`.
  - Create and execute a real Chrome browser automation test in scratch (`verify_intake_photo_management_browser.py`): testing photo addition, deletion of middle photo, badge re-indexing, form submission, and database verification.
  - Update `CHANGELOG.md` under `[Unreleased]`.
  - Verify all unit tests and Ruff linting pass with 0 regressions.
- **Checkpoint 18 (Intake Photo Preview Management Complete):** Single photo deletion works seamlessly without re-uploading the entire batch; file input stays synchronized via `DataTransfer`; cumulative capture allows adding photos one by one; delete buttons meet 44×44px touch target guidelines; all automated and browser tests pass cleanly.

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
| Mobile navigation breaking existing test assertions on tokens | High | Preserve all existing element IDs, form inputs, language tokens, and clarification badge classes across desktop and mobile templates. |
| Inaccessible mobile drawer trapping keyboard focus or screen readers | High | Provide complete ARIA attributes (`aria-expanded`, `aria-controls`, `aria-label`), keyboard `Escape` handler returning focus, and 44×44px touch targets. |
| Viewport resize causing desynchronized drawer states | Low | Add `resize` event listener resetting mobile drawer to closed (`hidden`, `aria-expanded="false"`) when width reaches `md:` (≥768px). |
| HTML5 `DataTransfer` unsupported in archaic browsers | Low | Modern baseline browsers (Chrome, Firefox, Safari 14.5+, Edge) fully support `new DataTransfer()`; feature detect and fallback gracefully if missing. |
| Tapping delete button unintentionally triggering file picker | High | `#previewContainer` is positioned outside `#dropZone` in the DOM; delete button click handler calls `e.stopPropagation()` and `e.preventDefault()`. |
| Race condition from photo deletion during active AI pre-flight or form submit | High | Form state guarding disables all delete buttons (`pointer-events-none opacity-50 cursor-not-allowed`) during `'identifying'` and `'submitting'` states. |
| Service Worker served under `/static/` failing to control `/intake/` and `/dashboard/` | High | Serve `/sw.js` and `/manifest.json` from root routes in `inventory/urls.py` with `Service-Worker-Allowed: /` and `Cache-Control: no-cache` headers. |
| Service Worker caching dynamic HTML pages and breaking Django CSRF tokens | High | Implement a pure network pass-through `fetch` listener in `/sw.js` with zero HTML/CSRF caching (Decision 42). |
| Revoked or expired browser push endpoints accumulating or failing requests | Medium | Catch `WebPushException` in `push_service.py`; automatically delete `PushSubscription` records on HTTP `404`/`410 Gone` and swallow network timeouts (`timeout=5`) so user requests never fail. |
| iOS Safari hiding `PushManager` when opened in a regular browser tab | Medium | Feature-detect `'PushManager' in window` and iOS standalone mode; display a friendly non-blocking helper toast instructing iOS users to tap *"Share → Add to Home Screen"*. |

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
- Approved: Urgent doubts badge on mobile bar: Direct mobile bar pill `❓ (X)` next to the sandwich button for immediate visibility (Option A).
- Approved: Mobile drawer style: Sticky dropdown accordion directly beneath the header (`bg-white border-b border-slate-200 shadow-lg`) with page content scrollable beneath (Option A).
- Approved: Multi-step camera capture: Cumulative append up to 10 photos (Option A).
- Approved: AI pre-flight advisory state on photo deletion: Retain advisory banner unless all photos are deleted (Option A).
- Approved: Intake title field: Hidden input auto-populated by identify button without cluttering assistant UI (Option A).
- Approved: Zero price handling: Treats `<= 0.00` or None as price pending (Option A).
- Approved: Fast-track transition: Items with pre-entered price promote straight from DRAFT to READY upon description creation (Option A).
- Approved: PWA & Push target users: Both Assistants (mobile intake & answering doubts) and Managers (staging & reviewing) (Option A).
- Approved: Push notification implementation scope: Full Web Push plumbing (`pywebpush`, VAPID keys, Service Worker `push`/`notificationclick` handlers, `PushSubscription` model, subscribe/unsubscribe/test endpoints, UI toggle) + helper service (Option A).
- Approved: Target push workflow events: Clarification Doubts Q&A (`PENDING` / `ANSWERED`) and New Intake / Lifecycle Bottlenecks (`DRAFT` / `PRICE_PENDING`), controlled via `.env` flag `PUSH_NOTIFICATIONS_LIVE_SIGNALS`.
- Approved: Service Worker caching strategy: Minimal pass-through Service Worker strictly for PWA installability and Push Notifications, no caching (Option B).
- Approved: Build Compilation Footer Format & Metadata Scope: UTC Timestamp + Git Commit SHA + Environment Badge (Option A).
- Approved: Intake AI Valuation & Reference Pricing: Reference Badges + Optional "Usar reventa" Button in intake and manager staging (Option A).

---

### Phase 15: Refined Product Lifecycle States, Dashboard Filtering & Intake AI Title Autofill
- [x] **Task 62:** Domain Layer & State Machine Expansion (`inventory/models.py`, migrations, signals)
- [x] **Task 63:** Intake AI Vision Model Upgrade (`gemini-flash-latest`) & Hidden Title Autofill (`ai_service.py`, `forms.py`, `intake.html`, `views.py`)
- [x] **Task 64:** Dashboard Filtering, Status Counts & Staging UI Badges (`views.py`, `dashboard.html`, `product_detail.html`)
- [x] **Task 65:** i18n Localization, Unit & Regression Tests, and Real-Browser Verification
- [x] **Checkpoint 19 (Lifecycle & Intake Complete):** Full lifecycle automation verified across all states (`DRAFT`, `PRICE_PENDING`, `READY`, `PUBLISHED`, `AWAITING_INFO`, `SOLD`, `BLOCKED`), intake identification uses `gemini-flash-latest` and populates `ai_title`, dashboard button filter works with live count, and all tests pass with 0 regressions.

---

### Phase 20: Installable PWA Support, VAPID Web Push Infrastructure & Live Signal Triggers (Vertical Slice 16)
- [x] **Task 66:** PWA Web App Manifest (`/manifest.json`), App Icons (`192x192`, `512x512`, `apple-touch-icon`), Meta Tags & Root Pass-Through Service Worker (`/sw.js`) (`inventory/views.py`, `inventory/urls.py`, `inventory/templates/inventory/sw.js`, `inventory/templates/inventory/base.html`, `inventory/static/inventory/icons/`).
- [x] **Task 67:** `PushSubscription` Model, VAPID Settings, `generate_vapid_keys` Command, Django Admin Action & `push_service.py` Dispatcher (`requirements.txt`, `config/settings.py`, `.env.example`, `inventory/models.py`, `inventory/migrations/0013_pushsubscription.py`, `inventory/admin.py`, `inventory/services/push_service.py`, `inventory/management/commands/generate_vapid_keys.py`).
- [x] **Task 68:** Push Subscription JSON API Endpoints (`/api/push/subscribe/`, `/api/push/unsubscribe/`, `/api/push/test/`), Navbar/Drawer Notification Toggle UI & `.env`-Guarded Live Workflow Signals (`inventory/views.py`, `inventory/urls.py`, `inventory/context_processors.py`, `inventory/models.py`, `inventory/templates/inventory/base.html`).
- [x] **Task 69:** Bilingual Localization (`es`/`en`), Comprehensive Unit & Integration Test Suite (`tests/test_pwa_push.py`) & Real Chrome Browser Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_pwa_push.py`, `CHANGELOG.md`).
- [x] **Checkpoint 20 (PWA Support & Web Push Notifications Complete):** `/manifest.json` and root `/sw.js` register cleanly with scope `/`; PWA icons and meta tags render across pages; `PushSubscription` model and VAPID key generator work; subscribe/unsubscribe/test endpoints and navbar/drawer UI toggles function properly; `push_service.py` dispatches encrypted Web Push payloads and prunes `404`/`410` subscriptions; `PUSH_NOTIFICATIONS_LIVE_SIGNALS` controls automatic signal alerts for Clarification Doubts and Draft/Price Pending bottlenecks; all unit and browser tests pass with 0 regressions.

---

### Phase 21: Dashboard Status Toolbar Modernization & Apilación Prevention (Vertical Slice 17)
- [x] **Task 70:** Decouple Dashboard Status Navigation & Filter Toolbar into a Single-Line Horizontal Scroll Rail (`inventory/templates/inventory/dashboard.html`, `tests/test_dashboard_responsive.py`).
- [x] **Checkpoint 21 (Anti-Apilación Toolbar Complete):** All 7 status tabs sit inside an accessible `<nav role="tablist">` with horizontal scrolling and hidden scrollbars; tabs never wrap or apilar on mobile/tablet viewports; touch targets satisfy WCAG ($\ge 36\text{px}$); Playwright multi-viewport automated test verifies vertical offset alignment across 390px, 768px, 1024px, and 1440px with screenshots captured.

---

### Phase 22: Responsive Mobile Typography & Form Readability Adaptation (Vertical Slice 18)
- [x] **Task 71:** Standardize Mobile Typography Scale, Eliminate Microscopic Fonts, and Safeguard Against iOS Safari Input Auto-Zoom (`inventory/templates/inventory/base.html`, `inventory/templates/inventory/dashboard.html`, `inventory/templates/inventory/intake.html`, `inventory/templates/inventory/product_detail.html`, `inventory/templates/registration/login.html`, `inventory/forms.py`, `tests/test_dashboard_responsive.py`).
- [x] **Checkpoint 22 (Mobile Typography Complete):** Sub-12px arbitrary classes (`text-[10px]`, `text-[11px]`) eliminated; inputs, selects, and textareas enforce $\ge 16\text{px}$ on mobile (`text-base sm:text-sm` and CSS override); `maximum-scale=1.0, user-scalable=no` removed for WCAG 2.1 AA zoom compliance; `<meta name="text-scale" content="scale">` added; Playwright test asserts computed input font size $\ge 16\text{px}$ on $390 \times 844$ with full visual screenshots.

---

### Phase 23: Product State Change History & Audit Trail (Vertical Slice 19)
- [x] **Task 72:** Domain Model `ProductStatusLog`, Helper Functions & Database Migration (`inventory/models.py`, `inventory/migrations/0014_productstatuslog.py`).
- [x] **Task 73:** Request User Context Capture Middleware & Automated Lifecycle Transition Logging (`inventory/middleware.py`, `config/settings.py`, `inventory/models.py`).
- [x] **Task 74:** Django Administration Read-Only Audit Changelist & Product Status Log Inline (`inventory/admin.py`).
- [x] **Task 75:** Staging Product Detail UI Lifecycle Audit Trail Timeline Card (`inventory/views.py`, `inventory/templates/inventory/product_detail.html`).
- [x] **Task 76:** Bilingual Localization (`es`/`en`), Comprehensive Test Suite (`tests/test_status_history.py`) & Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `CHANGELOG.md`).
- [x] **Checkpoint 23 (Product State Change History Complete):** Every product state change is recorded with timestamps, user attribution, from/to statuses, and trigger notes; timeline card renders cleanly on `/products/<pk>/` across viewports; Django Admin provides a read-only audit log and inline; all 299+ tests pass with 0 regressions.

---

### Phase 24: Compilation & Docker Image Build Timestamp Display (Vertical Slice 20)
- [x] **Task 77:** Version & Build Metadata Resolution Service (`inventory/services/version_service.py`).
- [x] **Task 78:** Global Template Context Processor & Django Settings Registration (`inventory/context_processors.py`, `config/settings.py`).
- [x] **Task 79:** Dockerfile & CI/CD Workflow Metadata Injection (`Dockerfile`, `.github/workflows/ci.yml`).
- [x] **Task 80:** Footer UI Modernization & Responsive Layout in `base.html` (`inventory/templates/inventory/base.html`).
- [x] **Task 81:** Bilingual Localization, Comprehensive Unit Tests & Full Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_build_info.py`, `CHANGELOG.md`).
- [x] **Checkpoint 24 (Build Compilation Info Complete):** Build timestamp, commit SHA, and environment badge display properly in footer across all views and viewports; Docker builds automatically bake in build metadata; tests pass with 0 regressions.

---

### Phase 25: Intake AI Valuation & Reference Pricing (Vertical Slice 21)
- [x] **Task 82:** Domain Model Expansion & Database Migration (`inventory/models.py`, `inventory/migrations/0015_product_estimated_prices.py`, `inventory/admin.py`).
- [x] **Task 83:** AI Service Schema & Prompt Upgrade (`inventory/services/ai_service.py`, `inventory/views.py`).
- [x] **Task 84:** Intake Form & Mobile UI Valuation Integration (`inventory/forms.py`, `inventory/templates/inventory/intake.html`).
- [x] **Task 85:** Staging Product Detail View Reference Benchmarks (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 86:** Bilingual Localization, Automated Unit & Integration Tests & Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_ai_valuation.py`, `CHANGELOG.md`).
- [x] **Checkpoint 25 (Intake AI Valuation & Reference Pricing Complete):** Intake identification estimates new MSRP and used resale value; values persist in `Product` model; intake form displays reference badges with one-click "Usar reventa" button; staging product detail shows benchmark badges beside manager sale price with "Aplicar" action; all unit and regression tests pass with 0 regressions.

---

### Phase 26: Consolidated Intake Session Notifications & Debounced Alerts (Vertical Slice 22)
- [x] **Task 87:** Domain Model `IntakeBatchSession`, `Product.batch_session` Foreign Key, Migration `0016_intake_batch_session.py` & Django Admin Registration (`inventory/models.py`, `inventory/migrations/0016_intake_batch_session.py`, `inventory/admin.py`).
- [x] **Task 88:** Sourcing Session Service Engine & Configuration Settings (`config/settings.py`, `inventory/services/intake_batch_service.py`).
- [x] **Task 89:** Lifecycle Post-Save Signal Refactoring & Urgent Alert Preservation (`inventory/models.py`, `tests/test_pwa_push.py`).
- [x] **Task 90:** Management Command `process_intake_batches` for CLI & Automated Cron Execution (`inventory/management/commands/process_intake_batches.py`).
- [x] **Task 91:** Bilingual Translations, Comprehensive Automated Test Suite & Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake_batch_notifications.py`, `CHANGELOG.md`).
- [x] **Checkpoint 26 (Consolidated Intake Session Notifications Complete):** Uploading multiple products consecutively records them under a single `IntakeBatchSession`; no immediate manager push alerts are dispatched for drafts; after the 15-minute sliding inactivity window passes, a single consolidated push alert (`📦 Lote completado: [X] nuevos productos`) is dispatched to `ROLE_MANAGER`; urgent clarification doubts and price pending alerts remain instant; CLI management command supports normal and dry-run execution; all unit and regression tests pass with 0 failures and 0 warnings.

---

### Phase 27: Sale Channel Tracking on Sold Products (Vertical Slice 23)
- [x] **Task 92:** Domain Model Expansion, Migrations & Admin Registration (`inventory/models.py`, `inventory/migrations/0017_product_sale_channel.py`, `inventory/admin.py`).
- [x] **Task 93:** Form Validation & Lifecycle Channel Logic (`inventory/forms.py`).
- [x] **Task 94:** Staging Product Detail UI Integration with Dynamic Selector & Quick-Picks (`inventory/views.py`, `inventory/templates/inventory/product_detail.html`).
- [x] **Task 95:** Dashboard Catalog Filtering & Product Card Channel Badges (`inventory/views.py`, `inventory/templates/inventory/dashboard.html`).
- [x] **Task 96:** Bilingual Localization, Comprehensive Automated Test Suite & Full Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_sale_channel.py`, `CHANGELOG.md`).
- [x] **Checkpoint 27 (Sale Channel Tracking Complete):** Marking a product as sold requires explicit channel attribution (in-store or marketplace); marketplace sales link to configured `MarketplaceSite` with `SET_NULL` cascade safety; product detail staging page provides progressive channel selector with 1-click published platform shortcuts; catalog dashboard displays channel badges and sub-filters sold items by channel; all automated tests pass with 0 failures and 0 linter errors.
---

### Phase 28: Product Soft-Delete, Archival & Erased Trash Category (Vertical Slice 24)
- [x] **Task 97:** Domain Model Fields (`is_deleted`, `deleted_at`, `deleted_by`), Methods (`soft_delete`, `restore`), Schema Migration (`0018_product_soft_delete.py`), and Admin Registration (`inventory/models.py`, `inventory/migrations/0018_product_soft_delete.py`, `inventory/admin.py`).
- [x] **Task 98:** Dedicated Action Views (`product_soft_delete_view`, `product_restore_view`) & URL Routing with Manager Role Protection (`inventory/views.py`, `inventory/urls.py`).
- [x] **Task 99:** Product Detail Staging UI Integration with Confirmation Modal, Trash Indicator Banner & Restore Action (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 100:** Dashboard Catalog Filtering, Erased Tab Navigation Pill, Aggregate Count Isolation & Search Scoping (`inventory/views.py`, `inventory/templates/inventory/dashboard.html`).
- [x] **Task 101:** Bilingual Localization, Comprehensive Automated Test Suite & Full Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_product_soft_delete.py`, `CHANGELOG.md`).
- [x] **Checkpoint 28 (Product Soft-Delete Complete):** Managers can move items to trash via confirmation modal; erased items are isolated into `?status=erased` with dedicated count and excluded from active catalog tabs/counters; erased items can be inspected and restored back to their prior lifecycle status; all tests pass 100% and linter passes with 0 warnings.

---

### Phase 37: Corporate Business Landing Page (`/`), Revised Marketplace URLs (`/tienda/`) & Staff Router (`/panel/`) (Vertical Slice 33)
- [x] **Task 133:** Revised URL Routing (`/`, `/tienda/`, `/tienda/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/`, `/como-comprar/`, `/go/whatsapp/`, `/go/whatsapp/<pk>/`, `/go/link/<link_pk>/`, `/aviso-legal/`, `/privacidad/`, `/cookies/`, `/panel/`), 301 Canonical Slug Redirect, Spanish Query Param Aliases (`?estado=`, `?precio=`, `?orden=`), & Navigation Updates (`storefront/urls.py`, `storefront/views.py`, `inventory/urls.py`, `storefront/templates/storefront/base_public.html`, `storefront/templates/storefront/catalog.html`).
- [x] **Task 134:** Corporate Business Landing Page (`storefront/templates/storefront/home.html`), Local Stitch Hero/Brand Assets (`inventory/static/img/storefront/`), `home_view` with Top 4 *"Recién llegados"* & `Schema.org/LocalBusiness` JSON-LD (`storefront/views.py`, `storefront/templates/storefront/home.html`, `inventory/static/img/storefront/`).
- [x] **Task 135:** Standalone Shareable *"¿Cómo comprar?"* Page (`/como-comprar/` — `storefront/templates/storefront/how_to_buy.html`), Updated `/sitemap.xml` (including `/`, `/tienda/`, 12 categories, products, `/como-comprar/`, and legal pages) & `/robots.txt` (`storefront/views.py`, `storefront/templates/storefront/how_to_buy.html`, `storefront/templates/storefront/partials/_how_to_buy_modal.html`).
- [x] **Task 136:** Bilingual Localization (`es`/`en`), Updated Automated & Browser Test Suites (`tests/test_storefront.py`, `tests/test_auth.py`, `tests/test_browser_daily_workflow.py`), Linter & Full Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po`, `tests/test_storefront.py`, `tests/test_auth.py`, `tests/test_browser_daily_workflow.py`, `CHANGELOG.md`).
- [x] **Checkpoint 37 (Corporate Landing Page & Revised URLs Complete):** `/` renders the Stitch corporate business landing page with parcel carriers (`SEUR`, `GLS`, `InPost`, `Amazon Hub`, `Kanguro`, `DHL`, `Punto Pack`), 4 parcel services + 3-step workflow, brand identity, 4 newest available products, trust stats, Alfafar map/contact card, and `LocalBusiness` JSON-LD; `/tienda/` and `/tienda/categoria/<slug>/` serve the marketplace catalog; `/tienda/producto/<slug>-<pk>/` serves the product detail with 301 canonical slug redirect; `/como-comprar/` and `/aviso-legal/`, `/privacidad/`, `/cookies/` return HTTP 200; `/panel/` routes staff; all unit and browser tests pass with 0 regressions.

---

### Phase 29: Product Detail Clarifications Hub (Vertical Slice 25)
- [x] **Task 102:** Domain Model Expansion (`is_direct_note`), Signal Logic Refactoring, Schema Migration (`0019_clarification_direct_note.py`), and Admin Registration (`inventory/models.py`, `inventory/migrations/0019_clarification_direct_note.py`, `inventory/admin.py`).
- [x] **Task 103:** Service & Form Layer for Direct Clarifications & AI Copywriting Formatting (`inventory/forms.py`, `inventory/services/ai_service.py`).
- [x] **Task 104:** Dedicated Action View (`product_add_direct_clarification_view`) & URL Routing with Multi-Role Permissions (`inventory/views.py`, `inventory/urls.py`).
- [x] **Task 105:** Product Detail Clarifications Hub UI with Dual-Mode Tabs, Responsive Styling & Accessibility (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 106:** Bilingual Localization, Comprehensive Automated Test Suite & Full Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_clarifications_hub.py`, `CHANGELOG.md`).
- [x] **Checkpoint 29 (Product Detail Clarifications Hub Complete):** Sourcing assistants and store managers can post direct clarification notes post-intake directly in the left column under intake notes; store managers can toggle between direct notes and Q&A doubts; direct notes save in resolved status without blocking the item in `AWAITING_INFO`; Gemini AI copywriting prompt incorporates both direct notes and resolved Q&A items; all tests pass 100% and linter passes with 0 warnings.

---

### Phase 30: Intake Mandatory Pre-flight Identification Gate (Vertical Slice 26)
- [x] **Task 107:** Frontend UI State Machine, Save Button Gating & Reset Logic (`inventory/templates/inventory/intake.html`).
- [x] **Task 108:** Bilingual Localization, Automated Test Suite & Full Regression Check (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake_identification_gate.py`, `CHANGELOG.md`).
- [x] **Checkpoint 30 (Intake Mandatory Identification Gate Complete):** The Save button on `/intake/` is disabled on initial load and remains disabled when photos are chosen until AI identification is triggered; running identification (success or handled fallback) unlocks the Save button; removing all photos resets the gate and re-disables Save; form submission is strictly guarded against premature submit; all tests pass 100% and linter passes with 0 warnings.

---

### Phase 31: Photo Reordering in Intake and Detail Workspaces (Vertical Slice 27)
- [x] **Task 109:** Backend Image Reordering API Endpoint & Permission Security (`inventory/views.py`, `inventory/urls.py`, `tests/test_photo_reordering.py`).
- [x] **Task 110:** Intake Form Hybrid Photo Reordering (Buttons + Drag & Drop) (`inventory/templates/inventory/intake.html`).
- [x] **Task 111:** Product Detail Gallery Reordering UI & Live Cover Preview (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 112:** Bilingual Localization, Automated Test Suite, E2E Verification & Changelog (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_photo_reordering.py`, `CHANGELOG.md`).
- [x] **Checkpoint 31 (Photo Reordering Complete):** Photos can be reordered in `/intake/` before saving with automatic `DataTransfer` file synchronization and primary cover badge; managers can reorder saved photos on `/products/<pk>/` with instant database persistence and `#mainImage` update; all tests pass 100% and linter passes cleanly.

---

### Phase 32: Low-DPI Intake Photo Miniatures & Delete Controls Optimization (Vertical Slice 28)
- [x] **Task 113:** Intake Form High-Density Miniature Grid, Enhanced Delete Controls & Lightbox Modal (`inventory/templates/inventory/intake.html`).
- [x] **Task 114:** Bilingual Localization, Automated Test Suite, Simulation Verification & Changelog (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake_low_dpi.py`, `CHANGELOG.md`).
- [x] **Checkpoint 32 (Low-DPI Intake Photo Miniatures & Delete Controls Complete):** Preview grid adapts responsively to a high-density 3-column layout (`grid-cols-3 sm:grid-cols-4 md:grid-cols-5`) on mobile devices; thumbnails render at compact ~90px–115px square preventing page scroll disruption; delete ('X') button is rendered with high-contrast styling and isolation ring eliminating subpixel blur on 1x DPI screens; tapping a miniature opens an accessible full-screen image inspection modal; all automated tests pass 100% and linter passes cleanly.

---

### Phase 33: Published Product Modifications & Platform Sync Tracking (Vertical Slice 29)
- [x] **Task 115:** Domain Model Expansion, Change-Detection Triggers, Schema Migration & Admin (`inventory/models.py`, `inventory/migrations/0020_product_platform_sync.py`, `inventory/admin.py`).
- [x] **Task 116:** Product Detail Photo Management: Upload Additional Photos & Individual Photo Deletion (`inventory/views.py`, `inventory/forms.py`, `inventory/urls.py`).
- [x] **Task 117:** 1-Click Platform Sync Clearance Action & Staging Workspace UI (`inventory/views.py`, `inventory/urls.py`, `inventory/templates/inventory/product_detail.html`).
- [x] **Task 118:** Dashboard Catalog Sub-Filtering & Product Card Sync Badges (`inventory/views.py`, `inventory/templates/inventory/dashboard.html`).
- [x] **Task 119:** Bilingual Localization, Comprehensive Automated Test Suite, Full Regression & Changelog (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_published_platform_sync.py`, `CHANGELOG.md`).
- [x] **Checkpoint 33 (Published Product Modifications & Platform Sync Complete):** Published products remain in `PUBLISHED` status while automatically tracking `needs_platform_sync = True` upon price changes, copy edits, photo updates, or new clarifications; managers can upload new photos and delete photos directly in the detail workspace; workspace renders prominent out-of-sync banner with 1-click clearance button; dashboard sub-filters out-of-sync listings with live counter badges; 100% test pass rate and clean linter.

---

### Phase 34: Detail View Photo Upload Component System (Vertical Slice 30)
- [x] **Task 120:** Detail View Photo Upload Component UI, Dropzone & Dual Capture Controls (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 121:** Client-Side WebP Compression Engine & Pre-Upload Thumbnail Queue (`inventory/templates/inventory/product_detail.html`).
- [x] **Task 122:** Bilingual Localization, Comprehensive Automated Test Suite, Verification & Changelog (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_detail_photo_upload_component.py`, `CHANGELOG.md`).
- [x] **Checkpoint 34 (Detail View Photo Upload Component Complete):** The photo upload UI in `/products/<pk>/` achieves full parity with `/intake/`: dashed dropzone with drag-and-drop feedback, dual camera ('📸 Tomar foto') and gallery ('🖼️ Seleccionar de la galería') buttons, client-side Canvas downscaling to max 2560px WebP, pending thumbnail queue with individual deletion, capacity-aware counter (10 - N_existing), full bilingual localization, and 100% test suite pass rate.

---

### Phase 35: Out-of-Sync Product Web Push Notifications (Vertical Slice 31)
- [x] **Task 123:** Push Service Dispatcher & Notification Formatting (inventory/services/push_service.py).
- [x] **Task 124:** Domain Model Edge-Transition Detection & Signal Receiver Integration (inventory/models.py).
- [x] **Task 125:** Bilingual Localization, Comprehensive Automated Test Suite, Full Regression & Changelog (locale/es/LC_MESSAGES/django.po, locale/es/LC_MESSAGES/django.mo, 	ests/test_out_of_sync_notifications.py, CHANGELOG.md).
- [x] **Checkpoint 35 (Out-of-Sync Product Web Push Notifications Complete):** Store managers receive immediate, deep-linked Web Push notifications when published items become out of sync, edge-transition logic prevents duplicate notification spam, clearance suppressions work cleanly, 100% test suite passes, and linter is clean.

---

### Phase 36: Public Marketplace Storefront Transformation — Rápido Pack (`rapidopack.es`, Vertical Slice 32)
- [x] **Task 126:** Domain Models (`Category`, `StorefrontConfiguration`, `ProductCondition`), `Product` & `ProductListingLink` Marketplace Fields, `ProductQuerySet.public_visible()`, Data Seed Migration (`0021_marketplace_storefront.py`), SQLite WAL Mode & Django Admin Registration (`inventory/models.py`, `inventory/migrations/0021_marketplace_storefront.py`, `inventory/admin.py`, `config/settings.py`).
- [x] **Task 127:** Gemini AI Taxonomy Auto-Classification (`ProductListingSchema`, `IntakePreflightSchema`), Staging Form/View/Template Controls & `classify_products` Backfill Command (`inventory/services/ai_service.py`, `inventory/forms.py`, `inventory/views.py`, `inventory/templates/inventory/product_detail.html`, `inventory/templates/inventory/dashboard.html`, `inventory/management/commands/classify_products.py`).
- [x] **Task 128:** Dedicated `storefront` App Scaffolding, Context Processor, URL Routing (`/` Public Catalog vs `/staff/` Staff Redirect) & Stitch `base_public.html` Layout (`storefront/`, `config/settings.py`, `config/urls.py`, `inventory/urls.py`, `tests/test_auth.py`).
- [x] **Task 129:** Public Catalog Homepage (`/`), 12-Category Rail, Price & Condition Filter Bar, Sorting, Responsive 4-Col/2-Col Product Grid (`_product_card.html`), Alfafar Store Banner & *"Saber más"* Modal (`_how_to_buy_modal.html`) (`storefront/views.py`, `storefront/templates/storefront/catalog.html`, `storefront/templates/storefront/partials/`).
- [x] **Task 130:** Public Product Detail View (`/p/<slug>-<pk>/`), 60/40 Gallery & Lightbox, Verification Certificate Box, Decoupled `_purchase_box.html` (Phase 1 $\to$ Phase 2 Ready) & Outbound Click Tracking (`/go/whatsapp/<pk>/`, `/go/link/<link_pk>/`) (`storefront/views.py`, `storefront/urls.py`, `storefront/templates/storefront/product_detail.html`, `storefront/templates/storefront/partials/_purchase_box.html`).
- [x] **Task 131:** SEO & Legal Compliance: OpenGraph + WhatsApp Rich Previews, `Schema.org/Product` JSON-LD, `/sitemap.xml`, `/robots.txt` & RGPD/LSSI Legal Pages (`/legal/aviso-legal/`, `/legal/privacidad/`, `/legal/cookies/`) (`storefront/views.py`, `storefront/urls.py`, `storefront/templates/storefront/legal_page.html`).
- [x] **Task 132:** Bilingual Localization (`es`/`en`), Comprehensive Storefront & Security Firewall Test Suite (`tests/test_storefront.py`) & Full Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_storefront.py`, `CHANGELOG.md`).
- [x] **Checkpoint 36 (Public Marketplace Storefront Complete):** `/` serves the Stitch-designed Rápido Pack marketplace homepage; `/p/<slug>-<pk>/` renders the 60/40 product detail view with OpenGraph and JSON-LD; `public_visible()` enforces 7-day `SOLD` social proof retention and strict internal data firewall (`raw_note` and `clarifications` never leaked); click tracking increments counters for WhatsApp and Wallapop/Vinted; Gemini auto-classifies categories and conditions; `classify_products` command works; all existing and new tests pass with 0 regressions.

---

### Phase 37: Corporate Business Landing Page (`/`) & URL Routing (Vertical Slice 33)
- [x] **Task 133:** Root URL Routing & View Delegation (`storefront/urls.py`, `storefront/views.py`, `config/urls.py`).
- [x] **Task 134:** Stitch Corporate Landing Page Template (`storefront/templates/storefront/home.html`).
- [x] **Task 135:** Standalone How-to-Buy Guide & Dedicated Category Routes (`/como-comprar/`, `/tienda/categoria/<slug>/`).
- [x] **Task 136:** Bilingual Localization, Automated & Browser Tests, Regression Verification (`locale/es/LC_MESSAGES/django.po`, `tests/test_storefront.py`, `tests/test_browser_daily_workflow.py`).
- [x] **Checkpoint 37 (Corporate Landing Page Complete):** `/` serves corporate landing page with multi-carrier parcel services and 4 newest arrivals; staff redirected to `/panel/`; direct category routes work; 100% tests pass.

---

### Phase 38: Comprehensive Project Texts & Bilingual Localization Audit & Fixes (Vertical Slice 34)
- [ ] **Task 137:** Audit & Harmonize Template Text & Python Code to English Source `msgid`s (`storefront/templates/`, `storefront/views.py`, `inventory/templates/`).
- [ ] **Task 138:** Complete Bilingual Translation Catalogs (`locale/es/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po`, and binary `.mo` compilation).
- [ ] **Task 139:** Automated Bilingual Test Suites (`tests/test_i18n.py`, `tests/test_storefront.py`) & Playwright Chrome Real-Browser Verification (`tests/test_browser_daily_workflow.py`).
- [ ] **Task 140:** Quality Gate, Bilingual Documentation, Changelog & User Merge Gate (`CHANGELOG.md`, `tasks/todo.md`).
- [ ] **Checkpoint 38 (Bilingual Localization & Project Texts Audit Complete):** All project texts are 100% localized, source strings follow standard English `msgid` convention, Spanish catalog is 100% complete with 0 empty translations, English catalog is present and compiled, Playwright and Django tests assert exact translations in both `es` and `en`, Ruff and system checks pass with zero warnings.
