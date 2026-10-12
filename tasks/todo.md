# Task List: Secondhand Inventory & Staging App

## Phase 1: Foundation & Domain Layer

### Task 1: Environment Setup & Project Scaffolding
**Description:** Initialize the Python virtual environment, install required dependencies (`Django`, `pillow`, `google-genai`, `python-dotenv`, `ruff`), and scaffold the base Django project configuration with media/static settings.
**Acceptance criteria:**
- [x] Dependencies documented in `requirements.txt` and installed in `.venv`.
- [x] Django project initialized (`config/` and `manage.py`).
- [x] `settings.py` configured with `MEDIA_ROOT`, `MEDIA_URL`, `STATIC_URL`, templates, and `.env` loading.
- [x] `.env.example` created with placeholders for `SECRET_KEY`, `DEBUG`, and `GEMINI_API_KEY`.
**Verification:**
- [x] Command succeeds: `python manage.py check`
**Dependencies:** None
**Files likely touched:**
- `requirements.txt`
- `.env.example`
- `manage.py`
- `config/settings.py`
- `config/urls.py`
**Estimated scope:** Medium (3-5 files)

---

### Task 2: Domain Models, Migrations & Admin Registration
**Description:** Implement `Product` and `ProductImage` models according to the specification, create and apply migrations, and register them in Django Admin with list displays and image inlines.
**Acceptance criteria:**
- [x] `Product` model created with `raw_note`, `ai_title`, `ai_description`, `sale_price` (Decimal, €), `is_sold`, `sold_at`, and timestamps.
- [x] `ProductImage` model created with foreign key to `Product`, `image` field, `order`, and upload path.
- [x] Initial migrations created and applied to SQLite database.
- [x] Django Admin registered with `ProductAdmin` (including `ProductImageInline`).
**Verification:**
- [x] Command succeeds: `python manage.py makemigrations --check --dry-run`
- [x] Unit tests pass: `python manage.py test tests.test_models`
**Dependencies:** Task 1
**Files likely touched:**
- `inventory/models.py`
- `inventory/admin.py`
- `inventory/migrations/0001_initial.py`
- `tests/test_models.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 3: Image Service for Pillow WebP Conversion & Validation
**Description:** Create `services/image_service.py` to handle automated image orientation correction, conversion to `.webp` with quality compression, and validation for size (<= 10MB) and quantity (<= 10).
**Acceptance criteria:**
- [x] `convert_to_webp(uploaded_file)` correctly strips EXIF orientation and exports a `.webp` `ContentFile`.
- [x] Uploaded image extensions and mime types validated.
- [x] Unit tests verify that JPEG/PNG uploads are converted to valid WebP format and saved.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_image_service`
**Dependencies:** Task 2
**Files likely touched:**
- `inventory/services/image_service.py`
- `tests/test_image_service.py`
**Estimated scope:** Small (2 files)

---

## Checkpoint 1: Foundation
- [x] `python manage.py check` reports no issues.
- [x] Migrations applied to SQLite database cleanly.
- [x] Model tests and image conversion tests pass.

---

## Phase 2: Authentication & Assistant Intake (Vertical Slice 1)

### Task 4: Authentication & Role Setup
**Description:** Set up authentication routes (login, logout) and helper decorators/mixins to differentiate between `assistants` (intake & catalog view) and `managers` (full staging, AI, pricing, and admin permissions).
**Acceptance criteria:**
- [x] Standard login/logout views and templates styled with Tailwind.
- [x] Role check utility (`is_manager`, `is_assistant`) or group definitions configured.
- [x] Automatic post-login redirection based on role (assistants to `/intake/`, managers to `/dashboard/`).
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_auth`
**Dependencies:** Task 3
**Files likely touched:**
- `inventory/views/auth_views.py` (or `inventory/views.py`)
- `inventory/templates/registration/login.html`
- `inventory/templates/inventory/base.html`
- `tests/test_auth.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 5: Mobile-First Product Intake Flow
**Description:** Implement `/intake/` route and template optimized for mobile phones, featuring multi-image capture, instant JavaScript client previews, raw notes input, and backend WebP image saving.
**Acceptance criteria:**
- [x] `ProductIntakeForm` accepts multiple image uploads and `raw_note`.
- [x] Clean, mobile-friendly interface with large buttons and responsive thumbnail preview grid.
- [x] Form submission converts images to `.webp` and creates `Product` + `ProductImage` records.
- [x] Success notification and quick reset for rapid back-to-back cataloging.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_intake`
- [x] Manual test: Upload 3 test images and raw note, verify WebP files saved in `media/products/`.
**Dependencies:** Task 4
**Files likely touched:**
- `inventory/forms.py`
- `inventory/views.py`
- `inventory/templates/inventory/intake.html`
- `tests/test_intake.py`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 2: Intake Slice
- [x] Assistant can log in and submit photos + notes from `/intake/`.
- [x] Uploaded photos are stored as `.webp` on disk.
- [x] Tests for auth and intake pass.

---

## Phase 3: Manager Dashboard & Photo ZIP Bundle (Vertical Slice 2)

### Task 6: Manager Catalog Dashboard
**Description:** Create the main catalog dashboard (`/` or `/dashboard/`) with search, filter tabs (`All`, `Active`, `Sold`), and responsive product summary cards displaying primary photo, title/raw note preview, price in `€`, and status badges.
**Acceptance criteria:**
- [x] Dashboard displays grid of products with primary thumbnail, date, notes/title, price, and status.
- [x] Filter by status (`all`, `active`, `sold`) and search query filtering by notes/title.
- [x] Quick link to product staging detail page and mobile intake.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_dashboard`
**Dependencies:** Task 5
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/dashboard.html`
- `tests/test_dashboard.py`
**Estimated scope:** Small to Medium (3 files)

---

### Task 7: Product Detail Staging View & In-Memory ZIP Download
**Description:** Build the product staging detail view (`/products/<pk>/`) with photo gallery and implement a streaming ZIP download endpoint to package all product `.webp` images into a single download.
**Acceptance criteria:**
- [x] Staging page displays full image gallery, preserved raw field notes, and current status.
- [x] "Download Photos (.ZIP)" button calls `/products/<pk>/download-zip/` and returns an in-memory `.zip` containing all images named `product_<id>_img_<index>.webp`.
- [x] Access restricted to authenticated users.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_zip_download`
**Dependencies:** Task 6
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/product_detail.html`
- `tests/test_zip_download.py`
**Estimated scope:** Medium (3 files)

---

## Checkpoint 3: Catalog & Asset Management Slice
- [x] Dashboard displays catalog accurately with working search and status filters.
- [x] Staging detail view shows gallery and preserved raw notes.
- [x] ZIP download returns a valid ZIP archive of all `.webp` images.

---

## Phase 4: Gemini Multimodal AI & Sales Tracking (Vertical Slice 3)

### Task 8: Gemini Multimodal Vision Service
**Description:** Implement `services/ai_service.py` to send product photos and raw notes to Google Gemini Flash, requesting structured JSON containing an SEO-friendly marketplace title and sales description.
**Acceptance criteria:**
- [x] `generate_product_listing(product)` builds multimodal prompt with image bytes and `product.raw_note`.
- [x] Uses Gemini structured JSON output schema (`title`, `description`).
- [x] Gracefully handles missing API keys, network failures, or unparseable responses with clear errors.
- [x] Unit tests with mocked Gemini responses verify prompt construction and error handling.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_ai_service`
**Dependencies:** Task 7
**Files likely touched:**
- `inventory/services/ai_service.py`
- `tests/test_ai_service.py`
**Estimated scope:** Small to Medium (2-3 files)


