# PRD: Published Product Modifications & Platform Sync Tracking

## 1. Executive Summary & Objective

In second-hand multi-channel reselling, items frequently evolve **after** they have been published across external platforms (Wallapop, Vinted, eBay, Milanuncios):
- **Price Drops / Increases**: Adjusting price to accelerate sales or respond to market demand.
- **Supplemental Details & Measurements**: Adding armpit-to-armpit measurements, fabric composition, or flaw clarifications discovered post-intake.
- **Additional Photos**: Snapping close-up photos of tags, flaws, or alternative angles requested by prospective buyers.
- **Photo Reordering**: Elevating a cleaner photo to the primary cover slot.

Because external marketplaces do not offer open public write APIs for individual second-hand seller accounts, updates in **2ndHand Staging Hub** cannot silently sync over the wire. If a manager drops a price from €50 to €35 in the hub, external ads will remain at €50 until manually updated. Without clear tracking, sellers lose track of which listings are out of sync.

### Objective:
1. Allow full editing of published products, including **copywriting, pricing, clarifications, and full photo management (uploading new photos, deleting photos, and reordering)** directly in the Product Detail workspace (`/products/<pk>/`).
2. Maintain the primary commercial lifecycle status as **`PUBLISHED`** (`🚀 Publicado`) so live items remain in catalog tallies, search, and active marketplace attribution.
3. Introduce an **orthogonal synchronization engine** (`needs_platform_sync = True`) that automatically flags products whenever a published item is modified.
4. Provide a high-visibility workspace alert and a **1-click "Mark Platforms as Updated"** button (`POST /products/<pk>/mark-synced/`) that clears the flag, timestamps the synchronization, and logs an audit trail event.
5. Provide dashboard sub-filtering (`?status=published&sync=out_of_sync`) so managers can discover and clear all pending marketplace updates in seconds.

---

## 2. User Stories & Core Use Cases

1. **Manager Price Drop & Sync Alert**:
   *As a store manager reviewing slow-moving published inventory, I lower the price of a vintage jacket from €65 to €45 in the product detail view. The hub automatically flags the item with `⚠️ Actualización Pendiente`, prompting me to update the price on Wallapop and Vinted, where price drops trigger push notifications to interested buyers.*
2. **Manager Attaching Supplemental Photos Post-Intake**:
   *As a store manager, a prospective buyer on Wallapop asks for a close-up of the brand tag and zipper. I take 2 new photos and upload them directly into the Product Detail workspace. The photos are converted to WebP in memory, appended to the gallery, and the item is marked as needing a platform update so I remember to add the photos to the live ad.*
3. **1-Click Sync Clearance**:
   *As a store manager, after copying the new photos and updated price into Wallapop and Vinted, I click "Marcar plataformas como actualizadas". The hub clears the warning banner, records my username and timestamp, and returns the product to a clean in-sync state.*
4. **Dashboard Batch Clearing**:
   *As a store manager starting my morning shift, I click the "Desincronizados" sub-filter under the "Publicados" tab on the dashboard to see all 4 items modified yesterday, allowing me to batch-update external ads efficiently.*

---

## 3. Architecture & Functional Requirements

### 3.1. Domain Model Expansion (`inventory/models.py`)

- **`Product` Fields**:
  - `needs_platform_sync`: `models.BooleanField(default=False, db_index=True, verbose_name=_("Needs Platform Sync"), help_text=_("Indicates whether published attributes were modified and require updating on external marketplaces"))`
  - `last_platform_synced_at`: `models.DateTimeField(null=True, blank=True, verbose_name=_("Last Platform Synced At"), help_text=_("Timestamp when external marketplace listings were last verified in sync"))`

- **Lifecycle Helper Method (`Product.mark_platform_synced(user)`):**
  ```python
  def mark_platform_synced(self, user=None):
      self.needs_platform_sync = False
      self.last_platform_synced_at = timezone.now()
      self.save(update_fields=["needs_platform_sync", "last_platform_synced_at", "updated_at"])
      ProductStatusLog.objects.create(
          product=self,
          from_status=self.status,
          to_status=self.status,
          changed_by=user,
          trigger="platform_sync_cleared",
          notes="Marketplace listings verified as synchronized"
      )
  ```

