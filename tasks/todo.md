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

---

## Phase 13: Cloudflare Turnstile Bot & Login Protection

### Task 38: Turnstile Settings, Service & Global Context Processor
**Description:** Configure Turnstile environment variables and settings (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `TURNSTILE_ENABLED`, `TURNSTILE_TIMEOUT`) in `config/settings.py` and `.env.example`. Implement `inventory/services/turnstile_service.py` with `verify_turnstile_token(token, remote_ip=None)` enforcing fail-closed timeout policy and supporting official Cloudflare dummy test keys. Create `turnstile` context processor in `inventory/context_processors.py` and comprehensive unit tests in `tests/test_turnstile.py`.
**Acceptance criteria:**
- [x] Turnstile settings configured with safe defaults (`TURNSTILE_ENABLED=False` if keys omitted).
- [x] `verify_turnstile_token` returns `True` for valid tokens or Cloudflare pass dummy keys (`1x00000000000000000000AA`), and `False` on invalid tokens, timeouts (>5.0s), or 5xx responses.
- [x] Global context processor injects `TURNSTILE_SITE_KEY` and `TURNSTILE_ENABLED` across all templates.
- [x] Unit tests verify service logic, dummy keys, timeouts, and network exceptions offline.
**Verification:**
- [x] Unit tests pass: `python manage.py test tests.test_turnstile`
**Dependencies:** Checkpoint 12
**Files likely touched:**
- `config/settings.py`
- `.env.example`
- `inventory/services/turnstile_service.py`
- `inventory/context_processors.py`
- `tests/test_turnstile.py`
**Estimated scope:** Medium (4-5 files)

---

### Task 39: Public Login Protection (Form & Template)
**Description:** Create `TurnstileValidationMixin` and `TurnstileAuthenticationForm` in `inventory/forms.py` that validates the token during `clean()` before checking credentials. Update `CustomLoginView` in `inventory/views.py` to use `TurnstileAuthenticationForm`. Update `inventory/templates/registration/login.html` to load Cloudflare Turnstile script, render widget above submit button (`data-theme="light"`), and display localized Turnstile validation error messages.
**Acceptance criteria:**
- [x] When `TURNSTILE_ENABLED=True`, login submission without token or with invalid token fails validation.
- [x] Localized error messages display properly in `login.html`.
- [x] Valid Turnstile token authenticates assistants and managers successfully.
- [x] When `TURNSTILE_ENABLED=False`, login proceeds without requiring Turnstile.
**Verification:**
- [x] Integration tests pass: `python manage.py test tests.test_turnstile`
**Dependencies:** Task 38
**Files likely touched:**
- `inventory/forms.py`
- `inventory/views.py`
- `inventory/templates/registration/login.html`
- `tests/test_turnstile.py`
**Estimated scope:** Medium (4 files)

---

### Task 40: Django Admin Login Protection
**Description:** Implement `TurnstileAdminAuthenticationForm` in `inventory/forms.py` (inheriting from `TurnstileValidationMixin` and `AdminAuthenticationForm`). Set `ManagerAdminSite.login_form = TurnstileAdminAuthenticationForm` and pass `extra_context` in `inventory/admin.py`. Create `inventory/templates/admin/login.html` to render Turnstile script and widget above the admin submit button.
**Acceptance criteria:**
- [x] When `TURNSTILE_ENABLED=True`, `/admin/login/` renders Turnstile challenge widget with `data-theme="light"`.
- [x] Submitting admin login without token or with invalid token is rejected with validation error.
- [x] Submitting valid credentials and valid Turnstile token logs manager in to Django Admin.
- [x] When `TURNSTILE_ENABLED=False`, admin login operates without requiring Turnstile.
**Verification:**
- [x] Integration tests pass: `python manage.py test tests.test_turnstile`
**Dependencies:** Task 39
**Files likely touched:**
- `inventory/forms.py`
- `inventory/admin.py`
- `inventory/templates/admin/login.html`
- `tests/test_turnstile.py`
**Estimated scope:** Medium (4 files)

---

### Task 41: i18n Translations, Documentation & Regression Testing
**Description:** Add Spanish translations for Turnstile validation messages (*"Por favor, completa la verificación de seguridad."*, *"Error en la verificación de seguridad. Por favor, inténtalo de nuevo."*) in `locale/es/LC_MESSAGES/django.po` and compile using `compile_locales`. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and `ruff check .` to verify 0 regressions.
**Acceptance criteria:**
- [x] Spanish translations compiled to `django.mo`.
- [x] Full automated test suite passes: `python manage.py test`.
- [x] Linter passes with 0 warnings: `ruff check .`.
- [x] `CHANGELOG.md` updated with Turnstile feature notes under `[Unreleased]`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 40
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `CHANGELOG.md`
**Estimated scope:** Small (3 files)

---

## Checkpoint 13: Cloudflare Turnstile Bot & Login Protection Complete
- [x] Both `/login/` and `/admin/login/` render Turnstile challenge when enabled.
- [x] Valid tokens allow seamless login for assistants and managers.
- [x] Missing/invalid tokens reject login with localized error messages.
- [x] Fail-closed policy protects against timeout and network errors.
- [x] Local dev and CI run cleanly with `TURNSTILE_ENABLED=False` or test dummy keys.
- [x] Full test suite (187 tests) passes with 0 regressions.
- [x] Code is formatted and passes Ruff linting.

---

## Phase 14: SQLite Automated Cloud Backup & Disaster Recovery (Vertical Slice 10)