---

### Task 9: AI Generation UI, One-Click Copy & Sales Tracking
**Description:** Wire up the "Generate AI Listing" button on the staging page, provide one-click copy buttons for title and description, and add controls to update `sale_price` (in `€`) and toggle `is_sold`.
**Acceptance criteria:**
- [x] "Generate AI Listing" button invokes the AI service and populates `ai_title` and `ai_description` (without altering `raw_note`).
- [x] One-click "Copy Title" and "Copy Description" buttons with visual feedback ("Copied!").
- [x] Sales form allows updating `sale_price` and marking the item sold/unsold.
- [x] Marking as sold sets `is_sold=True` and records `sold_at` timestamp.
**Verification:**
- [x] Full test suite passes: `python manage.py test`
- [x] Code formatting check passes: `ruff check .`
**Dependencies:** Task 8
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/product_detail.html`
- `inventory/static/js/staging.js`
- `tests/test_views.py`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 4: Complete End-to-End Workflow
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Complete flow verified:
  1. Assistant uploads photos and raw note via mobile intake.
  2. Manager views item in dashboard and opens staging view.
  3. Manager generates AI listing, copies title/description, and downloads photo ZIP.
  4. Manager enters sale price in `€` and marks item as sold.

---

## Phase 5: Multi-Language (i18n) Support

### Task 10: Django i18n Configuration & Windows-Friendly PO/MO Compiler
**Description:** Configure Django i18n settings (add `LocaleMiddleware`, `LANGUAGES`, `LOCALE_PATHS`, `USE_I18N = True`), add `polib` to `requirements.txt`, install it, configure `set_language` URL, and implement a custom `compile_locales` management command using `polib` to compile `.po` files to `.mo` on Windows without GNU gettext binaries.
**Acceptance criteria:**
- [x] `polib` added to `requirements.txt` and installed in `.venv`.
- [x] `config/settings.py` configured with `LocaleMiddleware`, `LANGUAGES = [('en', 'English'), ('es', 'Spanish')]`, `LANGUAGE_CODE = 'en'`, `LOCALE_PATHS = [BASE_DIR / 'locale']`.
- [x] `config/urls.py` includes `path('i18n/', include('django.conf.urls.i18n'))`.
- [x] `inventory/management/commands/compile_locales.py` created and tested to compile `.po` into `.mo`.
**Verification:**
- [x] Command succeeds: `python manage.py check`
- [x] Command succeeds: `python manage.py compile_locales`
**Dependencies:** Task 9
**Files likely touched:**
- `requirements.txt`
- `config/settings.py`
- `config/urls.py`
- `inventory/management/commands/compile_locales.py`
**Estimated scope:** Medium (4 files)

---

### Task 11: UI Translation Coverage (Templates, Forms, Views, Navbar Switcher & Spanish Catalog)
**Description:** Mark all static UI strings in templates, forms, models, and views with gettext hooks. Add an accessible manual language toggle in the navbar. Create `locale/es/LC_MESSAGES/django.po` with complete, accurate Spanish translations for all marked strings, and compile to `django.mo`.
**Acceptance criteria:**
- [x] Templates (`base.html`, `login.html`, `intake.html`, `dashboard.html`, `product_detail.html`) use `{% load i18n %}` and `{% trans %}` / `{% blocktrans %}`.
- [x] Navigation header contains a clean language switcher toggle (`[🇬🇧 EN | 🇪🇸 ES]`).
- [x] Form labels, help texts, validation error messages, and flash notifications wrapped with `gettext_lazy` / `gettext`.
- [x] Complete Spanish catalog written in `locale/es/LC_MESSAGES/django.po` and compiled to binary `django.mo`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
**Dependencies:** Task 10
**Files likely touched:**
- `inventory/templates/inventory/base.html`
- `inventory/templates/inventory/intake.html`
- `inventory/templates/inventory/dashboard.html`
- `inventory/templates/inventory/product_detail.html`
- `inventory/templates/registration/login.html`
- `inventory/forms.py`
- `inventory/views.py`
- `locale/es/LC_MESSAGES/django.po`
**Estimated scope:** Large (8 files)

---

### Task 12: Localized Gemini AI Prompting & i18n Automated Testing
**Description:** Update `services/ai_service.py` to adapt its system instructions to the active user language (generating Spanish title & description when in Spanish session), and create a comprehensive automated test suite `tests/test_i18n.py`.
**Acceptance criteria:**
- [x] `generate_product_listing(product, language=...)` adapts system prompt to output Spanish listing copy when `language == 'es'`.
- [x] `tests/test_i18n.py` validates:
  - Browser sending `Accept-Language: es` receives Spanish UI on login, intake, dashboard, and detail pages.
  - Browser sending `Accept-Language: en` or other languages falls back cleanly to English.
  - Form validation errors and flash messages render in the expected language.
  - Manual switcher sets language cookie and overrides browser header.
  - AI prompt language selection works correctly.
- [x] All 39 existing tests plus all new i18n tests pass (51 total tests).
- [x] Code formatting check passes: `ruff check .`
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_i18n`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 11
**Files likely touched:**
- `inventory/services/ai_service.py`
- `tests/test_ai_service.py`
- `tests/test_i18n.py`
**Estimated scope:** Medium (3 files)

