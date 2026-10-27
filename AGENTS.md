# AGENTS.md — Project Guidelines & Engineering Workflow

This file defines the mandatory operational rules, development workflow, architectural patterns, and coding conventions for AI agents working on **2ndHand Staging Hub** (`epic-tesla`).

---

## 1. Critical Rules & Hard Boundaries

1. **MANDATORY: Ask User Before Merging into `master`**
   - **All merges into `master` MUST be explicitly asked to and approved by the user before execution.**
   - Never run `git merge` into `master`, fast-forward `master`, or push directly to `origin/master` without first presenting the completed branch status and receiving explicit confirmation from the user.
   - *Why:* Pushing or merging to `master` triggers GitHub Actions CI/CD (`.github/workflows/ci.yml`) to build and publish `ghcr.io/saert3311/2nd-hand-manager:latest`, which **Watchtower** automatically pulls and deploys to the live production server.
2. **All Work Starts on a Dedicated Branch**
   - Always create or switch to a descriptive feature or bugfix branch (`feat/<feature-slug>` or `fix/<bug-slug>`) before editing code or documentation.
   - Note: An active multi-phase branch `feature/marketplace-storefront` also exists in the repository; verify which branch is appropriate if working on public storefront tasks.
3. **Never Commit Secrets or Environment Files**
   - Never stage or commit `.env`, API keys, VAPID private keys, OCI secret keys, or SQLite backup archives. Only document new configuration variables in `.env.example` with safe placeholder values.
4. **Non-Destructive Inventory & Database Operations**
   - Use soft-deletion (`product.soft_delete()` / `is_deleted=True`) for removing products from active staging. Never drop database tables, delete migrations, or wipe media/backups without explicit user authorization.
5. **Zero-Failure Quality Gate**
   - Every task and branch must pass 100% of the automated test suite (`manage.py test`), Django system checks (`manage.py check`), translation compilation (`manage.py compile_locales`), and Ruff linting (`ruff check .`) with zero errors or warnings before requesting a merge.
6. **Low-DPI & Narrow Android Mobile Viewports (OPPO A74 Baseline)**
   - Every page and UI component must render cleanly without horizontal overflow, clipped controls, or squished text on low-DPI and narrow Android mobile viewports such as the **OPPO A74** (`360×800` standard CSS viewport and `320×711` with Android display zoom / low effective DPI), not just `390×844` iPhone viewports.

---

## 2. How We Work (End-to-End Feature Workflow)

We follow a disciplined, spec-driven, incremental engineering workflow across phases:

### Step 1: Branch Creation
- Branch off `master` using `git checkout -b feat/<feature-slug>` (or `fix/<bug-slug>`).

### Step 2: Specification & PRD (`docs/prds/` & `SPEC.md`)
- For new features or phases, author a Product Requirements Document in `docs/prds/PRD-<feature-slug>.md` (and optionally refine raw concepts in `docs/ideas/<feature-slug>.md`).
- Update `SPEC.md` to record the new phase's objectives, domain model schema, URL routes, and architectural invariants.
- Commit as: `docs(prd): add PRD and specification for <feature>`

### Step 3: Implementation Plan & Task Breakdown (`tasks/plan.md` & `tasks/todo.md`)
- Append the technical design plan to `tasks/plan.md`.
- Break the implementation into thin, verifiable vertical tasks with explicit acceptance criteria, verification commands, and a final phase checkpoint in `tasks/todo.md`.
- Commit as: `docs(plan): add implementation plan and tasks for <feature>`

### Step 4: Incremental Vertical-Slice Implementation
Deliver code in atomic, logically scoped commits following Conventional Commits:
1. **Domain Layer & Admin (`inventory/models.py`, `inventory/migrations/`, `inventory/admin.py`)**:
   - Define models, `TextChoices` enums, indexes, validators, and lifecycle/audit methods.
   - Generate and apply migrations (`makemigrations` & `migrate`).
   - Register fields, custom badge columns, filters, and bulk actions in `manager_admin_site` (`inventory/admin.py`).
   - Commit as: `feat(inventory): ...`
