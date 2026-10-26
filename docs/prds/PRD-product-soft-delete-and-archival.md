# Product Requirements Document (PRD) & Technical Specification
# Product Soft-Delete, Archival & "Erased" Trash Category

## 1. Objective & Problem Statement

### 1.1 Problem Statement & Operational Background
Currently in the **2ndHand Staging Hub**:
1. Once a product is uploaded during intake, there is no direct mechanism in the user interface (specifically on the product detail page `/products/<pk>/`) to remove or discard products that were:
   - Uploaded erroneously or duplicated by an assistant.
   - Found to be broken, unsellable, damaged, counterfeit, or discarded during physical staging inspection.
   - Withdrawn by the owner or donated.
2. Store managers currently have no way to remove these items from the active workflow without accessing the Django Administration backend (`/admin/`).
3. If products are hard-deleted in Django Admin:
   - Linked images in Oracle Cloud Infrastructure (OCI) Object Storage and local database references risk orphaned records or accidental data loss.
   - Audit trail history (`ProductStatusLog`, `ProductClarification`, `ProductListingLink`, `IntakeBatchSession`) is destroyed, compromising business traceability and analytics.
   - Staff cannot recover accidentally deleted items.
4. Active catalog views (`/dashboard/`) become cluttered with obsolete or unlisted items, inflating metrics (`total_count`, `draft_count`, etc.) and confusing staging operations.

### 1.2 Objective
Implement a secure, recoverable **Product Soft-Delete and Archival ("Erased" Category)** feature:
1. **Domain Model Enrichment:** Add `is_deleted` (`BooleanField`, indexed, default `False`), `deleted_at` (`DateTimeField`, null/blank), and `deleted_by` (`ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)`) to `Product`.
2. **Catalog Isolation:** In all standard catalog views and counters (`all`, `active`, `draft`, `price_pending`, `ready`, `published`, `awaiting_info`, `sold`, `blocked`), automatically filter out and exclude soft-deleted items (`is_deleted=False`).
3. **Dedicated "Erased / Trash" Category:** Add a dedicated dashboard filter category `?status=erased` (labeled `🗑️ Eliminados` / `🗑️ Trash`) that displays exclusively erased products (`is_deleted=True`), along with its own isolated live count badge (`erased_count`).
4. **Product Detail Actions & Safety Controls:**
   - On the product detail page (`/products/<pk>/`), provide a prominent, accessible "Mover a papelera" / "Move to Trash" action restricted to `ROLE_MANAGER`.
   - Include an accessible confirmation modal explaining that the item will be hidden from the active catalog but can be restored at any time.
   - When viewing an already erased item (`is_deleted=True`), render an eye-catching warning banner and provide a 1-click "Restaurar producto" / "Restore Product" action to return it to the active catalog in its original status.
5. **Lifecycle & Audit Synchronization:** Record soft-deletion and restoration events in `ProductStatusLog` with actor attribution, timestamp, and context notes.
6. **Search & Platform Filter Isolation:** Ensure keyword queries and platform filters respect the erased partition (normal searches never return erased items; searching inside `?status=erased` queries only erased items).
7. **Django Admin Integration:** Expose `is_deleted` in `ProductAdmin` list columns, filters, and provide bulk actions to soft-delete and restore products.
8. **Bilingual Localization (i18n):** Complete translation catalogs in Spanish (`es`) and English (`en`).

---

## 2. Tech Stack & Architecture Context

- **Runtime / Framework:** Python 3.13+, Django 5.1+
- **Database:** SQLite (dev/staging) / PostgreSQL (production-ready).
- **Soft-Delete Architecture:** Non-destructive soft-delete pattern via `is_deleted` flag. No third-party heavy dependencies; implemented cleanly in Django ORM with custom managers/querysets and explicit view filtering to prevent breaking existing queries or complex prefetch relationships.
- **Frontend / Styling:** Django Templates + Tailwind CSS + accessible Vanilla JS modal dialogs.
- **Role Permissions:** Restrict soft-delete and restore operations strictly to `ROLE_MANAGER` (`inventory.permissions.is_manager`). Sourcing assistants cannot delete or hide products.
- **Internationalization (i18n):** Django `gettext_lazy` and template translation tags (`{% trans %}`, `{% blocktrans %}`).

