# Product Requirements Document (PRD) & Specification
# Product State Change History & Audit Trail ("When and Who Made It")

## 1. Objective

Provide complete operational visibility and traceability for the secondhand product lifecycle in the **2ndHand Staging Hub** by tracking **every product state change**, recording **when** it occurred, **who** made the change (or if it was automated by the system), and the **context/trigger** behind the transition.

### 1.1 Business Problems Solved
1. **Lack of State Attribution:** When a product moves from `draft` to `price_pending`, `ready`, `published`, `awaiting_info`, `blocked`, or `sold`, there is currently no historical log recording which team member (Assistant vs. Manager) or automated event triggered the change.
2. **Accountability for Missing Info & Doubts:** If an item is placed in `awaiting_info` or `blocked`, staff cannot see the historical timeline of who blocked it, who answered doubts, and when it became ready.
3. **Auditing Sales & Unsold Status:** When an item is marked as `sold` or reverted back to `ready`/`published`, store management needs an immutable audit trail showing who marked it sold, at what timestamp, and if a price adjustment was recorded.
4. **Staging Workflow Insights:** Managers cannot currently analyze how long products spend in each state (e.g., duration between intake and price assignment, or time waiting for clarification answers).

---

## 2. Tech Stack & Architecture Context

- **Backend:** Python 3.13, Django 5.1+
- **Database:** SQLite (local/dev) / PostgreSQL (production) with Django ORM
- **Authentication:** Django built-in auth (`User`, `assistants`, `managers` groups)
- **Frontend:** Django Templates, Tailwind CSS, Vanilla JavaScript
- **Internationalization (i18n):** Bilingual support (Spanish `es` default, English `en`) via Django `gettext`
- **Testing:** Django `TestCase`, Playwright E2E browser tests

---

## 3. Executable Commands

- **Run Dev Server:** `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
- **Create Migrations:** `.venv\Scripts\python.exe manage.py makemigrations inventory`
- **Apply Migrations:** `.venv\Scripts\python.exe manage.py migrate`
- **Run Targeted Tests:** `.venv\Scripts\python.exe manage.py test tests.test_status_history`
- **Run Full Test Suite:** `.venv\Scripts\python.exe manage.py test`
- **Run Code Linter:** `.venv\Scripts\ruff.exe check .`
- **Compile Locales:** `.venv\Scripts\python.exe manage.py compile_locales`

---

## 4. Project Structure & Affected Modules

```
inventory/
├── models.py                     # Add ProductStatusLog model; hook into Product state transition tracking
├── middleware.py                 # (Optional/Recommended) CurrentUserMiddleware for seamless request user capturing
├── admin.py                      # Register ProductStatusLogAdmin (read-only audit log) and ProductStatusLogInline
├── views.py                      # Expose status log timeline in product_detail_view
├── templates/inventory/
│   ├── product_detail.html       # Status History & Audit Trail timeline card
│   └── partials/
│       └── status_timeline.html  # Component rendering chronological state changes
├── migrations/
│   └── 0014_productstatuslog.py  # Migration for ProductStatusLog model
locale/
├── es/LC_MESSAGES/django.po      # Spanish translations for audit log labels and triggers
└── en/LC_MESSAGES/django.po      # English source strings
tests/
└── test_status_history.py        # Comprehensive unit & integration tests for status tracking
```

---

## 5. Domain Model Specification

### 5.1 `ProductStatusLog` Model

An append-only audit trail model tracking every lifecycle state transition for a `Product`:

```python
class ProductStatusLog(models.Model):
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="status_logs",
        verbose_name=_("Product"),
        help_text=_("The product whose state changed")
    )
    from_status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        null=True,
        blank=True,
        verbose_name=_("From Status"),
        help_text=_("Previous lifecycle status (null for initial creation)")
    )
    to_status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        verbose_name=_("To Status"),
        help_text=_("New lifecycle status")
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="status_changes",
        verbose_name=_("Changed By"),
        help_text=_("User who initiated the change (null if automated system event)")
    )
    trigger = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Trigger / Reason"),
        help_text=_("Machine code for event trigger (e.g. intake, price_update, marketplace_link, doubt_resolved)")
    )
    notes = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Notes / Description"),
        help_text=_("Human-readable explanation or contextual details (e.g. 'Sold for €45.00')")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Timestamp"),
        help_text=_("Exact time the state change was recorded")
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Product Status Log")
        verbose_name_plural = _("Product Status Logs")