### Task 42: DatabaseBackupLog Model, Migration & Model Tests
**Description:** Implement `DatabaseBackupLog` model in `inventory/models.py` tracking backup execution metrics (`filename`, `remote_path`, `file_size`, `duration_seconds`, `status`, `trigger_type`, `triggered_by`, `error_message`, `created_at`) with proper choices and verbose names. Generate and apply migration `0009_databasebackuplog`. Write unit tests in `tests/test_backup.py` verifying model instantiation, default values, string representation, ordering, and helper methods.
**Acceptance criteria:**
- [x] `DatabaseBackupLog` model defined with all required fields in `inventory/models.py`.
- [x] Migration generated and applied cleanly (`python manage.py makemigrations inventory`, `python manage.py migrate`).
- [x] Unit tests in `tests/test_backup.py` verify model attributes, field defaults, and `__str__`.
**Verification:**
- [x] Migration check succeeds: `python manage.py migrate`
- [x] Model tests pass: `python manage.py test tests.test_backup`
**Dependencies:** Checkpoint 13
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/0009_databasebackuplog.py`
- `tests/test_backup.py`
**Estimated scope:** Small to Medium (3 files)

---

### Task 43: SQLite Hot-Backup, Compression & Cloud Upload Service
**Description:** Implement `inventory/services/backup_service.py` with `backup_database(retention_days=30, compress=True, local_only=False, dry_run=False, trigger_type='scheduled', triggered_by=None)`. Use SQLite native online backup API (`sqlite3.Connection.backup()`) to create hot snapshot, compress via `gzip` (`.sqlite3.gz`), upload to OCI Object Storage bucket under `backups/db/%Y/%m/` via Django storages/boto3, prune remote backups older than `retention_days`, record execution details in `DatabaseBackupLog`, and handle failures gracefully without raising unhandled exceptions. Configure backup settings (`DB_BACKUP_RETENTION_DAYS`, `DB_BACKUP_PREFIX`) in `config/settings.py` and `.env.example`.
**Acceptance criteria:**
- [x] `backup_database()` performs consistent hot backup using `sqlite3.Connection.backup()`.
- [x] Gzip compression reduces SQLite snapshot size and saves `.sqlite3.gz` archive.
- [x] Remote upload streams to OCI Object Storage when configured, or saves to local `backups/` directory when `local_only=True` or cloud storage unavailable.
- [x] Automated retention pruning deletes remote/local archives older than `retention_days`.
- [x] Every execution (success or failure) creates a corresponding `DatabaseBackupLog` record.
- [x] Settings `DB_BACKUP_RETENTION_DAYS` (default 30) and `DB_BACKUP_PREFIX` (default `backups/db/`) defined.
- [x] Unit tests with mocked storage test full backup flow, dry run, local mode, pruning, and error recovery.
**Verification:**
- [x] Service unit tests pass: `python manage.py test tests.test_backup`
**Dependencies:** Task 42
**Files likely touched:**
- `config/settings.py`
- `.env.example`
- `inventory/services/backup_service.py`
- `tests/test_backup.py`
**Estimated scope:** Medium (4 files)

---

### Task 44: Django Management Command `backup_db`
**Description:** Implement `inventory/management/commands/backup_db.py` exposing CLI options (`--retention-days <N>`, `--no-compress`, `--local-only`, `--dry-run`, `--quiet`). Wraps `backup_database()`, formats console output (or suppresses when `--quiet`), logs summary info, and returns exit code 0 on success and 1 on failure for cron/container scheduling.
**Acceptance criteria:**
- [x] `python manage.py backup_db` runs default hot backup and retention pruning with formatted console output.
- [x] Flags `--retention-days`, `--no-compress`, `--local-only`, `--dry-run`, and `--quiet` function as specified.
- [x] Exit code is 0 on successful backup and 1 on error.
- [x] Unit and command integration tests verify CLI invocation and options.
**Verification:**
- [x] Command tests pass: `python manage.py test tests.test_backup`
- [x] Command runs: `python manage.py backup_db --local-only --dry-run`
**Dependencies:** Task 43
**Files likely touched:**
- `inventory/management/commands/backup_db.py`
- `tests/test_backup.py`
**Estimated scope:** Small to Medium (2 files)

---

### Task 45: Django Admin Audit Log, On-Demand Backup & Failure Alert Banner
**Description:** Register `DatabaseBackupLog` in `inventory/admin.py` with `DatabaseBackupLogAdmin` (read-only logs, status badges, size formatting, duration, trigger type). Add top-bar action button to trigger "Crear copia de seguridad ahora" with intermediate confirmation view and flash feedback. Implement global failure alert banner in `inventory/templates/admin/base_site.html` (or admin template override) warning managers when the most recent backup status is `failed`.
**Acceptance criteria:**
- [x] `DatabaseBackupLogAdmin` displayed in `ManagerAdminSite` with colored status badges, human-readable file sizes (`KB`/`MB`), and read-only protection.
- [x] On-demand backup button with confirmation view triggers manual backup and logs `trigger_type='manual'`, associating `triggered_by=request.user`.
- [x] Prominent alert banner renders at the top of admin pages if the latest backup attempt failed.
- [x] Integration tests verify admin views, manual trigger flow, permission gating, and failure banner rendering.
**Verification:**
- [x] Admin tests pass: `python manage.py test tests.test_backup`
**Dependencies:** Task 44
**Files likely touched:**
- `inventory/admin.py`
- `inventory/templates/admin/`
- `tests/test_backup.py`
**Estimated scope:** Medium (3-4 files)

---

### Task 46: i18n Translations, Documentation & Full Regression Suite
**Description:** Add Spanish translations in `locale/es/LC_MESSAGES/django.po` for all backup-related model fields, status choices, admin labels, button texts, confirmation messages, and alert banners. Compile binary catalog using `python manage.py compile_locales`. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and `ruff check .` to verify 0 regressions.
**Acceptance criteria:**
- [x] Spanish translations compiled to `django.mo`.
- [x] Full automated test suite passes: `python manage.py test`.
- [x] Linter passes with 0 warnings: `ruff check .`.
- [x] `CHANGELOG.md` updated with backup feature notes under `[Unreleased]`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 45
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `CHANGELOG.md`
**Estimated scope:** Small (3 files)

---

## Checkpoint 14: Automated SQLite Cloud Backup Complete
- [x] Hot backup creates consistent SQLite snapshots during active writes without locking.
- [x] Compressed `.sqlite3.gz` archives upload to OCI Object Storage bucket.
- [x] Retention lifecycle prunes backups older than 30 days.
- [x] CLI command `python manage.py backup_db` runs reliably with exit codes 0/1.
- [x] Managers can review backup logs and trigger on-demand backups in Django admin.
- [x] Prominent warning banner alerts managers if the last backup failed.
- [x] Local dev and offline CI work cleanly without cloud credentials.
- [x] Full test suite passes with 0 regressions.
- [x] Code is formatted and passes Ruff linting.

---

## Phase 15: Smart Intake Pre-flight: On-Demand Item Identification, Advisory Guidance & Direct Pricing

### Task 47: Optional Direct Sale Price on Intake Form
**Description:** Add an optional `sale_price` field to `ProductIntakeForm` in `inventory/forms.py` (matching `Product.sale_price` bounds: min 0.00, max 9,999,999.99). Render the field in `inventory/templates/inventory/intake.html` between field notes and submit button with Euro (`€`) prefix, mobile numeric inputmode, and clean placeholder. Update `product_intake_view` in `inventory/views.py` to persist `sale_price` directly to `product.sale_price` when provided. Add unit and view integration tests in `tests/test_intake.py`.
**Acceptance criteria:**
- [x] `ProductIntakeForm` exposes an optional `sale_price` field validating non-negative decimal numbers.
- [x] `intake.html` renders the `sale_price` input with Euro (`€`) prefix styling and responsive layout.
- [x] `product_intake_view` assigns `sale_price` to `product.sale_price` on save if provided, leaving it `None` if blank.
- [x] Unit and integration tests verify intake creation with and without `sale_price`.
**Verification:**
- [x] Focused tests pass: `python manage.py test tests.test_intake.ProductIntakeViewTests`
- [x] Linter passes: `ruff check .`
**Dependencies:** None (Task 46)
**Files likely touched:**
- `inventory/forms.py`
- `inventory/templates/inventory/intake.html`
- `tests/test_intake.py`
**Estimated scope:** Medium (3 files)

---

### Task 48: AI Vision Pre-flight Service & Pydantic Schema
**Description:** Implement `IntakePreflightSchema` and `identify_intake_product(images_bytes, raw_note, language)` in `inventory/services/ai_service.py`. Takes in-memory image bytes (sliced to the first 3 photos per approved Option A) and calls Google Gemini Multimodal Vision API (`gemini-2.5-flash`). Returns structured JSON with `identified_title`, `category`, `detected_attributes`, `missing_or_recommended_info` (list of missing tags/flaws/details), and `suggested_note`. Implement comprehensive error handling and offline mock unit tests in `tests/test_ai_service.py`.
**Acceptance criteria:**
- [x] `IntakePreflightSchema` defined with Pydantic for structured Gemini output.
- [x] `identify_intake_product()` queries Gemini Vision with system instructions tailored to detecting item identity and flagging missing inspection details.
- [x] Image list is capped to the first 3 photos (`images_bytes[:3]`) for rapid mobile response and reduced token usage.
- [x] Returns `{ "success": True, ... }` on success, or `{ "success": False, "error": "..." }` on API failure without raising unhandled exceptions.
- [x] Unit tests mock Gemini client and verify prompt creation, schema parsing, 3-photo truncation, and error fallback.
**Verification:**
- [x] Focused tests pass: `python manage.py test tests.test_ai_service`
**Dependencies:** Task 47
**Files likely touched:**
- `inventory/services/ai_service.py`
- `tests/test_ai_service.py`
**Estimated scope:** Small to Medium (2 files)

---

### Task 49: Asynchronous Pre-flight Endpoint
**Description:** Implement view `intake_identify_view(request)` at `POST /inventory/intake/identify/` in `inventory/views.py` and register the route in `inventory/urls.py`. Gated by `@login_required` (available to both Assistants and Managers). Validates uploaded image files, reads image bytes, calls `identify_intake_product()`, and returns a `JsonResponse`. Ensures CSRF protection and validates image format/count without writing temporary files to disk.
**Acceptance criteria:**
- [x] Route `POST /inventory/intake/identify/` (name: `inventory:intake_identify`) registered in `inventory/urls.py`.
- [x] Gated by `@login_required`; unauthenticated requests return redirect or 403.
- [x] Validates presence of at least 1 image file; returns HTTP 400 with helpful JSON error if empty.
- [x] Calls `identify_intake_product()` and returns JSON payload with detected title, category, missing info tips, and suggested notes.
- [x] Unit and integration tests verify view authorization, file validation, and JSON responses.
**Verification:**
- [x] Focused tests pass: `python manage.py test tests.test_views.IntakeIdentifyViewTests`
**Dependencies:** Task 48
**Files likely touched:**
- `inventory/views.py`
- `inventory/urls.py`
- `tests/test_views.py`
**Estimated scope:** Small to Medium (3 files)

---

### Task 50: Mobile Intake UI: On-Demand Identify Button, Loading State & Advisory Banner
**Description:** Update `inventory/templates/inventory/intake.html` to integrate the on-demand pre-flight workflow. Add a "🔍 Identificar producto" button disabled when 0 photos are selected and active when ≥1 photo is chosen. Add client-side JavaScript to dispatch asynchronous `fetch()` with `FormData` to `/inventory/intake/identify/`. Display a loading spinner and "Analizando fotos con IA..." while request is in flight. Render a non-blocking advisory alert banner above `raw_note` upon response displaying detected item name and missing detail tips. Include an "Añadir sugerencia a notas" button that smart-appends `suggested_note` to `raw_note` (fills if empty, appends on new line if notes exist). Form submit button remains active and unblocked at all times.
**Acceptance criteria:**
- [x] "🔍 Identificar producto" button toggles enabled/disabled state based on file input selection.
- [x] Clicking button initiates async fetch with loading feedback without freezing form inputs or submit button.
- [x] Advisory banner renders detected title and bulleted missing detail recommendations.
- [x] Clicking "Añadir sugerencia a notas" populates `raw_note` (fills if empty, appends on new line if existing notes present).
- [x] If identification fails or is skipped, assistant can continue and submit the intake form normally without disruption.
**Verification:**
- [x] Manual template verification & client script checks.
- [x] View tests verify template rendering and context variables: `python manage.py test tests.test_views`
**Dependencies:** Task 49
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
- `tests/test_views.py`
**Estimated scope:** Medium (2 files)

---

### Task 51: i18n Translations, Documentation & Full Regression Suite
**Description:** Add Spanish translations in `locale/es/LC_MESSAGES/django.po` for all new UI strings, buttons, loading labels, placeholders, advisory banners, and error messages. Compile binary catalogs using `python manage.py compile_locales`. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite (`python manage.py test`) ensuring 0 regressions, and verify 0 Ruff lint issues.
**Acceptance criteria:**
- [x] Spanish translations compiled to `django.mo`.
- [x] `CHANGELOG.md` updated under `[Unreleased]` with Smart Intake Pre-flight and Direct Pricing details.
- [x] Full automated test suite passes: `python manage.py test`.
- [x] Linter passes with 0 warnings: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 50
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `CHANGELOG.md`
**Estimated scope:** Small (3 files)

---

## Checkpoint 15: Smart Intake Pre-flight & Direct Pricing Complete
- [x] Assistant can enter an optional sale price in € during intake and it persists directly to `product.sale_price`.
- [x] "Identificar producto" button activates on photo selection and dispatches an async vision analysis.
- [x] Vision service analyzes up to the first 3 photos and identifies brand/model while detecting missing inspection details.
- [x] Advisory banner alerts the assistant to missing details (e.g. size tag, flaw photos) without blocking upload.
- [x] "Añadir sugerencia a notas" smart-appends AI suggestions to the raw notes textarea.
- [x] Intake form remains 100% functional and submittable whether identification is used, skipped, or fails.
- [x] All new UI strings display cleanly in Spanish and English.
- [x] Full automated test suite passes with 0 regressions.
- [x] Code is formatted and passes Ruff linting.

---

## Phase 16: Intake Form Async Protection, Double-Submit Prevention & Client-Side Validation

### Task 52: Accessible Client-Side File Validations & Price Bounds without alert()
**Description:** Implement client-side validation logic and accessible DOM alerts in `inventory/templates/inventory/intake.html`. Replace all native `window.alert()` calls with an accessible inline alert banner (`#intakeClientAlert`) using `role="alert"` and `aria-live="polite"`. Add validation on form submit when 0 photos are chosen, rendering the warning message, applying a temporary warning ring (`ring-2 ring-rose-300 border-rose-400 bg-rose-50/40`) to `#dropZone`, and scrolling smoothly to the dropzone. Add pre-upload validation when photos are selected: if more than 10 images are chosen, reject the selection, reset the file input, and show an inline alert; if any file exceeds 10MB (`file.size > 10 * 1024 * 1024`), reject the selection, reset the input, and show an inline alert with the offending filename and size in MB. Auto-clear the error ring and alert banner as soon as at least one valid image is selected (per approved Option A). Ensure `sale_price` bounds check on input.
**Acceptance criteria:**
- [x] Submitting with 0 photos displays `#intakeClientAlert` with accessible text and highlights `#dropZone` with warning ring and smooth scroll without native `alert()`.
- [x] Selecting >10 photos resets input, clears preview, and displays `#intakeClientAlert` without native `alert()`.
- [x] Selecting any file >10MB rejects the selection, resets input, and displays `#intakeClientAlert` with filename and calculated size in MB.
- [x] Selecting valid photos automatically removes any active error ring on `#dropZone` and hides `#intakeClientAlert`.
- [x] Price input is validated to prevent negative numbers or invalid values.
**Verification:**
- [x] Browser manual / automated check verifies inline alerts appear and disappear cleanly without `window.alert()`.
- [x] Django template syntax checks pass: `python manage.py check`
**Dependencies:** None (Task 51)
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
**Estimated scope:** Small to Medium (1-2 files)

---

### Task 53: Form State Machine & Asynchronous Operation Blocking
**Description:** Implement an explicit client-side form state machine (`'idle'`, `'identifying'`, `'submitting'`) in `inventory/templates/inventory/intake.html`. When the assistant clicks "Identificar producto" (`#identifyBtn`), transition `formState` to `'identifying'`: disable `#identifyBtn` with spinner, disable `#submitBtn` (`opacity-60 cursor-not-allowed`) with a title tooltip (*"Espera a que finalice el análisis con IA..."*), and lock `#dropZone` / `#imageInput` (`pointer-events-none opacity-70`) so photos cannot be changed mid-analysis. When the pre-flight request completes (either success or failure), return `formState` to `'idle'`, re-enable `#submitBtn`, and restore interactivity to the dropzone. Add fail-safe recovery so network timeouts or fetch errors never leave the form permanently locked.
**Acceptance criteria:**
- [x] Clicking "Identificar producto" sets `formState = 'identifying'`.
- [x] While `identifying`, `#submitBtn` is disabled, has opacity reduced, and shows tooltip explaining AI analysis is in progress.
- [x] While `identifying`, `#dropZone` has `pointer-events-none` preventing image manipulation or replacement mid-request.
- [x] When identification resolves (success or error), `formState` returns to `'idle'`, re-enabling `#submitBtn` and `#dropZone`.
- [x] Unhandled fetch rejection or network timeout safely catches error and restores `formState = 'idle'`.
**Verification:**
- [x] Unit / view tests verify intake endpoint behavior: `python manage.py test tests.test_views.IntakeIdentifyViewTests`
- [x] Browser test script verifies submit button and dropzone are disabled during AI pre-flight.
**Dependencies:** Task 52
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
**Estimated scope:** Small (1 file)

