# Published Product Modifications & Platform Sync Tracking

## Problem Statement
How might we empower store managers and assistants to edit published products (adjust prices, upload additional photos, reorder images, and add clarifications) while providing foolproof tracking so live listings across Wallapop, Vinted, eBay, etc., are never left outdated?

## Recommended Direction
Implement an **Orthogonal Platform Sync Engine & Workspace Photo Management** system that keeps products in their active commercial lifecycle status while giving managers clear visibility and 1-click clearance of external marketplace discrepancies:

1. **Orthogonal Sync State (`needs_platform_sync` & `last_platform_synced_at`):**
   - Products with active marketplace listings remain in `ProductStatus.PUBLISHED` (`🚀 Publicado`).
   - An orthogonal boolean field `needs_platform_sync` (`db_index=True`, default `False`) tracks whether modifications occurred post-publication.
   - `last_platform_synced_at` records the exact timestamp when external platforms were last brought in sync.

2. **Automated Change-Detection Triggers:**
   - When a product has active marketplace links (`listing_links.filter(is_active=True).exists()`):
     - Updating `sale_price` (price drops or increases) automatically sets `needs_platform_sync = True`.
     - Modifying `ai_title` or `ai_description` automatically sets `needs_platform_sync = True`.
     - Adding new photos, deleting photos, or reordering photos (changing primary cover photo) automatically sets `needs_platform_sync = True`.
     - Adding or resolving supplemental clarifications/notes sets `needs_platform_sync = True`.

3. **Product Detail Workspace Photo Management (`/products/<pk>/`):**
   - Extend the Photo Gallery card for store managers (`can_manage=True`):
     - **Upload Additional Photos**: In-memory WebP compression via Pillow, strictly adhering to the 10-photo maximum limit and 100MP decompression safety.
     - **Delete Individual Photos**: Manager action to delete flawed or obsolete shots.
     - **Reordering**: Retain instant drag-and-drop and touch controls with live `#mainImage` cover photo preview.

4. **1-Click "Mark Platforms as Updated" Workflow:**
   - Prominent workspace alert banner on `/products/<pk>/` when `needs_platform_sync=True`.
   - Dedicated POST action endpoint `POST /products/<pk>/mark-synced/` resetting `needs_platform_sync = False` and recording `last_platform_synced_at = now()`.
   - Immutable audit logging in `ProductStatusLog` (`trigger="platform_sync_cleared"`).

5. **Dashboard Discovery & Sub-Filtering:**
   - Under the `🚀 Publicados` tab on `/dashboard/`, display sub-filter navigation pills:
     `Todos (X)` vs `⚠️ Desincronizados (Y)` (`?status=published&sync=out_of_sync`).
   - Product cards with pending updates display an amber status badge: `⚠️ Actualizar plataformas` / `⚠️ Update Platforms`.

---

## Key Assumptions to Validate
- [ ] **Orthogonal Status Reliability:** Keeping published products in `PUBLISHED` status ensures sales attribution, external URL navigation, and catalog counting remain 100% accurate without breaking third-party links.
- [ ] **Manager Batching UX:** A single product-level "Mark as updated on all platforms" button provides the optimal speed/overhead balance for secondhand operators managing 2–4 marketplace channels.
- [ ] **Staging Photo Management:** Allowing managers to add and delete photos directly in `/products/<pk>/` eliminates the operational overhead of re-creating products from scratch when extra detail shots are required.

---

## MVP Scope

### 1. Data Layer (`inventory/models.py`)
- Add `needs_platform_sync` (`BooleanField`, default `False`, indexed).
- Add `last_platform_synced_at` (`DateTimeField`, null `True`, blank `True`).
- Add helper method `mark_platform_synced(user)` appending to `ProductStatusLog`.
- Trigger detection in `Product.save()` and signals/endpoints when published attributes mutate.

### 2. Service & Form Layer (`inventory/forms.py`, `inventory/services/image_service.py`)
- Add `ProductPhotoUploadForm` or multi-file field in `ProductUpdateForm` validating photo quantity ($N_{existing} + N_{new} \le 10$) and file sizes ($\le 10\text{MB}$).
- Handle in-memory Pillow WebP compression and creation of `ProductImage` records.

### 3. Views & Routing (`inventory/views.py`, `inventory/urls.py`)
- `product_mark_platform_synced_view` (`POST /products/<pk>/mark-synced/`).
- `product_delete_image_view` (`POST /products/<pk>/images/<image_id>/delete/`).
- Support photo upload processing in `product_detail_view`.

### 4. UI & Templates (`inventory/templates/inventory/`)
- `product_detail.html`:
  - Out-of-sync alert banner with 1-click update button.
  - Photo upload dropzone and delete buttons on thumbnails in Photo Gallery card.
- `dashboard.html`:
  - `?status=published&sync=out_of_sync` sub-filter pill and badge counter.
  - Amber badge on product card.

---

## Not Doing (and Why)
- **Not creating a separate primary lifecycle state (`UPDATE_PENDING`)**: A distinct state would remove live items from the Published catalog, confuse stock counting, and falsely imply external ads were unpublished.
- **Not automating external marketplace updates via headless scraping**: Scraping Wallapop/Vinted violates their Terms of Service and triggers account bans. The manual copy-paste flow using our clipboard shortcuts is reliable and safe.
- **Not separating per-platform sync checkboxes**: Adds unnecessary clicking; a single product-level confirmation fits the fast-paced reselling workflow.

---

## Open Questions
- None. All architectural decisions confirmed during ideation.