```

### 5.2 Transition Attribution Mechanics

To ensure 100% reliable tracking of **who** made the change:
1. **Request User Context Capture:**
   - Implement `CurrentUserMiddleware` using Python's `contextvars` (thread-safe, async-safe) to capture `request.user` during web requests.
   - Alternatively/additionally, allow explicit passing via `product.save(changed_by=user, trigger="...")` or `product._current_user = user`.
2. **Initial Intake Logging:**
   - When an assistant catalogs a new product in `/intake/`, log initial state transition `None -> DRAFT` (or `None -> READY` if pre-priced) with `changed_by=request.user`, trigger=`intake`.
3. **AI Description Generation & Price Updates:**
   - When a manager saves listing copy, transitions to `PRICE_PENDING` or `READY` record `changed_by=manager`, trigger=`staging_update`.
4. **Clarification Doubts Workflow:**
   - Opening a clarification transitions `READY/DRAFT -> AWAITING_INFO` with `changed_by=manager`, trigger=`clarification_opened`.
   - Answering the last clarification transitions `AWAITING_INFO -> READY` with `changed_by=assistant`, trigger=`clarification_resolved`.
5. **Marketplace Publishing & Link Modification:**
   - Adding a marketplace link transitions `READY -> PUBLISHED` with `changed_by=manager`, trigger=`marketplace_link_added`.
   - Removing all links transitions `PUBLISHED -> READY` with `changed_by=manager`, trigger=`marketplace_link_removed`.
6. **Commercial Sales Tracking:**
   - Marking item as sold transitions `* -> SOLD` with `changed_by=manager`, trigger=`marked_sold`.
   - Reverting an unsold item transitions `SOLD -> READY` with `changed_by=manager`, trigger=`reverted_unsold`.
7. **Administrative & Direct Edits:**
   - Changes via Django Admin capture the logged-in staff member.

---

## 6. User Interface & Display Specification

### 6.1 Product Detail Staging View (`/products/<pk>/`)
- Add a new card: **"Historial de Estados / Lifecycle Audit Trail"** on the product detail page.
- Layout:
  - Vertical timeline showing each transition from newest to oldest.
  - Visual badges for `from_status` $\to$ `to_status` using existing status colors (amber, emerald, blue, rose, purple, slate).
  - User attribution: Avatar/icon, username (e.g., *"Modificado por: Juan (Asistente)"* or *"Sistema / Automático"*).
  - Formatted relative & absolute timestamp (e.g., *"19 oct 2026, 16:45"*).
  - Contextual trigger note (e.g., *"Enlace añadido: Wallapop"*, *"Respondida aclaración: Medidas"*).
- Responsive mobile & desktop layout adhering to existing Tailwind design standards.

### 6.2 Django Administration (`/admin/inventory/productstatuslog/`)
- Read-only audit log:
  - List display: `product`, `from_status`, `to_status`, `changed_by`, `trigger`, `created_at`.
  - Filters: `to_status`, `from_status`, `trigger`, `created_at`, `changed_by`.
  - Search fields: `product__id`, `product__ai_title`, `changed_by__username`, `notes`.
  - Inline view: `ProductStatusLogInline` inside `ProductAdmin` (read-only table of state changes).

---

## 7. Code Style & Conventions

- Follow PEP 8 and project Ruff configuration.
- Use Django translation functions `gettext_lazy as _` for all model verbose names, help texts, and template strings.
- Never allow `ProductStatusLog` entries to be updated or deleted by standard staff users (immutability).

Example logging helper:
```python
def log_status_change(product, from_status, to_status, user=None, trigger="", notes=""):
    """Creates an immutable audit log entry for a product lifecycle status change."""
    if from_status == to_status and product.pk:
        return None
    return ProductStatusLog.objects.create(
        product=product,
        from_status=from_status,
        to_status=to_status,
        changed_by=user if user and user.is_authenticated else None,
        trigger=trigger,
        notes=notes
    )