---

### Task 54: Double-Submit Prevention & Submit Loading State
**Description:** Add double-submit prevention to the intake form in `inventory/templates/inventory/intake.html`. Attach an interceptor to the form's `submit` event using a synchronous boolean latch (`let isSubmitting = false;`). When submit is triggered, run client-side validation; if validation fails, prevent submit and keep `isSubmitting = false`. If validation passes and `isSubmitting` is false, set `isSubmitting = true`, transition `formState` to `'submitting'`, disable `#submitBtn`, show an animated SVG spinner, update button label to *"Guardando producto..."*, disable `#identifyBtn`, and set `pointer-events-none` on the form container. If a second tap or click occurs while `isSubmitting` is true, immediately call `e.preventDefault()` and return false, eliminating duplicate POST requests and duplicate product records.
**Acceptance criteria:**
- [x] Double-clicking or repeatedly tapping `#submitBtn` dispatches only 1 HTTP POST request.
- [x] Valid submission immediately shows loading spinner and changes text to *"Guardando producto..."*.
- [x] `#identifyBtn` and form controls are locked (`pointer-events-none`) during submission.
- [x] If client validation fails before submission, `isSubmitting` remains false and buttons remain interactive.
**Verification:**
- [x] Automated browser / integration test confirms repeated clicks produce exactly one POST and one database record.
- [x] View tests pass: `python manage.py test tests.test_intake`
**Dependencies:** Task 53
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
- `tests/test_intake.py`
**Estimated scope:** Small (2 files)

---

### Task 55: i18n Spanish Translations, Regression Tests & Playwright Browser Verification
**Description:** Add Spanish translations in `locale/es/LC_MESSAGES/django.po` for all new UI messages (0-photo alert, >10 photos alert, >10MB file alert, submit loading text, AI in-flight tooltip). Compile binary translation catalogs via `python manage.py compile_locales`. Update integration tests in `tests/test_intake.py` and `tests/test_views.py`. Run end-to-end browser verification script (`verify_intake_browser.py`) testing the full intake workflow, double-click protection, and async blocking in a real Chrome browser. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and Ruff linter.
**Acceptance criteria:**
- [x] All new UI strings localized in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] Unit & integration tests pass with 100% green: `python manage.py test`.
- [x] Real browser verification script runs and confirms double-click lock, async identify blocking, and validation alerts.
- [x] `CHANGELOG.md` updated under `[Unreleased]` with Phase 16 details.
- [x] Linter passes with 0 warnings: `ruff check .`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Browser script succeeds: `python .gemini/antigravity/brain/b80e4db2-82cf-46b6-b07e-3885a650d010/scratch/verify_intake_browser.py`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 54
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_intake.py`
- `tests/test_views.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4-5 files)

---

## Checkpoint 16: Intake Form Async Protection & Client-Side Validation Complete
- [x] Double-clicking or rapid tapping on the submit button never creates duplicate product records.
- [x] Triggering AI identification disables the submit button and locks the dropzone until the analysis resolves.
- [x] Submitting with 0 photos highlights the dropzone and displays an accessible inline alert without native `alert()`.
- [x] Selecting >10 photos or any photo >10MB rejects the invalid batch and shows an accessible inline alert.
- [x] Selecting a valid photo auto-clears the dropzone error ring and alert banner.
- [x] All new UI strings display cleanly in Spanish and English.
- [x] Full test suite passes with 0 regressions, and real browser verification confirms the user experience.



---

## Phase 17: Responsive Mobile Navigation & Collapsible Hamburger Drawer

### Task 56: Responsive Mobile Header Refactor & Hamburger Toggle Button
**Description:** Refactor the top navigation bar in `inventory/templates/inventory/base.html` to establish clean separation between desktop and mobile navigation using Tailwind `md:` (768px). On mobile screens (`< md`), hide the inline navigation links and inline language switcher. Introduce a prominent 44×44px hamburger toggle button (`#mobile-menu-button`) on the right side of the mobile header with full ARIA attributes (`aria-expanded="false"`, `aria-controls="mobile-menu"`, `aria-label`). The button contains an animated/swappable SVG icon displaying three horizontal bars (☰) when closed and an "✕" when open. Display a compact urgent attention pill `❓ (X)` directly on the mobile top bar next to the hamburger button when `pending_clarifications_count > 0` (Decision 27). Ensure desktop viewports (`≥ md`) hide the hamburger button (`md:hidden`) and render the complete horizontal header.
**Acceptance criteria:**
- [x] On screens `< 768px`, the header renders only the brand logo (`📦 2ndHand Staging`), the optional doubts pill `❓ (X)`, and `#mobile-menu-button`.
- [x] `#mobile-menu-button` meets WCAG 2.1 AA with minimum 44×44px touch target.
- [x] `#mobile-menu-button` has `aria-expanded="false"`, `aria-controls="mobile-menu"`, and localized `aria-label`.
- [x] Desktop screens (`≥ 768px`) hide `#mobile-menu-button` (`md:hidden`) and show full horizontal navigation.
- [x] Existing navigation IDs, links, and test invariants (`badge-pending-clarifications`, `name="language"`, `value="en"`, `value="es"`, `"Sign Out"`) remain preserved.
**Verification:**
- [x] Template syntax check: `python manage.py check`
- [x] Existing view tests continue to pass: `python manage.py test tests.test_views`
**Dependencies:** Checkpoint 16
**Files likely touched:**
- `inventory/templates/inventory/base.html`
- `tests/test_views.py`
**Estimated scope:** Small (2 files)

---

### Task 57: Collapsible Mobile Drawer Navigation, Keyboard & Touch Interaction
**Description:** Implement the collapsible mobile drawer `#mobile-menu` in `inventory/templates/inventory/base.html` styled as a sticky dropdown accordion (`bg-white border-b border-slate-200 shadow-lg`) directly below the header (Decision 28). Inside the drawer, include:
1. User profile card with username and localized role badge (`👤 Conectado como: assistant (Asistente)`).
2. Primary workflow links: 📷 Nueva Entrada (`inventory:intake`, highlighted), 📊 Catálogo / Dashboard (`inventory:dashboard`), ❓ Dudas pendientes (`inventory:dashboard?status=awaiting_info`, with count badge), and ⚙️ Panel de Administración (`/admin/`, manager-only).
3. Full-width segmented bilingual language switcher (`🇬🇧 English` / `🇪🇸 Español`) utilizing existing `set_language` form endpoints and CSRF tokens.
4. Isolated high-contrast Sign Out button separated from primary links to prevent accidental taps.
Add lightweight vanilla JavaScript handling:
- Toggling `#mobile-menu` open/closed on button click.
- Updating `aria-expanded="true"` / `"false"` and swapping between hamburger (☰) and close (✕) SVG icons.
- Pressing `Escape` key immediately closes the drawer and restores focus to `#mobile-menu-button`.
- Tapping outside the mobile menu (click outside) closes the drawer.
- Window resize to `≥ md` automatically resets the drawer to closed.
**Acceptance criteria:**
- [x] `#mobile-menu` drawer smoothly expands and collapses below the sticky header.
- [x] Tapping `#mobile-menu-button` toggles menu visibility, updates `aria-expanded`, and swaps SVG icon.
- [x] Drawer contains all navigation links (Intake, Dashboard, Doubts, Admin for managers, Language Switcher, Sign Out) with min 44×44px touch targets.
- [x] Pressing `Escape` or clicking outside closes the drawer and restores focus.
- [x] Resizing window to `≥ 768px` automatically resets the drawer to closed state.
**Verification:**
- [x] Template syntax check: `python manage.py check`
- [x] Unit & view tests pass: `python manage.py test tests.test_views`
**Dependencies:** Task 56
**Files likely touched:**
- `inventory/templates/inventory/base.html`
- `tests/test_views.py`
**Estimated scope:** Medium (2 files)

---

### Task 58: i18n Spanish Translations, Comprehensive Unit/Integration Test Suite & Browser Verification
**Description:** Add Spanish translations in `locale/es/LC_MESSAGES/django.po` for all new UI messages and ARIA labels (`Open menu`, `Close menu`, `Mobile navigation`, `Signed in as`, `English`, `Spanish`). Compile binary translation catalogs via `python manage.py compile_locales`. Add automated view tests in `tests/test_views.py` and `tests/test_i18n.py` verifying the mobile menu markup, ARIA attributes, desktop vs mobile visibility classes, and bilingual switcher forms. Create and execute a real Chrome browser automation script (`verify_mobile_nav_browser.py`) testing the mobile viewport (iPhone 14, 390×844): verifying initial uncluttered header, opening drawer, clicking navigation links, testing `Escape` key dismissal, and verifying outside click dismissal. Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and Ruff linter.
**Acceptance criteria:**
- [x] All new UI and accessibility strings localized in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] View and i18n test suites verify mobile menu elements, ARIA attributes, and language forms.
- [x] Real Chrome browser automation script runs on mobile viewport (390×844) and passes all assertions.
- [x] All 243+ unit and integration tests pass: `python manage.py test`.
- [x] Code passes linter check with 0 warnings: `ruff check .`.
- [x] `CHANGELOG.md` updated under `[Unreleased]` with Phase 17 details.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Browser script succeeds: `python .gemini/antigravity/brain/b80e4db2-82cf-46b6-b07e-3885a650d010/scratch/verify_mobile_nav_browser.py`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 57
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_views.py`
- `tests/test_i18n.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (5 files)

---

## Checkpoint 17: Responsive Mobile Navigation Complete
- [x] On mobile viewports (< 768px), header displays only brand, optional doubts pill, and hamburger button.
- [x] Tapping hamburger button opens accessible dropdown drawer with all links, language switcher, and logout.
- [x] Keyboard `Escape` and outside click dismiss the drawer cleanly.
- [x] Desktop screens (≥ 768px) display full uncollapsed horizontal navigation without hamburger button.
- [x] All UI strings and ARIA labels are translated in Spanish and English.
- [x] Real browser mobile test passes 100%, and full test suite passes with 0 regressions.

---

## Phase 18: Intake Photo Preview Management, Deletion & FileList Synchronization

### Task 59: Client-Side Photo State Management, Cumulative Capture & DataTransfer Synchronization
**Description:** Implement client-side photo state management in `inventory/templates/inventory/intake.html`. Introduce an internal array `selectedFiles: File[]` representing the active list of chosen images. Implement cumulative photo capture: when the user selects or captures photos via the file input or drag-and-drop, newly selected valid photos (each ≤10MB) are appended to `selectedFiles` up to the maximum 10 images rather than replacing previously selected files (Decision 31). If the selection would exceed 10 images total, show an accessible inline warning banner and retain the first 10. Implement `syncFileInput()` which constructs an HTML5 `DataTransfer` object, populates it with all files from `selectedFiles`, and assigns `imageInput.files = dt.files`. Dynamically update the photo counter (`#photoCount`: `X / 10 selected`) and toggle the "Identificar producto" button state (`disabled = selectedFiles.length === 0`).
**Acceptance criteria:**
- [x] `selectedFiles` array tracks active files in memory.
- [x] Cumulative file selection appends new files up to 10 max without erasing previously captured photos.
- [x] Total count >10 displays inline warning and does not exceed 10 files.
- [x] Individual files >10MB are rejected with clear error alert.
- [x] `syncFileInput()` synchronizes `imageInput.files` via standard `DataTransfer`.
- [x] `#photoCount` displays accurate active count (`X / 10 selected`).
- [x] `#identifyBtn` is enabled when `selectedFiles.length > 0` and disabled when empty.
**Verification:**
- [x] Template syntax check: `python manage.py check`
- [x] Existing view tests continue to pass: `python manage.py test tests.test_views`
**Dependencies:** Checkpoint 17
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
**Estimated scope:** Medium (1 file)