---

## 3. Executable Commands

```bash
# Activate virtual environment
.venv\Scripts\activate

# Database Migrations
.venv\Scripts\python.exe manage.py makemigrations inventory
.venv\Scripts\python.exe manage.py migrate

# Targeted Tests
.venv\Scripts\python.exe manage.py test tests.test_product_soft_delete

# Full Regression Suite
.venv\Scripts\python.exe manage.py test

# Code Quality & Linting
.venv\Scripts\ruff.exe check .

# Translation Catalog Compilation
.venv\Scripts\python.exe manage.py compile_locales
```

---

## 4. Project Structure & Affected Modules

```text
epic-tesla/
├── docs/prds/
│   └── PRD-product-soft-delete-and-archival.md   # This PRD & specification document
├── inventory/
│   ├── models.py                                 # Add is_deleted, deleted_at, deleted_by to Product, mark_as_deleted(), restore() methods
│   ├── views.py                                  # Add product_soft_delete_view, product_restore_view, update dashboard_view filtering & counts
│   ├── urls.py                                   # Register routes: /products/<pk>/delete/ and /products/<pk>/restore/
│   ├── admin.py                                  # ProductAdmin list_display, list_filter, soft_delete_selected, restore_selected actions
│   ├── templates/inventory/
│   │   ├── product_detail.html                   # Delete modal trigger, confirmation modal dialog, erased warning banner & restore button
│   │   └── dashboard.html                        # Erased tab navigation pill with erased_count badge, erased card indicator
│   └── migrations/
│       └── 0018_product_soft_delete.py           # Database migration for is_deleted, deleted_at, deleted_by
├── locale/
│   └── es/LC_MESSAGES/django.po                  # Spanish translation entries
└── tests/
    └── test_product_soft_delete.py               # Dedicated unit, view, admin, and integration tests
```

---

## 5. Detailed Technical Specifications

### 5.1 Data Model Changes (`Product` in `inventory/models.py`)

Add the following fields to `Product`:
```python
is_deleted = models.BooleanField(
    default=False,
    db_index=True,
    verbose_name=_("Erased / Deleted"),
    help_text=_("Whether the product is disabled and moved to the erased trash category"),
)
deleted_at = models.DateTimeField(
    null=True,
    blank=True,
    verbose_name=_("Deleted At"),
    help_text=_("Timestamp when product was moved to trash"),
)
deleted_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="deleted_products",
    verbose_name=_("Deleted By"),
    help_text=_("User who moved the product to trash"),
)
```

Add domain lifecycle helper methods to `Product`:
```python
def soft_delete(self, user=None, reason=""):
    """
    Marks the product as soft-deleted and records an audit log entry.
    Preserves original lifecycle status (e.g. DRAFT, READY, SOLD) for seamless restoration.
    """
    self.is_deleted = True
    self.deleted_at = timezone.now()
    self.deleted_by = user
    self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
    
    ProductStatusLog.objects.create(
        product=self,
        from_status=self.status,
        to_status=self.status,
        changed_by=user,
        notes=f"Product moved to trash / erased: {reason}".strip(": "),
    )

def restore(self, user=None):
    """
    Restores a soft-deleted product back to the active catalog in its previous status.
    """
    self.is_deleted = False
    self.deleted_at = None
    self.deleted_by = None
    self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
    
    ProductStatusLog.objects.create(
        product=self,
        from_status=self.status,
        to_status=self.status,
        changed_by=user,
        notes="Product restored from trash back to active catalog",
    )
```

### 5.2 Dashboard Filtering & Aggregate Counts (`inventory/views.py`)

In `dashboard_view(request)`:
1. **Query Filtering:**
   ```python
   if status_filter == "erased":
       products = products.filter(is_deleted=True)
   else:
       products = products.filter(is_deleted=False)
       # Apply regular status_filter: active, draft, ready, published, sold, etc.
   ```
