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
8. **Marketplace Sites & External Listing Links Tracking:** Database-backed marketplace platforms table (`MarketplaceSite`) managed via Django Admin, enabling managers to define and reorder resale sites (Wallapop, Vinted, eBay, Milanuncios, etc.). Products link dynamically to these platforms (`ProductListingLink`), allowing managers to record, view, open, and copy direct listing URLs directly from the product detail staging page (`/products/<pk>/`) and Django admin.
9. **Product Clarifications & Lifecycle State Machine:** Structured product lifecycle states (`DRAFT`, `AWAITING_INFO`, `READY`, `SOLD`, `BLOCKED`) coupled with an in-app clarification Q&A mechanism. When managers identify missing product info during staging, they submit categorized questions; assistants are alerted via top navigation badges (`❓ Dudas (X)`) and mobile intake banners to answer promptly. Resolved answers automatically enrich the Gemini Multimodal Vision prompt for higher-converting listings.
10. **Cloudflare Turnstile Login Protection:** Privacy-preserving smart CAPTCHA challenge integrated into the user login interface (`/login/`). Protects authentication against automated brute-force attacks and credential stuffing while offering seamless zero-friction verification for human staff. Fully configurable with test dummy keys and bypass options for local development and CI/CD automation.
11. **SQLite Automated Cloud Backup to OCI Object Storage:** Automated, zero-downtime daily backups of the primary SQLite database file directly into the configured Oracle Cloud Infrastructure (OCI) Object Storage bucket using SQLite's native online backup API and gzip compression. Includes retention pruning (30 days), a CLI management command (`python manage.py backup_db`), and an audit log table with on-demand backup triggers in Django Administration (`DatabaseBackupLog`).
12. **Smart Intake Pre-flight & Direct Pricing:** On-demand AI product identification and pre-flight advisory assistance directly inside the mobile intake screen (`inventory:intake`). Sourcing assistants can click "Identificar producto" to trigger a fast Gemini vision scan (`/inventory/intake/identify/`) returning detected specs and a non-blocking checklist of missing details (e.g. unreadable size tags or missing flaw photos) while the physical item is still in hand. Also introduces an optional sale price field (`sale_price`, €) directly on the intake form.
13. **Intake Form State Management, Async Blocking & Client-Side Validations:** Robust client-side form state machine (`idle`, `identifying`, `submitting`) on the mobile intake view (`/intake/`). Blocks interactions during asynchronous operations (disabling form submit and dropzone while AI pre-flight is in flight) to prevent race conditions and photo mutation; locks submit triggers on form POST to eliminate double-click duplicate records; and replaces native browser `alert()` dialogs with accessible, non-disruptive inline error alerts (`role="alert"`, `aria-live="polite"`) for zero photos, >10 image count, and >10MB individual file size limits.
14. **Responsive Mobile Navigation & Hamburger Drawer:** Streamlined, uncluttered header experience across mobile viewports (< 768px / `md:`). Collapses the horizontal links, language toggles, profile details, and logout actions into an accessible mobile hamburger drawer (`#mobile-menu`), while preserving the full desktop navigation layout on larger screens (`≥ md:`). Features WCAG 2.1 AA compliant 44×44px touch targets, dynamic SVG toggle (☰ to ✕), `aria-expanded` attributes, and `Escape` / outside-click dismissal.
15. **Intake Photo Preview Management & Individual Deletion:** Dynamic client-side photo management in the mobile intake form (`/intake/`). Each preview thumbnail rendered in `#previewGrid` features an accessible "✕" delete button conforming to WCAG 2.1 AA touch guidelines. Assistants can remove flawed or accidental photos individually without clearing or re-uploading the entire batch. Synchronizes with the native `<input type="file" multiple>` via the standard `DataTransfer` Web API, updates sequential `#N` badges and `X / 10 selected` counters, supports cumulative photo capture across camera snaps up to 10 photos, and disables delete actions during active AI vision or form submission states.
16. **Refined Product Lifecycle State Machine & Granular Commercial States:** Extended state machine implementing `DRAFT`, `PRICE_PENDING`, `READY`, `PUBLISHED`, `AWAITING_INFO`, `BLOCKED`, and `SOLD` with 100% automated transition logic evaluating product titles, descriptions, Euro prices, active marketplace links, and pending clarification doubts.
17. **Installable PWA Support & VAPID Web Push Alerts:** W3C Web App Manifest (`/manifest.json`), pass-through service worker (`/sw.js`), and VAPID Web Push notification infrastructure delivering instant real-time alerts to assistants (on pending doubts) and managers (on answered doubts and draft/pricing bottlenecks) controlled via `.env` live signals.
18. **Anti-Apilación Dashboard Horizontal Rail & Mobile High-Readability Typography:** Decoupled status filter rail with horizontal touch-scrolling preventing tab stacking (*apilación*), combined with standardized high-readability typography, elimination of sub-12px micro-fonts, and minimum 16px form inputs to prevent involuntary iOS Safari viewport auto-zooming.
19. **Product State Change History & User Audit Trail (`ProductStatusLog`):** Complete operational traceability recording every product state transition, capturing exact timestamps (`created_at`), previous and new lifecycle statuses (`from_status` $\to$ `to_status`), the acting user (`changed_by`), and contextual trigger descriptions, exposed via a visual timeline on the product staging page and searchable Django Admin changelist/inline.
20. **Compilation & Docker Image Build Timestamp Display ("Which Compilation Are We Using?"):** Operational traceability across environments (development, staging, production) displaying the build date, time, commit hash, and environment badge in the bottom application footer ([`docs/prds/PRD-docker-build-info-and-compilation-timestamp.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-docker-build-info-and-compilation-timestamp.md)).
21. **Intake AI Valuation & Reference Pricing ("New Retail Value & Used Resale Value"):** AI appraisal benchmarks estimating both the original new retail value (MSRP) and realistic secondhand market resale value during intake identification, persisted to the `Product` model and displayed near the sale price in both the intake form and product staging detail view ([`docs/prds/PRD-intake-ai-valuation-reference-prices.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-intake-ai-valuation-reference-prices.md)).
22. **Consolidated Intake Session Notifications ("Debounced Manager Push Alerts"):** Database-backed debounced sourcing session engine (`IntakeBatchSession`) bundling consecutive product uploads by an assistant within a 15-minute sliding inactivity window into a single consolidated Web Push alert to store managers (`📦 Lote completado: [X] nuevos productos`), eliminating notification spam while keeping urgent clarification doubts instant ([`docs/prds/PRD-consolidated-intake-session-notifications.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-consolidated-intake-session-notifications.md)).
23. **Sale Channel Tracking & Commercial Sales Attribution ("Where Was It Sold?"):** Comprehensive commercial sales channel recording on sold items (`sold_channel_type`, `sold_marketplace`, `sold_channel_notes`). Differentiates sales between physical in-store walk-ins (`in_store`), dynamic online marketplace platforms (`marketplace` linked to `MarketplaceSite`), and direct sales (`other`), backed by conditional form validation, detail view quick-pickers, dashboard sub-filtering (`?status=sold&channel=in_store`), and `ProductStatusLog` audit records ([`docs/prds/PRD-sale-channel-tracking.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-sale-channel-tracking.md)).
24. **Product Soft-Delete, Archival & "Erased" Trash Category ("Trash & Restore"):** Safe, non-destructive product soft-deletion (`is_deleted`, `deleted_at`, `deleted_by`) allowing managers to remove obsolete, damaged, or erroneous items from the staging workflow. Erased products are completely excluded from default catalog views and active status counts, isolated into a dedicated `?status=erased` ("🗑️ Eliminados" / "🗑️ Trash") tab with live count badge, and can be restored back to their exact prior status at any time from the product detail staging view ([`docs/prds/PRD-product-soft-delete-and-archival.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-product-soft-delete-and-archival.md)).
25. **Product Detail Clarifications Hub ("Direct Notes & Q&A Doubts"):** Unified post-intake clarification and knowledge hub situated directly below the preserved intake notes in `/products/<pk>/`. Enables assistants and managers to record direct supplemental clarifications (measurements, tags, condition, authenticity) without changing lifecycle status or creating blockers, while preserving manager-to-assistant Q&A doubts (`AWAITING_INFO`), with all resolved items directly consumed by Gemini AI copywriting ([`docs/prds/PRD-product-detail-clarifications-hub.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-product-detail-clarifications-hub.md)).
26. **Intake Mandatory Pre-flight Identification Gate ("Identify Before Save"):** Client-side workflow gate on `/intake/` disabling the primary Save button (`#submitBtn`) by default until pre-flight AI identification (`#identifyBtn`) has been executed. Enforces appraisal benchmark and spec extraction while providing resilient fallback unlocking on network/timeout blips ([`docs/prds/PRD-intake-mandatory-identification-gate.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-intake-mandatory-identification-gate.md)).
27. **Photo Reordering in Intake and Detail Workspaces:** Intuitive, mobile-first photo reordering across both `/intake/` (hybrid button controls, cover promotion, and desktop HTML5 drag-and-drop with `DataTransfer` synchronization) and `/products/<pk>/` (manager-only asynchronous reorder endpoint with atomic DB ordering and live cover photo preview) ([`docs/prds/PRD-photo-reordering.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-photo-reordering.md)).
28. **Low-DPI Intake Photo Miniatures & Delete Controls Optimization:** High-density 3-column mobile preview grid (`grid-cols-3 sm:grid-cols-4 md:grid-cols-5`), high-contrast unambiguous delete buttons with white isolation ring, streamlined non-obstructive sequence badges, and a tap-to-inspect full-size lightbox modal tailored for low-DPI (1x) handheld warehouse scanners and compact smartphones ([`docs/prds/PRD-intake-low-dpi-miniatures.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-intake-low-dpi-miniatures.md)).
29. **Published Product Modifications & Platform Sync Tracking:** Full editing of published products (copywriting, price adjustments, supplemental clarifications, and staging photo upload/delete/reorder) coupled with an orthogonal synchronization engine (`needs_platform_sync`, `last_platform_synced_at`), workspace warning banners, 1-click sync clearance (`POST /products/<pk>/mark-synced/`), and dashboard sub-filtering (`?status=published&sync=out_of_sync`) ([`docs/prds/PRD-published-product-modifications-and-platform-sync.md`](file:///C:/Users/Jose/antigravity/epic-tesla/docs/prds/PRD-published-product-modifications-and-platform-sync.md)).

---

## 2. Tech Stack & Dependencies
- **Language / Runtime:** Python 3.13+
- **Framework:** Django 5.x
- **Database:** SQLite (default for low-ops development/staging; PostgreSQL compatible)
- **Database Backup & Disaster Recovery:** Native SQLite Online Backup API (`sqlite3.Connection.backup()`) + `gzip` compression + automated upload to OCI Object Storage bucket via `boto3` / `django-storages` with automated retention lifecycle pruning.
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
- **Bot & Abuse Protection:** Cloudflare Turnstile (`challenges.cloudflare.com/turnstile/v0/api.js` client widget + server-side verification against `/siteverify`).
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

# Automated Database Backup to OCI Object Storage
python manage.py backup_db                  # Daily automated or manual backup
python manage.py backup_db --local-only     # Save locally without cloud upload
python manage.py backup_db --dry-run        # Simulate backup and retention pruning

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
│   ├── models.py                 # Product, ProductImage, DatabaseBackupLog
│   ├── forms.py                  # ProductIntakeForm, ProductUpdateForm (localized labels/errors)
│   ├── urls.py
│   ├── permissions.py
│   ├── views.py                  # Localized messages and templates
│   ├── management/
│   │   └── commands/
│   │       ├── setup_roles.py
│   │       ├── compile_locales.py # Python-native PO to MO compiler using polib
│   │       └── backup_db.py       # Automated SQLite hot-backup command
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py         # Gemini Multimodal Vision integration
│   │   ├── image_service.py      # Pillow WebP conversion and optimization
│   │   ├── turnstile_service.py  # Cloudflare Turnstile token validation service
│   │   └── backup_service.py     # SQLite online backup, gzip compression & OCI upload service
│   ├── templates/
│   │   ├── registration/
│   │   │   └── login.html        # Localized login template with Turnstile widget
│   │   ├── admin/
│   │   │   └── login.html        # Django admin login with Turnstile challenge
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
│   ├── test_storage.py           # OCI Object Storage integration & upload tests
│   ├── test_marketplace_sites.py # Marketplace platforms and product listing links tests
│   ├── test_turnstile.py         # Cloudflare Turnstile challenge and verification tests
│   └── test_backup.py            # SQLite online backup, compression & retention tests
└── docs/
    ├── intent/
    │   └── secondhand-inventory-app.md
    ├── prds/
    │   ├── PRD-dynamic-ai-configuration.md
    │   ├── PRD-multilanguage-support.md
    │   ├── PRD-oracle-object-storage.md
    │   ├── PRD-pagination-and-search.md
    │   ├── PRD-user-management-django-admin.md
    │   ├── PRD-product-marketplace-sites-tracking.md
    │   ├── PRD-cloudflare-turnstile-login-protection.md
    │   └── PRD-sqlite-automated-cloud-backup.md
    └── SPEC.md
```

---

## 4.1 Code Style
- **Conventions:** Follow PEP 8 and Django conventions. Ruff is configured as the linter (`pyproject.toml`).
- **Typing:** Use Python 3.13+ type hints on service methods and helper utilities (e.g. `product: Product, language: str = "en" -> dict[str, str]`).
- **Localization:** Every user-facing string must be wrapped with `gettext_lazy as _` in models/forms and `gettext as _` in views. Templates must use `{% trans "..." %}`.
- **Example Snippet:**
```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class MarketplaceSite(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Site Name"))
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name=_("Slug"))
    base_url = models.URLField(max_length=255, blank=True, default="", verbose_name=_("Base URL"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Is Active"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))

    class Meta:
        ordering = ["order", "name"]
        verbose_name = _("Marketplace Site")
        verbose_name_plural = _("Marketplace Sites")

    def __str__(self) -> str:
        return self.name
```

---

## 4.2 Testing Strategy
- **Framework:** Django standard `django.test.TestCase` run via `.venv\Scripts\python.exe manage.py test`.
- **Location:** Project `tests/` directory with targeted modules (e.g. `tests/test_marketplace_sites.py`).
- **Coverage:**
  - Unit tests for models (validation, unique constraints, ordering, string representation).
  - Admin integration tests (permissions gating with `ManagerAdminSite`, inline rendering, actions).
  - View tests for product detail page (link rendering, form submission, CSRF, URL validation, unauthorized role checks).
  - Internationalization tests for Spanish catalog translation of new models, forms, and admin labels.
  - Zero mock-leaks: Mock external network calls (e.g. OCI, Gemini) so the test suite runs fully offline in seconds.

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
| `estimated_retail_price` | DecimalField | max_digits=10, decimal_places=2, null=True, blank=True | Estimated original retail price when brand new (MSRP, €) |
| `estimated_resale_price` | DecimalField | max_digits=10, decimal_places=2, null=True, blank=True | Estimated secondhand market resale value (€) |
| `batch_session` | ForeignKey(IntakeBatchSession) | null=True, blank=True, on_delete=SET_NULL, related_name='products' | Intake uploading session during which item was cataloged |
| `status` | CharField | max_length=20, default='draft', db_index=True | Lifecycle state: `draft`, `awaiting_info`, `ready`, `sold`, `blocked` |
| `is_sold` | BooleanField | default=False | Status indicating if item has been sold (synchronized with status='sold') |
| `sold_at` | DateTimeField | null=True, blank=True | Timestamp when marked as sold |
| `sold_channel_type` | CharField | max_length=20, blank=True, default="", choices=[in_store, marketplace, other], db_index=True | Channel through which product was sold |
| `sold_marketplace` | ForeignKey(MarketplaceSite) | null=True, blank=True, on_delete=SET_NULL, related_name='sold_products' | Marketplace platform where the sale occurred (if sold on marketplace) |
| `sold_channel_notes` | CharField | max_length=255, blank=True, default="" | Optional sale ticket #, buyer reference, or order notes |
| `is_deleted` | BooleanField | default=False, db_index=True | Whether the product is soft-deleted and moved to the erased trash category |
| `deleted_at` | DateTimeField | null=True, blank=True | Timestamp when moved to trash |
| `deleted_by` | ForeignKey(User) | null=True, blank=True, on_delete=SET_NULL, related_name='deleted_products' | Manager who moved the product to trash |
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

### 5.4 `MarketplaceSite`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique site identifier |
| `name` | CharField | max_length=100, unique=True | Marketplace name (e.g., Wallapop, Vinted, eBay, Milanuncios) |
| `slug` | SlugField | max_length=100, unique=True, blank=True | URL slug and programmatic identifier |
| `base_url` | URLField | max_length=255, blank=True, default="" | Base URL / portal home (e.g., https://es.wallapop.com) |
| `is_active` | BooleanField | default=True, db_index=True | Whether platform is active and displayed in listing link forms |
| `order` | PositiveIntegerField | default=0 | Display ordering in UI lists and forms |
| `created_at` | DateTimeField | auto_now_add=True | Platform creation timestamp |
| `updated_at` | DateTimeField | auto_now=True | Platform update timestamp |

### 5.5 `ProductListingLink`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique link identifier |
| `product` | ForeignKey(Product) | related_name='listing_links', on_delete=CASCADE | Parent staged product |
| `site` | ForeignKey(MarketplaceSite) | related_name='product_links', on_delete=CASCADE | Marketplace site platform |
| `url` | URLField | max_length=1000 | Direct external URL to the live listing ad |
| `is_active` | BooleanField | default=True | Whether the ad is currently active / published |
| `created_at` | DateTimeField | auto_now_add=True | Link creation timestamp |
| `updated_at` | DateTimeField | auto_now=True | Link modification timestamp |

Constraints: `UniqueConstraint(fields=['product', 'site'], name='unique_product_site_link')`

### 5.6 `ProductClarification`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique clarification question identifier |
| `product` | ForeignKey(Product) | related_name='clarifications', on_delete=CASCADE | Parent product under review |
| `category` | CharField | max_length=30, choices=[measurements, tag_composition, flaws_condition, material_authenticity, general] | Question category for structured classification |
| `is_direct_note` | BooleanField | default=False, db_index=True | Whether entry is a direct post-intake note (True) or a pending manager doubt (False) |
| `question` | TextField | max_length=2000, blank=False | Clarification question submitted by manager (or note summary for direct notes) |
| `asked_by` | ForeignKey(User) | null=True, blank=True, on_delete=SET_NULL, related_name='asked_clarifications' | User who posted the question or direct note |
| `answer` | TextField | max_length=3000, blank=True, default="" | Response submitted by assistant (or note content for direct notes) |
| `answered_by` | ForeignKey(User) | null=True, blank=True, on_delete=SET_NULL, related_name='answered_clarifications' | Assistant who answered the question (or author for direct notes) |
| `status` | CharField | max_length=20, default='pending', choices=[pending, resolved] | Status of the clarification request |
| `created_at` | DateTimeField | auto_now_add=True | Question submission timestamp |
| `answered_at` | DateTimeField | null=True, blank=True | Answer timestamp |

### 5.7 `DatabaseBackupLog`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique backup log identifier |
| `filename` | CharField | max_length=255 | Name of the generated backup archive (e.g. `db_20261014_030000.sqlite3.gz`) |
| `remote_path` | CharField | max_length=500 | Storage object path in OCI Object Storage bucket (or local path if local-only) |
| `file_size` | BigIntegerField | default=0 | Compressed backup archive size in bytes |
| `duration_seconds` | FloatField | default=0.0 | Total backup execution time in seconds |
| `status` | CharField | max_length=20, default='success', choices=[('success', 'Success'), ('failed', 'Failed')] | Execution outcome status |
| `trigger_type` | CharField | max_length=20, default='scheduled', choices=[('scheduled', 'Scheduled / CLI'), ('manual', 'Manual / Admin')] | How the backup was initiated |
| `triggered_by` | ForeignKey(User) | null=True, blank=True, on_delete=SET_NULL | User who initiated manual backup (null for scheduled/CLI runs) |
| `error_message` | TextField | blank=True, default="" | Detailed exception trace or error description if backup failed |
| `created_at` | DateTimeField | auto_now_add=True | Execution timestamp |

### 5.8 `PushSubscription`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique push subscription identifier |
| `user` | ForeignKey(User) | related_name='push_subscriptions', on_delete=CASCADE | Subscribed user (manager or assistant) |
| `endpoint` | URLField | max_length=1000, unique=True | Unique browser push service endpoint URL |
| `p256dh` | CharField | max_length=255 | Client public encryption key (Base64URL) |
| `auth` | CharField | max_length=255 | Client authentication secret (Base64URL) |
| `user_agent` | CharField | max_length=500, blank=True, default="" | Subscribing device user agent string |
| `is_active` | BooleanField | default=True, db_index=True | Whether subscription is active and deliverable |
| `created_at` | DateTimeField | auto_now_add=True | Subscription registration timestamp |
| `updated_at` | DateTimeField | auto_now=True | Last subscription update timestamp |

### 5.9 `ProductStatusLog`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique status change log identifier |
| `product` | ForeignKey(Product) | related_name='status_logs', on_delete=CASCADE | Parent product whose state changed |
| `from_status` | CharField | max_length=20, null=True, blank=True | Previous lifecycle status (null for initial creation) |
| `to_status` | CharField | max_length=20 | New lifecycle status |
| `changed_by` | ForeignKey(User) | null=True, blank=True, on_delete=SET_NULL | User who initiated the state change (null for automated system events) |
| `trigger` | CharField | max_length=50, blank=True, default="" | Machine trigger code (e.g. intake, clarification_opened, etc.) |
| `notes` | TextField | blank=True, default="" | Human-readable explanation or context |
| `created_at` | DateTimeField | auto_now_add=True, db_index=True | Exact timestamp of state change |

### 5.10 `IntakeBatchSession`
| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | AutoField | Primary Key | Unique intake batch session identifier |
| `assistant` | ForeignKey(User) | related_name='intake_batches', on_delete=CASCADE | Sourcing assistant who cataloged the items |
| `started_at` | DateTimeField | default=timezone.now | Timestamp of the first item intake in the batch |
| `last_activity_at` | DateTimeField | default=timezone.now, db_index=True | Timestamp of the most recent item intake in the batch |
| `product_count` | PositiveIntegerField | default=1 | Total count of products cataloged during this session |
| `is_notified` | BooleanField | default=False, db_index=True | Whether consolidated push alert has been dispatched to managers |
| `closed_at` | DateTimeField | null=True, blank=True | Timestamp when session was finalized and marked closed |
| `created_at` | DateTimeField | auto_now_add=True | Creation timestamp |
| `updated_at` | DateTimeField | auto_now=True | Modification timestamp |

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
  - **Marketplace Links Card:** Dedicated visual section listing all active marketplace platforms (Wallapop, Vinted, eBay, Milanuncios, etc.). For each platform, display live ad link (clickable in new tab), one-click copy URL button, and input/controls to add, edit, or delete external listing links.

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

### 6.7 Marketplace Sites & External Listing Tracking
- **Configurable Platforms (`MarketplaceSite`):**
  - Store managers can create, edit, sort, and deactivate marketplace sites via Django Administration (`/admin/`).
  - Fields include `name`, `slug`, `base_url`, `is_active`, and `order`.
  - Default sites seeded automatically: Wallapop, Vinted, Milanuncios, eBay.
  - Flexibility: Adding new platforms (e.g. Vestiaire Collective, Todocoleccion, Etsy) requires zero code modifications or schema migrations.
- **Product Listing Links (`ProductListingLink`):**
  - Connects a `Product` to a `MarketplaceSite` with the live ad `url`.
  - Enforces uniqueness per `(product, site)` tuple so each product has at most one live listing URL per platform.
  - Displayed on `/products/<pk>/` with platform badges, one-click copy buttons, and direct external navigation with `target="_blank" rel="noopener noreferrer"`.
  - Inline editing and link deletion directly on the product detail page and in Django admin.

### 6.8 Dashboard Marketplace Platform Filtering
- **Dynamic Platform Selector:**
  - Integrated into the `/dashboard/` filter toolbar adjacent to the status tabs and search bar.
  - Displays a dropdown selector containing "All Platforms" / "Todas las plataformas" (default) plus all platforms that currently have at least one product with an active published listing link (`product_links__is_active=True`).
  - Platforms with 0 published items are strictly omitted to eliminate empty query dead-ends.
  - Option labels display platform name and count of published products (e.g., `Wallapop (12)`).
- **Multi-Filter State Preservation:**
  - Filtering parameter: `?platform=<slug>` (e.g. `?platform=wallapop`).
  - Fully combinable with `status` (`all`, `active`, `sold`), search query (`q`), and pagination (`page`).
  - Switching status tabs preserves the active platform filter.
  - Submitting or clearing search queries preserves the active platform filter.
  - Pagination links (`query_string`) preserve the active platform filter.
- **Query Performance & Deduplication:**
  - Filter applied using `products.filter(listing_links__site__slug=platform_filter, listing_links__is_active=True).distinct()`.
  - Platforms with published counts fetched with a single optimized aggregate query:
    `MarketplaceSite.objects.filter(product_links__is_active=True).annotate(published_count=Count('product_links__product', filter=Q(product_links__is_active=True), distinct=True)).filter(published_count__gt=0).order_by('order', 'name')`.

### 6.9 Product Clarifications & Staging Feedback Loop
- **Lifecycle Progression:**
  - `DRAFT`: Initial status when an assistant finishes intake on `/intake/`.
  - `AWAITING_INFO`: Transitioned automatically when a manager posts a clarification question on `/products/<pk>/`.
  - `READY`: Transitioned when all open questions on a product are resolved, ready for AI copy generation and marketplace listing.
  - `SOLD`: Item marked as sold. Legacy `is_sold` column kept synchronized.
  - `BLOCKED`: Item flagged as unsellable, counterfeit, or irreparable. Excluded from active listing workflows.
- **Clarification Categories:**
  - Categorized chips on staging UI: *Medidas / Tallas*, *Etiqueta / Composición / Marca*, *Defectos / Desgaste / Manchas*, *Material / Autenticidad*, *Consulta general*.
- **Assistant Notification & Discovery:**
  - Global context processor `inventory.context_processors.notifications` computes `pending_clarifications_count`.
  - Top navigation bar renders a high-visibility badge: `❓ Dudas (X)` for authenticated assistants and managers.
  - Mobile intake view (`/intake/`) displays a subtle dismissible alert banner informing assistants when items await their feedback.
- **Mobile Answering Flow:**
  - Assistants navigate directly from the notification badge to the awaiting product or the filtered dashboard (`?status=awaiting_info`).
  - On `/products/<pk>/`, assistants can view pending questions, submit concise answers, and mark the question resolved.
  - Submitting the final pending answer prompts the manager: *"✨ Nuevos datos disponibles — Regenerar descripción con IA"*.

### 6.10 Cloudflare Turnstile Bot & Login Protection
- **Purpose & Architecture:**
  - Secures the public authentication view (`/login/` / `CustomLoginView`) against automated brute-force attacks and credential stuffing without degrading the experience of warehouse sourcing assistants and managers.
  - Privacy-first and frictionless: Evaluates browser telemetry and proof-of-work in the background without interactive image puzzle challenges.
- **Client-Side Widget Integration (`inventory/templates/registration/login.html`):**
  - API script loaded asynchronously: `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>` only when `TURNSTILE_ENABLED=True`.
  - Challenge container placed directly above the "Iniciar sesión" submit button:
    `<div class="cf-turnstile my-3" data-sitekey="{{ TURNSTILE_SITE_KEY }}" data-theme="light"></div>`.
  - Automatically populates the POST payload with the challenge token in field `cf-turnstile-response`.
- **Server Verification Service (`inventory/services/turnstile_service.py`):**
  - Dedicated service function `verify_turnstile_token(token: str, remote_ip: str | None = None) -> bool`.
  - Dispatches HTTP POST to Cloudflare's validation endpoint: `https://challenges.cloudflare.com/turnstile/v0/siteverify` with fields:
    - `secret`: `settings.TURNSTILE_SECRET_KEY`
    - `response`: `token` (`cf-turnstile-response`)
    - `remoteip`: optional client IP
  - Enforces a 5.0-second HTTP request timeout.
  - Fail-closed in production: Returns `False` on timeouts, network errors, or non-200 responses, preventing bot bypass.
- **Form & View Integration (`inventory/forms.py` & `inventory/views.py`):**
  - Subclass `TurnstileAuthenticationForm(AuthenticationForm)` overriding `clean()`:
    - Evaluates Turnstile token when `settings.TURNSTILE_ENABLED` is `True`.
    - Validates token before expensive password hashing to shield database and CPU from bot floods.
    - Raises localized `ValidationError`:
      - Missing token: `_("Please complete the security challenge.")` / `_("Por favor, completa la verificación de seguridad.")`
      - Invalid/expired token: `_("Security verification failed. Please try again.")` / `_("Error en la verificación de seguridad. Por favor, inténtalo de nuevo.")`
  - `CustomLoginView` adopts `authentication_form = TurnstileAuthenticationForm` and passes `TURNSTILE_SITE_KEY` and `TURNSTILE_ENABLED` in context.
- **Environment Configuration & Testing Isolation:**
  - Settings: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `TURNSTILE_ENABLED` (boolean, defaults `False` if keys omitted), `TURNSTILE_TIMEOUT` (default `5.0`).
  - Official Cloudflare test dummy keys supported for offline development and testing:
    - Always passes: Sitekey `1x00000000000000000000AA`, Secret `1x0000000000000000000000000000000AA`.
    - Always fails: Sitekey `2x00000000000000000000AB`, Secret `2x0000000000000000000000000000000AB`.
  - Unit tests mock external network requests so automated suites run 100% offline without latency.

### 6.11 SQLite Automated Cloud Backup & Disaster Recovery
- **Hot-Backup Mechanism (`inventory/services/backup_service.py`):**
  - Utilizes SQLite native online backup API (`sqlite3.Connection.backup()`).
  - Creates consistent point-in-time database snapshots without locking database tables, terminating active connections, or interrupting ongoing web requests.
- **Gzip Compression Pipeline:**
  - Compresses snapshots with standard library `gzip` (`.sqlite3.gz`), reducing bandwidth and storage usage by ~80-90%.
  - Fallback flag to preserve uncompressed `.sqlite3` when desired.
- **Cloud Upload to OCI Object Storage:**
  - Uploads compressed snapshots directly to the configured OCI Object Storage bucket using the project's S3-compatible backend (`OCIObjectStorage` / `boto3`).
  - Remote key layout: `backups/db/%Y/%m/db_%Y%m%d_%H%M%S.sqlite3.gz` (customizable via `DB_BACKUP_PREFIX`).
- **Retention Lifecycle Management:**
  - Automatically lists remote backups under the backup prefix after every successful backup run.
  - Prunes backups older than `DB_BACKUP_RETENTION_DAYS` (default 30 days) to prevent unbounded storage costs.
- **Audit Logging & Admin Visibility (`DatabaseBackupLogAdmin`):**
  - Logs execution metrics (`file_size`, `duration_seconds`, `status`, `error_message`, `trigger_type`, `remote_path`).
  - Registered in `ManagerAdminSite` restricted to managers.
  - Provides a "Crear copia de seguridad ahora" button / confirmation view allowing store managers to create an on-demand snapshot directly from Django administration.
- **Management Command CLI (`inventory/management/commands/backup_db.py`):**
  - Invoked via `python manage.py backup_db`.
  - Supports `--retention-days <N>`, `--local-only`, `--no-compress`, `--dry-run`, and `--quiet`.
### 6.12 Smart Intake Pre-flight: On-Demand Item Identification & Direct Pricing
- **On-Demand Pre-flight Trigger:**
  - Located on the mobile intake form (`/intake/`).
  - Gated button: "🔍 Identificar producto" (disabled when 0 photos are selected, active when ≥1 photo is chosen).
  - Triggers asynchronous JavaScript `fetch()` to `POST /inventory/intake/identify/` using `FormData` with client-selected image files and current `raw_note`.
  - Non-blocking: Loading indicator indicates *"Analizando fotos con IA..."*; form inputs and submit buttons remain responsive.
- **Vision Pre-flight Service (`inventory/services/ai_service.py`):**
  - Sends image bytes and notes to Gemini Vision (`gemini-2.5-flash`).
  - Structured output using `IntakePreflightSchema`:
    - `identified_title`: concise detected item title.
    - `category`: detected product category.
    - `detected_attributes`: list of visible attributes (color, materials, logos, cuts).
    - `missing_or_recommended_info`: list of actionable tips (e.g. *"Tag with size is not visible"*, *"Underside sole wear not shown"*).
    - `suggested_note`: recommended draft summary.
- **Advisory Guidance Banner & Actionable Shortcut:**
  - Renders above the `raw_note` field upon successful identification.
  - Highlights missing details as bulleted warning tips (amber/blue style).
  - Includes a one-click button: *"Añadir sugerencia a notas"* that appends or sets `suggested_note` into the `raw_note` textarea.
  - Advisory only: Does not prevent or block form submission.
- **Direct Sale Price Capture (`sale_price`):**
  - `ProductIntakeForm` includes an optional `sale_price` field in Euro (`€`).
  - When provided during intake, persisted directly to `Product.sale_price` upon form submission.

### 6.13 Intake Form State Management, Async Protection & Client-Side Validations
- **Form State Machine (`formState`):**
  - Managed in `inventory/templates/inventory/intake.html` via vanilla JavaScript.
  - Three discrete states: `'idle'`, `'identifying'`, and `'submitting'`.
  - **Pre-Flight Identification Mandatory Gate (`hasIdentified`):**
    - The Save button (`#submitBtn`) initializes in a disabled state (`disabled = true`, `opacity-50 cursor-not-allowed`) with helper text `#submitHelpText` informing the user: *"Identifica el producto con IA para habilitar el guardado"* / *"Identify product with AI first to enable saving"*.
    - `#identifyBtn` is enabled as soon as at least 1 photo is selected.
    - Tapping "Identificar producto" triggers analysis. Upon completion (success OR network/timeout error fallback), `hasIdentified = true` unlocks `#submitBtn` into full active emerald styling.
    - If individual photos are added or deleted while photos remain, `hasIdentified` stays true and Save remains enabled. If all photos are deleted, `hasIdentified` resets to false and the Save button is re-disabled.
    - Form submission handler blocks any synthetic or shortcut submits if `!hasIdentified`.
  - **`identifying` State:**
    - Triggered when the assistant clicks "Identificar producto".
    - Disables `#identifyBtn` and displays animated spinner with *"Analizando fotos con IA..."*.
    - Disables `#submitBtn` (`opacity-60 cursor-not-allowed`) with title tooltip: *"Espera a que finalice el análisis con IA..."*.
    - Locks `#dropZone` and `#imageInput` (`pointer-events-none opacity-70`) to prevent file selection changes mid-analysis.
    - Transitions back to `'idle'` upon fetch completion (success or error).
  - **`submitting` State:**
    - Triggered when the user submits valid intake data.
    - Locks `#submitBtn` immediately (`disabled`, `opacity-75 cursor-not-allowed`), displays spinner, and sets text to *"Guardando producto..."*.
    - Disables `#identifyBtn` and locks form fields (`pointer-events-none`) to prevent double-click duplicate submissions.
    - If client validation fails prior to submission, remains in `'idle'` and restores interactivity.
- **Double-Submit Prevention:**
  - Synchronous boolean latch `let isSubmitting = false;` guarantees that rapid successive taps or clicks dispatch at most one HTTP POST request.
  - Form submit handler returns early with `e.preventDefault()` if `isSubmitting` is already true.
- **Accessible Client-Side Validations (No Blocking Popups):**
  - Native `window.alert()` is completely removed from the intake workflow.
  - An inline banner `#intakeClientAlert` (`role="alert"`, `aria-live="polite"`) presents clean warning and error messages.
  - **Zero Photos Guard:** If the form is submitted with 0 photos, displays an inline message (*"Por favor, adjunta al menos una foto del producto antes de guardar."*), rings the dropzone in warning rose/amber, and scrolls into view.
  - **Max 10 Images Guard:** Selecting >10 images rejects the batch, resets the file input, and displays an inline warning banner (*"Has seleccionado más de 10 fotos. Por favor, selecciona un máximo de 10 imágenes."*).
  - **File Size Guard (10MB limit):** Inspects `file.size > 10 * 1024 * 1024` on each selected file before network transmission. If any file exceeds 10MB, cancels selection and displays an inline error with the file name and size in MB.
  - **Price Field Guard:** Validates `sale_price >= 0` and within `9999999.99` bounds.
- **Fail-Safe Recovery:**
  - If any asynchronous fetch or network error occurs, or if `beforeunload` or page reload is triggered, the state safely resets to `'idle'` with controls re-enabled so the user is never stranded.

### 6.14 Responsive Mobile Navigation Header & Collapsible Drawer
- **Responsive Breakpoint:**
  - Tailwind breakpoint `md:` (768px) divides mobile and desktop navigation.
- **Desktop Navigation (`≥ md` / ≥ 768px):**
  - Mobile menu toggle button `#mobile-menu-button` is hidden (`md:hidden`).
  - Standard horizontal navigation links (Intake, Dashboard, Doubts badge, Admin for managers) and language switcher form remain visible (`hidden md:flex`).
  - User greeting, role badge, and Sign Out button remain visible in the top bar.
- **Mobile Header Bar (`< md` / < 768px):**
  - Standard horizontal navigation and inline language switcher are hidden.
  - Top header bar declutters down to:
    1. App Brand logo (`📦 2ndHand Staging`).
    2. Compact urgent attention pill: displays `❓ {{ pending_clarifications_count }}` if unresolved clarifications exist.
    3. Mobile Menu Toggle Button (`#mobile-menu-button`): Minimum 44×44px touch target, displaying an animated SVG hamburger icon (☰) when closed and an "✕" close icon when open.
- **Mobile Drawer Panel (`#mobile-menu`):**
  - Positioned directly below the sticky header bar (`bg-white border-b border-slate-200 shadow-lg`).
  - Hidden by default (`hidden`).
  - Accessible vertical stack containing:
    1. **User Identity & Role Card:** Displays username and localized role badge (e.g. `👤 Conectado como: assistant (Asistente)`).
    2. **Primary Navigation Links:**
       - 📷 Nueva Entrada (`inventory:intake`): Styled with prominent accent background for fast field access.
       - 📊 Catálogo / Dashboard (`inventory:dashboard`).
       - ❓ Dudas pendientes (`inventory:dashboard?status=awaiting_info`): Includes item count badge if pending questions exist.
       - ⚙️ Panel de Administración (`/admin/`): Rendered conditionally for users with manager permissions.
    3. **Segmented Language Switcher:** Full-width bilingual switcher with clear flag icons and labels (`🇬🇧 English` / `🇪🇸 Español`) utilizing existing `set_language` form endpoints and CSRF tokens.
    4. **Sign Out Action:** Clean, separated logout button to prevent accidental clicks.
- **Accessibility & Interaction Contract:**
  - `#mobile-menu-button`: Attributes `aria-expanded="false"`, `aria-controls="mobile-menu"`, and localized `aria-label`.
  - Toggling updates `aria-expanded="true"` and swaps the inner SVG between hamburger and close icons.
  - Keyboard: Pressing `Escape` while `#mobile-menu` is open immediately closes the drawer and restores focus to `#mobile-menu-button`.
  - Click Outside: Clicking anywhere outside the mobile menu closes the drawer.
  - Viewport Resize: Resizing window above 768px automatically ensures the drawer resets to closed state.
  - Test Invariant Preservation: All existing navigation token IDs and classes (`badge-pending-clarifications`, `name="language"`, `value="en"`, `value="es"`, `"Sign Out"`) remain present in the DOM for automated testing compatibility.

### 6.15 Intake Photo Preview Management, Deletion & FileList Synchronization
- **Client-Side File State (`selectedFiles`):**
  - An internal JavaScript array `selectedFiles: File[]` maintains the live set of chosen image files on `/intake/`.
  - Incremental photo capture: Selecting or snapping additional photos appends valid images to `selectedFiles` up to the 10-image maximum, rather than erasing previously selected photos.
- **FileList Synchronization Engine (`syncFileInput`):**
  - Employs standard HTML5 `DataTransfer` to mutate `imageInput.files = dt.files` whenever photos are added or deleted.
  - Guarantees that form submission dispatches only the active, curated photo set.
- **Interactive Preview Card (`#previewGrid`):**
  - Aspect-square thumbnail container with rounded corners and border.
  - Top-left index badge `#N` (`bg-black/60 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full`).
  - Top-right accessible delete button ("✕"):
    - Touch target: Minimum 44×44px interactive tap area.
    - Visual button: 28×28px circular button with red/rose accent (`bg-rose-600 hover:bg-rose-700 text-white shadow-md`).
    - SVG cross icon (`stroke-width="2.5"`).
    - ARIA attributes: `type="button"`, `aria-label="Remove photo #N"`, `title="Remove photo"`.
- **Dynamic Deletion Recalibration:**
  - Tapping "✕" on photo `i`:
    - Prevents event bubbling (stops file picker dialog from opening).
    - Splices item `i` out of `selectedFiles`.
    - Synchronizes `imageInput.files` via `DataTransfer`.
    - Re-renders preview grid, updating remaining sequential badges (`#1`, `#2`, ...).
    - Updates counter text (`X / 10 selected`).
  - If all photos are deleted (`selectedFiles.length === 0`):
    - Resets `imageInput.value = ''`.
    - Hides `#previewContainer`.
    - Resets `#photoCount` to `0 / 10 selected`.
    - Disables `#identifyBtn` with *"Select photos first"*.
  - If photos remain (`selectedFiles.length > 0`):
    - Keeps `#identifyBtn` active.
- **Form State Guarding:**
  - During `'identifying'` or `'submitting'` states, all delete buttons are disabled (`pointer-events-none opacity-50 cursor-not-allowed`) to prevent data race conditions mid-operation.

### 6.16 Consolidated Intake Session Notifications ("Debounced Manager Push Alerts")
- **Problem & Rationale:**
  - Sourcing assistants frequently catalogue 10–20 products consecutively during a sourcing run.
  - Sending immediate Web Push notifications for each individual draft causes notification spam for store managers, leading to alert muting.
- **Debounced Sourcing Batch Engine (`IntakeBatchSession`):**
  - When a product is created in `DRAFT` status:
    - The immediate push notification in `notify_managers_on_product_lifecycle_save` is suppressed.
    - The system looks for an open `IntakeBatchSession` (`is_notified=False`) for the assistant within the sliding inactivity window (`INTAKE_SESSION_DEBOUNCE_MINUTES = 15`).
    - If found, increments `product_count` and updates `last_activity_at = timezone.now()`.
    - If not found or if the previous session exceeded the window, creates a new `IntakeBatchSession(product_count=1)`.
    - Links `product.batch_session = session`.
- **Consolidated Web Push Dispatch:**
  - Evaluates expired sessions where `is_notified=False` and `timezone.now() - last_activity_at >= 15 min`.
  - Dispatches a single consolidated Web Push notification to `ROLE_MANAGER`:
    - **Title:** `📦 Lote completado: %(count)s nuevos productos` (or `📦 Lote completado: %(count)s productos catalogados por %(assistant)s`).
    - **Body:** `Toca para revisar las prendas en el panel de staging.`
    - **URL:** `/dashboard/?status=draft`
    - **Tag:** `intake-batch-{session.id}`
  - Sets `session.is_notified = True` and `session.closed_at = timezone.now()`.
- **Zero-Broker Architecture & Execution Triggers:**
  - Operates without Celery or Redis.
  - Triggered via CLI management command: `python manage.py process_intake_batches` (with `--dry-run` support) for cron jobs or host system timers.
  - Opportunistic evaluation during intake uploads ensures prompt dispatch without external worker overhead.
- **Urgent Notification Isolation:**
  - Urgent clarification questions and answers (`ProductClarification`) and price pending transitions (`PRICE_PENDING`) bypass debouncing and remain instant real-time alerts.

### 6.17 Sale Channel Tracking & Commercial Attribution on Sold Products
- **Context & Operational Need:**
  - When marking products as sold, the business must record commercial attribution to know whether the transaction occurred physically in-store or online via a specific marketplace platform (e.g. Wallapop, Vinted, eBay).
- **Domain Modeling & Referential Safety:**
  - `Product` records `sold_channel_type` (`in_store`, `marketplace`, `other`), `sold_marketplace` (`ForeignKey(MarketplaceSite, on_delete=SET_NULL)`), and optional `sold_channel_notes`.
  - Referential safety: Deleting a `MarketplaceSite` never deletes associated products or sales history; foreign keys cascade to `NULL` (`SET_NULL`).
- **Interactive Staging Detail UI (`/products/<pk>/`):**
  - Checking "Mark Product as Sold" progressively reveals channel controls.
  - Quick-selection chips automatically highlight any marketplace where the product had active published listing links (`ProductListingLink`).
  - Displays prominent sold badge with channel, selling price, and date when viewing already-sold inventory.
- **Conditional Form Validation:**
  - `ProductUpdateForm` enforces channel selection when a product is marked sold. If `marketplace` is selected, an active marketplace platform is mandatory.
- **Dashboard Visibility & Multi-Channel Filtering (`/dashboard/`):**
  - Product cards in `?status=sold` render channel badges (e.g. `🏪 Tienda`, `🌐 Wallapop`).
  - Catalog dashboard provides sub-filtering by channel (`?status=sold&channel=in_store` vs `?status=sold&channel=marketplace`).
- **Audit Logging Synchronization:**
  - `ProductStatusLog` captures sales channel and selling price in historical timeline entries.

---

### 6.18 Product Soft-Delete, Archival & Erased Trash Category
1. **Catalog Visibility & Default Exclusions:**
   - In all default dashboard views (`status=all`, `active`, `draft`, `price_pending`, `ready`, `published`, `awaiting_info`, `sold`, `blocked`), products with `is_deleted=True` are strictly excluded from QuerySets.
   - All standard status aggregate counters calculate exclusively over non-deleted items (`is_deleted=False`).
   - A dedicated dashboard category `?status=erased` ("🗑️ Eliminados" / "🗑️ Trash") displays soft-deleted items with an isolated `erased_count` badge.
2. **Product Detail Trash Action & Confirmation Modal:**
   - In `/products/<pk>/`, non-deleted products provide a "Mover a papelera" / "Move to Trash" button restricted to `ROLE_MANAGER`.
   - Clicking triggers an accessible confirmation modal warning the manager that the item will be hidden from the active catalog but can be restored at any time.
   - Confirming submits a POST request to `/products/<pk>/delete/` which sets `is_deleted=True`, timestamps `deleted_at`, links `deleted_by`, and appends an audit log in `ProductStatusLog`.
3. **Erased Product Detail Inspection & Restoration:**
   - When an erased product is inspected, a prominent warning banner is displayed informing the user of its trash state.
   - A 1-click "Restaurar producto" / "Restore Product" button submits POST to `/products/<pk>/restore/`, which clears `is_deleted`, `deleted_at`, and `deleted_by`, logs the restoration in `ProductStatusLog`, and returns the product to its exact prior status in the active catalog.
4. **Search Isolation:**
   - Keyword search across active catalog views will never return erased items.
   - Searching within `?status=erased&q=...` searches specifically among erased products.

### 6.19 Product Detail Clarifications Hub ("Direct Notes & Q&A Doubts")
1. **Unified Left-Column Placement:**
   - Positioned in the Left Column (`lg:col-span-5`) of `/products/<pk>/` directly beneath "Preserved Intake Notes", establishing an all-in-one factual knowledge base alongside photos.
2. **Dual-Mode Clarifications Support:**
   - **Direct Clarification Notes (`is_direct_note=True`):** Immediate post-intake details (measurements, brand tags, materials, flaws) added by assistants or managers. Automatically created in `RESOLVED` status without changing product lifecycle status or triggering blocking states.
   - **Manager Doubt Inquiries (`is_direct_note=False`):** Formal Q&A doubts opened by store managers requesting missing data from assistants. Automatically transitions product status to `AWAITING_INFO` and notifies assistants.
3. **Role-Gated Controls:**
   - Both Sourcing Assistants and Store Managers can add direct clarification notes.
   - Only Store Managers can open pending doubt inquiries or dismiss/delete clarification items.
   - Both roles can answer pending doubts.
4. **AI Vision Copywriting Integration:**
   - All resolved clarifications (both direct notes and answered Q&As) are included in the Gemini AI prompt.
   - The unapplied clarifications callout (`has_unapplied_clarifications`) indicates when new notes are available for copy regeneration.

### 6.20 Photo Reordering in Intake and Detail Workspaces
1. **Intake Form Hybrid Reordering (`/intake/`):**
   - The in-memory array `selectedFiles` can be reordered by the assistant before cataloging.
   - Each preview card features accessible tap/click controls: `◀` Move Left, `▶` Move Right, and `⭐ Portada / Make Cover` (moves photo to position #1), alongside HTML5 drag-and-drop handles for desktop power users.
   - The primary cover position (#1) receives a prominent badge `⭐ #1 Portada` / `⭐ #1 Cover`.
   - Any reordering triggers `syncFileInput()` via `DataTransfer`, repopulating `<input type="file" name="images">` in the updated order so `request.FILES.getlist('images')` arrives pre-sorted for `ProductImage.order = 0, 1, 2...`.
   - Reordering preserves the pre-flight AI identification gate status (`hasIdentified`). Re-running AI identification passes the updated first 3 photos (`selectedFiles.slice(0, 3)`).
2. **Product Detail Workspace Reordering (`/products/<pk>/`):**
   - Restricted to Store Managers (`can_manage=True` / `@manager_required`).
   - The Photo Gallery card features an interactive thumbnail reordering mode with move left/right controls, 1-click "Set as Cover", and drag-and-drop reordering.
   - Persists changes asynchronously via `POST /products/<pk>/images/reorder/` with atomic database updates (`ProductImage.order = index`).
   - Automatically synchronizes the primary featured image `#mainImage` and displays an accessible toast notice.

## 7. AI Service Contract (`ai_service.py`)
```python
def generate_product_listing(
    product: Product,
    model_name: str | None = None,
    language: str = "en",
) -> dict[str, str]:
    """
    Sends product photos, preserved raw notes, and resolved Q&A clarifications
    to Google Gemini Multimodal Vision API. Uses dynamic prompt configuration from
    AIPromptConfiguration (with fallback to default instructions).
    """

def identify_intake_product(
    images_bytes: list[bytes],
    raw_note: str = "",
    language: str = "es",
) -> dict:
    """
    Analyzes uploaded product images during intake using Gemini Multimodal Vision API.
    Returns structured JSON with identified_title, category, detected_attributes,
    missing_or_recommended_info, and suggested_note.
    """
```
When `product.clarifications.filter(status='resolved').exists()` is true, the resolved Q&A pairs are formatted into the system/prompt context:
```text
ADDITIONAL VERIFIED DETAILS & CLARIFICATIONS:
- [Medidas / Tallas]: Ancho axila a axila 56cm, largo 68cm.
- [Material]: 100% Piel ovina legítima, forro en buen estado.
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
- **Marketplace Platforms Admin (`MarketplaceSiteAdmin`):**
  - Registered in `ManagerAdminSite` restricted to managers (`is_manager(user)`).
  - Enables managers to view, add, modify, reorder (`order`), and toggle `is_active` for supported marketplace sites.
  - List display includes platform name, slug, base URL, active status, order, and count of linked products.
  - Prepopulated `slug` field generated from `name`.
- **Product Listing Links Admin Inline (`ProductListingLinkInline`):**
  - Configured as a `TabularInline` within `ProductAdmin`.
  - Enables managers to view, add, and adjust marketplace links directly when editing a product in `/admin/`.

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
  - Validate all marketplace listing URLs with Django's `URLValidator` enforcing standard HTTP/HTTPS schemes.
  - Enforce uniqueness of listing links per product and marketplace site (`UniqueConstraint(fields=['product', 'site'])`).
  - Restrict marketplace platform configuration in `/admin/` strictly to managers.
  - Cascade delete listing links when a parent product is deleted.
  - Verify Cloudflare Turnstile token on login submissions when `TURNSTILE_ENABLED=True`.
  - Validate Turnstile token before evaluating password hash in `TurnstileAuthenticationForm.clean()` to protect CPU resources.
  - Mock Cloudflare `siteverify` network calls during automated tests so tests run 100% offline.
  - Use SQLite's native online backup API (`sqlite3.Connection.backup()`) to create consistent database snapshots without locking web requests.
  - Gzip compress database backups before uploading to OCI Object Storage to save bandwidth and storage.
  - Prune backups older than `DB_BACKUP_RETENTION_DAYS` (default 30 days) to prevent unbounded bucket growth.
  - Mock OCI cloud storage during automated backup tests so test suites run 100% offline.
- **Ask First:**
  - Choosing between OCI S3-compatible API keys vs Native OCI API Key (PEM) authentication.
  - Configuring bucket access permissions (public bucket vs presigned URLs).
  - Adding third-party translation cloud services (Google Cloud Translation API, DeepL).
  - Translating stored database records dynamically.
  - Implementing infinite scrolling or client-side JavaScript pagination instead of server-side pagination.
  - Changing authentication backend (e.g. SSO / OAuth).
  - Adding external LLM providers (e.g. OpenAI, Anthropic) beyond Google Gemini.
  - Allowing non-manager assistants to add or modify listing URLs on the product page.
  - Allowing multiple distinct links for the exact same marketplace platform on a single product.
  - Automated marketplace scraping or API syncing with external platforms.
  - Changing Cloudflare Turnstile failure policy (fail-closed vs fail-open) during third-party outages.
  - Extending Turnstile challenge protection to Django Admin login (`/admin/login/`).
  - Changing backup retention schedule (<14 days or >90 days).
  - Implementing database restoration directly from the Django admin web UI.
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
  - Allow non-manager assistants to create, modify, or delete `MarketplaceSite` records in Django Admin.
  - Store unsafe URL protocols (e.g. `javascript:`, `data:`) in marketplace links.
  - Hardcode marketplace platforms in application code without a database-backed `MarketplaceSite` model.
  - Expose `TURNSTILE_SECRET_KEY` in frontend templates, HTML comments, or client-side JavaScript.
  - Block local development or automated CI runners when Cloudflare Turnstile keys are omitted (clean bypass when `TURNSTILE_ENABLED=False`).
  - Execute raw filesystem copies of `db.sqlite3` during active web writes.
  - Block active user requests or interrupt web traffic during database backups.
  - Store uncompressed database dumps in public storage bucket folders.

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
19. Managers can add, edit, reorder, and deactivate `MarketplaceSite` records in `/admin/`.
20. Migrations pre-populate active default platforms: Wallapop, Vinted, Milanuncios, and eBay.
21. The product detail page (`/products/<pk>/`) displays all active marketplace platforms in a dedicated links card.
22. Saved marketplace links render with direct external link navigation (`target="_blank" rel="noopener noreferrer"`) and one-click copy buttons.
23. Managers can add, edit, or delete marketplace links directly on the product detail page and in Django admin (`ProductListingLinkInline`).
24. Database constraint prevents duplicate links for the same platform on a single product.
25. Deactivating a site in Django Admin immediately removes it from new link inputs while preserving existing links.
26. All new model fields, admin forms, and product page link elements display cleanly in Spanish (`es`) and English (`en`).
27. The dashboard displays a platform selector dropdown alongside status tabs and search bar.
28. Only marketplace platforms with at least 1 published product link are included in the selector.
29. Selecting a platform filters the product catalog to only items published on that platform (`listing_links__site__slug=platform, listing_links__is_active=True`).
30. Filter state is fully retained across status tabs ("Active", "Sold", "All"), keyword/date searches, and page navigation (Page 1, Page 2).
31. Selecting "All Platforms" returns to the unfiltered inventory catalog.
32. Managers can submit clarification questions categorized under *Medidas*, *Etiqueta*, *Defectos*, *Material*, or *General* on `/products/<pk>/`, transitioning product status to `awaiting_info`.
33. Global context processor injects `pending_clarifications_count`, displaying an attention badge `❓ Dudas (X)` in the top navigation bar whenever unanswered questions exist.
34. Assistants receive an alert banner on `/intake/` and can answer pending questions directly from mobile on `/products/<pk>/`.
35. When all questions for a product are resolved, status automatically updates to `ready` (or `draft`) and prompts the manager to re-generate the AI listing.
36. Resolved clarifications are automatically formatted and passed to the Gemini Multimodal Vision API, producing copy that incorporates verified dimensions and flaw disclosures.
37. The dashboard supports filtering by `status=awaiting_info` and `status=blocked` with dynamically scoped badge counters.
38. When `TURNSTILE_ENABLED=True`, the login page (`/login/`) renders the Cloudflare Turnstile challenge widget above the submit button.
39. Submitting valid user credentials alongside a valid Turnstile token successfully logs in assistants and managers.
40. Submitting login credentials with a missing or invalid Turnstile token rejects authentication with an actionable localized validation error message.
41. When `TURNSTILE_ENABLED=False` (default for local development and CI), user login operates smoothly without requiring Turnstile interaction or external network requests.
42. Dedicated automated test suite in `tests/test_turnstile.py` passes 100% offline without network calls or external flakiness.
43. Running `python manage.py backup_db` creates an uncorrupted, point-in-time snapshot of the SQLite database using SQLite's native online backup API without interrupting active web transactions.
44. The backup snapshot is gzip-compressed (`.sqlite3.gz`) and uploaded to the configured OCI Object Storage bucket under `backups/db/`.
45. Remote backups older than `DB_BACKUP_RETENTION_DAYS` (default 30 days) are automatically pruned from the cloud bucket.
46. Every backup execution creates an audit entry in `DatabaseBackupLog` with timestamp, file size, duration, status, remote path, and error message (if any).
47. Store managers can inspect backup logs and trigger an immediate on-demand backup directly from Django Administration.
48. Dedicated automated test suite in `tests/test_backup.py` passes 100% offline with zero external cloud dependencies.
49. On `/intake/`, the "Identificar producto" button remains disabled until at least one photo is chosen, and activates immediately upon image selection.
50. Clicking "Identificar producto" sends photos to `/inventory/intake/identify/` and displays a loading state while locking the submit button and image picker until the request completes, preventing race conditions.
51. When the vision API returns missing info recommendations (e.g. missing size tag or flaw inspection), an advisory guidance banner appears above the field notes listing the suggestions.
52. The assistant can click "Añadir sugerencia a notas" to populate the `raw_note` textarea with the AI's suggested note.
53. The intake form includes an optional `sale_price` (€) field that successfully saves the entered price to `product.sale_price`.
54. If the identification request fails, times out, or is skipped, the intake form can be submitted normally with zero disruption.
55. On `/intake/`, clicking "Identificar producto" transitions the form to `identifying` state, disabling the submit button and locking the dropzone until the request resolves.
56. Attempting to submit the intake form while AI identification is in flight is prevented with clear visual feedback.
57. When the user submits the form with valid data, the submit button is immediately disabled with a loading spinner and *"Guardando producto..."*, preventing duplicate POST requests on repeated taps or clicks.
58. Attempting to submit 0 photos displays an accessible inline alert banner (`#intakeClientAlert`) and highlights the dropzone without triggering native browser alerts.
59. Selecting more than 10 photos or any photo larger than 10MB triggers an accessible inline error banner with file details, clearing invalid inputs without calling `alert()`.
60. In the event of network failure or AI error during pre-flight identification, the form state automatically resets to `idle`, restoring submit and dropzone interactivity.
61. On viewports `< 768px`, the top navigation bar displays only the brand logo, optional doubts attention pill, and the 44×44px mobile menu button (`#mobile-menu-button`).
62. Clicking `#mobile-menu-button` opens the `#mobile-menu` drawer, toggling `aria-expanded` and switching the icon from hamburger (☰) to close (✕).
63. The `#mobile-menu` drawer contains accessible navigation links for Intake, Dashboard, Doubts, Admin (for managers), full-width language switcher, and Sign Out.
64. Pressing the `Escape` key or tapping outside the open `#mobile-menu` drawer immediately closes it and restores focus to the toggle button.
65. On desktop viewports (`≥ 768px`), `#mobile-menu-button` and `#mobile-menu` remain hidden, and the full horizontal navigation bar is displayed.
66. On `/intake/`, selecting photos renders thumbnail cards in `#previewGrid` with an individual delete button ("✕") on each image.
67. Tapping the delete button on an individual thumbnail removes only that photo, leaving other selected photos intact.
68. When a photo is deleted, remaining photos immediately re-index (`#1`, `#2`, ...), the photo counter updates (`X / 10 selected`), and `imageInput.files` synchronizes via `DataTransfer`.
69. If all photos are deleted, the preview grid hides, the counter resets to `0 / 10 selected`, and the "Identificar producto" button disables.
70. Delete buttons on thumbnail previews are disabled while AI pre-flight identification or form submission is in flight (`pointer-events-none`).

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
- **Marketplace Platforms Architecture:** Decoupled `MarketplaceSite` model managed in Django Admin instead of hardcoded choice fields to allow adding new marketplaces on the fly.
- **Listing Link Cardinality:** One link per marketplace platform per product via database `UniqueConstraint(fields=['product', 'site'])`.
- **URL Security:** Validation using Django `URLValidator` enforcing standard `http`/`https` protocols.
- **Dashboard Platform Selector Dynamic Population:** Only marketplace platforms with at least one active product link (`product_links__is_active=True`) appear in the dashboard selector to eliminate empty queries.
- **Multi-Filter State Preservation:** The `platform` query parameter composes symmetrically with `status`, `q`, and `page` parameters.
- **Platform Status Counters Scoping:** When a platform filter is active, status counters ("All", "Active", "Sold") dynamically update to reflect counts of products published on that specific platform.
- **Platform Dropdown Formatting:** Options display platform name and active published count, e.g. `Wallapop (12)`.
- **Platform Filter Submission:** Changing the dropdown immediately triggers form auto-submission (`onchange="this.form.submit()"`).
- **Product Lifecycle Model:** Discrete `status` enum (`draft`, `awaiting_info`, `ready`, `sold`, `blocked`) with backward-compatible synchronization with the legacy `is_sold` column.
- **Clarification Thread Architecture:** Dedicated `ProductClarification` model supporting single question + single answer per issue with structured category tags.
- **Notification Mechanism:** Lightweight global context processor querying unresolved questions count, avoiding polling or websocket overhead.
- **AI Prompt Enrichment:** Resolved Q&A details dynamically appended to Gemini Vision prompt without overwriting or mutating immutable original intake field notes (`raw_note`).
- **Publishing Gate:** Staging UI displays a caution banner if a manager attempts to link marketplaces while a product is in `awaiting_info` or `blocked` status.
- **Bot & Abuse Protection Engine:** Cloudflare Turnstile chosen over legacy reCAPTCHA for privacy preservation (no cross-site ad tracking) and frictionless experience (no distorted text or puzzle grids).
- **Form-Level Validation Hook:** Turnstile verification executed within `TurnstileAuthenticationForm.clean()` prior to database credential checks, protecting CPU resources against brute-force password hashing attacks.
- **Test Dummy Key Compatibility:** Support for Cloudflare's standard test sitekeys/secrets (`1x00000000000000000000AA` always pass, `2x00000000000000000000AB` always fail) to facilitate deterministic testing.
- **Fail-Secure Timeout Policy:** Default 5.0s network timeout with fail-closed behavior on timeout or third-party outage.
- **SQLite Online Backup Engine:** Native `sqlite3.Connection.backup()` chosen over raw filesystem copying to prevent torn pages, WAL inconsistencies, or database corruption during active concurrent web requests.
- **Compression Format:** Standard library `gzip` chosen for high compression ratio (~80-90% reduction) with zero external binary dependencies.
- **Bucket Infrastructure Reuse:** The existing OCI Object Storage bucket is reused under a dedicated prefix `backups/db/` to avoid separate bucket provisioning.
- **Default Retention Window:** Set to 30 days of daily backups (~30-50MB total bucket usage).
- **Intake Pre-flight Trigger:** On-demand button click ("Identificar producto") chosen over automatic scanning to conserve API quota and avoid unexpected layout jumping while selecting photos.
- **Intake Advisory Guidance:** Purely non-blocking advisory banner chosen over a modal or blocking gate, prioritizing field intake speed and uninterrupted assistant workflow.
- **Direct Intake Pricing:** Manual optional `sale_price` capture without automated AI pricing estimation during intake, keeping pricing responsibility with the user.
- **Intake Form State Machine:** Tri-state machine (`idle`, `identifying`, `submitting`) managed in client-side vanilla JavaScript to eliminate race conditions between AI pre-flight and intake submission.
- **Accessible Validation Alerts:** Browser `window.alert()` replaced with accessible inline DOM element (`role="alert"`, `aria-live="polite"`) matching Tailwind UI design system.
- **Responsive Mobile Navigation Breakpoint:** Tailwind `md:` (768px) selected to ensure phones and small tablets receive the simplified header and collapsible drawer, while desktop and laptop screens retain the full horizontal navigation.
- **Mobile Menu Architecture:** Lightweight vanilla JavaScript toggle with zero external dependencies, managing SVG icon switching, `aria-expanded`, keyboard `Escape`, and outside-click dismissal.
- **Urgent Doubts Badge on Mobile Bar:** Direct mobile bar pill `❓ (X)` displayed on the sticky header next to the hamburger button when pending doubts exist, ensuring immediate visibility for sourcing assistants without needing to open the menu.
- **Mobile Menu Panel Layout:** Sticky dropdown accordion positioned directly beneath the header (`bg-white border-b border-slate-200 shadow-lg`), leaving page content scrollable beneath with zero layout shift.
- **Intake Photo State Synchronization:** In-memory array `selectedFiles: File[]` synchronized to `imageInput.files` via standard HTML5 `DataTransfer` Web API, enabling single-photo deletion without full-batch re-upload.
- **Thumbnail Delete Button Accessibility:** Delete button placed on top-right of preview cards with minimum 44×44px touch target, WCAG-compliant contrast, and localized `aria-label="Remove photo #N"`.
- **Cumulative Photo Selection:** Smartphone camera snaps or repeated file picker selections append newly selected valid photos to `selectedFiles` up to the 10-photo maximum, enabling assistants to snap photos one-by-one.
- **Advisory Banner Persistence on Photo Deletion:** Deleting an individual photo retains any active AI identification advisory banner unless all photos are deleted, allowing assistants to manually re-run pre-flight check if desired.

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
4. **Product Page Link Modification Roles:**
   - On the product detail page (`/products/<pk>/`), should Field Sourcing Assistants (User A) be allowed to input and edit marketplace listing links, or should link editing be reserved strictly for Store Managers (User B)?
   - **Option A (Recommended):** Manager-only editing. Assistants have read-only visibility (clickable external links and copy buttons), matching the pricing and staging permission model.
   - **Option B:** Both Assistants and Managers can add and update listing links on `/products/<pk>/`.
   *Which role access model do you prefer for modifying listing links on the product page?*
5. **Multiple Listings Per Platform:**
   - Can a product ever have more than one listing link on the same marketplace platform (e.g. two separate Wallapop ads for different bundles or test listings)?
   - **Option A (Recommended):** Strict 1 link per platform per product (`UniqueConstraint`). Keeps the UI clean and simple.
   - **Option B:** Allow multiple links per platform per product (no uniqueness constraint on `(product, site)`).
   *Do you want to restrict to one link per platform per product, or allow multiple links per site?*
6. **Marketplace Link Deletion Behavior:**
   - When a manager wants to clear a link for a marketplace on the product detail page:
   - **Option A (Recommended):** Provide a direct "Remove" button or saving an empty input deletes the `ProductListingLink` record.
   - **Option B:** Provide an "Active/Inactive" toggle for each link so the URL is retained historically even if delisted.
   *How would you like removal or delisting to be handled on the product detail page?*
7. **Platform-Filtered Status Counters vs Overall Counters:**
   - When filtering by platform (e.g. `?platform=wallapop`):
   - **Option A (Recommended): Scoped to Selected Platform:** Status counters ("All (X)", "Active (Y)", "Sold (Z)") update to count products published on that specific platform.
   - **Option B: Global Catalog Counters:** Status counters always reflect total inventory counts regardless of the platform filter.
   *Which behavior do you prefer for status counters when a platform filter is active?*
8. **Dropdown Option Representation:**
   - In the platform selector dropdown:
   - **Option A (Recommended): Platform Name with Item Count:** e.g., `Todas las plataformas`, `Wallapop (12)`, `Vinted (8)`, `eBay (2)`.
   - **Option B: Platform Name Only:** e.g., `Todas las plataformas`, `Wallapop`, `Vinted`, `eBay`.
   *Which format do you prefer for the dropdown options?*
9. **Selector Form Submission Mechanism:**
   - When changing the platform selection in the dropdown:
   - **Option A (Recommended): Instant Auto-Submit (`onchange="this.form.submit()"`):** Selecting a platform immediately refreshes the filtered catalog without needing an extra click.
   - **Option B: Explicit "Filter" Button:** User selects the platform and must click a "Filter" button.
   *Which interaction do you prefer for triggering the filter?*
10. **Auto-Transition Status upon All Clarifications Resolved:**
   - When the assistant answers the final pending question on a product:
   - **Option A (Recommended): Auto-transition to `ready`:** Status becomes `ready` immediately and displays a prominent badge *"✨ Nuevos datos disponibles — Regenerar descripción con IA"*.
   - **Option B: Auto-transition to `draft`:** Status returns to `draft` for general manager review before manual promotion to `ready`.
   *Which status should the product automatically transition to once all clarifications are answered?*
11. **Assistant Clarification Reply Permissions:**
   - Can assistants close or delete clarification questions, or only submit answer text?
   - **Option A (Recommended): Answer submission only:** Assistants can submit or update their answer; only managers can delete questions or close them without an answer.
   - **Option B: Full resolution control:** Assistants can also mark questions as "No aplicable" / close without answering.
   *What level of control should assistants have over clarification requests?*
12. **Clarification Photo Attachment Support:**
   - Should assistants be able to attach an extra photo when answering a question (e.g. close-up of a care tag or tape measure on garment)?
   - **Option A (Recommended for MVP): Text-only responses first:** Assistants respond with text (e.g. measurements or composition); photo uploads can be added in a future phase.
   - **Option B: Include optional photo upload in MVP:** Include an optional file input in the clarification answer form that creates an additional `ProductImage`.
   *Do you prefer text-only answers for the MVP, or optional photo uploads immediately?*
13. **Turnstile Failure & Timeout Policy (Fail-Closed vs Fail-Open):**
   - If Cloudflare's `/siteverify` endpoint times out (e.g. 5.0 seconds) or returns an HTTP 5xx error:
   - **Option A (Recommended - Fail-Closed):** Reject the login attempt and show a retry message (*"Security verification failed. Please try again."*). Maximizes security against automated attack bursts during service degradation.
   - **Option B (Fail-Open):** Log a warning and allow the authentication to proceed checking username and password alone. Maximizes system availability if Cloudflare experiences an outage.
   *Which policy do you prefer when the Cloudflare verification service is unreachable?*
14. **Scope of Turnstile Protection:**
   - Which authentication endpoints should require Turnstile verification?
   - **Option A (Recommended - Public Login `/login/` only):** Protect the public-facing staff login interface. Django Admin (`/admin/login/`) remains protected by Django's native authentication and manager group permission gating.
   - **Option B (Public Login + Django Admin Login):** Also apply Turnstile challenge to the Django admin login interface.
   *Should Turnstile protect only `/login/` or also `/admin/login/`?*
15. **Widget Theme & Appearance:**
   - How should the Turnstile widget be rendered visually?
   - **Option A (Recommended - Fixed Light Theme):** Explicit `data-theme="light"` to match the clean white card login container in Tailwind CSS.
   - **Option B (Auto Theme):** `data-theme="auto"` respecting client operating system dark/light mode preferences.
   *Which widget theme do you prefer for the login screen?*
16. **Backup Retention Window:**
   - How long should daily automated backups be retained in the OCI Object Storage bucket before being automatically pruned?
   - **Option A (Recommended — 30 Days):** Retain daily backups for 30 days. Keeps bucket storage minimal (~30-50MB total) while offering a full month of restore points.
   - **Option B (60 Days):** Retain daily backups for 60 days.
   - **Option C (Grandfather-Father-Son / GFS):** Keep daily backups for 7 days, weekly snapshots for 4 weeks, and monthly snapshots for 12 months.
   *Which retention policy do you prefer for database backups?*
17. **On-Demand Admin Backup Execution UX:**
   - How should store managers trigger manual database backups in Django Administration?
   - **Option A (Recommended — Admin Top Bar Button & Confirmation View):** A prominent button "Crear copia de seguridad ahora" on the `DatabaseBackupLog` changelist leading to an intermediate confirmation page that executes the backup and flashes status feedback.
   - **Option B (Changelist Action Dropdown):** Selected as a batch action from the actions dropdown on `DatabaseBackupLog`.
   *Which admin interaction pattern do you prefer for on-demand backups?*
18. **Notification on Backup Failure:**
   - If an automated scheduled backup encounters a network or storage failure:
   - **Option A (Recommended — Django Admin Warning Banner + Log):** When the most recent backup status is `failed`, render an alert banner in Django Administration informing managers to inspect the error log.
   - **Option B (Silent Audit Log Only):** Record failure in `DatabaseBackupLog` without displaying a banner in the Django admin UI.
   *Which failure notification behavior do you prefer?*
19. **Suggested Notes Application Behavior:**
   - When the assistant clicks "Añadir sugerencia a notas" / "Apply suggestion to notes":
   - **Option A (Recommended): Append / Smart Fill:** If `raw_note` is empty, fills it with `suggested_note`. If notes already exist, appends the suggestion on a new line preserving the assistant's original input.
   - **Option B: Replace:** Overwrites `raw_note` completely with `suggested_note`.
   *Which behavior do you prefer when applying the suggested note?*
20. **Intake Vision Analysis Photo Sample Size:**
   - How many photos should be sent to Gemini during the intake pre-flight check?
   - **Option A (Recommended — First 3 Photos):** Send up to 3 photos (e.g. front, tag, back). Keeps payload tiny, API response ≤2.0s on mobile data, and token consumption low.
   - **Option B (All Selected Photos, up to 10):** Send all selected images. More exhaustive check, but increases mobile payload size and API latency (~3-5s).
   *Do you prefer a fast sample (up to 3 photos) or analyzing all selected images?*
21. **Action on Oversized Files (>10MB):**
   - When an assistant selects multiple photos where only 1 exceeds the 10MB limit:
   - **Option A (Recommended — Reject Entire Selection):** Reject the selection, reset the file input to empty, and alert the user which file was oversized so they can re-select valid photos.
   - **Option B (Filter & Keep Valid Photos):** Automatically filter out the oversized photo and keep the remaining valid photos in the input selection using `DataTransfer`.
   *Which behavior do you prefer when one or more selected photos exceed 10MB?*
22. **Dropzone Error Ring Reset Timing:**
   - When the dropzone is highlighted in red/rose due to zero-photo submission attempt:
   - **Option A (Recommended — Auto-clear on File Selection):** Automatically remove the error ring and alert banner as soon as the user selects at least one valid image.
   - **Option B (Dismiss Button):** Keep the banner visible with an explicit dismiss "✕" button until closed by user or re-submitted.
   *Which dismiss interaction do you prefer for the validation error banner?*
23. **Urgent Doubts Badge on Mobile Bar:**
    - When pending clarification questions exist (`pending_clarifications_count > 0`), should a compact doubts pill appear directly on the mobile top bar next to the sandwich button, or only inside the expanded drawer?
    - **Option A (Recommended — Direct Mobile Bar Pill):** Display a compact pill `❓ (X)` directly on the sticky mobile top bar, so assistants instantly notice urgent manager questions without opening the menu.
    - **Option B (Inside Menu Only):** Keep the top bar strictly minimal (only logo + sandwich button), showing the doubts count only when the menu drawer is opened.
    *Which placement do you prefer for urgent doubt notifications on mobile?*
24. **Drawer Style & Animation (Accordion Dropdown vs Slide-in Offcanvas):**
    - How should the mobile navigation menu open?
    - **Option A (Recommended — Sticky Dropdown Accordion):** Expands cleanly directly beneath the header with vertical flow (`bg-white border-b border-slate-200 shadow-lg`). Zero layout shift, extremely reliable on mobile browsers, and leaves page content scrollable beneath.
    - **Option B (Slide-in Offcanvas Drawer from Right):** Slides in from the right edge with a dark backdrop overlay covering the entire screen.
    *Which mobile menu transition style do you prefer?*
25. **Multi-Step Camera Capture Behavior (Cumulative Append vs Batch Replacement):**
    - When an assistant takes a picture with their smartphone camera or opens the file picker again while photos are already selected:
    - **Option A (Recommended — Cumulative Append up to 10):** Newly selected valid photos are appended to the existing list (`selectedFiles`) up to the maximum 10-photo limit. Enables taking photos one by one or in small bursts.
    - **Option B (Batch Replacement):** Selecting new photos replaces the entire previous selection with the new files.
    *Which behavior do you prefer when selecting additional photos?*
26. **AI Pre-flight Advisory State on Photo Deletion:**
    - If the assistant ran "Identificar producto" (pre-flight AI check) and an advisory card is displayed, what should happen if they delete one of the photos?
    - **Option A (Recommended — Retain Advisory Banner):** Keep the advisory banner and suggested notes visible (only clearing if all photos are deleted), allowing the assistant to manually re-run "Identificar producto" if desired.
    - **Option B (Auto-Clear Advisory on Any Deletion):** Immediately dismiss the AI suggestion card whenever any photo is removed to ensure suggestions strictly reflect the current photo subset.
    *Which behavior do you prefer for the AI advisory card when a photo is deleted?*
27. **Compilation & Docker Image Build Footer Format & Metadata Scope:**
    - How should the build compilation information be presented in the bottom footer?
    - **Option A (Recommended — UTC Timestamp + Git Commit SHA + Environment Badge):** Displays `Build: YYYY-MM-DD HH:MM UTC • Commit: [sha] • [PROD/DEV]` (localized in Spanish as `Compilación: YYYY-MM-DD HH:MM UTC • Commit: [sha] • [PROD/DEV]`). Prevents server/browser timezone drift and gives definitive identification for bug reports.
    - **Option B (Timestamp Only):** Displays strictly `Build: YYYY-MM-DD HH:MM UTC` without commit hash or environment badge.
    - **Option C (Localized Browser Timezone via JS):** Uses client JavaScript to convert UTC build time into the client device's local timezone.
    *Which footer display format and scope do you prefer?*
    - **Decision:** Option A approved — UTC Timestamp + Git Commit SHA + Environment Badge.
28. **Intake AI Valuation & Reference Pricing Adoption Pattern:**
    - When Gemini preflight identification estimates the original new price (MSRP) and used resale value during intake:
    - **Option A (Recommended — Reference Badges + Optional "Usar reventa" Button):** Render the estimated new and used prices as benchmark pills in the AI advisory card and beneath the target sale price input, with a one-click button "Usar precio estimado" to populate the sale price field if desired without overwriting without explicit assistant consent.
    - **Option B (Auto-populate Sale Price):** Automatically set the `sale_price` input value to `estimated_resale_price` if `sale_price` is currently empty.
    *Which adoption pattern do you prefer for the intake sale price?*
    - **Decision:** Option A approved — Reference Badges + Optional "Usar reventa" Button.
29. **Consolidated Intake Session Notification Inactivity Window & Dispatch Architecture:**
    - How should sourcing uploads be grouped to eliminate manager notification fatigue?
    - **Option A (Recommended & Selected): Database-Backed Debounced Sourcing Session Engine (`IntakeBatchSession`):**
      Consecutive uploads by the same assistant within a sliding 15-minute inactivity window are bundled into one session. When 15 minutes pass without new uploads, a single consolidated Web Push notification is dispatched to store managers (`📦 Lote completado: [X] nuevos productos catalogados por [Asistente]`), pointing to `/dashboard/?status=draft`. Processed via `python manage.py process_intake_batches` and intake request hooks without external message brokers (no Celery, no Redis).
    - **Option B (Manual "Finish Batch" Button on Mobile):** Assistant must remember to tap a "Finish Sourcing Session" button after uploading their items.
    *Which session completion pattern do you prefer?*
    - **Decision:** Option A approved — Database-backed 15-minute sliding inactivity debounce window.
30. **Sale Channel Selection UX & Legacy Product Handling:**
    - When a manager marks a product as sold on `/products/<pk>/`:
    - **Option A (Recommended — Explicit Selection with Quick-Picks):** The channel dropdown defaults to an unselected placeholder (`--- Seleccionar canal ---`) requiring deliberate choice. If the product was previously published to one or more marketplace links (e.g. Wallapop, Vinted), one-click shortcut pills are rendered above the dropdown alongside a quick "Tienda física" button. Legacy sold products with no recorded channel display `-` and are not broken.
    - **Option B (Auto-Default to In-Store):** The channel dropdown automatically selects "Tienda física / In-Store" by default unless changed.
    *Which sale channel interaction pattern do you prefer?*

31. **Product Soft-Delete, Archival & "Erased" Trash Category Architecture:**
    - When a product is removed or disabled on `/products/<pk>/`:
    - **Option A (Recommended & Selected — Non-Destructive Soft-Delete with Restore Capability):**
      Add `is_deleted`, `deleted_at`, and `deleted_by` to `Product`. Hide erased items by default from all active catalog tabs and counters. Isolate them in a dedicated `?status=erased` ("🗑️ Eliminados") dashboard tab. Provide an accessible confirmation modal in `/products/<pk>/` to move to trash, and a 1-click "Restaurar producto" button to restore back to its previous lifecycle status (`draft`, `ready`, `sold`, etc.) without loss of photos, pricing, or audit history. Restricted to `ROLE_MANAGER`.
    - **Option B (Permanent Hard Deletion):**
      Permanently delete the database row and call OCI Object Storage to purge image files. Risk of irreversible data loss, broken audit history, and orphaned references.
    *Which archival and deletion architecture do you prefer?*
    - **Decision:** Option A approved — Non-destructive soft-delete with dedicated erased category and full restoration capability.

32. **Product Detail Clarifications Hub Architecture & Placement:**
    - How should product clarifications and post-intake supplemental notes be supported and positioned in `/products/<pk>/`?
    - **Option A (Recommended & Selected — Dual-Mode Hub in Left Column):**
      Support both **Direct Clarifications/Notes** (instant info discovered after intake by assistants or managers without blocking status) and **Manager Doubt Inquiries** (Q&A transitioning to `AWAITING_INFO`), located in the Left Column directly below "Preserved Intake Notes" to form a cohesive factual details hub.
    - **Option B (Direct Clarifications Only):** Only allow notes without pending Q&A doubt state.
    - **Option C (Q&A Doubts Only):** Only allow manager questions requiring assistant answers.
    *Decision:* Option A approved — Dual-mode clarifications hub (direct notes + Q&A) in the left column below intake notes with role-appropriate permissions.

33. **Intake Mandatory Pre-flight Identification Gate Architecture:**
    - How should the Save button gating and pre-flight identification enforcement behave on `/intake/`?
    - **Option A (Recommended & Selected — Resilient UI Gate with Identification Requirement):**
      Initialize the Save button (`#submitBtn`) as disabled with guidance text requiring AI identification before saving. Once identification is executed (or in the event of an API error/timeout fallback), unlock the Save button. Retain the unlocked state if photos are modified, but reset to disabled if all photos are removed.
    - **Option B (Strict Success Only):**
      Require `data.success === true` before enabling the Save button, permanently blocking saving if the API is offline.
    *Decision:* Option A approved — Resilient UI gate unlocking on identification attempt with offline fallback and photo reset tracking.

34. **Photo Reordering Architecture & Usability Standards:**
    - How should photo reordering operate across the intake form (`/intake/`) and the product detail workspace (`/products/<pk>/`)?
    - **Option A (Recommended & Selected — Hybrid Mobile-First Controls + Drag-and-Drop):**
      - In `/intake/`: Client-side hybrid controls (Move Left/Right, 1-click "Set as Cover", and HTML5 drag-and-drop) with immediate `DataTransfer` synchronization and identification gate preservation.
      - In `/products/<pk>/`: Manager-only asynchronous reorder endpoint (`POST /products/<pk>/images/reorder/`) with atomic database ordering, live featured image updates, and accessible toast notifications.
    - **Option B (Drag-and-Drop Only):** Rely exclusively on mouse drag-and-drop, risking touch gesture collisions with vertical scrolling on mobile devices.
    - **Option C (Buttons Only):** Restrict to button clicks without desktop drag-and-drop capability.
    *Decision:* Option A approved — Hybrid mobile-first controls with drag-and-drop, manager-only detail permissions, and identification gate preservation.

35. **Low-DPI Intake Photo Miniatures & Delete Controls Architecture:**
    - How should photo previews and controls be adapted for low-DPI (1x) handheld warehouse terminals and compact smartphones?
    - **Option A (Recommended & Selected — High-Density Responsive Grid + High-Contrast Controls + Lightbox Modal):**
      - Grid: 3 columns on compact mobile (`grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 sm:gap-2.5`), scaling down cards to ~90px–115px to prevent vertical page hijacking.
      - Delete Button: High-contrast rose badge with bold SVG cross and white isolation ring (`ring-1 ring-white/90`) to eliminate subpixel blur and background blending on 1x DPI screens.
      - Inspection: Full-screen lightbox modal (`#imagePreviewModal`) accessible on thumbnail click to verify sharpness and item details before saving.
    - **Option B (Maintain 2-Column Grid with Larger Text):** Retain `grid-cols-2`, continuing to take up most of the mobile viewport with large thumbnail cards.
    *Decision:* Option A approved — High-density 3-column mobile grid with high-contrast delete button and tap-to-inspect lightbox modal.

36. **Published Product Modifications & Platform Synchronization Architecture:**
    - How should modifications to already-published products be handled across the state machine, photo pipeline, and external marketplace listings?
    - **Option A (Recommended & Selected — Orthogonal Sync State + Detail Photo Management + 1-Click Clearance):**
      - Retain primary lifecycle status `PUBLISHED` (`🚀 Publicado`) so items remain active in catalog statistics, external URL navigation, and sales attribution.
      - Add orthogonal boolean `needs_platform_sync` (indexed) and `last_platform_synced_at` to `Product`.
      - Automatically flag `needs_platform_sync = True` whenever price, title, description, photos, or clarifications change on a published product.
      - Enable full photo management (uploading new photos with Pillow WebP compression up to 10 photos, deleting photos, and reordering) in `/products/<pk>/`.
      - Render workspace alert banner and 1-click clearance button (`POST /products/<pk>/mark-synced/`) with audit trail logging.
      - Add dashboard sub-filter `?status=published&sync=out_of_sync` with live badge count.
    - **Option B (New Primary State `UPDATE_PENDING`):**
      - Transition the product out of `PUBLISHED` into a separate state, hiding it from published listings until verified. Risk of broken external ad tracking and incorrect inventory counts.
    *Decision:* Option A approved — Orthogonal sync state with detail photo management, 1-click clearance, and dashboard sub-filter.


37. **Detail View Photo Upload Component System Architecture:**
    - How should the photo upload interface in `/products/<pk>/` be structured to achieve parity with the Intake flow?
    - **Option A (Recommended & Selected — Unified Mobile-First Intake Component Parity):**
      - Implement the exact Intake upload architecture in `/products/<pk>/`:
        - Dashed drag-and-drop dropzone (`#detailDropZone`) with desktop dragover feedback.
        - Dual mobile-first action buttons: dedicated camera capture (`#detailCameraInput` with `capture="environment"`) and multi-file gallery selection (`#detailImageInput`).
        - Client-side Canvas downscaling to max 2560px WebP (quality 0.82) with hardware EXIF orientation handling, preventing Android LMK memory crashes and speeding up uploads.
        - Live thumbnail preview queue (`#detailPendingGrid`) with index badges, remove buttons (✕), and clear-all action before submitting.
        - Dynamic capacity counter (`X available / max 10`) dynamically respecting already-attached photos ($10 - N_{existing}$).
        - Submission via `DataTransfer` form integration into existing `product_upload_images_view` with defense-in-depth server validation.
    - **Option B (Maintain Minimal Native File Input):**
      - Keep the simple `<input type="file">` selector. Lacks mobile camera shortcut, client-side compression, drag-and-drop, and preview queue.
    *Decision:* Option A approved — Unified mobile-first photo upload component system with drag-and-drop, dual camera/gallery actions, client-side WebP compression, and pre-upload preview queue.

38. **Out-of-Sync Product Web Push Notification Architecture:**
    - How should store managers be alerted when a published product undergoes post-publication modifications and becomes out of sync?
    - **Option A (Recommended & Selected — Real-Time Web Push to Managers with Edge-Transition Guard):**
      - Track _initial_needs_platform_sync in Product.__init__ and compute _previous_needs_platform_sync in Product.save().
      - Hook into the post_save lifecycle signal receiver (notify_managers_on_product_lifecycle_save).
      - Fire strictly on edge transition (False -> True) on non-deleted products:
        - Dispatch encrypted Web Push via VAPID and pywebpush to all active Store Managers (ROLE_MANAGER + active staff/superusers).
        - Payload:
          - Title: _('⚠️ Product Out of Sync: %(title)s') % {'title': product.display_title}
          - Body: _('Modifications detected on published item. External platform listings require updating.')
          - URL: /products/<pk>/ (deep link straight to product detail with warning banner and 1-click clearance button).
          - Tag: product-out-of-sync-<pk> (collapses successive notifications for the same product in OS drawer).
      - Suppress notification on subsequent edits while needs_platform_sync is already True (anti-spam).
      - Suppress notification on platform sync clearance (mark_platform_synced()).
      - Gate with PUSH_NOTIFICATIONS_LIVE_SIGNALS for environment and test isolation.
    - **Option B (Poll-Based Periodic Batch Notification):**
      - Debounce out-of-sync products into a cron batch similar to intake sessions. Delays critical pricing/photo discrepancy alerts by 15+ minutes.
    - **Option C (Email Notification Only):**
      - Send emails instead of Web Push. Higher latency, lower mobile immediacy.
    *Decision:* Option A approved — Real-time Web Push notification to Store Managers on False -> True edge transitions with anti-spam suppression, deep-linking, and PUSH_NOTIFICATIONS_LIVE_SIGNALS gating.

