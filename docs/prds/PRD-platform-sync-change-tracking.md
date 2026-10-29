# PRD: Granular Out-of-Sync Change Tracking (Phase 44)

## 1. Objective

### Problem Statement
In 2ndHand Staging Hub, when a published product is modified (e.g. photos changed, title/description edited, price updated, doubts answered, or reservation toggled), `needs_platform_sync` is set to `True`. However, **the reason is lost immediately**. Store Managers see only a generic warning (*"Update Required on Marketplaces / Out of Sync"*).

When managing 20+ active marketplace ads across Wallapop, Vinted, Milanuncios, and eBay, the manager does not know what changed without manually comparing every field and photo against external platforms. They waste time checking whether they need to update the price, paste a revised description, swap photos, or adjust reservation status.

### Target Users & Goal
- **Store Managers**: When inspecting an out-of-sync product in the Staging Workspace (`#platformSyncBanner`), browsing the Dashboard cards, receiving a Web Push notification, or reviewing the Lifecycle Status Audit Log, managers must immediately see exactly **what was updated**:
  - `📷 Photos` (`📷 Fotos`)
  - `🏷️ Title` (`🏷️ Título`)
  - `📝 Description` (`📝 Descripción`)
  - `💰 Price` (`💰 Precio`)
  - `📌 Other` (`📌 Otro` — Doubts/Clarifications or Reservation status)

Edits must **accumulate** across multiple edits (e.g., updating price and then cropping a photo records both `Photos` and `Price`), and reset cleanly when the manager clicks **Mark Platforms as Updated**.

---

## 2. Tech Stack

- **Runtime & Language:** Python 3.13+
- **Web Framework:** Django 5.x (`inventory` app)
- **Database:** SQLite with online backup
- **Frontend:** Django Templates + Tailwind CSS + Vanilla JS
- **Push Service:** Web Push via `pywebpush` (`inventory/services/push_service.py`)
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

# 5. Run Targeted Platform Sync Tests
.venv\Scripts\python.exe manage.py test tests.test_published_platform_sync tests.test_out_of_sync_notifications

# 6. Run Full Test Suite
.venv\Scripts\python.exe manage.py test
```

---

## 4. Project Structure

```text
epic-tesla/
├── docs/ideas/
│   └── platform-sync-change-tracking.md             # Ideation one-pager
├── docs/prds/
│   └── PRD-platform-sync-change-tracking.md         # PRD (this file)
├── inventory/
│   ├── models.py                                    # PlatformSyncReason enum, Product.platform_sync_reasons, methods
│   ├── views.py                                     # product_detail_view, image endpoints calling add_platform_sync_reasons
│   ├── services/
│   │   └── push_service.py                          # send_out_of_sync_notification with human-readable reasons
│   ├── templates/inventory/
│   │   ├── product_detail.html                      # #platformSyncBanner with distinct category badges
│   │   └── dashboard.html                           # Product card badge with compact change icons
│   └── admin.py                                     # Display platform_sync_reasons in custom Django Admin
├── locale/
│   ├── es/LC_MESSAGES/django.po                     # Spanish translations
│   └── en/LC_MESSAGES/django.po                     # English translations
└── tests/
    ├── test_published_platform_sync.py              # Unit tests for accumulation, clearing, and reasons
    ├── test_out_of_sync_notifications.py            # Push notification body test with reasons
    └── test_oppo_a74_responsive.py                  # Responsive checks on 320x711 & 360x800
```

---

## 5. Architectural Design & Domain Model Specification

### 5.1 `PlatformSyncReason` Enum (`inventory/models.py`)
```python
class PlatformSyncReason(models.TextChoices):
    PHOTOS = "photos", _("Photos")
    TITLE = "title", _("Title")
    DESCRIPTION = "description", _("Description")
    PRICE = "price", _("Price")
    OTHER = "other", _("Other")
```

### 5.2 `Product` Schema & Lifecycle Methods (`inventory/models.py`)
```python
class Product(models.Model):
    ...
    needs_platform_sync = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Needs Platform Sync"),
        help_text=_("Whether edits were made after publication that need updating on external platforms"),
    )
    platform_sync_reasons = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Platform Sync Reasons"),
        help_text=_("List of change categories that triggered out-of-sync status"),
    )
    last_platform_synced_at = models.DateTimeField(...)