---

### Task 60: Interactive Preview Thumbnail Card, Accessible Deletion & State Guarding
**Description:** Refactor the thumbnail rendering logic in `inventory/templates/inventory/intake.html`. Render each photo in `#previewGrid` with an aspect-square container, an index badge `#N` at top-left, and an accessible delete button ("✕") at top-right. The delete button must provide a minimum 44×44px interactive touch target meeting WCAG 2.1 AA (using a 28×28px visual rose button with SVG cross), with `type="button"`, `aria-label="Remove photo #N"`, and `title="Remove photo"`. When clicked:
1. Prevent event propagation and default behavior so the parent dropzone file dialog does not trigger.
2. Remove file at index `i` from `selectedFiles`.
3. Call `syncFileInput()` to synchronize `imageInput.files`.
4. Re-render the preview grid, recalculating sequential badges (`#1`, `#2`, ...).
5. Update `#photoCount` text and `#identifyBtn` state.
6. If all photos are deleted (`selectedFiles.length === 0`), reset dropzone, hide `#previewContainer`, and reset `#photoCount`.
7. Retain any active AI identification advisory banner unless all photos are deleted (Decision 32).
8. Form state guarding: during `'identifying'` and `'submitting'` states, disable all delete buttons (`pointer-events-none opacity-50 cursor-not-allowed`) to prevent data race conditions mid-operation.
**Acceptance criteria:**
- [x] Each preview card displays an index badge `#N` and a top-right "✕" delete button.
- [x] Delete button meets 44×44px minimum touch target with explicit `aria-label="Remove photo #N"`.
- [x] Clicking "✕" removes only the specified photo without triggering the file dialog.
- [x] Remaining photos are dynamically re-indexed (`#1`, `#2`, ...) and `#photoCount` updates.
- [x] Deleting all photos resets dropzone, counter, and identify button.
- [x] Existing AI advisory card is preserved unless all photos are deleted.
- [x] Delete buttons are disabled/unclickable during `'identifying'` and `'submitting'` states.
**Verification:**
- [x] Template syntax check: `python manage.py check`
- [x] Unit & view tests pass: `python manage.py test tests.test_views`
**Dependencies:** Task 59
**Files likely touched:**
- `inventory/templates/inventory/intake.html`
**Estimated scope:** Medium (1 file)

---

### Task 61: i18n Spanish Translations, Automated Tests & Real Browser Verification
**Description:** Add Spanish translation strings for `"Remove photo"` / `"Eliminar foto"` and counter strings in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo` via `python manage.py compile_locales`. Update and expand automated view tests in `tests/test_views.py` and `tests/test_intake.py` verifying template markup, delete button accessibility attributes, and successful form submissions with uploaded files. Create and execute a real Chrome browser automation test in scratch (`verify_intake_photo_management_browser.py`) testing:
1. Selecting 3 sample images.
2. Verifying 3 preview cards with badges `#1`, `#2`, `#3` and counter `3 / 10`.
3. Clicking delete on photo `#2`.
4. Verifying preview cards shrink to 2, badges re-index to `#1`, `#2`, and counter updates to `2 / 10`.
5. Filling out intake fields and submitting the form.
6. Verifying in the Django database that the created product has exactly 2 photos attached.
Update `CHANGELOG.md` under `[Unreleased]`. Run full test suite and Ruff linter.
**Acceptance criteria:**
- [x] All new strings localized in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] Automated tests verify preview container structure, delete button ARIA labels, and intake submission.
- [x] Real Chrome browser automation script verifies deletion, re-indexing, and submission end-to-end.
- [x] All 248+ tests pass: `python manage.py test`.
- [x] Ruff linter reports 0 errors: `ruff check .`.
- [x] `CHANGELOG.md` updated under `[Unreleased]`.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales`
- [x] Full test suite passes: `python manage.py test`
- [x] Browser script succeeds: `python .gemini/antigravity/brain/b80e4db2-82cf-46b6-b07e-3885a650d010/scratch/verify_intake_photo_management_browser.py`
- [x] Linter passes: `ruff check .`
**Dependencies:** Task 60
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_views.py`
- `tests/test_intake.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (5 files)

---

## Checkpoint 18: Intake Photo Preview Management Complete
- [x] Assistants can delete individual photos from preview cards without re-uploading the entire batch.
- [x] `imageInput.files` remains perfectly synchronized with client preview via standard `DataTransfer`.
- [x] Photo counter and sequential index badges (`#1`, `#2`, ...) update dynamically upon deletion.
- [x] Deleting all photos cleanly resets dropzone and disables identification button.
- [x] Delete buttons meet 44×44px touch target guidelines and are locked during async operations.
- [x] Real Chrome browser automation test passes end-to-end, and all unit tests pass with 0 regressions.

---

## Phase 19: Refined Product Lifecycle States, Dashboard Filtering & Intake AI Title Autofill

### Task 62: Domain Layer & State Machine Expansion
**Description:** Expand `ProductStatus` in `inventory/models.py` with `PRICE_PENDING = "price_pending"` and `PUBLISHED = "published"`. Implement `Product.compute_lifecycle_status()` with automatic state rules:
- `SOLD` if `self.is_sold or self.status == ProductStatus.SOLD`
- `BLOCKED` if `self.status == ProductStatus.BLOCKED`
- `AWAITING_INFO` if `self.clarifications.filter(status=ClarificationStatus.PENDING).exists()`
- `PUBLISHED` if `self.listing_links.filter(is_active=True).exists()`
- If no description (`not self.ai_description or not self.ai_description.strip()`): `DRAFT`
- If title and description, but price is None or `<= Decimal("0.00")`: `PRICE_PENDING`
- If title, description, and price `> Decimal("0.00")`: `READY`
Implement `sync_lifecycle_status()` on `Product` and connect signals on `ProductListingLink` (`post_save`, `post_delete`) and `ProductClarification` (`post_save`, `post_delete`) to trigger state recalculation. Generate and execute Django migration `0012_*.py`.
**Acceptance criteria:**
- [x] `ProductStatus` has `PRICE_PENDING` and `PUBLISHED` options with localized display names.
- [x] `compute_lifecycle_status()` handles all combinations of title, description, price, links, and clarifications.
- [x] `Product.save()` automatically updates status when not manually set to SOLD or BLOCKED.
- [x] Signals on `ProductListingLink` automatically set `PUBLISHED` on link save and revert to computed state on link delete.
- [x] Signals on `ProductClarification` revert from `AWAITING_INFO` to computed state (`PUBLISHED`, `READY`, `PRICE_PENDING`, `DRAFT`) when doubts are resolved.
- [x] Migration generated and applied cleanly: `python manage.py makemigrations && python manage.py migrate`.
**Verification:**
- [x] Command succeeds: `python manage.py makemigrations --check --dry-run`
- [x] Unit tests pass: `python manage.py test tests.test_lifecycle`
**Dependencies:** None
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/0012_*.py`
- `tests/test_lifecycle.py`
**Estimated scope:** Medium (3 files)

---

### Task 63: Intake AI Vision Model Upgrade & Hidden Title Autofill
**Description:** Update `inventory/services/ai_service.py` so `identify_intake_product` uses model `gemini-flash-latest`. Update `ProductIntakeForm` in `inventory/forms.py` to include `ai_title` as a hidden input. Update `inventory/templates/inventory/intake.html` to render `{{ form.ai_title }}` and update the client-side `identifyBtn` handler to populate `document.getElementById('id_ai_title').value = data.identified_title` upon successful response. Update `ProductIntakeView` in `inventory/views.py` so `product.ai_title` is saved from the intake form.
**Acceptance criteria:**
- [x] `identify_intake_product` calls Google GenAI SDK with `model="gemini-flash-latest"`.
- [x] `ProductIntakeForm` includes `ai_title` field rendered with `HiddenInput`.
- [x] Client-side JS populates `#id_ai_title` when "Identificar producto" finishes.
- [x] Saving the intake form stores `ai_title` on the new `Product` instance, preventing generic title fallbacks.
**Verification:**
- [x] Unit & view tests pass: `python manage.py test tests.test_intake`
**Dependencies:** Task 62
**Files likely touched:**
- `inventory/services/ai_service.py`
- `inventory/forms.py`
- `inventory/templates/inventory/intake.html`
- `inventory/views.py`
- `tests/test_intake.py`
**Estimated scope:** Medium (4-5 files)

---

