# Technical Specification: Secondhand Inventory & Staging App

## 1. Objective
Build a lightweight, responsive Django web application for a secondhand reselling workflow that connects two primary user roles:
1. **Sourcing Assistant (User A):** Uses a mobile-first interface to rapidly upload photos and rough field notes directly from a phone.
2. **Manager / Lister (You):** Reviews items on a desktop dashboard, triggers multimodal vision AI to generate marketplace-ready listing copy, downloads product images in bulk, copies text to the clipboard for external marketplace posting, and tracks sales status and prices.
3. **Multi-Language Support (i18n):** Complete bilingual support (Spanish & English). The interface automatically detects the user's browser language via `Accept-Language`, rendering the entire UI in Spanish (`es`) for Spanish-language browsers and cleanly falling back to English (`en`) for any other language.
4. **Cloud Object Storage (Oracle Cloud Infrastructure):** Product images are saved directly to an Oracle Cloud Infrastructure (OCI) Object Storage bucket instead of the local server disk. Uploaded photos are postprocessed to WebP in memory and transferred to cloud storage, eliminating local disk consumption and ensuring stateless, scalable deployment.
5. **Catalog Pagination & Multi-Field Search:** Server-side pagination capping catalog listings at 20 items per page with query-preserving navigation links, accompanied by multi-field search allowing discovery by title, description/field note, and creation or sale dates.
6. **User Management & Admin Role Gating:** Dedicated user management in Django administration restricted exclusively to store Managers (`is_manager(user)`), allowing managers to add, modify, deactivate, and remove assistants with role badges, productivity counts, and automatic permission synchronization.
7. **Dynamic AI Model & Prompt Configuration:** Database-backed configuration managed in Django administration (`AIPromptConfiguration`), enabling store managers to tune Gemini model names (free-form), temperature, and localized copywriting prompt instructions without modifying codebase files or triggering server restarts, backed by automatic fallback to hardcoded defaults.

---

## 2. Tech Stack & Dependencies
- **Language / Runtime:** Python 3.13+
- **Framework:** Django 5.x
- **Database:** SQLite (default for low-ops development/staging; PostgreSQL compatible)
- **Cloud Object Storage:**
  - Oracle Cloud Infrastructure (OCI) Object Storage bucket.
  - Integration options:
    - **Recommended:** `django-storages[boto3]` leveraging OCI's native Amazon S3-compatible API endpoint (`https://{namespace}.compat.objectstorage.{region}.oraclecloud.com`) with OCI Customer Secret Keys.
    - **Alternative:** Custom Django Storage backend powered by the official `oci` Python SDK with API Key / PEM credentials.
  - Zero local disk footprint: In-memory image compression via `io.BytesIO` / `ContentFile` before upload.
- **Internationalization (i18n):**
  - Django `LocaleMiddleware` for automatic browser language negotiation (`Accept-Language` header).
  - Django translation system (`django.utils.translation`, `{% load i18n %}`, `{% trans %}`).
  - Standard PO/MO message catalogs (`locale/es/LC_MESSAGES/django.po`).
  - `polib` Python library for portable compilation of `.po` files to binary `.mo` catalogs directly on Windows without requiring external GNU gettext binaries.
- **Image Processing:** Pillow (`PIL`) for validation and automated postprocessing (converting uploaded photos to `.webp` with quality optimization to save storage).
- **AI Integration:** Google Gemini API (`google-genai` / Gemini 2.5/1.5 Flash multimodal).
- **Frontend / Styling:** Django Templates + Tailwind CSS (via CDN) + lightweight Vanilla JavaScript (clipboard copy, multi-image preview, async AI generation feedback).
- **Currency:** Euro (`€`) default formatting.
- **Archive / Zip:** Python standard library `zipfile` for bundling photos on download directly from storage stream.
- **Environment Management:** `python-dotenv` for local `.env` configuration.

---

## 3. Commands
```bash
# Environment Setup
python -m venv .venv
.venv\Scripts\Activate.ps1       # Windows PowerShell
pip install -r requirements.txt

# Database Migrations
python manage.py makemigrations
python manage.py migrate

# Create Superuser (Admin / Manager)
python manage.py createsuperuser

# Compile Translation Catalogs (.po -> .mo)
python manage.py compile_locales

# Run Development Server
python manage.py runserver

# Testing & Quality
python manage.py test
ruff check .
```

