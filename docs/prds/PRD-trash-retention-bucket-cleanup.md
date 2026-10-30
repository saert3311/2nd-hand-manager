# PRD: Trash Retention Policy & OCI Bucket Permanent Cleanup (Phase 45)

## 1. Objective

### Problem Statement
In **2ndHand Staging Hub**, removing products from active staging uses soft-deletion (`product.soft_delete()`, setting `is_deleted=True` and `deleted_at=timezone.now()`). Soft-deleted items move to the Trash tab (`?status=erased`), preserving their lifecycle state and media.

However, over time:
1. Soft-deleted items accumulate indefinitely in the trash with no automated expiration or retention policy.
2. High-resolution WebP photos (up to 10 photos per product, up to 2560px) continue occupying space in the **Oracle Cloud Infrastructure (OCI) Object Storage** bucket, incurring ongoing cloud storage costs for useless or discarded items.
3. Store Managers have **no mechanism to permanently delete** a discarded item or empty the trash, leaving the bucket cluttered with abandoned product images.

### Target Users & Goal
- **Store Managers**:
  - Ability to permanently delete an individual discarded item directly from the Product Detail workspace (`#erasedProductBanner`), permanently freeing both database records and OCI bucket storage.
  - Ability to empty all trash or purge expired trash (older than retention window) in bulk directly from the Staging Dashboard (`?status=erased`).
  - View live storage reclamation metrics (number of discarded items and photos).
  - Protected by accessible confirmation dialogs (`#actionConfirmModal`) to prevent accidental destruction.
- **Automated Operations / System**:
  - Scheduled background execution (`python manage.py purge_expired_trash --days=30`) to purge products soft-deleted beyond a configurable retention threshold (`TRASH_RETENTION_DAYS = 30`).
  - Storage-first safe deletion: all media files are deleted from the OCI bucket before cascading database records, preventing orphaned "ghost" files.
  - Lightweight audit tombstone preserved in `ProductStatusLog` to maintain financial and inventory traceability.

---

## 2. Tech Stack

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Object Storage:** Oracle Cloud Infrastructure (OCI) Object Storage / S3-compatible API via `django-storages` + `boto3` (`inventory/services/storage.py`)
- **Database:** SQLite with zero-downtime online backup
- **Frontend:** Django Templates + Tailwind CSS + Vanilla JS (OPPO A74 responsive baseline `320×711` & `360×800`)
- **Localization:** Bilingual (`es` / `en`) via Django `i18n` and `polib` (`manage.py compile_locales`)
- **Testing:** Automated unit, integration, permission, and Playwright responsive tests (`manage.py test`)

---

## 3. Commands

```powershell
# 1. Lint & Style Check (Ruff)
.venv\Scripts\ruff.exe check .

# 2. Django System Check
.venv\Scripts\python.exe manage.py check

# 3. Create & Apply Migrations
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate

# 4. Compile Bilingual Translation Catalogs (.po -> .mo)
.venv\Scripts\python.exe manage.py compile_locales

# 5. Run Management Command to Purge Expired Trash (Dry Run)
.venv\Scripts\python.exe manage.py purge_expired_trash --dry-run

# 6. Run Management Command to Purge Expired Trash (Execute)
.venv\Scripts\python.exe manage.py purge_expired_trash --days=30

# 7. Run Targeted Test Suite
.venv\Scripts\python.exe manage.py test tests.test_trash_retention_and_cleanup

# 8. Run Full Automated Test Suite
.venv\Scripts\python.exe manage.py test
```

---

## 4. Project Structure

```text
epic-tesla/
├── docs/ideas/
│   └── trash-retention-and-bucket-cleanup.md        # Ideation one-pager
├── docs/prds/
│   └── PRD-trash-retention-bucket-cleanup.md        # PRD (this file)
├── inventory/
│   ├── models.py                                    # ProductStatusLog tombstone snapshots, SET_NULL product FK, image file deletion signal
│   ├── services/
│   │   └── trash_service.py                         # purge_product_and_media, purge_expired_trash, get_trash_metrics
│   ├── management/commands/
│   │   └── purge_expired_trash.py                   # CLI management command for scheduled cron / ops
│   ├── views.py                                     # product_permanent_delete_view, dashboard_empty_trash_view
│   ├── templates/inventory/
│   │   ├── product_detail.html                      # #btnPermanentDelete in #erasedProductBanner
│   │   └── dashboard.html                           # "Empty Trash" buttons and stats in ?status=erased
│   └── admin.py                                     # Display audit tombstones in custom Django Admin
├── locale/
│   ├── es/LC_MESSAGES/django.po                     # Spanish translations
│   └── en/LC_MESSAGES/django.po                     # English translations
└── tests/
    └── test_trash_retention_and_cleanup.py          # Unit & integration tests for purging, storage deletion, permissions, CLI
```

---

## 5. Architectural Design & Domain Specification

### 5.1 Configuration (`config/settings.py` & `.env.example`)
```python
# Retention window in days before soft-deleted items become eligible for automated purging.
TRASH_RETENTION_DAYS = int(os.getenv("TRASH_RETENTION_DAYS", "30"))
```

### 5.2 Audit Tombstone Preservation (`inventory/models.py`)
In `ProductStatusLog`:
1. `product` ForeignKey updated to `on_delete=models.SET_NULL, null=True, blank=True`.
2. Added fields:
   - `product_id_snapshot = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Archived Product ID"))`
   - `product_title_snapshot = models.CharField(max_length=255, blank=True, default="", verbose_name=_("Archived Product Title"))`
3. Updated `__str__` to gracefully fall back to snapshot values when `product_id` is null.