### Task 64: Dashboard Filtering, Status Counts & Staging UI Badges
**Description:** In `inventory/views.py` (`dashboard_view`), add query filtering for `status_filter == "price_pending"` and `status_filter == "published"`. Add `price_pending_count` to status counter aggregation scoped to active platform filters and search queries. In `inventory/templates/inventory/dashboard.html`, add the "Precio pendiente" button filter tab with counter badge `({{ price_pending_count }})`. In `inventory/templates/inventory/product_detail.html`, add badge styling for `PRICE_PENDING` (amber/orange badge) and `PUBLISHED` (cyan/blue badge).
**Acceptance criteria:**
- [x] Dashboard displays **"Precio pendiente"** tab between Active/Doubts with live count.
- [x] Clicking "Precio pendiente" filters catalog to items with title and description but missing price.
- [x] Counter for `price_pending_count` updates dynamically when platform or search filters are applied.
- [x] Product detail page renders distinct badges for `PRICE_PENDING` and `PUBLISHED`.
**Verification:**
- [x] View tests pass: `python manage.py test tests.test_dashboard`
**Dependencies:** Task 62, Task 63
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/dashboard.html`
- `inventory/templates/inventory/product_detail.html`
- `tests/test_dashboard.py`
**Estimated scope:** Medium (4 files)

---

### Task 65: i18n Localization, Unit & Regression Tests, and Real-Browser Verification
**Description:** Add Spanish translation strings for `"Price Pending"` / `"Precio pendiente"` and `"Published"` / `"Publicado"` in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo`. Write comprehensive unit tests for all state transitions, view queries, and form saves. Execute full test suite (`python manage.py test`) ensuring all 281 tests pass with 0 regressions. Create and run a real Google Chrome verification script testing:
1. Intake form: clicking "Identificar producto" sets `ai_title` in background; item is saved in `DRAFT`.
2. Manager adds description: item auto-transitions to `PRICE_PENDING`.
3. Dashboard filter button "Precio pendiente" lists the item with live badge count.
4. Manager inputs price: item auto-transitions to `READY`.
5. Manager adds marketplace link: item auto-transitions to `PUBLISHED`.
6. Manager deletes link: item auto-reverts to `READY`.
**Acceptance criteria:**
- [x] All new strings localized in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] Full automated test suite passes with 100% success (281 tests).
- [x] Real Chrome browser verification succeeds and captures screenshots for all lifecycle states.
**Verification:**
- [x] Command succeeds: `python manage.py compile_locales` (or `compilemessages`)
- [x] Full test suite passes: `python manage.py test`
- [x] Browser script succeeds: `python manage.py test tests.test_browser_lifecycle`
**Dependencies:** Task 62, Task 63, Task 64
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_lifecycle.py`
- `tests/test_browser_lifecycle.py`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 19: Refined Product Lifecycle, Dashboard Filtering & Intake AI Title Complete
- [x] Product status machine implements `DRAFT`, `PRICE_PENDING`, `READY`, `PUBLISHED`, `AWAITING_INFO`, `SOLD`, `BLOCKED`.
- [x] State transitions are 100% automated on product save and link additions/deletions.
- [x] Intake pre-flight AI identification uses `gemini-flash-latest` and populates `ai_title` hidden input.
- [x] Catalog dashboard features a dedicated "Precio pendiente" filter tab with live counts.
- [x] Real Chrome browser verification script confirms end-to-end functionality.

---

## Phase 20: Installable PWA Support, VAPID Web Push Infrastructure & Live Signal Triggers

### Task 66: PWA Web App Manifest, App Icons, Meta Tags & Root Pass-Through Service Worker
**Description:** Generate branded PWA icons (`icon-192.png`, `icon-512.png`, `apple-touch-icon.png`) under `inventory/static/inventory/icons/`. Implement `manifest_view` (`/manifest.json`) and `service_worker_view` (`/sw.js`) in `inventory/views.py` and register root routes in `inventory/urls.py`. Create `inventory/templates/inventory/sw.js` with `install`, `activate`, a zero-cache pass-through `fetch` handler, a `push` event listener (rendering JSON notifications with `tag` collapsing and `navigator.setAppBadge`), and a `notificationclick` listener (focusing existing tab or opening deep-link URL). Add `<link rel="manifest">`, `theme-color`, Apple touch icon, and Service Worker registration script to `inventory/templates/inventory/base.html`.
**Acceptance criteria:**
- [x] `GET /manifest.json` returns `200 OK` with `Content-Type: application/manifest+json`, `display: "standalone"`, `scope: "/"`, and valid icon references.
- [x] `GET /sw.js` returns `200 OK` with `Content-Type: application/javascript`, `Service-Worker-Allowed: /`, and `Cache-Control: no-cache, no-store, must-revalidate`.
- [x] `/sw.js` implements pass-through `fetch` (no HTML/CSRF caching), `push`, and `notificationclick` listeners.
- [x] `base.html` includes `<link rel="manifest">`, `<meta name="theme-color" content="#059669">`, Apple PWA meta tags, and registers `/sw.js` on load.
**Verification:**
- [x] Unit tests pass: `.venv\Scripts\python.exe manage.py test tests.test_pwa_push`
**Dependencies:** None
**Files likely touched:**
- `inventory/views.py`
- `inventory/urls.py`
- `inventory/templates/inventory/sw.js`
- `inventory/templates/inventory/base.html`
- `inventory/static/inventory/icons/icon-192.png`
- `inventory/static/inventory/icons/icon-512.png`
- `inventory/static/inventory/icons/apple-touch-icon.png`
**Estimated scope:** Medium (5 files + static icons)

---

### Task 67: `PushSubscription` Model, VAPID Configuration, Key Generator Command & `push_service.py`
**Description:** Add `pywebpush>=2.0.1` to `requirements.txt`. Add `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`, and `PUSH_NOTIFICATIONS_LIVE_SIGNALS` to `config/settings.py` and `.env.example`. Implement the `PushSubscription` model in `inventory/models.py` (`user`, `endpoint` unique, `p256dh`, `auth`, `user_agent`, `is_active`, timestamps), generate and apply migration `0013_pushsubscription.py`, and register `PushSubscriptionAdmin` in `inventory/admin.py` with a `"Send test push notification"` admin action. Implement `inventory/management/commands/generate_vapid_keys.py` to generate ECDSA P-256 VAPID keys. Implement `inventory/services/push_service.py` with `is_push_configured()`, `send_push_to_subscription()`, `send_push_to_user()`, and `send_push_to_group()` including automatic pruning of expired subscriptions on HTTP `404`/`410 Gone`.
**Acceptance criteria:**
- [x] `PushSubscription` model and migration `0013_pushsubscription.py` created and applied cleanly.
- [x] `python manage.py generate_vapid_keys` outputs valid Base64URL `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` values.
- [x] `push_service.py` dispatches encrypted Web Push payloads via `pywebpush.webpush()` and automatically deletes subscriptions returning HTTP `404` or `410`.
- [x] `PushSubscriptionAdmin` accessible to Managers in Django Admin with `"Send test push notification"` action.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py generate_vapid_keys`
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
- [x] Unit tests pass: `.venv\Scripts\python.exe manage.py test tests.test_pwa_push`
**Dependencies:** Task 66
**Files likely touched:**
- `requirements.txt`
- `config/settings.py`
- `.env.example`
- `inventory/models.py`
- `inventory/migrations/0013_pushsubscription.py`
- `inventory/admin.py`
- `inventory/services/push_service.py`
- `inventory/management/commands/generate_vapid_keys.py`
**Estimated scope:** Medium (5-7 files)

---

### Task 68: Push Subscription JSON Endpoints, Navbar/Drawer Toggle UI & `.env`-Guarded Live Workflow Signals
**Description:** Implement authenticated JSON endpoints `push_subscribe_view` (`POST /api/push/subscribe/`), `push_unsubscribe_view` (`POST /api/push/unsubscribe/`), and `push_test_view` (`POST /api/push/test/`) in `inventory/views.py` and `inventory/urls.py`. Update `inventory/context_processors.py` to expose `VAPID_PUBLIC_KEY`, `PUSH_CONFIGURED`, and `user_has_push_subscription`. Add the `"🔔 Activar alertas"` / `"🔔 Alertas activas"` toggle button to both the desktop navbar and mobile drawer in `inventory/templates/inventory/base.html`, including client-side `PushManager.subscribe()` handling, iOS non-standalone detection hint, and `navigator.setAppBadge` synchronization. Wire live signal handlers in `inventory/models.py` guarded by `settings.PUSH_NOTIFICATIONS_LIVE_SIGNALS` for Clarification Doubts Q&A (`PENDING` -> notify `assistants`; `ANSWERED` -> notify `managers`) and Intake/Lifecycle bottlenecks (`DRAFT` creation and `PRICE_PENDING` transition -> notify `managers`).
**Acceptance criteria:**
- [x] `POST /api/push/subscribe/`, `/api/push/unsubscribe/`, and `/api/push/test/` authenticate the user, validate payloads, and manage `PushSubscription` records idempotently.
- [x] Desktop navbar (`#push-toggle-btn`) and mobile drawer (`#mobile-push-toggle-btn`) render the push toggle button and reflect active subscription state.
- [x] When `PUSH_NOTIFICATIONS_LIVE_SIGNALS=True`, creating a doubt notifies `assistants`, answering a doubt notifies `managers`, and new `DRAFT` or `PRICE_PENDING` transitions notify `managers`.
- [x] When `PUSH_NOTIFICATIONS_LIVE_SIGNALS=False`, signals do not dispatch push notifications.
**Verification:**
- [x] View and signal tests pass: `.venv\Scripts\python.exe manage.py test tests.test_pwa_push`
**Dependencies:** Task 66, Task 67
**Files likely touched:**
- `inventory/views.py`
- `inventory/urls.py`
- `inventory/context_processors.py`
- `inventory/models.py`
- `inventory/templates/inventory/base.html`
**Estimated scope:** Medium (5 files)

---