---

## 4. Project Structure
```text
epic-tesla/
├── manage.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings.py               # Configured with LANGUAGES, LOCALE_PATHS, LocaleMiddleware
│   ├── urls.py
│   └── wsgi.py
├── locale/                       # Project-level translation catalogs
│   ├── en/
│   │   └── LC_MESSAGES/
│   │       ├── django.po
│   │       └── django.mo
│   └── es/
│       └── LC_MESSAGES/
│           ├── django.po         # Spanish UI translations
│           └── django.mo         # Compiled binary catalog
├── inventory/
│   ├── __init__.py
│   ├── admin.py                  # Django admin registration
│   ├── apps.py
│   ├── models.py                 # Product, ProductImage (with gettext_lazy verbose names)
│   ├── forms.py                  # ProductIntakeForm, ProductUpdateForm (localized labels/errors)
│   ├── urls.py
│   ├── permissions.py
│   ├── views.py                  # Localized messages and templates
│   ├── management/
│   │   └── commands/
│   │       ├── setup_roles.py
│   │       └── compile_locales.py # Python-native PO to MO compiler using polib
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py         # Gemini Multimodal Vision integration
│   │   └── image_service.py      # Pillow WebP conversion and optimization
│   ├── templates/
│   │   ├── registration/
│   │   │   └── login.html        # Localized login template
│   │   └── inventory/
│   │       ├── base.html         # Localized layout, navbar, language selector
│   │       ├── intake.html       # Localized mobile intake form
│   │       ├── dashboard.html    # Localized catalog dashboard & filter tabs
│   │       └── product_detail.html # Localized staging view & copy buttons
│   └── static/
│       ├── css/
│       └── js/
├── media/                        # User-uploaded product photos (saved as .webp)
├── tests/
│   ├── test_models.py
│   ├── test_views.py
│   ├── test_auth.py
│   ├── test_intake.py
│   ├── test_dashboard.py
│   ├── test_zip_download.py
│   ├── test_image_service.py
│   ├── test_ai_service.py
│   ├── test_i18n.py              # Language negotiation and translation tests
│   └── test_storage.py           # OCI Object Storage integration & upload tests
└── docs/
    ├── intent/
    │   └── secondhand-inventory-app.md
    ├── prds/
    │   ├── PRD-dynamic-ai-configuration.md
    │   ├── PRD-multilanguage-support.md
    │   └── PRD-oracle-object-storage.md
    └── SPEC.md
```

---

## 5. Data Models

### 5.1 `Product`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | UUID/AutoField | Primary Key | Unique product identifier |
| `raw_note` | TextField | blank=True | Original raw notes taken by assistant (preserved, user language) |
| `ai_title` | CharField | max_length=255, blank=True | AI-generated marketplace title (editable) |
| `ai_description` | TextField | blank=True | AI-generated marketplace listing copy (editable) |
| `sale_price` | DecimalField | max_digits=10, decimal_places=2, null=True, blank=True | Target or final sale price in Euros (€) |
| `is_sold` | BooleanField | default=False | Status indicating if item has been sold |
| `sold_at` | DateTimeField | null=True, blank=True | Timestamp when marked as sold |
| `created_by` | ForeignKey(User) | null=True, on_delete=SET_NULL | User who cataloged the item |
| `created_at` | DateTimeField | auto_now_add=True | Creation timestamp |
| `updated_at` | DateTimeField | auto_now=True | Last modification timestamp |

### 5.2 `ProductImage`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique image identifier |
| `product` | ForeignKey(Product) | related_name='images', on_delete=CASCADE | Parent product |
| `image` | ImageField | upload_to='products/%Y/%m/' | Uploaded image file (auto-converted to WebP) |
| `order` | PositiveIntegerField | default=0 | Display order (primary image is order 0) |
| `created_at` | DateTimeField | auto_now_add=True | Upload timestamp |