2. **Service & Form Layer (`inventory/services/`, `inventory/forms.py`)**:
   - Encapsulate business logic, external API calls (Gemini AI, OCI S3, Web Push, Turnstile), and image processing inside `inventory/services/`.
   - Implement conditional form validation in `clean()` on `ProductIntakeForm` / `ProductUpdateForm`.
   - Commit as: `feat(inventory): ...`
3. **Views & Routing (`inventory/views.py`, `inventory/urls.py`, `inventory/permissions.py`)**:
   - Protect all views with `@login_required` and manager-only operations with `@manager_required`.
   - Enforce POST-only execution on all state-mutating endpoints.
   - Commit as: `feat(views): ...`
4. **Templates & UI (`inventory/templates/`)**:
   - Build responsive, mobile-first Tailwind CSS interfaces in `intake.html`, `dashboard.html`, `product_detail.html`, and `base.html`.
   - Commit as: `feat(ui): ...` and `feat(dashboard): ...`

### Step 5: Bilingual Localization, Tests & Changelog
- **Translations**: Wrap all user-facing strings in Python (`gettext_lazy as _` / `gettext as _`) and templates (`{% trans %}` / `{% blocktrans %}`). Add Spanish translations to `locale/es/LC_MESSAGES/django.po` and compile to `django.mo` using `python manage.py compile_locales`.
- **Automated Tests**: Create or extend `tests/test_<feature>.py` covering models, services, forms, view permissions (manager vs. assistant), dashboard filtering/scoping, admin integration, and ES/EN localization.
- **Changelog & Task Tracking**: Document the changes in `CHANGELOG.md` and check off completed items (`[x]`) in `tasks/todo.md`.
- Commit as: `feat(<scope>): add test suite, bilingual translations, and changelog for <feature>`

### Step 6: Release Bump & User Merge Approval Gate
- When preparing a release:
  1. Bump the default `APP_VERSION` in `config/settings.py` (and `Dockerfile` if applicable).
  2. Seal the version section in `CHANGELOG.md` (`## [X.Y.Z] - YYYY-MM-DD`).
  3. Commit as: `docs(release): bump version to X.Y.Z and seal changelog for <feature>`
- **STOP AND ASK THE USER** before merging into `master`, creating git tags (`vX.Y.Z`), or pushing `master` to `origin`.

---

## 3. Project Architecture & Domain Reference

### User Roles & Access Control (`inventory/permissions.py`)
- **Sourcing Assistant (`assistants` group / `is_assistant`)**:
  - Uses the mobile-first intake flow (`/intake/`) to capture photos, record field notes, trigger AI pre-flight identification & valuation benchmarks, and resolve clarification doubts (`❓ Dudas`).
  - Has read-only visibility into active catalog items; cannot modify staging fields, prices, sales channels, or soft-delete items, and cannot view erased (`is_deleted=True`) items or access Django Admin.
- **Store Manager (`managers` group, `is_staff`, or `is_superuser` / `is_manager`)**:
  - Full access to the staging dashboard (`/dashboard/`), product detail workspace (`/products/<pk>/`), AI copywriting generation, pricing, sale channel attribution, marketplace link management, clarification creation, soft-delete/restore (`?status=erased`), photo ZIP downloads, and the custom Django Admin (`manager_admin_site`).

### Product Lifecycle State Machine (`inventory/models.py`)
- **`ProductStatus` States**:
  - `DRAFT` (`draft`): Missing AI/listing description (`not ai_description`).
  - `PRICE_PENDING` (`price_pending`): Has title and description, but no `sale_price` (or `<= 0.00`).
  - `READY` (`ready`): Has title, description, and `sale_price > 0`, with no active `ProductListingLink`.
  - `PUBLISHED` (`published`): Automatically assigned when at least one active `ProductListingLink` exists.
  - `AWAITING_INFO` (`awaiting_info`): Automatically assigned when an unresolved `ProductClarification` (`status=PENDING`) exists.
  - `SOLD` (`sold`): Marked as sold (`is_sold=True`) with required `sold_channel_type` (`in_store`, `marketplace`, or `other`), optional `sold_marketplace` (`MarketplaceSite`), and `sold_channel_notes`.
  - `BLOCKED` (`blocked`): Manually blocked from publication.