---

## Checkpoint 5: Multi-Language Verification
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] Browser language detection and manual language switcher verified end-to-end.

---

## Phase 6: Oracle Cloud Infrastructure Object Storage Integration

### Task 13: Dependency Installation & OCI Storage Backend Configuration
**Description:** Add `django-storages` and `boto3` to `requirements.txt`, install in `.venv`, configure `config/settings.py` with `STORAGES` dictionary pointing to OCI S3-compatible backend (or test fallback when unconfigured), and update `.env.example` with documented OCI environment variables (`OCI_STORAGE_ACCESS_KEY`, `OCI_STORAGE_SECRET_KEY`, `OCI_STORAGE_BUCKET_NAME`, `OCI_STORAGE_NAMESPACE`, `OCI_STORAGE_REGION`, `OCI_STORAGE_ENDPOINT_URL`).
**Acceptance criteria:**
- [x] `django-storages` and `boto3` added to `requirements.txt` and installed in `.venv`.
- [x] `config/settings.py` configures `STORAGES['default']` for OCI Object Storage when credentials are provided, with clean local/in-memory fallback when unconfigured or testing.
- [x] `.env.example` updated with OCI Object Storage configuration variables.
**Verification:**
- [x] Command succeeds: `python manage.py check`
**Dependencies:** Checkpoint 5
**Files likely touched:**
- `requirements.txt`
- `config/settings.py`
- `.env.example`
**Estimated scope:** Small (3 files)

---

### Task 14: In-Memory WebP Image Pipeline & Cloud Storage Integration
**Description:** Ensure that `inventory/services/image_service.py` processes WebP entirely in-memory using `io.BytesIO` / `ContentFile` so image saving directly streams to the configured storage backend. Ensure `ProductImage.image.url` generates cloud URLs. Ensure `product_download_zip_view` and `generate_product_listing` stream image bytes directly via `img_obj.image.open('rb')` without requiring local filesystem paths.
**Acceptance criteria:**
- [x] `process_and_convert_to_webp` converts and validates in-memory without creating temporary files on local disk.
- [x] `ProductImage.image` saves directly to the configured storage backend.
- [x] `product_download_zip_view` streams file bytes from cloud storage into the in-memory ZIP archive.
- [x] `ai_service.py` reads image bytes directly from cloud storage for Gemini Multimodal Vision analysis.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_image_service tests.test_zip_download`
**Dependencies:** Task 13
**Files likely touched:**
- `inventory/services/image_service.py`
- `inventory/views.py`
- `inventory/services/ai_service.py`
**Estimated scope:** Small (3 files)

---

### Task 15: Storage Integration Tests & Test Mocking
**Description:** Implement `tests/test_storage.py` validating that image uploads store files via the cloud storage backend, URL resolution builds the proper OCI endpoint, streaming ZIP and AI vision work with cloud-backed files, and no persistent files are written to local disk. Ensure all 51 existing tests continue passing without requiring live OCI credentials.
**Acceptance criteria:**
- [x] `tests/test_storage.py` tests OCI storage backend upload, retrieval, and URL generation.
- [x] Tests verify that `media/products/` remains empty after image creation.
- [x] All 51 existing tests plus new storage tests pass (57 total tests).
- [x] Linter passes: `ruff check .`.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_storage`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 14
**Files likely touched:**
- `tests/test_storage.py`
**Estimated scope:** Small (1-2 files)

---

## Checkpoint 6: Oracle Object Storage Verification
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] Product images upload to OCI Object Storage bucket, leaving zero local disk files.

---

## Phase 7: Catalog Pagination & Multi-Field Search

### Task 16: Multi-Field Search Query & Date Parser Logic
**Description:** Implement robust multi-field search logic in `inventory/views.py` (or a dedicated `inventory/services/search_service.py` helper). The search must match across `ai_title`, `raw_note`, `ai_description`, and dynamically parse date inputs (ISO `YYYY-MM-DD`, slashed `DD/MM/YYYY`, `MM/DD/YYYY`, year-month `YYYY-MM`, and 4-digit year `YYYY`) to filter by `created_at__date` and `sold_at__date`.
**Acceptance criteria:**
- [x] Text search queries match `ai_title`, `raw_note`, and `ai_description`.
- [x] Date queries in `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, and `YYYY-MM` formats correctly match `created_at__date` and `sold_at__date`.
- [x] Non-date text queries do not raise parsing exceptions.
- [x] Query composition preserves existing status filtering (`all`, `active`, `sold`).
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_pagination_search`
**Dependencies:** Checkpoint 6
**Files likely touched:**
- `inventory/views.py`
- `tests/test_pagination_search.py`
**Estimated scope:** Small (2 files)