```

#### Reason Accumulation Method:
```python
def add_platform_sync_reasons(self, *reasons: str, user=None, commit=True):
    """
    Accumulates one or more change reasons into self.platform_sync_reasons
    in canonical order without duplicates, sets needs_platform_sync = True,
    and saves the product if commit=True.
    """
    if self.is_sold or self.status == ProductStatus.SOLD:
        return

    is_published = (
        self.status == ProductStatus.PUBLISHED
        or (self.pk and self.listing_links.filter(is_active=True).exists())
    )
    if not is_published:
        return

    canonical_order = [
        PlatformSyncReason.PHOTOS,
        PlatformSyncReason.TITLE,
        PlatformSyncReason.DESCRIPTION,
        PlatformSyncReason.PRICE,
        PlatformSyncReason.OTHER,
    ]
    existing = set(self.platform_sync_reasons or [])
    for r in reasons:
        if r in canonical_order:
            existing.add(r)

    # Sort in canonical order
    self.platform_sync_reasons = [r for r in canonical_order if r in existing]
    self.needs_platform_sync = True
    if commit:
        self.save(update_fields=["needs_platform_sync", "platform_sync_reasons"], changed_by=user)
```

#### Property `platform_sync_reason_badges`:
Returns a list of dicts for template rendering:
```python
@property
def platform_sync_reason_badges(self) -> list[dict]:
    """
    Returns localized metadata for currently pending out-of-sync reasons.
    """
    if not self.needs_platform_sync:
        return []
    
    meta = {
        PlatformSyncReason.PHOTOS: {"code": "photos", "icon": "📷", "label": _("Photos")},
        PlatformSyncReason.TITLE: {"code": "title", "icon": "🏷️", "label": _("Title")},
        PlatformSyncReason.DESCRIPTION: {"code": "description", "icon": "📝", "label": _("Description")},
        PlatformSyncReason.PRICE: {"code": "price", "icon": "💰", "label": _("Price")},
        PlatformSyncReason.OTHER: {"code": "other", "icon": "📌", "label": _("Other")},
    }
    reasons = self.platform_sync_reasons or []
    if not reasons:
        # Fallback for legacy items that had needs_platform_sync=True
        return [meta[PlatformSyncReason.OTHER]]
    return [meta[r] for r in reasons if r in meta]
```

#### Clearing Sync (`mark_platform_synced`):
```python
def mark_platform_synced(self, user=None, commit=True):
    cleared_reasons = list(self.platform_sync_reasons or [])
    self.needs_platform_sync = False
    self.platform_sync_reasons = []
    self.last_platform_synced_at = timezone.now()
    self._clearing_platform_sync = True
    if commit:
        self.save(
            update_fields=["needs_platform_sync", "platform_sync_reasons", "last_platform_synced_at"],
            changed_by=user,
        )
    self._clearing_platform_sync = False
    
    # Audit trail with cleared reasons
    reason_labels = ", ".join(str(r) for r in cleared_reasons)
    notes = f"Marketplace listings verified as synchronized"
    if reason_labels:
        notes += f" (Resolved: {reason_labels})"
    log_status_change(
        product=self,
        from_status=self.status,
        to_status=self.status,
        user=user,
        trigger="platform_sync_cleared",
        notes=notes,
    )
```

### 5.3 Detection in `Product.save()`
In `Product.save()`:
```python
if is_published and not self.is_sold and self.status != ProductStatus.SOLD and not getattr(self, "_clearing_platform_sync", False):
    new_reasons = set()
    if self.sale_price != getattr(self, "_initial_sale_price", None):
        new_reasons.add(PlatformSyncReason.PRICE)
    if (self.ai_title or "") != (getattr(self, "_initial_ai_title", None) or ""):
        new_reasons.add(PlatformSyncReason.TITLE)
    if (self.ai_description or "") != (getattr(self, "_initial_ai_description", None) or ""):
        new_reasons.add(PlatformSyncReason.DESCRIPTION)
    if getattr(self, "is_reserved", False) != getattr(self, "_initial_is_reserved", False):
        new_reasons.add(PlatformSyncReason.OTHER)

    if new_reasons:
        canonical_order = [PlatformSyncReason.PHOTOS, PlatformSyncReason.TITLE, PlatformSyncReason.DESCRIPTION, PlatformSyncReason.PRICE, PlatformSyncReason.OTHER]
        existing = set(self.platform_sync_reasons or [])
        existing.update(new_reasons)
        self.platform_sync_reasons = [r for r in canonical_order if r in existing]
        self.needs_platform_sync = True