- **Soft-Delete & Archival (`is_deleted`, `deleted_at`, `deleted_by`)**:
  - Orthogonal to `status`: `product.soft_delete(user)` sets `is_deleted=True` while preserving `product.status` so `product.restore(user)` restores the item to its exact prior lifecycle state.
  - Soft-deleted products are strictly excluded from all default dashboard tabs (`all`, `active`, `draft`, `ready`, `sold`, etc.), standard tab counters, and global searches, appearing only under `?status=erased` (`🗑️ Eliminados` / `🗑️ Trash`).
- **Immutable Audit Trail (`ProductStatusLog`)**:
  - Every status change, sale channel transition, clarification event, and soft-delete/restore operation creates an immutable `ProductStatusLog` entry.
  - Acting users are resolved automatically via thread-safe `CurrentUserMiddleware` (`inventory/middleware.py` using `contextvars`).
  - Cascade deletions of `Product` use `ProductQuerySet` and `_deleting_product_pks` context tracking to prevent orphan status logs from violating SQLite foreign key constraints.

### Key Services (`inventory/services/`)
- `ai_service.py`: Google Gemini Multimodal Vision (`google-genai`) for intake pre-flight identification, retail/resale valuation appraisal (`IntakePreflightSchema`), and full listing copywriting generation (`AIPromptConfiguration` DB-backed prompts with hardcoded fallbacks).
- `image_service.py`: Pillow validation and in-memory conversion to `.webp` (max 2560px dimension, `MAX_IMAGE_PIXELS = 100_000_000` for 48MP/50MP smartphone sensors), stripping EXIF metadata and neutralizing polyglot/decompression bomb payloads.
- `intake_batch_service.py`: Groups consecutive assistant draft uploads into a debounced `IntakeBatchSession` (default 15-minute window) to send a single consolidated Web Push notification to managers (`process_intake_batches` command).
- `push_service.py`: VAPID Web Push dispatcher (`pywebpush`) with automatic pruning of expired (`404`/`410`) `PushSubscription` endpoints.
- `storage.py` & `backup_service.py`: Oracle Cloud Infrastructure (OCI) S3-compatible object storage backend and zero-downtime SQLite online backup (`sqlite3.Connection.backup()` + gzip + retention pruning).
- `version_service.py`: Resolves build timestamp, commit SHA, version, and environment for the global footer (`#footer-build-time`, `#footer-build-sha`, `#footer-build-env`).

---

## 4. Technical Conventions & Known Gotchas

### Python & Django Conventions
- **Linter & Formatting**: Enforced via Ruff (`pyproject.toml`: `target-version = "py313"`, `line-length = 120`, rules `E, F, I, W`).
- **Query Optimization**: Always prevent N+1 queries in views and admin by pairing foreign keys and reverse relations with `select_related()` (e.g., `created_by`, `sold_marketplace`, `deleted_by`) and `prefetch_related()` (e.g., `images`, `listing_links__marketplace_site`, `clarifications`, `status_logs`). Compute dashboard badge counts in a single `.aggregate()` query using conditional `Count("id", filter=Q(...))`.
- **Storage in Tests**: `config/settings.py` automatically switches `STORAGES['default']` to `django.core.files.storage.InMemoryStorage` when `IS_TESTING` is true, ensuring fast, disk-free test execution.
- **URL Validation**: Always validate external marketplace URLs with `HTTP_URL_VALIDATOR` (`schemes=["http", "https"]`) to block `javascript:` or `data:` URI injection.