### 5.3 `AIPromptConfiguration`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique configuration identifier |
| `language` | CharField | max_length=10, choices=[('es', 'Español'), ('en', 'English')] | Target language code |
| `model_name` | CharField | max_length=64, default="gemini-2.5-flash" | Gemini model identifier (free-form text, e.g. gemini-2.5-flash, gemini-2.5-pro) |
| `temperature` | FloatField | default=0.3, validators=[0.0-1.0] | LLM generation sampling temperature |
| `system_instruction` | TextField | blank=False | Editable copywriting guidelines and marketplace formatting rules |
| `is_active` | BooleanField | default=True | Active profile toggle for this language (enforces max 1 active per language) |
| `created_at` | DateTimeField | auto_now_add=True | Configuration creation timestamp |
| `updated_at` | DateTimeField | auto_now=True | Last modification timestamp |

---

## 6. Key Features & Workflows

### 6.1 Assistant Intake (Mobile-First)
- URL: `/intake/`
- Accessibility: Sourcing Assistant & Manager.
- Features:
  - Responsive, high-contrast mobile form.
  - Multi-file image selector (`<input type="file" multiple accept="image/*" capture="environment">`).
  - Limits: Max 10 images per product, up to 10MB each.
  - Automatic backend postprocessing: Images converted to `.webp` format upon save.
  - Raw notes input area.
  - Instant client-side thumbnail previews before uploading.
  - Quick submit with visual feedback.
  - Full Spanish UI localization when accessed from a Spanish browser.

### 6.2 Manager Dashboard & Product Catalog
- URL: `/` or `/dashboard/`
- Accessibility: All authenticated users (with role-based actions).
- Features:
  - Filterable by status: `All` / `Todos`, `Active` / `Activo`, `Sold` / `Vendido`.
  - Search by title or raw note keyword.
  - Card/Table view displaying primary photo, title/note preview, price in `€`, status badge, and date.

### 6.3 Product Detail & Staging Hub
- URL: `/products/<pk>/`
- Features:
  - **Photo Gallery:** Grid of all attached photos with zoom/lightbox preview.
  - **ZIP Download:** Button to download an in-memory `.zip` archive containing all optimized `.webp` photos named `product_<id>_img_<index>.webp`.
  - **Preserved Note:** Dedicated read-only view of the assistant's original field note.
  - **AI Generation Engine:** "Generate AI Listing" button calling Gemini Multimodal Vision with attached images and `raw_note`. Returns structured JSON (`title`, `description`).
  - **One-Click Copy:** Fast copy buttons for Title and Description to paste directly into marketplace listing windows.
  - **Sales Management:** Form to update `sale_price` (in `€`) and toggle `is_sold`.

### 6.4 Internationalization & Localization (i18n / l10n)
- **Automatic Language Negotiation & Manual Switcher:**
  - `LocaleMiddleware` configured immediately after `SessionMiddleware` and before `CommonMiddleware`.
  - Determines user language via `Accept-Language` HTTP header sent by the client browser.
  - If language starts with `es` (e.g., `es`, `es-ES`, `es-MX`, `es-AR`), activate Spanish (`es`).
  - For all other languages (`en`, `fr`, `de`, etc.), cleanly fall back to `LANGUAGE_CODE = 'en'`.
  - **Manual Language Switcher:** A clean, accessible toggle in the navigation header (`[🇬🇧 EN | 🇪🇸 ES]`) powered by Django's built-in `set_language` view, enabling users to manually override browser settings at will.
- **Coverage:**
  - Templates wrapped with `{% load i18n %}` and `{% trans "..." %}` / `{% blocktrans %}...{% endblocktrans %}`.
  - Python files wrapped with `from django.utils.translation import gettext_lazy as _`.
  - Flash messages, validation errors, and form labels localized into Spanish.

### 6.5 Cloud Asset Storage (Oracle Cloud Infrastructure Object Storage)
- **Target Storage Backend:** Oracle Cloud Infrastructure (OCI) Object Storage bucket.
- **Decoupled Architecture:**
  - Product photos are stored in the OCI Object Storage bucket rather than the local filesystem.
  - Image processing (Pillow orientation correction and WebP conversion) happens strictly in-memory (`io.BytesIO` / `ContentFile`).
  - Processed WebP images are uploaded directly to OCI under `products/%Y/%m/product_<hash>.webp`.
  - Local `media/products/` directory remains unused for permanent storage.