2. **Aggregate Counts:**
   In `counts_qs = Product.objects.all()`:
   - For all standard status counts (`total_count`, `active_count`, `draft_count`, `price_pending_count`, `ready_count`, `published_count`, `awaiting_info_count`, `sold_count`, `blocked_count`), add filter condition `is_deleted=False`.
   - Add new counter:
     ```python
     erased_count=Count("id", filter=Q(is_deleted=True), distinct=True)
     ```
3. **Search Query Isolation:**
   When `q` is supplied:
   - If `status=erased`: search matches only erased products.
   - Otherwise: search matches only active non-erased products.

### 5.3 Product Detail UI & Confirmation Modal (`product_detail.html`)

1. **Active Product (Non-deleted):**
   - In the staging actions card (or top action header), render a red outline button:
     ```html
     <button type="button" onclick="openDeleteProductModal()"
             class="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition shadow-xs">
       🗑️ {% trans "Move to Trash" %}
     </button>
     ```
   - An accessible confirmation modal `#deleteProductModal`:
     - Explains: *"Are you sure you want to move this product to the trash? It will be hidden from the active catalog, but you can restore it anytime from the 'Erased' category."*
     - Contains a CSRF-protected form submitting `POST` to `reverse('inventory:product_soft_delete', kwargs={'pk': product.pk})`.
     - Provides "Cancelar" and "Confirmar eliminación" buttons.

2. **Erased Product (`is_deleted=True`):**
   - Prominent banner at the top of `#product-detail-container`:
     ```html
     <div class="p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
       <div class="flex items-center gap-3">
         <span class="text-2xl">🗑️</span>
         <div>
           <h4 class="text-sm font-bold text-amber-900">{% trans "This product is in the trash" %}</h4>
           <p class="text-xs text-amber-700">{% trans "It is currently hidden from the catalog. You can restore it to resume staging." %}</p>
         </div>
       </div>
       <form method="post" action="{% url 'inventory:product_restore' product.pk %}">
         {% csrf_token %}
         <button type="submit" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow transition">
           ♻️ {% trans "Restore Product" %}
         </button>
       </form>
     </div>
     ```

### 5.4 Endpoints & Security Checks (`inventory/urls.py` & `inventory/views.py`)

- `POST /products/<pk>/delete/` (`name="product_soft_delete"`):
  - Strictly `@login_required` and `@manager_required`. Rejects `GET` requests with `HttpResponseNotAllowed(["POST"])`.
  - Calls `product.soft_delete(user=request.user)`.
  - Sets success flash message: `messages.success(request, _("Product successfully moved to trash."))`.
  - Redirects to `inventory:dashboard` (with `?status=erased` or standard dashboard).
- `POST /products/<pk>/restore/` (`name="product_restore"`):
  - Strictly `@login_required` and `@manager_required`.
  - Calls `product.restore(user=request.user)`.
  - Sets success flash message: `messages.success(request, _("Product successfully restored to catalog."))`.
  - Redirects back to `inventory:product_detail` for that product.

### 5.5 Django Admin Integration (`inventory/admin.py`)

- In `ProductAdmin`:
  - Add `is_deleted` and `deleted_at` to `list_display`.
  - Add `is_deleted` to `list_filter`.
  - Add admin actions:
    - `soft_delete_selected`: moves selected products to trash.
    - `restore_selected`: restores selected products from trash.

---

## 6. Code Style & Example

Follow existing conventions:
- Strict typing, docstrings on domain methods.
- Translations using `django.utils.translation.gettext_lazy as _`.
- Atomic methods with audit trail records.

```python
# inventory/models.py
def soft_delete(self, user=None, reason: str = "") -> None:
    """Soft-delete product by marking is_deleted=True and logging status change."""
    self.is_deleted = True
    self.deleted_at = timezone.now()
    self.deleted_by = user
    self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])
    ProductStatusLog.objects.create(
        product=self,
        from_status=self.status,
        to_status=self.status,
        changed_by=user,
        notes=_("Moved to trash: %(reason)s") % {"reason": reason} if reason else _("Moved to trash"),
    )
```

---

## 7. Testing Strategy