### Frontend, Mobile UX & Accessibility Conventions
- **Low-DPI & Narrow Mobile Viewport Rule (OPPO A74 `360×800` & `320×711` Support)**:
  - Do not assume a `390px` (iPhone) minimum mobile width. Devices like the **OPPO A74** operate at a `360×800` CSS viewport by default and drop to `320×711` (or `320×640`) when Android Display Size / Font Scaling or low-DPI modes are active.
  - **Zero Horizontal Overflow**: All views must maintain `document.documentElement.scrollWidth <= document.documentElement.clientWidth` down to `320px`–`360px` viewport widths.
  - **Fluid Flex/Grid & Spanish Text Expansion**: Always pair flex/grid children with `min-w-0`, `flex-wrap`, and `break-words` so longer Spanish labels (e.g., dual camera/gallery buttons, status pills, price benchmark badges) wrap gracefully instead of clipping off-screen. Use responsive compact padding (`px-3 sm:px-6`, `p-3.5 sm:p-6`) on narrow mobile screens.
  - **Low-DPI Visual Clarity**: Avoid faint hairline borders and low-contrast muted text (`text-slate-400`) that blur on lower-DPI panels; enforce WCAG 2.1 AA contrast (`>= 4.5:1`) and distinct surface borders (`border-slate-200` / `border-slate-300`).
  - **Playwright Viewport Matrix**: Include `360×800` (OPPO A74 mobile) and `320×711` (low-DPI / zoomed mobile) in automated Playwright responsive tests alongside `390×844`, `768×1024`, and `1440×900`.
- **HTML5 `<input type="number">` Localization Gotcha**:
  - Under the Spanish locale (`es`), Django formats decimals with a comma (`35,50`), which causes browsers to sanitize `<input type="number">` values to `""` (wiping the price in the UI and on form submit).
  - **Rule**: Always `{% load l10n %}` and apply `|unlocalize` on numeric form input values (e.g., `value="{{ form.sale_price.value|unlocalize|default:'' }}"`).
- **Mobile Input Font Size (iOS Safari Auto-Zoom Prevention)**:
  - All interactive `<input>`, `<select>`, and `<textarea>` elements must render at `>= 16px` (`text-base sm:text-sm`) on viewports `<= 640px` to prevent involuntary iOS Safari page zooming.
- **No Sub-12px Micro-Fonts & Anti-Apilación**:
  - Avoid arbitrary micro-font classes (`text-[10px]`, `text-[11px]`); use `text-xs sm:text-sm` or larger.
  - Keep the dashboard status navigation bar in a single-line horizontal scroll rail (`overflow-x-auto flex-nowrap whitespace-nowrap`) decoupled from search/filter controls so tabs never stack vertically (*apilación*).
- **Android Mobile Camera Capture & Memory Safety**:
  - Trigger `<input type="file" capture="environment">` via native `<label for="cameraInput">` elements rather than synthetic JS `.click()`, and call `stopPropagation()` on file inputs so clicks do not bubble up to `#dropZone` and open the gallery instead of the camera.
  - Downscale captured photos client-side via Canvas to max 2560px WebP before upload to prevent Android Low Memory Killer (LMK) browser tab crashes.
- **Accessible Feedback Over Native Dialogs**:
  - Never use blocking browser `alert()` or `confirm()`. Use inline accessible banners (`role="alert"`, `aria-live="polite"`) or semantic modal dialogs (`role="dialog"`, `aria-modal="true"`).

---

## 5. Standard Commands Reference (Windows PowerShell)

Always use the workspace virtual environment (`.venv\Scripts\...`) when running commands:

```powershell
# 1. Lint & Style Check (Ruff)
.venv\Scripts\ruff.exe check .

# 2. Django System Check
.venv\Scripts\python.exe manage.py check

# 3. Run Full Automated Test Suite
.venv\Scripts\python.exe manage.py test

# 4. Run a Specific Test Module
.venv\Scripts\python.exe manage.py test tests.test_product_soft_delete

# 5. Create & Apply Database Migrations
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate

# 6. Compile Bilingual Translation Catalogs (.po -> .mo via polib)
.venv\Scripts\python.exe manage.py compile_locales

# 7. Process Debounced Intake Notification Batches
.venv\Scripts\python.exe manage.py process_intake_batches

# 8. Local SQLite Backup Verification
.venv\Scripts\python.exe manage.py backup_db --local-only
```