---

### Task 17: Dashboard Server-Side Pagination & Query-Preserving UI Navigation
**Description:** Update `dashboard_view` in `inventory/views.py` to paginate catalog products at max 20 items per page (`PAGE_SIZE = 20`) using Django's `Paginator`. Update `inventory/templates/inventory/dashboard.html` to render products from `page_obj`, display a responsive pagination toolbar with Previous/Next buttons, item summary counter ("Showing X to Y of Z products"), and elided page numbering, ensuring that all navigation links preserve existing `q` and `status` query parameters.
**Acceptance criteria:**
- [x] Catalog listings cap at 20 products per page (`PAGE_SIZE = 20`).
- [x] Out-of-bounds or non-integer page requests fallback gracefully (`paginator.get_page`).
- [x] Template displays "Showing X to Y of Z products" summary count.
- [x] Previous and Next buttons render with appropriate disabled/active states.
- [x] Page links retain active search query and status filter in URL query strings.
- [x] Sourcing assistant `/intake/` recent uploads remains unpaginated (5 items).
**Verification:**
- [x] Visual verification and DOM structure inspection in browser.
- [x] Unit tests pass: `python manage.py test tests.test_pagination_search`
**Dependencies:** Task 16
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/dashboard.html`
**Estimated scope:** Medium (2 files)

---

### Task 18: i18n Translation & Comprehensive Unit/Integration Test Suite
**Description:** Update `locale/es/LC_MESSAGES/django.po` to provide natural Spanish translations for all new pagination and search labels (e.g. "Showing %(start)d to %(end)d of %(total)d products", "Previous", "Next", "Page %(current)d of %(total)d", search placeholder). Compile catalogs to `.mo` via `python manage.py compile_locales`. Implement full test suite in `tests/test_pagination_search.py` verifying pagination across multiple pages, boundary handling, date search, text search, combined filters, and Spanish rendering.
**Acceptance criteria:**
- [x] All new pagination strings marked with `{% trans %}` or `_()`.
- [x] Spanish translations added to `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] `tests/test_pagination_search.py` contains tests covering:
  - Catalog with >20 items paginating properly (page 1, page 2).
  - Out of range page numbers.
  - Search by title, raw note, description.
  - Search by date (ISO, European, Year-Month).
  - Combined search + status filter + pagination parameter preservation.
  - Spanish localized pagination UI rendering.
- [x] Full test suite passes: `python manage.py test`.
- [x] Linter passes: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 17
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_pagination_search.py`
**Estimated scope:** Medium (3 files)

---

## Checkpoint 7: Pagination & Search Verification
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] Catalog dashboard renders at max 20 items per page with query-preserving pagination links.
- [x] Multi-field search works for title, description, and date queries in English and Spanish.

---

## Phase 8: User Management & Django Admin Role Gating

### Task 19: Custom ManagerAdminSite & Role Gating
**Description:** Implement custom `ManagerAdminSite` subclassing `admin.AdminSite` in `inventory/admin.py` (or registering it in `config/urls.py`). Override `has_permission` to strictly enforce `is_manager(request.user)`. When an authenticated non-manager (such as an assistant) navigates to `/admin/`, return HTTP 403 Forbidden with a clear permission denied response. Customize admin branding headers (`site_header`, `site_title`, `index_title`).
**Acceptance criteria:**
- [x] Users in `managers` group or superusers can access `/admin/`.
- [x] Users in `assistants` group attempting to access `/admin/` receive HTTP 403 Forbidden.
- [x] Anonymous users accessing `/admin/` are directed to login.
- [x] Custom admin titles and headers are localized.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_admin_user_management`
**Dependencies:** Checkpoint 7
**Files likely touched:**
- `inventory/admin.py`
- `config/urls.py`
- `tests/test_admin_user_management.py`
**Estimated scope:** Small (3 files)

---

### Task 20: Enhanced CustomUserAdmin with Role Badges & Productivity Counts
**Description:** Customize `User` model administration in `inventory/admin.py` via `CustomUserAdmin` (inheriting from `django.contrib.auth.admin.UserAdmin`). Add `role_badge` column in `list_display`, `cataloged_items_count` column linking to items created by the user, custom role filter (`RoleListFilter`), automatic synchronization of `is_staff` when saving users (`save_model`), and quick admin actions to assign Assistant role, assign Manager role, and safely deactivate users (`is_active=False`).
**Acceptance criteria:**
- [x] User list displays role badges (`Superuser`, `Manager`, `Assistant`).
- [x] User list displays cataloged items count with optimized annotation query (no N+1).
- [x] Saving a user automatically sets `is_staff=True` if in `managers` and `is_staff=False` if only in `assistants`.
- [x] Admin actions `make_assistant`, `make_manager`, and `deactivate_users` execute properly.
- [x] Navigation bar admin link in `base.html` conditionally appears for managers (`can_manage` / `is_manager`).
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_admin_user_management`
**Dependencies:** Task 19
**Files likely touched:**
- `inventory/admin.py`
- `inventory/templates/inventory/base.html`
- `tests/test_admin_user_management.py`
**Estimated scope:** Medium (3 files)

---

### Task 21: i18n Translations & Comprehensive Admin Test Suite
**Description:** Update `locale/es/LC_MESSAGES/django.po` to translate all custom admin role badges, column headers, action descriptions, and filter titles. Compile with `python manage.py compile_locales`. Implement full test suite in `tests/test_admin_user_management.py` verifying admin access gating (manager access, assistant 403, anonymous redirect), user creation, role assignment, deactivation, and catalog count display.
**Acceptance criteria:**
- [x] All new admin strings marked with `_()` and translated into Spanish in `django.po`.
- [x] `compile_locales` succeeds without error.
- [x] `tests/test_admin_user_management.py` covers:
  - Manager can log into admin.
  - Assistant gets 403 Forbidden on admin.
  - Role badges and cataloged counts rendered.
  - Actions `make_assistant`, `make_manager`, `deactivate_users` function properly.
  - Role synchronization on save.
- [x] Full test suite passes: `python manage.py test`.
- [x] Linter passes: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 20
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_admin_user_management.py`
**Estimated scope:** Medium (3 files)