- **Serving & Downloads:**
  - Staging detail and dashboard templates render image URLs pointing directly to the OCI Object Storage bucket.
  - In-memory ZIP packaging (`product_download_zip_view`) streams image bytes from the storage backend directly into the download archive without reading from local disk.
  - AI listing generation (`ai_service.py`) accesses image content via Django's storage API (`img_obj.image.open('rb')`).

### 6.6 Catalog Pagination & Multi-Field Search
- **Server-Side Pagination:**
  - Primary catalog overview (`dashboard_view`) capped at **20 items per page** (`PAGE_SIZE = 20`) via `django.core.paginator.Paginator`.
  - Robust page resolution using `paginator.get_page(page_number)` to gracefully handle non-integer or out-of-range page requests.
  - Elided page range display (`get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)`).
  - Query string retention: Page navigation links preserve active search (`q`) and status filter (`status`) parameters.
  - Responsive pagination component: Mobile shows clean prev/next; desktop displays elided numbered buttons and item counter.
- **Multi-Field Search:**
  - Text Search: Case-insensitive containment across `ai_title`, `raw_note`, and `ai_description`.
  - Date Search: Automated date string parsing supporting standard formats:
    - ISO: `YYYY-MM-DD`
    - Slashed / Hyphenated: `DD/MM/YYYY`, `DD-MM-YYYY`, `MM/DD/YYYY`, `MM-DD-YYYY`
    - Year-Month: `YYYY-MM`
    - Year: `YYYY`
    Matches `created_at__date` and `sold_at__date` when recognized as a valid date.
  - Unified UX: Manager enters either text, a date, or both without needing separate search fields.

---

## 7. AI Service Contract (`ai_service.py`)
```python
def generate_product_listing(
    product: Product,
    model_name: str | None = None,
    language: str = "en",
) -> dict[str, str]:
    """
    Inputs:
      - product.raw_note: string
      - product.images: QuerySet of ProductImage
      - model_name: optional override; if None, resolves from active AIPromptConfiguration
      - language: str ("es" or "en") - dynamically resolved from active request locale
    Process:
      - Queries active AIPromptConfiguration for the target language.
      - If found: uses configured model_name, temperature, and custom copywriting instructions.
      - If absent or DB error: falls back seamlessly to hardcoded defaults (gemini-2.5-flash, temp 0.3).
      - Loads image bytes and raw notes.
      - Envelopes prompt with fixed technical schema instructions guaranteeing ProductListingSchema output.
      - Executes Gemini Multimodal Vision API call.
      - Returns schema-validated JSON:
        {
          "title": "Concise SEO-friendly marketplace title in target language",
          "description": "Engaging, bulleted sales copy with condition details in target language"
        }
    """
```


---

## 8. Role-Based Permissions & Administration User Management
- **Role Architecture:**
  - **Assistant Group (`assistants`):** Field intake staff. Access to `/intake/`, `/dashboard/` (read-only catalog view of all items), own profile. Cannot trigger AI listings, edit prices, mark sold, or access Django Admin.
  - **Manager Group (`managers` or `is_superuser`):** Store leadership. Full access to AI generation, pricing, status modification, photo ZIP downloads, and Django Admin.
- **Admin Panel Access Control (`ManagerAdminSite`):**
  - Django Administration (`/admin/`) access is strictly gated by `ManagerAdminSite.has_permission(request)`.
  - Only active users who satisfy `is_manager(user)` (`user.is_active and (user.is_superuser or user.groups.filter(name='managers').exists() or user.is_staff)`) are permitted.
  - Assistants attempting to access `/admin/` are strictly blocked (`403 Forbidden` / access denied).
- **Customized User Management (`CustomUserAdmin`):**
  - Registered in Django Admin to manage assistants and managers.
  - **List Display:** Username, Email, Role badge (`Superuser`, `Manager`, `Assistant`, `None`), Cataloged items count (`created_products.count()`), Active status, Date joined.
  - **Automated Flag Synchronization:** Assigning a user to the `managers` group sets `is_staff=True`. Assigning a user solely to `assistants` ensures `is_staff=False`.
  - **Actions:** Quick actions to assign Assistant role, assign Manager role, and safely deactivate users.