- **Automated Change-Detection Triggers**:
  - A helper `flag_platform_sync_needed()` is evaluated when:
    1. `ProductUpdateForm` is submitted with changes to `ai_title`, `ai_description`, or `sale_price` while `status == PUBLISHED` or active `ProductListingLink` exists.
    2. New photos are uploaded in `product_detail_view`.
    3. An existing photo is deleted in `product_delete_image_view`.
    4. Photos are reordered in `product_reorder_images_view` if the primary cover image (`order=0`) changes.
    5. A new clarification note is added or a doubt is answered on a published item.

### 3.2. Photo Management in Product Detail (`inventory/views.py` & `inventory/templates/inventory/product_detail.html`)

- **Upload Additional Photos**:
  - Store managers (`can_manage=True`) can upload additional image files directly within the Photo Gallery card.
  - Validates total count: existing images + new images $\le 10$.
  - Uses `convert_to_webp()` in memory via `image_service.py` to strip EXIF, convert to `.webp` 2560px, and enforce the 100MP decompression safety limit.
  - Automatically assigns sequential `order` values ($N_{existing}, N_{existing}+1, \dots$).
  - If product is published, sets `needs_platform_sync = True`.

- **Delete Individual Photos**:
  - **Endpoint**: `POST /products/<pk>/images/<image_id>/delete/` (`name="product_delete_image"`)
  - **Permissions**: `@login_required`, `@manager_required`, `@require_POST`.
  - Ensures at least 1 photo remains (cannot delete the only photo of a product).
  - Deletes `ProductImage` record and adjusts remaining sequence `order`.
  - If product is published, sets `needs_platform_sync = True`.

### 3.3. Sync Action Endpoint (`POST /products/<pk>/mark-synced/`)

- **Route**: `/products/<pk>/mark-synced/` (`name="product_mark_platform_synced"`)
- **Access Control**: `@login_required`, `@manager_required`, `@require_POST`.
- Resets `needs_platform_sync = False` and updates `last_platform_synced_at`.
- Creates audit trail entry in `ProductStatusLog`.
- Redirects back to `/products/<pk>/` with an accessible success flash message.

### 3.4. Dashboard Filtering & Scoping (`inventory/views.py` & `inventory/templates/inventory/dashboard.html`)

- **Sub-Filter Navigation under "Publicados" Tab**:
  - When viewing `?status=published`:
    - `Todos (N)` (`/dashboard/?status=published`)
    - `⚠️ Desincronizados (M)` (`/dashboard/?status=published&sync=out_of_sync`)
  - Aggregate badge count computed efficiently in a single query:
    `Count("id", filter=Q(is_deleted=False, is_sold=False, status=ProductStatus.PUBLISHED, needs_platform_sync=True))`
- **Product Card Badge**:
  - Published products with `needs_platform_sync=True` display an amber pulse badge:
    `⚠️ Actualizar plataformas` / `⚠️ Update Platforms`.

---

## 4. Accessibility & Mobile Standards (`frontend-ui-engineering`)

1. **Accessible Banner**:
   - `role="alert"`, `aria-live="polite"` with high-contrast amber styling (`bg-amber-50 border-amber-300 text-amber-950`).
2. **Touch Targets**:
   - "Marcar plataformas como actualizadas" button has minimum 44×44px touch target on mobile viewports.
3. **Typography**:
   - All input controls, labels, and badges adhere to minimum 16px font size on mobile viewports to eliminate iOS Safari auto-zooming.
4. **No Arbitrary Micro-Fonts**:
   - Uses `text-xs sm:text-sm` for badges and button text.

---

## 5. Bilingual Localization & Testing

1. **Translations (`locale/es/LC_MESSAGES/django.po`)**:
   - "Needs Platform Sync" $\to$ "Requiere sincronización en plataformas"
   - "Mark Platforms as Updated" $\to$ "Marcar plataformas como actualizadas"
   - "This product was modified after publication. External listings may be out of date." $\to$ "Este producto fue modificado después de su publicación. Los anuncios en plataformas externas pueden estar desactualizados."
   - "Upload More Photos" $\to$ "Subir más fotos"
   - "Delete Photo" $\to$ "Eliminar foto"
   - "Out of Sync" $\to$ "Desincronizados"
2. **Automated Test Suite (`tests/test_published_platform_sync.py`)**:
   - Model fields and `mark_platform_synced()` logic.
   - Auto-trigger on price changes, description updates, photo additions/deletions/reorder, and clarifications.
   - Endpoint permissions (manager allowed, assistant blocked with HTTP 403).
   - Detail view UI alert banner and sync button.
   - Dashboard sub-filter scoping and aggregate badge counts.
   - Photo upload and deletion in detail workspace.
   - Bilingual Spanish/English localization.
