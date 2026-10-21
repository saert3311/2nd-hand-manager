# Product Requirements Document (PRD) & Specification
# Consolidated Intake Session Notifications ("Debounced Manager Push Alerts")

## 1. Objective & Problem Statement

### 1.1 Problem Statement & Operational Background
Currently, store managers receive an instant Web Push notification every time a product is created in draft status (`📦 New Intake in Draft: <title>`) via `notify_managers_on_product_lifecycle_save` in `inventory/models.py`. 

During physical sourcing sessions, an assistant typically intakes a batch of 10 to 20 garments or items consecutively over a 20–40 minute period. This results in:
1. **Severe Notification Fatigue:** The manager's phone or computer buzzes every 2–3 minutes with isolated alerts, providing no contextual sense of whether the assistant has finished uploading.
2. **Notification Disabling:** Managers are tempted to mute browser push alerts entirely, causing them to miss urgent, time-sensitive events (such as clarification doubts asked by assistants or price bottlenecks).
3. **Fragmented Staging Workflow:** Managers click on an alert for an individual item while the assistant is still in the middle of uploading the rest of the lot, rather than reviewing the batch in a consolidated pass.

### 1.2 Objective
Eliminate notification spam by introducing a **Database-Backed Debounced Sourcing Session Engine** (`IntakeBatchSession`). 

Consecutive uploads by the same assistant within a sliding 15-minute inactivity window are bundled into a single batch session. When 15 minutes pass without new uploads from that assistant (or when explicitly processed), the session closes and dispatches a single, consolidated Web Push notification to store managers:
- **Title:** `📦 Lote completado: %(count)s nuevos productos` (e.g., *"📦 Lote completado: 8 nuevos productos catalogados por Clara"*).
- **Body:** *"Toca para revisar las prendas en el panel de staging."*
- **URL:** Direct link to `/dashboard/?status=draft` (or filtered by session batch).
- **Tag:** `intake-batch-{session.id}`.

Urgent clarification doubts (`ProductClarification`) and price-pending alerts (`PRICE_PENDING`) remain **instant and un-debounced**.

---

## 2. Tech Stack & Architecture Context

- **Runtime / Framework:** Python 3.13, Django 5.1+
- **Zero-Broker Architecture:** Operates completely without Celery or Redis. The application runs in a lightweight, self-contained Docker Compose / SQLite / PostgreSQL environment. Sourcing batch state is tracked cleanly in the relational database.
- **Notification Delivery:** Existing Web Push infrastructure (`pywebpush`, VAPID, `inventory/services/push_service.py`).
- **Batch Evaluation Triggers:**
  1. **CLI Management Command:** `python manage.py process_intake_batches` for cron jobs, Docker host system timers, or background schedules.
  2. **Opportunistic Request Dispatcher:** Evaluated whenever an intake product is uploaded or dashboard view accessed, dispatching any batches whose inactivity window has expired.
- **Internationalization (i18n):** Bilingual notification strings (Spanish default `es`, English `en`) via Django `gettext`.

---

## 3. Executable Commands

- **Run Dev Server:** `.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000`
- **Create Migrations:** `.venv\Scripts\python.exe manage.py makemigrations inventory`
- **Apply Migrations:** `.venv\Scripts\python.exe manage.py migrate`
- **Process Intake Batches (CLI):** `.venv\Scripts\python.exe manage.py process_intake_batches`
- **Process Intake Batches (Dry Run):** `.venv\Scripts\python.exe manage.py process_intake_batches --dry-run`
- **Run Targeted Tests:** `.venv\Scripts\python.exe manage.py test tests.test_intake_batch_notifications`
- **Run Full Test Suite:** `.venv\Scripts\python.exe manage.py test`
- **Code Linter:** `.venv\Scripts\ruff.exe check .`
- **Compile Translations:** `.venv\Scripts\python.exe manage.py compile_locales`

---

## 4. Project Structure & Affected Modules

```text
inventory/
├── models.py                     # Add IntakeBatchSession model, add batch_session FK to Product, refactor post_save signal
├── migrations/
│   └── 0016_intake_batch_session.py # Database migration for IntakeBatchSession and Product.batch_session
├── services/
│   ├── intake_batch_service.py   # Core batch engine: record_product_intake, process_pending_batches
│   └── push_service.py          # Existing push notification dispatcher (send_push_to_group)
├── management/commands/
│   └── process_intake_batches.py # CLI command to evaluate expired sessions and dispatch push alerts
├── admin.py                      # Register IntakeBatchSessionAdmin in ManagerAdminSite with product inlines
config/
└── settings.py                   # INTAKE_SESSION_DEBOUNCE_MINUTES (default 15, env-configurable)
locale/
├── es/LC_MESSAGES/django.po      # Spanish translations for batch push title, body, and admin labels
└── en/LC_MESSAGES/django.po      # English translations
tests/
└── test_intake_batch_notifications.py # Unit, integration, and signal tests for debounced intake notifications
```