- **AI Prompt Configuration Admin (`AIPromptConfigurationAdmin`):**
  - Registered in `ManagerAdminSite` restricted to managers.
  - Enables managers to view and edit `model_name` (free-form), `temperature`, `system_instruction`, and `is_active` for each language (`es`, `en`).
  - Validation ensures valid temperatures (0.0 to 1.0) and maintains only one active configuration per language.

---

## 9. Boundaries
- **Always:**
  - Mark all static user-facing text for translation using standard Django `_()` or `{% trans %}`.
  - Compile translation `.po` files into `.mo` catalogs before running tests or launching the server.
  - Ensure fallback to English (`en`) is seamless whenever a requested translation or language is missing.
  - Preserve `raw_note` untouched in the user's raw input language regardless of UI language.
  - Process uploaded images into WebP in memory before uploading to cloud storage.
  - Save all product images to Oracle Object Storage bucket without persisting files on local disk.
  - Enforce max 10 photos per product and max 10MB per file during validation.
  - Store OCI credentials and API keys in `.env` and load via `os.environ` / `python-dotenv`.
  - Use in-memory or mocked storage in automated unit tests so tests do not depend on active cloud network access.
  - Cap catalog list views at 20 items per page with server-side pagination.
  - Preserve active filter and search query parameters (`status`, `q`) across pagination page links.
  - Sanitize and parameterize all search queries using Django ORM `Q` lookups to prevent injection.
  - Restrict `/admin/` access strictly to managers (`is_manager(user)`).
  - Synchronize `is_staff` flag automatically based on manager vs assistant role.
  - Retrieve AI model, temperature, and prompt from active `AIPromptConfiguration` with transparent fallback to hardcoded constants if unavailable.
  - Enforce that user-edited prompt instructions cannot bypass Pydantic `ProductListingSchema` validation.
- **Ask First:**
  - Choosing between OCI S3-compatible API keys vs Native OCI API Key (PEM) authentication.
  - Configuring bucket access permissions (public bucket vs presigned URLs).
  - Adding third-party translation cloud services (Google Cloud Translation API, DeepL).
  - Translating stored database records dynamically.
  - Implementing infinite scrolling or client-side JavaScript pagination instead of server-side pagination.
  - Changing authentication backend (e.g. SSO / OAuth).
  - Adding external LLM providers (e.g. OpenAI, Anthropic) beyond Google Gemini.
- **Never:**
  - Store permanent product images on local server disk (`MEDIA_ROOT`).
  - Commit OCI secrets, private keys, or passwords to version control.
  - Hardcode Spanish strings directly into templates or Python files without gettext markers.
  - Alter the user's preserved `raw_note` during translation or AI processing.
  - Require external GNU gettext OS binaries to build or run the project on Windows.
  - Execute unbounded unpaginated queries on main catalog views.
  - Allow non-manager assistants to access Django administration (`/admin/`).
  - Allow non-manager assistants to access or edit `AIPromptConfiguration`.
  - Crash AI listing generation when a database prompt configuration is missing, deactivated, or malformed (always fall back to safe defaults).

---

## 10. Success Criteria
1. When a product is cataloged on `/intake/`, photos are processed to WebP in memory and saved directly to the configured Oracle Object Storage bucket.
2. Local filesystem storage (`media/products/`) remains empty, leaving no permanent file footprint on the server.
3. Dashboard thumbnails and staging gallery images load seamlessly using OCI Object Storage URLs.
4. "Download Photos (.ZIP)" streams images directly from OCI Object Storage into the download bundle.
5. Gemini Multimodal Vision AI reads image bytes retrieved from OCI storage and generates listing copy successfully.
6. All automated unit and integration tests pass cleanly with mocked/in-memory cloud storage.
7. Multilingual support (Spanish & English) functions continuously with OCI-backed assets.
8. When more than 20 products exist in the catalog, `/dashboard/` paginates the catalog into batches of 20 items with active pagination controls ("Previous", "Next", and numbered page links).
9. Navigating between pages preserves active `status` and `q` search parameters (e.g. `?status=active&q=jacket&page=2`).
10. Entering a date query (e.g. `2026-10-10`, `10/10/2026`, `2026-10`) returns items created or sold on that date.
11. Entering a text query matches title (`ai_title`), generated description (`ai_description`), or raw field notes (`raw_note`).
12. All pagination and search labels switch between Spanish and English cleanly according to the active language.
13. Only verified managers can access `/admin/`; assistants attempting to access `/admin/` are strictly blocked.
14. Managers can add, modify, deactivate, and delete assistants in `/admin/` with visual role badges and cataloging metrics.
15. Managers can edit Gemini model names, temperature, and copywriting instructions via `AIPromptConfiguration` in `/admin/`.
16. Changes made to active prompt configurations immediately apply to subsequent AI listing generations.
17. Deactivating or deleting configurations causes `generate_product_listing` to gracefully fall back to built-in defaults without crashing.
18. Database migrations pre-populate active default configurations for Spanish and English.