### Task 69: Bilingual Localization (`es`/`en`), Comprehensive Test Suite & Real Chrome Browser Verification
**Description:** Add Spanish translations for all new PWA and Push Notification UI strings (`Enable Alerts`, `Alerts Active`, `Send Test Push`, iOS Home Screen hint, notification titles/bodies) in `locale/es/LC_MESSAGES/django.po` and compile `django.mo` via `python manage.py compile_locales`. Write comprehensive unit, API, signal, and real Chrome browser tests in `tests/test_pwa_push.py`. Update `CHANGELOG.md`. Run `ruff check .` and the full test suite (`python manage.py test`).
**Acceptance criteria:**
- [x] All new strings translated in `locale/es/LC_MESSAGES/django.po` and compiled to `django.mo`.
- [x] `tests/test_pwa_push.py` covers manifest, service worker headers/scope, subscription CRUD endpoints, `410 Gone` pruning, `generate_vapid_keys`, `.env` signal triggers, and Chrome Service Worker registration.
- [x] Full test suite passes with 0 errors and `ruff check .` passes cleanly.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py compile_locales`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
- [x] Full test suite passes: `.venv\Scripts\python.exe manage.py test`
**Dependencies:** Task 66, Task 67, Task 68
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_pwa_push.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 20: Installable PWA Support, VAPID Web Push Infrastructure & Live Signal Triggers Complete
- [x] `/manifest.json` and root-scoped pass-through `/sw.js` are served and registered cleanly across pages.
- [x] PWA icons (`192x192`, `512x512`, `apple-touch-icon.png`) and meta tags are present in `base.html`.
- [x] `PushSubscription` model, admin action, `generate_vapid_keys` command, and `push_service.py` are implemented and verified.
- [x] Subscribe/unsubscribe/test JSON endpoints and navbar/drawer UI toggles work end-to-end.
- [x] `.env` flag `PUSH_NOTIFICATIONS_LIVE_SIGNALS` controls automatic signal-driven push alerts for Clarification Doubts and Draft/Price Pending bottlenecks.
- [x] All unit tests, browser tests, and Ruff lint checks pass with 0 regressions.

---

## Phase 21: Dashboard Status Toolbar Modernization & Apilación Prevention (Vertical Slice 17)

### Task 70: Horizontal Status Navigation Rail, Toolbar Decoupling & Multi-Viewport Anti-Apilación Verification
**Description:** Refactor [`inventory/templates/inventory/dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html) to decouple the status navigation tabs from the action/filter toolbar (search input and platform selector). Enclose status tabs in an accessible `<nav role="tablist">` with horizontal scrolling (`overflow-x-auto`, `flex-nowrap`, `whitespace-nowrap`, hidden scrollbars) and smooth touch momentum scrolling (`-webkit-overflow-scrolling: touch`). Upgrade all status tab touch targets to $\ge 36\text{px}$ height with responsive padding and badge counters. Add Playwright multi-viewport responsive test `test_dashboard_responsive_tabs_no_apilation` in [`tests/test_dashboard_responsive.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_dashboard_responsive.py) testing across 390px, 768px, 1024px, and 1440px viewports and asserting that all tabs share identical vertical offset ($\Delta \le 4\text{px}$) with zero apilación.
**Acceptance criteria:**
- [x] Status navigation tabs sit in a single horizontal scroll rail without wrapping or piling up vertically across mobile and tablet viewports.
- [x] Filter toolbar (search and platform select) is cleanly isolated beneath the status rail.
- [x] All tabs meet WCAG touch target standards ($\ge 36\text{px}$ mobile / $32\text{px}$ desktop).
- [x] Playwright multi-viewport automated test passes across 4 standard screen widths with audit screenshots captured in `browser_verification_screenshots/`.
**Verification:**
- [x] Test passes: `.venv\Scripts\python.exe manage.py test tests.test_dashboard_responsive`
**Dependencies:** None
**Files likely touched:**
- `inventory/templates/inventory/dashboard.html`
- `tests/test_dashboard_responsive.py`
**Estimated scope:** Small (2 files)

---

## Checkpoint 21: Dashboard Status Toolbar Modernization Complete
- [x] Horizontal scroll rail prevents tab apilación across mobile, tablet, laptop, and desktop viewports.
- [x] Status filter tab touch targets and counter badges satisfy WCAG standards.
- [x] Playwright multi-viewport responsive tests pass and screenshots are stored for visual audit.

---

## Phase 22: Responsive Mobile Typography & Form Readability Adaptation (Vertical Slice 18)

### Task 71: Standardize Mobile Typography Scale, Eliminate Microscopic Fonts & Prevent iOS Safari Auto-Zoom
**Description:** Audit and adapt typography across all key application templates ([`base.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/base.html), [`dashboard.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/dashboard.html), [`intake.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/intake.html), [`product_detail.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/inventory/product_detail.html), [`login.html`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/templates/registration/login.html)) and form widgets ([`inventory/forms.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/forms.py)). Eliminate sub-12px arbitrary font sizes (`text-[10px]`, `text-[11px]`) and static unscaled `text-xs` on primary content, buttons, labels, and badges. Enforce input font sizes $\ge 16\text{px}$ on mobile (`text-base sm:text-sm` and `@media (max-width: 640px) { input, select, textarea { font-size: 1rem !important; } }`) to prevent iOS Safari auto-zoom. Remove `maximum-scale=1.0, user-scalable=no` for WCAG 2.1 AA pinch-to-zoom compliance, and add `<meta name="text-scale" content="scale">` for OS dynamic type preferences. Add Playwright test `test_mobile_typography_and_input_font_sizes` in [`tests/test_dashboard_responsive.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_dashboard_responsive.py) asserting computed input font-size $\ge 16\text{px}$ on 390x844 mobile viewport and capturing visual screenshots.
**Acceptance criteria:**
- [x] Arbitrary `text-[10px]` and `text-[11px]` classes eliminated; critical text scaled to `text-xs sm:text-sm` or `text-sm sm:text-base`.
- [x] All form inputs render at $\ge 16\text{px}$ on mobile screens preventing involuntary iOS Safari auto-zoom.
- [x] Viewport meta tag allows pinch-to-zoom up to 200% and `<meta name="text-scale" content="scale">` is active.
- [x] Full test suite (299 tests) passes cleanly and `ruff check .` passes with 0 issues.
- [x] Playwright assertions confirm computed font size $\ge 16\text{px}$ on mobile viewports.
**Verification:**
- [x] Full test suite passes: `.venv\Scripts\python.exe manage.py test`
- [x] Responsive tests pass: `.venv\Scripts\python.exe manage.py test tests.test_dashboard_responsive`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
**Dependencies:** Task 70
**Files likely touched:**
- `inventory/templates/inventory/base.html`
- `inventory/templates/inventory/dashboard.html`
- `inventory/templates/inventory/intake.html`
- `inventory/templates/inventory/product_detail.html`
- `inventory/templates/registration/login.html`
- `inventory/forms.py`
- `tests/test_dashboard_responsive.py`
**Estimated scope:** Medium (7 files)

---

## Checkpoint 22: Responsive Mobile Typography & Form Readability Complete
- [x] All application views render legible, comfortably readable typography on smartphone screens.
- [x] Involuntary iOS Safari auto-zoom on form inputs is eliminated with computed font size $\ge 16\text{px}$.
- [x] Pinch-to-zoom and OS dynamic text scaling preferences are supported.
- [x] Automated unit and Playwright tests verify 100% compliance with zero regressions.

---

## Phase 23: Product State Change History & Audit Trail (Vertical Slice 19)

### Task 72: Domain Model `ProductStatusLog`, Helper Functions & Database Migration
**Description:** Implement `ProductStatusLog` model in `inventory/models.py` with fields: `product` (FK to `Product`, CASCADE), `from_status` (CharField choices, nullable), `to_status` (CharField choices), `changed_by` (FK to User, SET_NULL, nullable, blank), `trigger` (CharField, default=""), `notes` (TextField, default=""), and `created_at` (DateTimeField auto_now_add=True, db_index=True). Implement `log_status_change(product, from_status, to_status, user=None, trigger="", notes="")` helper function. Create and apply migration `0014_productstatuslog.py`.
**Acceptance criteria:**
- [x] `ProductStatusLog` model is defined with correct choices, indexes, and verbose names.
- [x] `log_status_change` helper creates immutable log entries and ignores no-op transitions (`from_status == to_status`).
- [x] Migration `0014_productstatuslog.py` created and applied cleanly.
- [x] Unit tests verify model constraints and log record creation.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_status_history`
**Dependencies:** None
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/0014_productstatuslog.py`
- `tests/test_status_history.py`
**Estimated scope:** Small (3 files)

---

### Task 73: Request User Context Capture Middleware & Automated Lifecycle Transition Logging
**Description:** Create `inventory/middleware.py` with `CurrentUserMiddleware` using Python's `contextvars` to thread-safely expose `get_current_user()` and `set_current_user(user)`. Register the middleware in `config/settings.py`. Hook into `Product.save()` and lifecycle transitions: detect when `initial_status != current_status`, capture acting user (explicit or from middleware), and invoke `log_status_change`. Update signals and methods (`mark_as_sold`, `mark_as_unsold`, `ProductListingLink` post_save/post_delete, `ProductClarification` post_save/post_delete) to pass appropriate triggers (`intake`, `pricing`, `staging_update`, `clarification_opened`, `clarification_resolved`, `marketplace_link_added`, `marketplace_link_removed`, `marked_sold`, `reverted_unsold`) and context notes.
**Acceptance criteria:**
- [x] `CurrentUserMiddleware` captures `request.user` during web requests and resets cleanly after response.
- [x] Transitions during `/intake/` log `None -> DRAFT` (or `READY`) attributed to the sourcing assistant.
- [x] Transitions during detail editing, doubt Q&A, and marketplace links log accurate `from_status`, `to_status`, `changed_by`, and `trigger`.
- [x] CLI/automated transitions without a request user safely record `changed_by=None` ("Sistema / Automático").
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_status_history`
**Dependencies:** Task 72
**Files likely touched:**
- `inventory/middleware.py`
- `config/settings.py`
- `inventory/models.py`
- `tests/test_status_history.py`
**Estimated scope:** Medium (4 files)

---

### Task 74: Django Administration Read-Only Audit Changelist & Product Status Log Inline
**Description:** Register `ProductStatusLog` in `inventory/admin.py` with `ProductStatusLogAdmin` and `ProductStatusLogInline` inside `ProductAdmin`. Ensure complete immutability: disable add, change, and delete permissions (`has_add_permission=False`, `has_change_permission=False`, `has_delete_permission=False`). Provide list display with color-coded status badges, filters (`to_status`, `from_status`, `trigger`, `created_at`, `changed_by`), search across product ID/title/user/notes, and date hierarchy.
**Acceptance criteria:**
- [x] `ProductStatusLog` appears in Django Admin under Inventory.
- [x] Logs cannot be added, edited, or deleted via Django Admin.
- [x] `ProductStatusLogInline` renders historical timeline table on product edit pages.
- [x] Only store managers can access the changelist and inline.
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_status_history`
**Dependencies:** Task 72
**Files likely touched:**
- `inventory/admin.py`
- `tests/test_status_history.py`
**Estimated scope:** Small (2 files)

---

### Task 75: Staging Product Detail UI Lifecycle Audit Trail Timeline Card
**Description:** Update `inventory/views.py` (`product_detail_view`) to prefetch and supply `status_logs` ordered by `-created_at`. In `inventory/templates/inventory/product_detail.html`, add a modern, accessible **"Historial de Estados"** timeline card displaying recent transitions. Show status badges for `from_status` $\to$ `to_status`, formatted timestamp, actor (username + role badge or System), trigger badge, and contextual note. Include a collapsible toggle if there are more than 4 entries.
**Acceptance criteria:**
- [x] Timeline card renders on `/products/<pk>/` with accurate historical transitions.
- [x] Shows who made the change (with role badge) and when (formatted localized timestamp).
- [x] Responsive design functions seamlessly across desktop and mobile ($390 \times 844$) screens.
- [x] Non-blocking and clean layout with zero layout shifts.
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_status_history`
**Dependencies:** Task 72, Task 73
**Files likely touched:**
- `inventory/views.py`
- `inventory/templates/inventory/product_detail.html`
- `tests/test_status_history.py`
**Estimated scope:** Medium (3 files)

---

### Task 76: Bilingual Localization (`es`/`en`), Comprehensive Test Suite & Regression Check
**Description:** Add Spanish translation strings for all new model fields, triggers, admin titles, and timeline UI labels in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo`. Write extensive unit and integration tests in `tests/test_status_history.py` covering all lifecycle permutation triggers, request user attribution, CLI/system fallback, Django admin inline, and UI rendering. Execute `ruff check .` and the full test suite (`python manage.py test`).
**Acceptance criteria:**
- [x] All new strings localized in Spanish and compiled with `python manage.py compile_locales`.
- [x] `tests/test_status_history.py` covers 100% of state change triggers and user attribution paths.
- [x] Full test suite (299+ tests) passes with 0 failures and 0 regressions.
- [x] `ruff check .` passes with 0 warnings.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py compile_locales`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
- [x] Full test suite passes: `.venv\Scripts\python.exe manage.py test`
**Dependencies:** Task 72, Task 73, Task 74, Task 75
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_status_history.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 23: Product State Change History & Audit Trail Complete
- [x] `ProductStatusLog` model and migration `0014_productstatuslog.py` applied.
- [x] `CurrentUserMiddleware` captures acting user during web requests; system fallback works when user is None.
- [x] All state transitions (`draft`, `price_pending`, `ready`, `published`, `awaiting_info`, `blocked`, `sold`) generate accurate log entries.
- [x] Product detail page displays an accessible visual audit timeline.
- [x] Django Admin provides an immutable read-only changelist and inline.
- [x] Full test suite passes with 0 regressions and `ruff check .` passes cleanly.

---

## Phase 24: Compilation & Docker Image Build Timestamp Display (Vertical Slice 20)

### Task 77: Version & Build Metadata Resolution Service (`inventory/services/version_service.py`)
**Description:** Create `inventory/services/version_service.py` with `get_build_info()`. Implement cascading resolution: (1) environment variables (`APP_BUILD_TIME`, `APP_BUILD_COMMIT`, `APP_VERSION`, `APP_ENV`), (2) filesystem check for baked Docker files (`/app/build_date.txt` and `/app/build_commit.txt` or project root), (3) Git fallback when running locally (`git log -1` and `git rev-parse --short HEAD`), and (4) default development fallback (`"Desarrollo local"` / `"Local Development"`). Cache the parsed result in memory so subsequent calls incur zero subprocess or disk I/O.
**Acceptance criteria:**
- [x] `get_build_info()` resolves build timestamp, short commit SHA, and environment badge.
- [x] Environment variables override filesystem and Git metadata.
- [x] In-memory caching avoids repetitive shell execution or disk reads.
- [x] Gracefully handles missing Git binaries, missing repo metadata, and empty environment variables without raising exceptions.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py test tests.test_build_info`
**Dependencies:** None
**Files likely touched:**
- `inventory/services/version_service.py`
- `tests/test_build_info.py`
**Estimated scope:** Small (2 files)

---

### Task 78: Global Template Context Processor & Django Settings Registration
**Description:** Implement `build_info` context processor in `inventory/context_processors.py` that exposes the `build_info` dictionary to all Django templates. Add fallback settings in `config/settings.py` (`APP_BUILD_TIME`, `APP_BUILD_COMMIT`, `APP_VERSION`, `APP_ENV`) read from `os.getenv()`, and register `'inventory.context_processors.build_info'` in `TEMPLATES[0]['OPTIONS']['context_processors']`.
**Acceptance criteria:**
- [x] `inventory/context_processors.py` contains `build_info(request)`.
- [x] Context processor registered in `config/settings.py`.
- [x] `build_info` context dictionary is available in every template context (authenticated and unauthenticated).
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py check`
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_build_info`
**Dependencies:** Task 77
**Files likely touched:**
- `inventory/context_processors.py`
- `config/settings.py`
- `tests/test_build_info.py`
**Estimated scope:** Small (3 files)

---

### Task 79: Dockerfile & CI/CD Workflow Metadata Injection
**Description:** Update `Dockerfile` to accept `ARG BUILD_TIME=""`, `ARG BUILD_COMMIT=""`, and `ARG APP_VERSION="1.0.0"`, exporting them as `ENV APP_BUILD_TIME`, `ENV APP_BUILD_COMMIT`, and `ENV APP_VERSION`. Add a build step in `Dockerfile` that writes `/app/build_date.txt` automatically if `BUILD_TIME` was not provided, guaranteeing every `docker build .` captures the exact build execution timestamp. Update `.github/workflows/ci.yml` in both `docker-build-and-smoke-test` and `publish-image` jobs to pass dynamic `BUILD_TIME` and `BUILD_COMMIT` build arguments.
**Acceptance criteria:**
- [x] `Dockerfile` defines `ARG` and `ENV` for `BUILD_TIME`, `BUILD_COMMIT`, and `APP_VERSION`.
- [x] `Dockerfile` generates `/app/build_date.txt` at build time if `BUILD_TIME` is not supplied.
- [x] `.github/workflows/ci.yml` passes build timestamp and Git SHA during container build & push.
- [x] Non-root execution (`USER appuser`) and security constraints remain preserved.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\ruff.exe check .`
- [x] Docker configuration check: syntax and schema verification
**Dependencies:** Task 77, Task 78
**Files likely touched:**
- `Dockerfile`
- `.github/workflows/ci.yml`
**Estimated scope:** Small (2 files)

---

### Task 80: Footer UI Modernization & Responsive Layout in `base.html`
**Description:** Modernize the application footer in `inventory/templates/inventory/base.html` to display the compilation metadata. Include: (1) the platform tagline/copyright, (2) an accessible, responsive horizontal flex rail containing `⏱️ Build: <build_time>` (`id="footer-build-time"`), `🔖 Commit: <commit_short>` (`id="footer-build-sha"`), and an environment status badge (`PROD`, `STAGING`, `DEV`). Ensure mobile responsiveness with `flex-wrap justify-center gap-x-2 gap-y-1` and `text-[11px] sm:text-xs`, preventing horizontal overflow on $390 \times 844$ viewports.
**Acceptance criteria:**
- [x] Footer renders build timestamp, commit hash, and environment badge across all pages (`/dashboard/`, `/intake/`, `/products/<pk>/`, `/login/`).
- [x] Elements feature standard DOM IDs (`#footer-build-time`, `#footer-build-sha`).
- [x] Layout flows seamlessly on mobile viewports without horizontal scrollbars or clipping.
- [x] Conforms to WCAG color contrast standards.
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_build_info`
**Dependencies:** Task 77, Task 78
**Files likely touched:**
- `inventory/templates/inventory/base.html`
- `tests/test_build_info.py`
**Estimated scope:** Small (2 files)

---

### Task 81: Bilingual Localization, Comprehensive Unit Tests & Full Regression Check
**Description:** Add Spanish translation strings for `"Build:"`, `"Commit:"`, `"Development"`, `"Production"`, and `"Staging"` in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo`. Write extensive unit tests in `tests/test_build_info.py` validating environment variable parsing, filesystem fallbacks, Git fallbacks, template rendering, and locale switching. Run `ruff check .` and the full regression suite (`python manage.py test`).
**Acceptance criteria:**
- [x] Spanish translations compiled in `django.mo`.
- [x] `tests/test_build_info.py` tests all fallback layers and template rendering.
- [x] Full test suite (314+ tests) passes with 0 failures and 0 errors.
- [x] `ruff check .` passes with 0 warnings.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py compile_locales`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
- [x] Full test suite passes: `.venv\Scripts\python.exe manage.py test`
**Dependencies:** Task 77, Task 78, Task 79, Task 80
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_build_info.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 24: Build Compilation & Version Info Complete
- [x] Build timestamp, commit SHA, and environment badge display properly in footer across all views and viewports.
- [x] Docker builds automatically bake in build metadata.
- [x] Local development cleanly falls back to Git commit information.
- [x] All unit and regression tests pass with 0 failures.
- [x] `ruff check .` passes cleanly.

---

## Phase 25: Intake AI Valuation & Reference Pricing (Vertical Slice 21)

### Task 82: Domain Model Expansion & Database Migration (`inventory/models.py`, `inventory/migrations/0015_product_estimated_prices.py`, `inventory/admin.py`)
**Description:** Add `estimated_retail_price` and `estimated_resale_price` decimal fields to the `Product` model in `inventory/models.py`. Both fields should allow `null=True, blank=True`, validate non-negative values up to `9999999.99` with `max_digits=10, decimal_places=2`, and provide translatable `verbose_name` and `help_text`. Generate migration `0015_product_estimated_prices.py` and apply it cleanly. Update `inventory/admin.py` to display the new fields in `ProductAdmin` list display and fieldsets.
**Acceptance criteria:**
- [x] `Product.estimated_retail_price` and `Product.estimated_resale_price` defined in `inventory/models.py`.
- [x] Migration `0015_product_estimated_prices.py` generated and applied cleanly to SQLite.
- [x] `ProductAdmin` in `inventory/admin.py` exposes both valuation fields in `list_display`, `fieldsets`, or `readonly_fields`.
- [x] Admin and model validations enforce non-negative values.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py migrate`
- [x] Model checks pass: `.venv\Scripts\python.exe manage.py check`
**Dependencies:** None
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/0015_product_estimated_prices.py`
- `inventory/admin.py`
**Estimated scope:** Small (3 files)

---

### Task 83: AI Service Schema & Prompt Upgrade (`inventory/services/ai_service.py`, `inventory/views.py`)
**Description:** Update `IntakePreflightSchema` in `inventory/services/ai_service.py` to add `estimated_retail_price: Optional[float] = None` and `estimated_resale_price: Optional[float] = None` with descriptive field annotations. Update `PREFLIGHT_ES_INSTRUCTION` and `PREFLIGHT_EN_INSTRUCTION` to evaluate original new retail MSRP and realistic second-hand market value (Wallapop, Vinted, eBay in €), explicitly instructing the model to return `null` if the item is unbranded or impossible to estimate. Ensure `identify_intake_product()` rounds float values to 2 decimal places and handles nulls gracefully. Update `intake_identify_view` in `inventory/views.py` to pass both fields in the JSON response payload.
**Acceptance criteria:**
- [x] `IntakePreflightSchema` supports `estimated_retail_price` and `estimated_resale_price`.
- [x] Both Spanish and English preflight instructions guide Gemini to appraise new retail MSRP and used resale value in Euros (€).
- [x] `identify_intake_product()` returns clean float/Decimal values rounded to 2 decimal places, or `None` if unable to value.
- [x] `intake_identify_view` returns `estimated_retail_price` and `estimated_resale_price` in the JSON response dictionary.
**Verification:**
- [x] Unit tests pass: `.venv\Scripts\python.exe manage.py test tests.test_ai_service`
- [x] Linter passes: `.venv\Scripts\ruff.exe check inventory/services/ai_service.py inventory/views.py`
**Dependencies:** Task 82
**Files likely touched:**
- `inventory/services/ai_service.py`
- `inventory/views.py`
**Estimated scope:** Small (2 files)

---

### Task 84: Intake Form & Mobile UI Valuation Integration (`inventory/forms.py`, `inventory/templates/inventory/intake.html`)
**Description:** Update `ProductIntakeForm` in `inventory/forms.py` to include `estimated_retail_price` and `estimated_resale_price` using `forms.HiddenInput` widgets. In `inventory/templates/inventory/intake.html`, render `#advisoryValuationContainer` inside `#aiAdvisoryBanner` displaying cards for "PVP Nuevo (MSRP)" and "Reventa estimada". Beneath the target sale price input (`#id_sale_price`), render benchmark badges and a one-click button "✨ Usar precio de reventa estimado" (`#btnUseEstimatedResale`) that fills `#id_sale_price` with `data.estimated_resale_price` when clicked. Update the client-side JavaScript to populate the hidden fields upon receiving the preflight identification JSON.
**Acceptance criteria:**
- [x] `ProductIntakeForm` binds `estimated_retail_price` and `estimated_resale_price` as hidden inputs.
- [x] When the assistant clicks "Identificar producto", the valuation badges in `#advisoryValuationContainer` update with the formatted prices or hide gracefully if `null`.
- [x] Benchmark reference badges and `#btnUseEstimatedResale` button appear below `#id_sale_price`.
- [x] Clicking "Usar precio de reventa estimado" populates `#id_sale_price.value` with the detected resale price.
- [x] Submitting the intake form persists both values into the newly created `Product` record.
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_intake`
- [x] Linter passes: `.venv\Scripts\ruff.exe check inventory/forms.py`
**Dependencies:** Task 82, Task 83
**Files likely touched:**
- `inventory/forms.py`
- `inventory/templates/inventory/intake.html`
**Estimated scope:** Medium (2 files)

---

### Task 85: Staging Product Detail View Reference Benchmarks (`inventory/templates/inventory/product_detail.html`)
**Description:** In `inventory/templates/inventory/product_detail.html`, inside the Pricing & Status section adjacent to the manager's `Sale Price (€)` input (`#id_sale_price`), render benchmark badges displaying: (1) `PVP Nuevo (MSRP): €XX.XX`, (2) `Reventa estimada: €YY.YY`, and (3) an optional discount-to-new percentage badge if both retail and sale price exist. For managers (`can_manage`), provide a quick-click pill "Aplicar reventa (€YY.YY)" that populates `#id_sale_price` without overwriting unless explicitly tapped. Gracefully display "—" if valuation is not available.
**Acceptance criteria:**
- [x] Product detail view displays benchmark badges `#ref-retail-price` and `#ref-resale-price` near `#id_sale_price`.
- [x] "Aplicar reventa" quick button populates `#id_sale_price` on click.
- [x] Layout remains responsive on mobile screens ($390 \times 844$) without horizontal scroll or layout shifts.
- [x] Graceful fallback displayed when valuation is null or unestimated.
**Verification:**
- [x] Unit tests pass: `.venv\Scripts\python.exe manage.py test tests.test_views`
- [x] Template validation: no unclosed tags or syntax errors.
**Dependencies:** Task 82, Task 83, Task 84
**Files likely touched:**
- `inventory/templates/inventory/product_detail.html`
**Estimated scope:** Small (1 file)

---

### Task 86: Bilingual Localization, Automated Unit & Integration Tests & Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_ai_valuation.py`, `CHANGELOG.md`)
**Description:** Add Spanish translations for all new strings ("Estimated Retail Price (€)", "Estimated Resale Price (€)", "Est. New Retail (MSRP)", "Est. Used Resale", "Usar precio de reventa estimado", "Aplicar reventa", etc.) in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo`. Create a dedicated test suite `tests/test_ai_valuation.py` covering: (1) Pydantic schema validation with valid floats, integer values, nulls, and missing fields; (2) Mock Gemini response in `identify_intake_product` parsing valuation; (3) `ProductIntakeForm` binding and saving `estimated_retail_price` and `estimated_resale_price`; (4) Product detail view rendering reference benchmarks; (5) Null valuation handling; (6) Validation limits (non-negative, max digits). Run `ruff check .` and the full regression test suite (323+ tests).
**Acceptance criteria:**
- [x] Spanish translations compiled in `django.mo`.
- [x] `tests/test_ai_valuation.py` covers schema validation, form binding, view rendering, and edge cases.
- [x] Full test suite (323+ tests) passes with 0 failures and 0 errors.
- [x] `ruff check .` passes cleanly with 0 warnings.
- [x] `CHANGELOG.md` updated documenting Phase 25 additions.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py compile_locales`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
- [x] Targeted test succeeds: `.venv\Scripts\python.exe manage.py test tests.test_ai_valuation`
- [x] Full test suite succeeds: `.venv\Scripts\python.exe manage.py test`
**Dependencies:** Task 82, Task 83, Task 84, Task 85
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_ai_valuation.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 25: Intake AI Valuation & Reference Pricing Complete
- [x] Model fields `estimated_retail_price` and `estimated_resale_price` migrated and registered in admin.
- [x] AI preflight scan parses and returns new MSRP and secondhand resale price estimates in € or null.
- [x] Intake mobile view displays reference valuation cards and provides one-click button to adopt resale price.
- [x] Staging product detail view displays reference benchmark badges beside manager sale price input with quick-apply action.
- [x] Bilingual localization compiled and verified.
- [x] All unit and regression tests pass with 0 failures.
- [x] `ruff check .` passes cleanly.

---

## Phase 26: Consolidated Intake Session Notifications & Debounced Alerts (Vertical Slice 22)

### Task 87: Domain Model `IntakeBatchSession`, `Product.batch_session` Foreign Key, Migration `0016_intake_batch_session.py` & Django Admin Registration (`inventory/models.py`, `inventory/migrations/0016_intake_batch_session.py`, `inventory/admin.py`)
**Description:** Implement the `IntakeBatchSession` domain model in `inventory/models.py` with fields: `assistant` (FK User), `started_at` (DateTimeField), `last_activity_at` (DateTimeField, db_index=True), `product_count` (PositiveIntegerField, default=1), `is_notified` (BooleanField, default=False, db_index=True), `closed_at` (DateTimeField, null=True, blank=True), and timestamps. Add compound indexes on `["is_notified", "last_activity_at"]` and `["assistant", "is_notified"]`. Add foreign key `batch_session = models.ForeignKey(IntakeBatchSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")` to the `Product` model. Generate migration `0016_intake_batch_session.py` and apply it cleanly. Register `IntakeBatchSessionAdmin` in `inventory/admin.py` with `list_display`, `list_filter`, and a read-only tabular inline of associated products.
**Acceptance criteria:**
- [x] `IntakeBatchSession` model created with all required fields, indexes, and string representation.
- [x] `Product.batch_session` foreign key added with `on_delete=models.SET_NULL` and `related_name="products"`.
- [x] Migration `0016_intake_batch_session.py` generated and applied cleanly without errors.
- [x] `IntakeBatchSessionAdmin` registered in `manager_admin_site` with `ProductInline` and searchable assistant fields.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py migrate`
- [x] Django check passes: `.venv\Scripts\python.exe manage.py check`
**Dependencies:** None
**Files likely touched:**
- `inventory/models.py`
- `inventory/migrations/0016_intake_batch_session.py`
- `inventory/admin.py`
**Estimated scope:** Small (3 files)

---

### Task 88: Sourcing Session Service Engine & Configuration Settings (`config/settings.py`, `inventory/services/intake_batch_service.py`)
**Description:** Add `INTAKE_SESSION_DEBOUNCE_MINUTES` setting in `config/settings.py` (default: 15, reading from `os.getenv`). Create `inventory/services/intake_batch_service.py` implementing: (1) `get_debounce_minutes()` helper; (2) `record_product_intake(product, assistant=None)` to find an active un-notified session within the debounce window or instantiate a new session, increment `product_count`, update `last_activity_at`, and assign `product.batch_session`; (3) `process_pending_intake_batches(debounce_minutes=None, dry_run=False)` to query expired unnotified sessions (`is_notified=False` and `last_activity_at <= now - window`), format bilingual push notifications (`📦 Lote completado: %(count)s nuevos productos`), dispatch them to `ROLE_MANAGER` via `send_push_to_group`, and flag `is_notified=True` with `closed_at=now()`.
**Acceptance criteria:**
- [x] `INTAKE_SESSION_DEBOUNCE_MINUTES` defined in `config/settings.py` with integer fallback to 15.
- [x] `record_product_intake()` groups uploads within 15 minutes into the same `IntakeBatchSession` and sets `product.batch_session`.
- [x] Uploads occurring after the 15-minute window or after session closure initiate a new `IntakeBatchSession`.
- [x] `process_pending_intake_batches()` queries only unnotified expired sessions, formats title and body, dispatches push alerts, and marks sessions closed/notified idempotently.
- [x] `dry_run=True` reports what would be processed without mutating records or sending Web Push alerts.
**Verification:**
- [x] Unit tests pass: `.venv\Scripts\python.exe manage.py test tests.test_intake_batch_notifications`
- [x] Linter passes: `.venv\Scripts\ruff.exe check inventory/services/intake_batch_service.py config/settings.py`
**Dependencies:** Task 87
**Files likely touched:**
- `config/settings.py`
- `inventory/services/intake_batch_service.py`
**Estimated scope:** Small (2 files)

---

### Task 89: Lifecycle Post-Save Signal Refactoring & Urgent Alert Preservation (`inventory/models.py`, `tests/test_pwa_push.py`)
**Description:** Refactor `notify_managers_on_product_lifecycle_save` post-save signal in `inventory/models.py`. When a product is created in `ProductStatus.DRAFT`, suppress the immediate `send_push_to_group` call and instead invoke `record_product_intake(product=instance, assistant=instance.created_by)`. Opportunistically call `process_pending_intake_batches()` to clean up any past expired sessions. Crucially verify that immediate notifications for `PRICE_PENDING` and all `ProductClarification` question/answer signals remain instant and untouched. Update existing signal tests in `tests/test_pwa_push.py` to reflect the debounced batch behavior for draft products.
**Acceptance criteria:**
- [x] Creating a draft product no longer dispatches an immediate individual Web Push alert to managers.
- [x] The created draft product is assigned to the assistant's active `IntakeBatchSession`.
- [x] Immediate alerts for `PRICE_PENDING` still fire immediately when a product transitions to price pending.
- [x] Immediate alerts for clarification questions and resolved answers in `notify_assistant_on_clarification_save` and `notify_manager_on_clarification_answer` continue firing immediately.
- [x] Existing signal test in `tests/test_pwa_push.py` updated to verify debounced intake recording.
**Verification:**
- [x] Tests pass: `.venv\Scripts\python.exe manage.py test tests.test_pwa_push`
- [x] Linter passes: `.venv\Scripts\ruff.exe check inventory/models.py tests/test_pwa_push.py`
**Dependencies:** Task 87, Task 88
**Files likely touched:**
- `inventory/models.py`
- `tests/test_pwa_push.py`
**Estimated scope:** Small (2 files)

---

### Task 90: Management Command `process_intake_batches` for CLI & Automated Cron Execution (`inventory/management/commands/process_intake_batches.py`)
**Description:** Create `inventory/management/commands/process_intake_batches.py` exposing CLI command `python manage.py process_intake_batches`. Support `--debounce-minutes` (integer override) and `--dry-run` (simulation mode) options. The command executes `process_pending_intake_batches()` and outputs a clean, human-readable summary of processed sessions and dispatched push alerts to `stdout`.
**Acceptance criteria:**
- [x] Command `process_intake_batches` registered and callable via `manage.py`.
- [x] `--debounce-minutes` flag allows overriding the default inactivity window.
- [x] `--dry-run` flag executes in simulation mode without updating database records or dispatching push alerts.
- [x] Stdout reports the exact number of expired batches found and notifications sent.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py process_intake_batches --dry-run`
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py process_intake_batches --help`
**Dependencies:** Task 88
**Files likely touched:**
- `inventory/management/commands/process_intake_batches.py`
**Estimated scope:** Small (1 file)

---

### Task 91: Bilingual Translations, Comprehensive Automated Test Suite & Regression Verification (`locale/es/LC_MESSAGES/django.po`, `locale/es/LC_MESSAGES/django.mo`, `tests/test_intake_batch_notifications.py`, `CHANGELOG.md`)
**Description:** Add Spanish translations for all new strings ("Intake Batch Session", "Intake Batch Sessions", "Started At", "Last Activity At", "Product Count", "Is Notified", "Closed At", "📦 Lote completado: %(count)s nuevos productos", "📦 Lote completado: %(count)s productos catalogados por %(assistant)s", "Toca para revisar las prendas en el panel de staging.") in `locale/es/LC_MESSAGES/django.po` and compile to `django.mo`. Build a dedicated test suite `tests/test_intake_batch_notifications.py` covering: (1) sequential upload grouping into single session; (2) inactivity window debounce expiration; (3) single consolidated push dispatch with correct count and URL `/dashboard/?status=draft`; (4) idempotency (no duplicate dispatch on second pass); (5) independent session tracking per assistant; (6) creation of new session after previous session closed; (7) CLI command execution with `--dry-run` and live modes; (8) isolation ensuring clarifications and price pending alerts remain instant. Update `CHANGELOG.md` with Phase 26 details and verify full test suite (337+ tests).
**Acceptance criteria:**
- [x] Spanish translations compiled in `django.mo` with 0 fuzzy or missing entries.
- [x] Comprehensive test suite in `tests/test_intake_batch_notifications.py` passes 100%.
- [x] Full regression suite (337+ tests) passes with 0 failures and 0 errors.
- [x] `ruff check .` passes with 0 warnings.
- [x] `CHANGELOG.md` updated with Phase 26 release notes.
**Verification:**
- [x] Command succeeds: `.venv\Scripts\python.exe manage.py compile_locales`
- [x] Targeted tests pass: `.venv\Scripts\python.exe manage.py test tests.test_intake_batch_notifications`
- [x] Full test suite passes: `.venv\Scripts\python.exe manage.py test`
- [x] Linter passes: `.venv\Scripts\ruff.exe check .`
**Dependencies:** Task 87, Task 88, Task 89, Task 90
**Files likely touched:**
- `locale/es/LC_MESSAGES/django.po`
- `locale/es/LC_MESSAGES/django.mo`
- `tests/test_intake_batch_notifications.py`
- `CHANGELOG.md`
**Estimated scope:** Medium (4 files)

---

## Checkpoint 26: Consolidated Intake Session Notifications Complete
- [x] `IntakeBatchSession` model and migration `0016_intake_batch_session.py` applied cleanly and registered in admin.
- [x] Uploading consecutive products during intake groups them under one `IntakeBatchSession` without sending individual push alerts.
- [x] After 15 minutes of inactivity, a single consolidated push alert is dispatched to store managers with the accurate batch count.
- [x] Management command `process_intake_batches` operates reliably in live and dry-run modes.
- [x] Urgent clarification questions and price pending notifications continue to notify immediately without debouncing.
- [x] Bilingual localization compiled and verified.
- [x] All unit and regression tests pass with 0 failures.
- [x] `ruff check .` passes cleanly.