---

## 5. Domain Model & Service Specification

### 5.1 `IntakeBatchSession` Model (`inventory/models.py`)

Tracks the active intake uploading session per assistant:

```python
class IntakeBatchSession(models.Model):
    assistant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intake_batches",
        verbose_name=_("Assistant"),
        help_text=_("The assistant who uploaded products during this session"),
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Started At"),
        help_text=_("Timestamp when the first product of the batch was uploaded"),
    )
    last_activity_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Last Activity At"),
        help_text=_("Timestamp of the most recent product upload in this session"),
    )
    product_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Product Count"),
        help_text=_("Total number of products cataloged during this batch session"),
    )
    is_notified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Notified"),
        help_text=_("Whether the consolidated manager push notification has been sent"),
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Closed At"),
        help_text=_("Timestamp when the session was finalized and marked closed"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]
        verbose_name = _("Intake Batch Session")
        verbose_name_plural = _("Intake Batch Sessions")
        indexes = [
            models.Index(fields=["is_notified", "last_activity_at"]),
            models.Index(fields=["assistant", "is_notified"]),
        ]

    def __str__(self):
        assistant_name = self.assistant.get_full_name() or self.assistant.username
        return f"Batch #{self.pk} by {assistant_name} ({self.product_count} items) - {'Notified' if self.is_notified else 'Pending'}"
```

### 5.2 `Product` Model Association (`inventory/models.py`)

Add nullable foreign key to trace each item to its intake session:

```python
batch_session = models.ForeignKey(
    "IntakeBatchSession",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="products",
    verbose_name=_("Intake Batch Session"),
    help_text=_("The intake uploading session in which this product was cataloged"),
)
```

### 5.3 Batch Session Engine (`inventory/services/intake_batch_service.py`)

Two primary operations:

1. **`record_product_intake(product, assistant=None)`:**
   - Looks for an open, un-notified session for this assistant (`is_notified=False`).
   - If found and `timezone.now() - session.last_activity_at < timedelta(minutes=debounce_minutes)`:
     - Increments `session.product_count += 1`.
     - Updates `session.last_activity_at = timezone.now()`.
     - Associates `product.batch_session = session`.
   - If not found or if the previous session exceeded the debounce window:
     - Creates a new `IntakeBatchSession` with `product_count=1`.
     - Associates `product.batch_session = new_session`.
   - Returns the active `IntakeBatchSession`.

2. **`process_pending_intake_batches(debounce_minutes=None, dry_run=False)`:**
   - Queries sessions where `is_notified=False` and `last_activity_at <= now - debounce_window`.
   - For each expired session:
     - Formats consolidated push notification:
       - **Title:** `📦 Lote completado: %(count)s nuevos productos` (or `📦 Lote completado: %(count)s productos por %(name)s` if assistant name is available).
       - **Body:** `Toca para revisar las prendas en el panel de staging.`
       - **URL:** `/dashboard/?status=draft`
       - **Tag:** `intake-batch-{session.id}`
     - If not `dry_run`:
       - Dispatches push notification via `send_push_to_group(group_name=ROLE_MANAGER, ...)`.
       - Marks `session.is_notified = True` and `session.closed_at = timezone.now()`.
       - Saves session.
   - Returns count of processed batches.

### 5.4 Refactoring Lifecycle Signal (`inventory/models.py`)

In `notify_managers_on_product_lifecycle_save`:
- Remove immediate `send_push_to_group` for `created and instance.status == ProductStatus.DRAFT`.
- Instead, invoke `record_product_intake(product=instance, assistant=instance.created_by)`.
- In addition, opportunistically invoke `process_pending_intake_batches()` to clean up any past expired sessions without waiting for cron.
- **CRITICAL:** Preserve immediate `PRICE_PENDING` alerts and all `ProductClarification` question/answer signals.

### 5.5 CLI Management Command (`inventory/management/commands/process_intake_batches.py`)

```bash
python manage.py process_intake_batches [--debounce-minutes=15] [--dry-run]
```
- Outputs number of unnotified expired sessions found and notifications dispatched.
- Safe to run on a 5-minute cron or system timer.

---

## 6. Code Style & Example Snippet

```python
# inventory/services/intake_batch_service.py
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from inventory.models import IntakeBatchSession, Product
from inventory.permissions import ROLE_MANAGER
from inventory.services.push_service import send_push_to_group

def get_debounce_minutes() -> int:
    return getattr(settings, "INTAKE_SESSION_DEBOUNCE_MINUTES", 15)

def record_product_intake(product: Product, assistant=None) -> IntakeBatchSession | None:
    user = assistant or product.created_by
    if not user:
        return None

    debounce_minutes = get_debounce_minutes()
    cutoff = timezone.now() - timedelta(minutes=debounce_minutes)

    active_session = (
        IntakeBatchSession.objects.filter(
            assistant=user,
            is_notified=False,
            last_activity_at__gte=cutoff,
        )
        .order_by("-last_activity_at")
        .first()
    )

    if active_session:
        active_session.product_count += 1
        active_session.last_activity_at = timezone.now()
        active_session.save(update_fields=["product_count", "last_activity_at", "updated_at"])
    else:
        active_session = IntakeBatchSession.objects.create(
            assistant=user,
            started_at=timezone.now(),
            last_activity_at=timezone.now(),
            product_count=1,
            is_notified=False,
        )

    if product.batch_session_id != active_session.id:
        product.batch_session = active_session
        product.save(update_fields=["batch_session"])

    return active_session
```