### 5.3 Storage Cleanup on Image Deletion (`inventory/models.py`)
Attached `post_delete` handler for `ProductImage` to guarantee that whenever a `ProductImage` is deleted (via cascade, admin, or script), the corresponding file in `default_storage` is deleted:
```python
@receiver(post_delete, sender=ProductImage)
def cleanup_product_image_file_on_delete(sender, instance, **kwargs):
    if instance.image and instance.image.name:
        try:
            default_storage.delete(instance.image.name)
        except Exception:
            pass
```

### 5.4 Trash Domain Service (`inventory/services/trash_service.py`)
- `purge_product_and_media(product, user=None) -> dict`:
  - Enforces `is_deleted=True` precondition (cannot purge active products).
  - Iterates over all attached `ProductImage` instances and calls `default_storage.delete(img.image.name)`.
  - Records an immutable tombstone in `ProductStatusLog` with `trigger="permanently_purged"`, snapshotting title, ID, deleted image count, and acting manager.
  - Deletes the `Product` database record (cascading related links, images, clarifications).
  - Returns summary dict: `{"product_id": pk, "title": title, "images_purged": count, "success": True}`.
- `purge_expired_trash(days=None, dry_run=False, user=None) -> dict`:
  - Filters `Product.objects.filter(is_deleted=True, deleted_at__lte=cutoff_date)`.
  - If `dry_run=True`, returns count and metadata without executing deletion.
  - If `dry_run=False`, executes `purge_product_and_media` for each eligible product.
- `empty_all_trash(user=None) -> dict`:
  - Purges all products currently in `is_deleted=True`.
- `get_trash_metrics() -> dict`:
  - Returns `{"trash_count": int, "expired_count": int, "total_images": int, "retention_days": int}`.

### 5.5 Management Command (`inventory/management/commands/purge_expired_trash.py`)
- Options:
  - `--days`: Retention days override (defaults to `settings.TRASH_RETENTION_DAYS`).
  - `--all`: Purge all soft-deleted items regardless of age.
  - `--dry-run`: Simulate purge and output eligible count and image paths without deleting.
  - `--quiet`: Suppress verbose per-item stdout.

### 5.6 View Layer & Permissions (`inventory/views.py`)
- `product_permanent_delete_view(request, pk)`:
  - `@login_required`, `@manager_required`, `@require_POST`.
  - Retrieves soft-deleted product (`is_deleted=True` required; returns 400 if product is not in trash).
  - Calls `purge_product_and_media(product, user=request.user)`.
  - Emits localized success message and redirects to `dashboard?status=erased`.
- `dashboard_empty_trash_view(request)`:
  - `@login_required`, `@manager_required`, `@require_POST`.
  - Parameter `mode = request.POST.get("mode", "expired")` (`"expired"` or `"all"`).
  - Calls `purge_expired_trash(user=request.user)` or `empty_all_trash(user=request.user)`.
  - Emits localized success message and redirects to `dashboard?status=erased`.

### 5.7 UI & Mobile Ergonomics (`product_detail.html` & `dashboard.html`)
- **Product Detail Workspace (`#erasedProductBanner`)**:
  - Displays red destructive button: `🗑️ {% trans "Delete Permanently" %}` alongside existing `♻️ {% trans "Restore Product" %}` button.
  - Wires into accessible modal dialog `#actionConfirmModal` with explicit warning: `{% trans "Permanently delete this product and all its photos from cloud storage? This action cannot be undone." %}`.
- **Dashboard Trash View (`?status=erased`)**:
  - Above the product card grid, displays a dedicated management strip when `status_filter == 'erased'`:
    - Metrics badge: `{% trans "Items in Trash:" %} {{ erased_count }}` and expired items count.
    - Button: `🗑️ {% trans "Empty Expired Trash" %}` (when expired items exist).
    - Button: `⚠️ {% trans "Empty All Trash" %}` (with modal confirmation).
  - Fully responsive on `320×711` and `360×800` (OPPO A74 mobile viewports) with wrapping flex and `min-h-[40px]` tap targets.

---

## 6. Security, Safety & Audit Invariants

1. **Role Gating:** Only Store Managers (`is_manager(request.user)`) can access permanent purge endpoints. Assistants receive 403 Forbidden.
2. **Soft-Delete Prerequisite:** Active products (`is_deleted=False`) can NEVER be hard-purged directly via these endpoints. An item must first be soft-deleted.
3. **Storage-First Order of Operations:** Photos are deleted from the OCI Object Storage bucket *before* or alongside database record deletion, ensuring zero orphaned bucket files even on partial failures.
4. **Permanent Audit Trail:** The `ProductStatusLog` table retains an immutable tombstone for every permanently purged item, recording who purged it, when, the item's title, and the number of photos removed.
5. **No Native Dialogs:** Confirmations strictly use accessible HTML `<dialog role="dialog">` modal `#actionConfirmModal`.

---

## 7. Testing Strategy

1. **Unit Tests (`tests/test_trash_retention_and_cleanup.py`)**:
   - `purge_product_and_media` deletes all `ProductImage` files from `default_storage` and removes the product.
   - `ProductStatusLog` survives product deletion with populated snapshots.
   - `purge_expired_trash` correctly identifies items where `deleted_at <= now - retention_days`.
   - `purge_expired_trash --dry-run` does not delete any files or database rows.
   - `product_permanent_delete_view` rejects non-managers and rejects active (non-erased) items.
   - `dashboard_empty_trash_view` correctly purges expired vs. all items.
2. **Localization & Translations**:
   - Spanish translations verified for all buttons, notices, and CLI messages.
3. **Responsive UI Verification**:
   - Zero horizontal overflow on `320×711` (zoomed OPPO A74) and `360×800` (standard OPPO A74).