---

## 11. Decisions Log
- **Supported Languages:** English (`en`, default) and Spanish (`es`).
- **Detection Method:** Automatic client negotiation via browser `Accept-Language` headers with `LocaleMiddleware`.
- **Manual Language Switcher:** Included in navigation header (`set_language`).
- **AI Output Language:** Matches the active user interface language (generates Spanish copy when in Spanish mode, English when in English mode).
- **Windows Portability:** Use a Python-native compilation script/command (`polib`) to compile `.po` into `.mo` without relying on external C-based `gettext.exe`.
- **Currency:** Set to Euro (`€`).
- **Image Limits:** Maximum 10 photos per product, 10MB maximum file size per upload.
- **Storage Optimization:** Server-side postprocessing to convert all uploaded images to WebP format in memory.
- **Cloud Asset Storage:** Oracle Cloud Infrastructure (OCI) Object Storage bucket replaces local disk storage.
- **Catalog Page Size:** 20 items per page (`PAGE_SIZE = 20`) via Django `Paginator`.
- **Search Scope:** Multi-field unified search supporting text (title, note, description) and date patterns (ISO, European/US slash, year-month).
- **Admin Access Restriction:** Custom `ManagerAdminSite` restricting `/admin/` exclusively to `is_manager(user)`.
- **User Management Customization:** `CustomUserAdmin` with role badges, cataloging counts, and automated group/staff synchronization.
- **AI Parameter Configuration:** Database-backed `AIPromptConfiguration` model editable in Django admin.
- **Model Name Flexibility:** Free-form text input (defaulting to `gemini-2.5-flash`) to enable zero-code adoption of new Gemini releases.
- **Prompt Safety Boundary:** Separation of editable copywriting tone from immutable JSON output schema envelopes to prevent parsing failures.

---

## 12. Open Questions
1. **Assistant Deletion vs Deactivation:**
   - Deactivating a user (`is_active = False`) blocks login immediately while preserving historical attribution on all products they cataloged (`created_by`).
   - Hard deletion removes the user row and sets `created_by = NULL` on their products (via `on_delete=models.SET_NULL`).
   - **Recommended Approach:** Provide both in admin, with a warning / bulk action emphasizing Deactivation as best practice.
   *Do you agree with prioritizing deactivation as the primary offboarding method while retaining hard delete if needed?*
2. **Admin Entry Point for Assistants:**
   - If an assistant attempts to navigate directly to `/admin/`:
   - **Option A (Recommended):** Return standard HTTP 403 Permission Denied with a localized message: "Manager privileges required to access administration."
   - **Option B:** Redirect them directly to `/intake/` or `/dashboard/` with a warning message.
   *Which behavior do you prefer when an assistant navigates to `/admin/`?*
3. **Active Configuration Uniqueness Enforcement:**
   - When a manager saves an `AIPromptConfiguration` as active (`is_active=True`):
   - **Option A (Automatic Deactivation of Previous - Recommended):** Saving an active configuration automatically sets any other configuration for that same language to `is_active=False`.
   - **Option B (Strict Validation Error):** If an active configuration already exists for that language, the admin form rejects the save with a validation error asking the manager to manually deactivate the other one first.
   *Which behavior do you prefer for managing active configurations?*