---

## 7. Testing Strategy

Comprehensive automated test suite in `tests/test_intake_batch_notifications.py` covering:

1. **Session Grouping on Sequential Uploads:**
   - Assistant uploads Item 1 $\to$ `IntakeBatchSession` created with `product_count=1`.
   - Assistant uploads Item 2 within 5 minutes $\to$ same session updated with `product_count=2`, `last_activity_at` refreshed.
   - Assert **zero** push notifications were sent immediately to managers.
2. **Debounce Expiration & Single Push Dispatch:**
   - Advance clock by 15 minutes (`last_activity_at <= now - 15min`).
   - Run `process_pending_intake_batches()`.
   - Assert exactly **one** push notification sent to `ROLE_MANAGER`.
   - Assert notification payload contains `product_count=2` and URL `/dashboard/?status=draft`.
   - Assert `session.is_notified` is `True` and `session.closed_at` is set.
3. **Idempotency & Duplicate Prevention:**
   - Run `process_pending_intake_batches()` a second time.
   - Assert **zero** additional push notifications dispatched.
4. **Subsequent Upload Creates New Session:**
   - Assistant uploads Item 3 after the previous session closed/notified.
   - Assert a new `IntakeBatchSession` is created with `product_count=1`.
5. **Multi-Assistant Isolation:**
   - Assistant A and Assistant B upload items simultaneously.
   - Assert each assistant has their own independent `IntakeBatchSession`.
6. **Preservation of Urgent Non-Draft Notifications:**
   - Create a clarification question $\to$ alerts assistant immediately.
   - Assistant answers clarification $\to$ alerts managers immediately.
   - Transition to `PRICE_PENDING` $\to$ alerts managers immediately.
7. **CLI Management Command:**
   - Execute `call_command('process_intake_batches')` with `--dry-run` and normal modes.
   - Verify proper exit code and stdout summary.

---

## 8. Boundaries

### Always Do
- Keep architecture zero-broker: Use database tracking and scheduled/opportunistic execution. No Redis or Celery.
- Preserve instant alerts for all urgent events (clarifications, doubts, pricing bottlenecks).
- Associate each intake product with its `batch_session` for administrative auditability.
- Use `django.utils.timezone.now()` everywhere for timezone consistency.
- Support full bilingual localization (`es` and `en`) for notification titles, body, and Django Admin.

### Ask First
- Changing the default debounce window from 15 minutes.
- Changing notification target destination from `/dashboard/?status=draft`.
- Adding mandatory manual UI buttons on the assistant mobile form.

### Never Do
- Never introduce Redis, Celery, RabbitMQ, or external daemon dependencies.
- Never debounce or delay urgent manager questions / clarification doubts (`ProductClarification`).
- Never delete or drop past `IntakeBatchSession` records upon session closure (maintain audit history).
- Never send individual draft notifications when `INTAKE_SESSION_DEBOUNCE_MINUTES > 0`.

---

## 9. Success Criteria

1. **Zero Notification Spam:** Uploading 15 products in 20 minutes triggers exactly 1 push notification instead of 15.
2. **Accurate Item Counts:** Batch notification accurately displays the total number of items uploaded in the session (e.g. `8 nuevos productos`).
3. **Auditability:** Every `Product` uploaded via intake links to its parent `IntakeBatchSession`, visible in Django Admin.
4. **Full Test Suite Green:** All existing 337 tests plus new batch notification tests pass cleanly with 0 errors and 0 failures.
5. **Zero Breaking Changes:** Web Push subscriptions, PWA manifest, service worker, and clarification flows operate without regression.

---

## 10. Open Questions & User Choices

1. **Notification Target Link:**
   - **Option A (Recommended):** Link to `/dashboard/?status=draft` so managers immediately see all pending drafts awaiting AI copy and pricing.
   - **Option B:** Link to `/dashboard/?batch=<session_id>` to filter strictly to the items from that specific session.
   *(Option A recommended for MVP as managers generally clear the draft queue).*

2. **Debounce Window Threshold:**
   - **Option A (Recommended):** 15-minute sliding inactivity window (`INTAKE_SESSION_DEBOUNCE_MINUTES = 15`), configurable via `.env`.
   - **Option B:** 10-minute sliding window.
   - **Option C:** Dynamic setting editable in Django Admin via a configuration model.
   *(Option A recommended for zero-complexity operational reliability).*