```

### 5.4 Photo Operations & Clarifications
- In `inventory/views.py`:
  - `product_upload_images_view`: `product.add_platform_sync_reasons(PlatformSyncReason.PHOTOS, user=request.user)`
  - `product_delete_image_view`: `product.add_platform_sync_reasons(PlatformSyncReason.PHOTOS, user=request.user)`
  - `product_reorder_images_view`: when primary image changes, `product.add_platform_sync_reasons(PlatformSyncReason.PHOTOS, user=request.user)`
  - `product_edit_image_view` (crop/rotate): `product.add_platform_sync_reasons(PlatformSyncReason.PHOTOS, user=request.user)`
  - `product_detail_view` (batch upload in detail): `product.add_platform_sync_reasons(PlatformSyncReason.PHOTOS, user=request.user)`
- In `inventory/models.py`:
  - `sync_product_on_clarification_save`: when doubt/direct note opened/resolved on published product, `product.add_platform_sync_reasons(PlatformSyncReason.OTHER, user=acting_user)`

### 5.5 Push Notifications (`send_out_of_sync_notification`)
```python
def send_out_of_sync_notification(product, trigger_reason: str | None = None) -> int:
    ...
    labels = [b["label"] for b in product.platform_sync_reason_badges]
    reasons_str = ", ".join(labels) if labels else str(_("General details"))
    title = str(_("⚠️ Out of Sync: %(title)s") % {"title": product.display_title})
    body = str(_("Modified after publication. Updated: %(reasons)s. External listings require sync.") % {"reasons": reasons_str})
    ...
```

### 5.6 UI Specification
1. **Product Detail Banner (`#platformSyncBanner`)**:
   - Header: *"Update Required on Marketplaces"* (`⚠️ Out of Sync`).
   - Underneath the description text, render a flex container with category badge pills:
     - `📷 Photos` / `📷 Fotos` (emerald/slate/amber style)
     - `🏷️ Title` / `🏷️ Título`
     - `📝 Description` / `📝 Descripción`
     - `💰 Price` / `💰 Precio`
     - `📌 Other` / `📌 Otro`
   - Mobile: `flex-wrap gap-1.5` ensuring zero horizontal overflow on `320px` viewport width.
2. **Dashboard Product Cards (`dashboard.html`)**:
   - On photo badge:
     `⚠️ Update Platforms` followed by compact category icons (e.g. `📷 💰`).
     Accessible tooltip with localized summary (e.g., `title="{% trans 'Out of sync: Photos, Price' %}"`).
3. **Audit History (`#status-history-section`)**:
   - Status change logs and `platform_sync_cleared` note reflect the specific reasons resolved.

---

## 6. Acceptance Criteria

- [ ] `Product.platform_sync_reasons` stores a list of unique canonical strings (`photos`, `title`, `description`, `price`, `other`).
- [ ] Modifying `sale_price` on a published product adds `price`.
- [ ] Modifying `ai_title` adds `title`.
- [ ] Modifying `ai_description` adds `description`.
- [ ] Modifying `is_reserved` adds `other`.
- [ ] Uploading, deleting, cropping/rotating, or changing cover photo order adds `photos`.
- [ ] Opening/resolving clarifications on a published product adds `other`.
- [ ] Multiple consecutive edits accumulate in `platform_sync_reasons` without overwriting prior reasons.
- [ ] Clicking **Mark Platforms as Updated** clears `platform_sync_reasons` to `[]`, sets `needs_platform_sync = False`, and records the resolved reasons in `ProductStatusLog`.
- [ ] Product Detail banner renders distinct visual chips for each active reason.
- [ ] Dashboard cards display compact indicator icons without horizontal overflow on `320×711` & `360×800` (OPPO A74).
- [ ] Push notification body includes human-readable updated categories.
- [ ] 100% of automated tests pass, zero Ruff warnings, zero Django check issues.
