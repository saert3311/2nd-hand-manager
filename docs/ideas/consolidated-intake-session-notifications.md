# Consolidated Intake Session Notifications: Debounced Sourcing Batch Alerts

## Problem Statement

Store managers currently receive an instant push notification for every single product uploaded during intake (`📦 New Intake in Draft: <title>`). When an assistant catalogues a batch of 10 to 20 items in a sourcing session, the manager's phone buzzes continuously, causing severe notification fatigue and prompting managers to silence alerts entirely.

**How might we** bundle sequential product uploads by an assistant into a single, high-value batch notification once their uploading session concludes, so managers are alerted when inventory is actually ready for review without suffering notification spam?

---

## Recommended Direction

Implement a **Database-Backed Debounced Sourcing Session Engine** (`IntakeBatchSession`) with an inactivity window:

1. **Upload Session Tracking:**
   - Track intake activity per assistant. When an assistant uploads an item via `/intake/`, the system connects the item to an active `IntakeBatchSession` record (`assistant`, `started_at`, `last_activity_at`, `product_count`, `is_notified`, `closed_at`).
   - If an active session exists with activity within the last 15 minutes, update `last_activity_at = now()` and increment `product_count`.
   - If no active session exists or the previous session has been closed/notified, initialize a fresh `IntakeBatchSession`.

2. **Automated Inactivity Window (Debounce):**
   - Configurable window defaulting to 15 minutes (`INTAKE_SESSION_DEBOUNCE_MINUTES = 15`).
   - If 15 minutes elapse without new uploads from that assistant, the session is marked closed and dispatches a single consolidated Web Push notification to store managers.
   - **Push Title:** `📦 Lote completado: %(count)s nuevos productos` (e.g., *"📦 Lote completado: 8 artículos catalogados por Clara"*).
   - **Push Body:** *"Toca para revisar las prendas en el panel de staging."*
   - **Push URL:** Direct link to `/dashboard/?status=draft`.

3. **Lightweight, Zero-Broker Architecture:**
   - Operates cleanly within the existing Django + SQLite/PostgreSQL architecture without requiring Celery or Redis.
   - Evaluated periodically via a lightweight management command (`python manage.py process_intake_batches`) and opportunistic request checks.

---

## Key Assumptions to Validate

- [ ] A 15-minute inactivity window reliably distinguishes between an assistant taking a short break and having finished a sourcing lot.
- [ ] Managers find a single consolidated batch notification significantly more actionable and less intrusive than per-item notifications.
- [ ] A single isolated upload (1 item) waiting 15 minutes before notifying managers does not introduce unacceptable delays into the cataloging workflow.

---

## MVP Scope

### In Scope
1. **Domain Model (`IntakeBatchSession` in `inventory/models.py`):**
   - Fields: `assistant` (FK User), `started_at`, `last_activity_at`, `product_count`, `is_notified`, `closed_at`.
   - Database migration and Django Admin registration for auditability.
2. **Signal Refactoring:**
   - Suppress the immediate individual `created and status == DRAFT` push notification in `notify_managers_on_product_lifecycle_save`.
   - Register the newly created product under the assistant's active `IntakeBatchSession`.
3. **Batch Notification Dispatcher (`inventory/services/intake_batch_service.py`):**
   - Evaluates expired unnotified sessions (`now() - last_activity_at >= 15 min`).
   - Dispatches a single formatted Web Push alert to `ROLE_MANAGER` using `push_service.send_push_to_group()`.
   - Flags `is_notified = True, closed_at = now()`.
4. **Periodic Command:**
   - `python manage.py process_intake_batches` to process pending sessions cleanly.
5. **Configuration Settings:**
   - `INTAKE_SESSION_DEBOUNCE_MINUTES` in `settings.py` (default: 15) with `.env` override.

### Out of Scope (Not Doing & Why)
- **Celery / Redis Workers:** We will NOT add Redis or Celery to the stack. The application is lightweight, self-contained, and Dockerized; maintaining external message broker daemons adds unnecessary memory and operational overhead.
- **Mandatory Manual "End Session" Buttons:** We will NOT force assistants to remember to click a "Finish Batch" button. Mobile field workers frequently close the browser or lock their phone; an automated inactivity debounce eliminates human error.
- **Debouncing Clarification Doubts:** Urgent questions regarding damaged items or missing sizes (`❓ Nueva duda`) will remain instant. Only new intake drafts are debounced.

---

## Open Questions

1. **Dashboard Filter:** Should clicking the batch notification open the dashboard filtered specifically to products from that session, or generally to `/dashboard/?status=draft`?
2. **Batch Timeout Customization:** Is a `.env` configuration (`INTAKE_SESSION_DEBOUNCE_MINUTES=15`) sufficient, or should store managers be able to adjust this threshold dynamically in Django Admin?
