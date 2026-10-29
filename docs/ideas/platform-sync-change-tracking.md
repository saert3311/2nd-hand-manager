# Platform Sync Change Tracking (Granular Out-of-Sync Reasons)

## Problem Statement
How might we make it immediately obvious to a Store Manager which specific fields or assets (Photos, Title, Description, Price, or Other) changed on a published product across the Detail Banner, Dashboard Cards, Web Push Notifications, and Audit Log, so they can update external marketplaces (Wallapop, Vinted, Milanuncios, eBay) in seconds without guesswork?

## Recommended Direction
Extend the existing `Product.needs_platform_sync` boolean mechanism with an accumulating `platform_sync_reasons` JSON list field on `Product`, backed by a `PlatformSyncReason` (`TextChoices`) enum with five canonical categories:
- `photos` (`📷 Photos` / `📷 Fotos`)
- `title` (`🏷️ Title` / `🏷️ Título`)
- `description` (`📝 Description` / `📝 Descripción`)
- `price` (`💰 Price` / `💰 Precio`)
- `other` (`📌 Other` / `📌 Otro`)

Whenever a published, unsold product is modified:
1. **`Product.save()`** detects changes to `ai_title` (`title`), `ai_description` (`description`), `sale_price` (`price`), or `is_reserved` (`other`) and merges those reasons into `platform_sync_reasons`.
2. **Photo endpoints** (`product_upload_images_view`, `product_delete_image_view`, `product_reorder_images_view`, `product_edit_image_view`, and `product_detail_view` image upload) add `photos` via `product.add_platform_sync_reasons()`.
3. **Clarification signals** (`sync_product_on_clarification_save` when doubts or direct notes are opened or answered on a published product) add `other`.
4. **Clearing**: Clicking **Mark Platforms as Updated** (`product.mark_platform_synced()`) resets `needs_platform_sync = False`, clears `platform_sync_reasons = []`, updates `last_platform_synced_at`, and records the synced categories in `ProductStatusLog`.

## Key Assumptions to Validate
- [x] **Multi-edit accumulation:** Editing Price in step 1 and cropping a Photo in step 2 retains both `["photos", "price"]` rather than overwriting.
- [x] **Zero N+1 queries:** Storing `platform_sync_reasons` directly on `Product` requires 0 extra queries on `/dashboard/`.
- [x] **Narrow mobile viewport safety (`320×711` & `360×800`):** Compact icon indicators on dashboard cards and wrapping `flex-wrap` category pills in `#platformSyncBanner` cause zero horizontal overflow.

## MVP Scope
- **Domain Model (`inventory/models.py`):**
  - `PlatformSyncReason` (`TextChoices`: `PHOTOS`, `TITLE`, `DESCRIPTION`, `PRICE`, `OTHER`).
  - `Product.platform_sync_reasons = models.JSONField(default=list, blank=True)`.
  - Helper `Product.add_platform_sync_reasons(*reasons, commit=True)` & property `platform_sync_reason_badges` returning localized metadata (`code`, `icon`, `label`).
  - Track `ai_title`, `ai_description`, `sale_price`, and `is_reserved` in `Product.__init__()` and `Product.save()`.
  - Update `mark_platform_synced()` to log the cleared reasons into `ProductStatusLog` (e.g., `"Marketplace listings verified as synchronized (Updated: Photos, Price)"`) and clear `platform_sync_reasons`.
- **Views & Signals (`inventory/views.py`, `inventory/models.py`):**
  - Update all photo mutation views and clarification signals to call `product.add_platform_sync_reasons(...)`.
- **Push Notifications (`inventory/services/push_service.py`):**
  - Include human-readable updated categories in `send_out_of_sync_notification()` body.
- **Templates (`product_detail.html`, `dashboard.html`):**
  - `#platformSyncBanner`: Render distinct category pills (`📷 Photos`, `🏷️ Title`, `📝 Description`, `💰 Price`, `📌 Other`).
  - Dashboard product cards: Display compact change icons inside the `⚠️ Update Platforms` badge with accessible tooltip/labels.
- **Bilingual Localization & Tests:**
  - Full English and Spanish translations (`locale/es/`, `locale/en/`) + unit and responsive browser tests.

## Not Doing (and Why)
- **Per-marketplace-site individual sync toggles** — Adds extra clicks for the manager; a single global "Mark Platforms as Updated" button matches the existing fast workflow.
- **Full text before/after diffs in the banner** — Creates visual clutter on narrow `320px`–`360px` mobile screens when a description is 500+ characters long; category tags tell the manager everything they need to copy/paste.
- **Triggering platform sync on internal-only metadata** (such as `views_count`, `whatsapp_clicks`, or `estimated_retail_price`) — These do not affect live Wallapop/Vinted listings.

## Open Questions
- None. Requirements and scope were aligned via `/idea-refine`.
