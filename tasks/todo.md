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