---

## Checkpoint 8: User Management Verification
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] `/admin/` access is strictly gated to managers; assistants receive 403.
- [x] Custom user admin displays role badges, catalog counts, and handles role/deactivation actions.

---

## Phase 9: Dynamic AI Model & Prompt Configuration (Vertical Slice 6)

### Task 22: AIPromptConfiguration Domain Model, Migrations & Initial Seed
**Description:** Define the `AIPromptConfiguration` model in `inventory/models.py` with fields `language`, `model_name` (CharField default `"gemini-2.5-flash"`), `temperature` (FloatField default 0.3 with validators `0.0`–`1.0`), `system_instruction` (TextField), `is_active` (BooleanField default True), and audit timestamps. Implement custom `save()` logic enforcing Option A: saving an active config (`is_active=True`) automatically sets any other configuration for the same language to `is_active=False`. Generate schema migration and create data migration to seed the active defaults for Spanish and English.
**Acceptance criteria:**
- [x] `AIPromptConfiguration` model defined with all fields, validators, and localized verbose names.
- [x] Model `save()` method automatically deactivates other active configurations for the same language when `is_active=True`.
- [x] Schema migration generated and applied cleanly.
- [x] Data migration seeds active default records for `es` and `en` with current production prompts and model `gemini-2.5-flash`.
**Verification:**
- [x] Command succeeds: `python manage.py makemigrations --check --dry-run`
- [x] Command succeeds: `python manage.py migrate`
**Dependencies:** Checkpoint 8
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/`
- `tests/test_models.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 23: Django Admin Registration & Form Validation (AIPromptConfigurationAdmin)
**Description:** Register `AIPromptConfiguration` in `inventory/admin.py` under `ManagerAdminSite`. Provide structured fieldsets (`Model Parameters`, `Copywriting & Prompt Instructions`, `Status`), `list_display` (`language`, `model_name`, `temperature`, `is_active`, `updated_at`), list filters (`is_active`, `language`), search fields (`model_name`, `system_instruction`), and helpful admin guidance on how prompt instructions are safely embedded within the system output schema envelope.
**Acceptance criteria:**
- [x] `AIPromptConfigurationAdmin` registered on `admin.site` (which is `ManagerAdminSite`).
- [x] List view shows language, model name, temperature, active status, and updated timestamp.
- [x] Accessible strictly to managers; assistants denied via existing site permission gating.
- [x] Validation prevents temperature out of `[0.0, 1.0]`.
**Verification:**
- [x] Command succeeds: `python manage.py check`
- [x] Unit tests pass: `python manage.py test tests.test_admin_user_management`
**Dependencies:** Task 22
**Files likely touched:**
- `inventory/admin.py`
**Estimated scope:** Small (1 file)

---

### Task 24: AI Service Integration with Dynamic Lookup & Resilient Fallback
**Description:** Refactor `generate_product_listing(product, model_name=None, language="en")` in `inventory/services/ai_service.py` to dynamically fetch the active `AIPromptConfiguration` for the resolved language. If found, use configured `model_name` (unless explicitly overridden in kwargs), `temperature`, and `system_instruction`. If not found or if a database query error occurs, transparently fall back to hardcoded defaults without crashing. Merge user copywriting instructions into the immutable system envelope that injects `product.raw_note` and guarantees `ProductListingSchema` JSON output.
**Acceptance criteria:**
- [x] `generate_product_listing` dynamically queries `AIPromptConfiguration.objects.filter(language=..., is_active=True).first()`.
- [x] Passes dynamic model name to `client.models.generate_content(model=...)` and temperature to `types.GenerateContentConfig(temperature=...)`.
- [x] If no active DB record exists, seamlessly uses hardcoded defaults without raising exceptions.
- [x] Technical schema envelope and field note preservation remain completely intact.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_ai_service`
**Dependencies:** Task 22, Task 23
**Files likely touched:**
- `inventory/services/ai_service.py`
**Estimated scope:** Small (1-2 files)

---

### Task 25: i18n Translations & Comprehensive AI Configuration Test Suite
**Description:** Extract and translate all new user-facing and admin strings into Spanish in `locale/es/LC_MESSAGES/django.po` and compile catalogs with `python manage.py compile_locales`. Implement comprehensive automated tests in `tests/test_ai_service.py` and `tests/test_models.py` covering: dynamic model override, dynamic temperature forwarding, active config switching/demotion, empty/missing DB fallback, and admin access control. Ensure all repository checks pass.
**Acceptance criteria:**
- [x] All new model fields and admin labels translated in `django.po` and compiled to `django.mo`.
- [x] Unit tests verify:
  - Database config override for model, temperature, and instructions.
  - Automatic deactivation of existing configuration when a new one is set to active (Option A).
  - Resilient fallback to defaults when DB has no active configuration or raises an exception.
  - Temperature forwarded to GenAI config.
- [x] Full test suite passes: `python manage.py test`.
- [x] Linter passes: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 24
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_ai_service.py`
- `tests/test_models.py`
**Estimated scope:** Medium (3-4 files)