Build a comprehensive test suite in `tests/test_product_soft_delete.py` verifying:
1. **Model Domain Tests:**
   - Default `is_deleted=False`, `deleted_at=None`, `deleted_by=None`.
   - `soft_delete()` sets flags, timestamps, user, and creates audit log in `ProductStatusLog`.
   - `restore()` clears flags and restores original state.
2. **Dashboard Query & Count Isolation:**
   - Normal dashboard queries (`status=all`, `active`, `draft`, `sold`) exclude erased products.
   - `status=erased` returns only erased products.
   - Live aggregate counts (`total_count`, `active_count`, etc.) accurately reflect only non-deleted products.
   - `erased_count` accurately tracks deleted items.
3. **Search & Platform Filter Isolation:**
   - Search term matching an erased product does NOT appear in normal search results.
   - Search term inside `?status=erased&q=...` correctly locates the erased product.
4. **View Security & Permissions:**
   - Non-manager (assistant) cannot POST to `/products/<pk>/delete/` or `/restore/` (403 or redirect).
   - Manager can successfully soft-delete and restore.
5. **UI & Detail Staging View:**
   - Product detail page shows "Move to Trash" button and modal for active products.
   - Erased product shows trash banner and "Restore Product" button.
6. **Django Admin Verification:**
   - Admin list display, filtering, and bulk actions (`soft_delete_selected`, `restore_selected`) work properly.
7. **Bilingual Localization:**
   - Verify Spanish translations render correctly in both dashboard and detail views.

---

## 8. Boundaries

- **Always:**
  - Exclude soft-deleted products from all normal dashboard views and counter aggregates.
  - Require manager privileges (`ROLE_MANAGER`) to soft-delete or restore.
  - Record full audit trail in `ProductStatusLog` upon delete and restore.
  - Run full test suite (`python manage.py test`) and linter (`ruff check .`) before merging.
- **Ask First:**
  - Whether assistants should ever be allowed to delete their own draft items before a manager reviews them.
  - Whether permanent hard deletion (purging OCI images and DB records) is desired, or if soft-delete is sufficient.
- **Never:**
  - Perform hard deletes of products from standard UI endpoints.
  - Silently leak erased products into normal public or manager catalog listings.
  - Break foreign key relationships with `ProductListingLink`, `ProductClarification`, or `IntakeBatchSession`.

---

## 9. Success Criteria

1. On `/products/<pk>/`, a manager can click "Mover a papelera" / "Move to Trash", confirm in the modal, and the product is soft-deleted.
2. The product immediately disappears from all default catalog views (`all`, `active`, `draft`, `ready`, `sold`, etc.) and does not inflate active status counters.
3. Navigating to the `🗑️ Eliminados` / `🗑️ Trash` dashboard tab (`?status=erased`) shows the soft-deleted product and its count.
4. Opening an erased product detail page shows a prominent trash banner with a "Restaurar producto" / "Restore Product" button.
5. Clicking "Restaurar producto" restores the product to its exact prior status (`draft`, `ready`, `sold`, etc.) and returns it to the active catalog.
6. Deletion and restoration events are recorded in `ProductStatusLog` with timestamp and user.
7. Full regression suite passes with 0 failures and linter passes with 0 errors.

---

## 10. Open Questions for Human Review

1. **Permanent Deletion ("Hard Delete"):**
   - *Recommendation:* Keep soft-delete only for now (`is_deleted=True` with restore capability) to preserve OCI storage files and audit logs. Only superusers in Django Admin could permanently delete if ever needed. Does this meet your expectations?
2. **Assistant Permissions:**
   - *Recommendation:* Only store managers (`ROLE_MANAGER`) can soft-delete or restore products; sourcing assistants cannot delete items. (If an assistant makes an intake error, the manager can trash it or the assistant can ask a clarification). Is this acceptable?
3. **Redirect Target after Moving to Trash:**
   - *Recommendation:* When a manager moves a product to the trash from the detail view, redirect them to the catalog dashboard (`/dashboard/?status=erased` with a flash message *"Producto movido a la papelera"*). Is this the preferred destination?