```

---

## 8. Testing Strategy

1. **Unit Tests (`tests/test_status_history.py`):**
   - Test log creation on product intake creation (`None -> DRAFT`).
   - Test log creation on price update (`DRAFT -> PRICE_PENDING -> READY`).
   - Test log creation on clarification question creation and answering (`READY -> AWAITING_INFO -> READY`).
   - Test log creation on marketplace link addition and deletion (`READY -> PUBLISHED -> READY`).
   - Test log creation on mark sold and unsold (`* -> SOLD -> READY`).
   - Test `changed_by` correctly records the active user vs. System (`None`).
2. **Security & Immutability Tests:**
   - Verify non-superusers cannot delete or alter historical status log records.
3. **Integration & View Tests:**
   - Verify timeline renders accurately on `/products/<pk>/` under both Spanish and English locales.
   - Verify Django admin inline and changelist render with zero N+1 queries.

---

## 9. Boundaries

### 9.1 Always Do
- Record previous status (`from_status`) and new status (`to_status`).
- Record UTC timestamp with Django timezone support (`created_at`).
- Gracefully handle `user=None` for background tasks, management commands, or automated system signals.
- Maintain full backward compatibility with existing tests and workflows.

### 9.2 Ask First
- Changing existing `ProductStatus` choice values or database column names.
- Adding third-party packages (e.g., `django-simple-history` vs. native lightweight `ProductStatusLog` model).

### 9.3 Never Do
- Never block product saving if status logging encounters a non-fatal error.
- Never allow historical log rows to be edited or overwritten via standard UI forms.
- Never hardcode user-facing strings without Django `gettext` localization.

---

## 10. Success Criteria

- [ ] Every status change on any `Product` automatically generates a `ProductStatusLog` record.
- [ ] Log records capture exact timestamp (`created_at`), previous status, new status, and the acting user (`changed_by`).
- [ ] Status change timeline is visually accessible on the product detail page (`/products/<pk>/`) in both desktop and mobile viewports.
- [ ] Django admin provides a searchable, filterable read-only changelist and product inline for status logs.
- [ ] 100% test coverage for state transition logging with 0 regressions across the 299 existing tests.

---

## 11. Open Questions for Human Review

1. **Lightweight Native Model vs. Third-Party Library:**
   - **Option A (Recommended — Native `ProductStatusLog` model):** Build a purpose-built, zero-dependency model tracking strictly lifecycle state changes (`status`), user, timestamp, and trigger note. Minimal database overhead, perfectly tailored to the staging UI timeline.
   - **Option B (Third-party package like `django-simple-history`):** Tracks full diffs of every single field on `Product`. Provides total field auditing, but creates large shadow tables, adds external dependencies, and requires custom parsing to extract status-only timelines.
   *Recommendation: Option A.*

2. **User Context Propagation Technique:**
   - **Option A (Recommended — Dual Strategy):** A thread-safe `CurrentUserMiddleware` using Python 3.13 `contextvars` to automatically capture `request.user` during web requests, plus explicit `changed_by` parameter support on model methods (`mark_as_sold`, `sync_lifecycle_status`). This guarantees user attribution even when signals trigger status updates.
   - **Option B (Strict Explicit Passing):** Pass `user` explicitly through all views and service functions down to `product.save()`. Does not require middleware, but requires modifying multiple method signatures across views and signals.
   *Recommendation: Option A.*

3. **Product Detail View Placement:**
   - **Option A (Recommended — Dedicated Timeline Card in Right/Left Column):** Render a collapsible or compact timeline card on `/products/<pk>/` displaying the last 5 state changes with a "Ver historial completo" toggle.
   - **Option B (Admin Only):** Expose status history exclusively in Django Administration (`/admin/`), keeping the product staging detail page focused strictly on listing copy and marketplace links.
   *Recommendation: Option A (valuable for assistants and managers directly in the app).*