---

## Checkpoint 9: Dynamic AI Configuration Complete
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] Managers can configure Gemini model name, temperature, and prompt copy in `/admin/`.
- [x] Active config changes immediately reflect in listing generation.
- [x] Fallback ensures 100% resilience when database configuration is absent.

---

## Phase 10: Marketplace Sites & External Listing Links Tracking (Vertical Slice 7)

### Task 26: Marketplace Platforms & Listing Links Domain Models, Migrations & Initial Seed
**Description:** Implement `MarketplaceSite` (`name`, `slug`, `base_url`, `is_active`, `order`, timestamps) and `ProductListingLink` (`product`, `site`, `url`, `is_active`, timestamps) models in `inventory/models.py`. Configure unique constraint `(product, site)` on `ProductListingLink`, URL validation, ordering, and verbose names with `gettext_lazy`. Generate schema migration and create data migration seeding default platforms (Wallapop, Vinted, Milanuncios, eBay).
**Acceptance criteria:**
- [x] `MarketplaceSite` and `ProductListingLink` models created with required fields, constraints, and string representations.
- [x] Schema migration created and applied cleanly.
- [x] Data migration seeds active platforms: Wallapop (`https://es.wallapop.com`), Vinted (`https://www.vinted.es`), Milanuncios (`https://www.milanuncios.com`), and eBay (`https://www.ebay.es`).
**Verification:**
- [x] Command succeeds: `python manage.py makemigrations --check --dry-run`
- [x] Command succeeds: `python manage.py migrate`
**Dependencies:** Checkpoint 9
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/`
**Estimated scope:** Medium (3-4 files)

---

### Task 27: Django Admin Integration (MarketplaceSiteAdmin & ProductListingLinkInline)
**Description:** Register `MarketplaceSite` in `inventory/admin.py` under `ManagerAdminSite`. Provide list display (`name`, `slug`, `base_url`, `is_active`, `order`, `links_count`), list editable (`is_active`, `order`), search fields (`name`, `slug`, `base_url`), and prepopulated slug from name. Register `ProductListingLinkInline` as a `TabularInline` in `ProductAdmin` to inspect and edit listing URLs directly on the product admin change page. Ensure assistant users are strictly denied access via site-level permission gating.
**Acceptance criteria:**
- [x] `MarketplaceSiteAdmin` registered under `admin_site` with list display, search, and ordering.
- [x] `ProductListingLinkInline` displayed within `ProductAdmin`.
- [x] Non-manager assistants cannot access `/admin/` or manipulate sites/links.
**Verification:**
- [x] Command succeeds: `python manage.py check`
**Dependencies:** Task 26
**Files likely touched:**
- `inventory/admin.py`
**Estimated scope:** Small (1 file)

---

### Task 28: Product Detail Page Listing Links Management (Form Handling & Template UI)
**Description:** Implement listing links management on the product detail staging page (`/products/<pk>/`). In `inventory/views.py`, prefetch product links and active sites, and handle link additions, updates, or removals (restricted to managers). Update `inventory/templates/inventory/product_detail.html` with a dedicated "Marketplace Links" card displaying active platforms, live link navigation (`target="_blank" rel="noopener noreferrer"`), one-click copy URL button, and manager-only edit/delete controls (with read-only view for assistants).
**Acceptance criteria:**
- [x] Product detail page displays an integrated card listing all active marketplace platforms.
- [x] Managers can add, update, and remove URLs for any active platform directly on the page.
- [x] Saved links provide direct clickable external links and one-click copy buttons.
- [x] Assistants have read-only visibility (can click links and copy URLs, but cannot edit or delete).
**Verification:**
- [x] Manual test: Staging page loads with active platforms, link is saved, copied, and opened in new tab.
**Dependencies:** Task 26, Task 27
**Files likely touched:**
- `inventory/forms.py`
- `inventory/views.py`
- `inventory/templates/inventory/product_detail.html`
**Estimated scope:** Medium (3 files)

---

### Task 29: i18n Translations & Comprehensive Test Suite for Marketplace Tracking
**Description:** Translate all new model fields, admin strings, and product detail UI elements into Spanish in `locale/es/LC_MESSAGES/django.po` and compile catalogs with `compile_locales`. Implement comprehensive tests in `tests/test_marketplace_sites.py` covering: model validation, unique constraint on `(product, site)`, seed migration data, admin permission gating, product detail view CRUD and role enforcement, and translation catalog integrity. Ensure full repository test suite and linter pass.
**Acceptance criteria:**
- [x] All new strings translated in `locale/es/` and compiled to binary `.mo`.
- [x] Comprehensive unit & integration tests written in `tests/test_marketplace_sites.py` covering models, admin, views, permissions, and validation.
- [x] Full test suite passes: `python manage.py test`.
- [x] Linter passes: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 28
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_marketplace_sites.py`
**Estimated scope:** Medium (3-4 files)

---

## Checkpoint 10: Marketplace Sites Tracking Complete
- [x] All unit and integration tests pass (`python manage.py test`).
- [x] Code passes `ruff check .`.
- [x] Managers can add and manage marketplace platforms in Django admin.
- [x] Product detail page displays marketplace listing links with external navigation and one-click copy.
- [x] Managers can edit/delete links, while assistants have read-only access.
- [x] All features localized in Spanish and English.

---

## Phase 11: Dashboard Marketplace Platform Filter (Vertical Slice 6)

### Task 30: Backend Filtering & Dynamic Platform Aggregation in `dashboard_view`
**Description:** Update `dashboard_view` in `inventory/views.py` to aggregate platforms that currently have active published links (`product_links__is_active=True`), extract the `platform` query parameter (`?platform=<slug>`), filter the product catalog using `listing_links__site__slug`, scope status counters (`total_count`, `active_count`, `sold_count`) to the selected platform, and ensure pagination preserves the `platform` parameter in `query_string`.
**Acceptance criteria:**
- [x] `available_platforms` queryset only includes `MarketplaceSite` records where `product_links__is_active=True` count > 0, annotated with `published_count`.
- [x] `platform_filter` parses `request.GET.get('platform')` and filters `products` by `listing_links__site__slug` with `.distinct()`.
- [x] Status counters (`total_count`, `active_count`, `sold_count`) dynamically update to count products matching the active platform filter.
- [x] Invalid or empty platform parameter cleanly defaults to all products without raising exceptions.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_marketplace_sites`
**Dependencies:** Checkpoint 10
**Files likely touched:**
- `inventory/views.py`
**Estimated scope:** Small (1 file)

---

### Task 31: Dashboard Template UI for Platform Selector & Multi-Filter Composition
**Description:** Add a responsive platform selector dropdown to the dashboard filter toolbar in `inventory/templates/inventory/dashboard.html`. The selector lists "All Platforms" / "Todas las plataformas" and each available platform with its count (`Name (count)`), auto-submits on change (`onchange="this.form.submit()"`), preserves active `status` and `q` search parameters, and ensures status tabs and search clear buttons preserve the selected platform.
**Acceptance criteria:**
- [x] Styled platform dropdown `<select>` rendered in the dashboard toolbar with Tailwind styling.
- [x] Options show platform name and published count (`Wallapop (12)`).
- [x] Selecting a platform auto-submits the form and refreshes the catalog.
- [x] Status tabs ("All", "Active", "Sold") preserve `&platform=<slug>` when clicked.
- [x] Search form preserves `<input type="hidden" name="platform" value="{{ platform_filter }}">`.
- [x] Pagination controls preserve `platform` across page changes.
**Verification:**
- [x] Manual check: Dashboard displays dropdown with counts, switching platform updates list and preserves status/search/pagination.
**Dependencies:** Task 30
**Files likely touched:**
- `inventory/templates/inventory/dashboard.html`
**Estimated scope:** Small (1 file)

---

### Task 32: i18n Translations & Comprehensive Automated Test Suite for Platform Filter
**Description:** Translate all new user-facing strings into Spanish in `locale/es/LC_MESSAGES/django.po` and compile catalogs. Implement comprehensive unit and integration tests in `tests/test_marketplace_sites.py` verifying: dynamic platform queryset (only platforms with published products), catalog filtering by platform, multi-filter composition with status and search, status counter scoping to platform, invalid platform slug handling, and pagination parameter retention. Document changes in `CHANGELOG.md`.
**Acceptance criteria:**
- [x] All new strings translated in `locale/es/` and compiled to `.mo`.
- [x] Comprehensive tests written covering platform query annotation, filter by platform, status tab scoping, search combinations, and pagination.
- [x] Full repository test suite passes: `python manage.py test`.
- [x] Linter passes: `ruff check .`.
- [x] `CHANGELOG.md` updated under `[Unreleased]`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 31
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_marketplace_sites.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (3-4 files)

---

## Checkpoint 11: Platform Filter Complete
- [x] Platform selector displays only platforms with active published links and their product count.
- [x] Catalog filters accurately by selected platform with instant auto-submit.
- [x] Status counters ("All", "Active", "Sold") dynamically update to reflect the scoped platform.
- [x] Filter state is retained across status tabs, search queries, and pagination.
- [x] Selecting "All Platforms" returns to the full catalog.
- [x] Full test suite and linter pass cleanly.

---

## Phase 12: Product Clarifications & Lifecycle States (Vertical Slice 8)

### Task 33: Domain Models & Migration for Lifecycle States & Clarifications
**Description:** Implement `ProductStatus` TextChoices (`DRAFT`, `AWAITING_INFO`, `READY`, `SOLD`, `BLOCKED`) and add `status` field to `Product` model. Maintain 100% backward compatibility by keeping `is_sold` property and database column synchronized on save. Create `ProductClarification` model with fields `product`, `category` (Choices: `MEASUREMENTS`, `TAG_COMPOSITION`, `FLAWS_CONDITION`, `MATERIAL_AUTHENTICITY`, `GENERAL`), `question`, `asked_by`, `answer`, `answered_by`, `status` (`PENDING`, `RESOLVED`), and timestamps. Register in Django admin with `ProductClarificationInline` and `ProductClarificationAdmin`. Create and apply migration `0007` populating status for existing products.
**Acceptance criteria:**
- [x] `Product.status` field created with choices `draft`, `awaiting_info`, `ready`, `sold`, `blocked` (default: `draft`, db_index=True).
- [x] `is_sold` column kept in sync: setting `is_sold=True` sets `status=ProductStatus.SOLD`; setting `status=ProductStatus.SOLD` sets `is_sold=True`.
- [x] `ProductClarification` model created with foreign keys to `Product` and `User`, category choices, and `status` (`pending`, `resolved`).
- [x] Django admin registered for `ProductClarification` and as an inline in `ProductAdmin`.
- [x] Migration applied cleanly to SQLite database.
**Verification:**
- [x] Command succeeds: `python manage.py makemigrations --check --dry-run`
- [x] Unit tests pass: `python manage.py test tests.test_clarifications`
**Dependencies:** Checkpoint 11
**Files likely touched:**
- `inventory/models.py`
- `inventory/admin.py`
- `inventory/migrations/0007_product_status_and_clarification.py`
- `tests/test_clarifications.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 34: Global Notification Context Processor, Top Nav Badge & Mobile Intake Banner
**Description:** Create `inventory/context_processors.py` with `notifications(request)` returning `pending_clarifications_count`. Register it in `config/settings.py` template options. Update `inventory/templates/inventory/base.html` to display a high-visibility badge `❓ Dudas (X)` adjacent to navigation links for authenticated users when pending questions exist, linking to `/dashboard/?status=awaiting_info`. Add a dismissible alert banner to `inventory/templates/inventory/intake.html` informing assistants when items await their feedback.
**Acceptance criteria:**
- [x] Context processor `inventory.context_processors.notifications` returns `{"pending_clarifications_count": X}` for authenticated users.
- [x] Registered in `config/settings.py` `TEMPLATES['OPTIONS']['context_processors']`.
- [x] Top navigation renders `❓ Dudas (X)` when `pending_clarifications_count > 0`, linking to `{% url 'inventory:dashboard' %}?status=awaiting_info`.
- [x] Mobile intake screen (`/intake/`) renders an alert banner alerting assistants to pending questions.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_clarifications`
- [x] Manual check: Badge appears when a pending clarification is created and disappears when resolved.
**Dependencies:** Task 33
**Files likely touched:**
- `inventory/context_processors.py`
- `config/settings.py`
- `inventory/templates/inventory/base.html`
- `inventory/templates/inventory/intake.html`
- `tests/test_clarifications.py`
**Estimated scope:** Medium (4-5 files)

---

### Task 35: Product Detail Staging Q&A UI & Clarification Interaction Flow
**Description:** Enhance the product staging page (`/products/<pk>/`) to display a color-coded lifecycle status badge and a dedicated Clarification Q&A card. Managers can select category chips (*Medidas*, *Etiqueta*, *Defectos*, *Material*, *General*), enter questions, and submit, automatically transitioning product status to `AWAITING_INFO`. Assistants can view pending questions, submit answers via a mobile-friendly form, marking the clarification resolved. When all open questions for a product are answered, status automatically transitions to `READY`, and a visual callout prompts the manager: *"✨ Nuevos datos disponibles — Regenerar descripción con IA"*. Add a publishing gate warning on the marketplace links card if status is `AWAITING_INFO` or `BLOCKED`.
**Acceptance criteria:**
- [x] Product status badge rendered in header with color-coded states (`draft`, `awaiting_info`, `ready`, `sold`, `blocked`).
- [x] Managers can submit new clarification questions with category chips, shifting product status to `AWAITING_INFO`.
- [x] Assistants can submit answers to pending questions on `/products/<pk>/`, marking them `resolved`.
- [x] Answering the final pending question on a product automatically transitions its status to `READY`.
- [x] Staging page displays a prominent banner when resolved answers are ready for AI regeneration.
- [x] Marketplace links card displays a caution alert when product is in `AWAITING_INFO` or `BLOCKED` status.
**Verification:**
- [x] Unit & integration tests pass: `python manage.py test tests.test_clarifications`
**Dependencies:** Task 34
**Files likely touched:**
- `inventory/views.py`
- `inventory/forms.py`
- `inventory/templates/inventory/product_detail.html`
- `tests/test_clarifications.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 36: Dashboard Status Filtering, Dynamic Status Counters & AI Prompt Integration
**Description:** Update `dashboard_view` in `inventory/views.py` to support filtering by `status=awaiting_info` and `status=blocked` alongside `all`, `active`, and `sold`. Scope status counters (`total_count`, `active_count`, `awaiting_info_count`, `sold_count`, `blocked_count`) dynamically to the active platform filter and search query. Update `inventory/templates/inventory/dashboard.html` status tab bar with badges. Update `generate_product_listing` in `inventory/services/ai_service.py` to format resolved clarifications into the Gemini prompt payload alongside `raw_note`.
**Acceptance criteria:**
- [x] Dashboard filters catalog by `status=awaiting_info` and `status=blocked`.
- [x] Status tab bar includes "Dudas pendientes" with scoped badge counter.
- [x] Status counters remain scoped to active platform filter (`?platform=<slug>`) and search query (`?q=<term>`).
- [x] `generate_product_listing` appends resolved clarification Q&As into the prompt context for Gemini Multimodal Vision.
**Verification:**
- [x] Unit & integration tests pass: `python manage.py test tests.test_clarifications`
**Dependencies:** Task 35
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/dashboard.html`
- `inventory/services/ai_service.py`
- `tests/test_clarifications.py`
**Estimated scope:** Medium (4 files)

---

### Task 37: i18n Translations, Documentation & Regression Testing
**Description:** Localize all new user-facing strings (statuses, categories, form labels, buttons, banners, badges) in Spanish (`locale/es/LC_MESSAGES/django.po`) and compile using `manage.py compile_locales`. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and `ruff check .` to verify 0 regressions.
**Acceptance criteria:**
- [x] All new strings translated in `locale/es/` and compiled to `.mo`.
- [x] Full test suite passes: `python manage.py test`.
- [x] Linter passes with 0 warnings: `ruff check .`.
- [x] `CHANGELOG.md` updated with feature description under `[Unreleased]`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 36
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `CHANGELOG.md`
**Estimated scope:** Small (3 files)

---

## Checkpoint 12: Product Clarifications & Lifecycle States Complete
- [x] Product lifecycle state machine active (`draft`, `awaiting_info`, `ready`, `sold`, `blocked`).
- [x] Managers can submit categorized questions, changing product status to `awaiting_info`.
- [x] Top nav badge `❓ Dudas (X)` and mobile intake alert notify assistants of pending questions.
- [x] Assistants can answer questions from mobile on product page, auto-transitioning status to `ready`.
- [x] Manager is alerted to regenerate AI listing when new answers are available.
- [x] Gemini Vision prompt includes resolved clarifications in generated copy.
- [x] Dashboard filters products by `status=awaiting_info` and scopes counters.
- [x] Spanish and English translations active.
- [x] Full test suite and linter pass with 0 errors.








