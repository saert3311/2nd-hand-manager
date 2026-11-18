# Store-Exclusive `Published` Lifecycle Status

## Problem Statement
How might we allow store managers to move complete, priced products (`Title` + `Description` + `Price > 0`) into **`Published`** (`🌐 Publicado`) when they are sold exclusively on our physical/web store (with zero external Wallapop/Vinted links), without automatic lifecycle recalculation resetting them back to **`Ready to Publish`** (`✅ Listo para publicar`) or triggering false **"Out of Sync"** (`Desincronizado`) alerts on subsequent edits?

## Recommended Direction
Make `ProductStatus.PUBLISHED` work cleanly in both modes while preserving `Ready to Publish` as the external cross-posting queue:

1. **Preserve Manual `Published` When Complete (`compute_lifecycle_status`, `Product.save`, `sync_lifecycle_status`)**:
   - Attaching an active `ProductListingLink` still auto-promotes `READY -> PUBLISHED`.
   - Deleting or deactivating the last `ProductListingLink` (`trigger="marketplace_link_removed"`) still auto-reverts `PUBLISHED -> READY`.
   - When a manager sets `status = ProductStatus.PUBLISHED` manually (or saves edits to a store-exclusive `PUBLISHED` item), `compute_lifecycle_status(preserve_manual_published=True)` retains `PUBLISHED` provided `ai_title`, `ai_description`, and `sale_price > 0` are present.
   - Clearing the price (`<= 0`), opening a pending clarification, blocking, or marking sold still take precedence cleanly.
   - Explicitly changing status back to `READY` when no external links exist transitions back to `READY`.
2. **External-Link-Only Platform Sync (`needs_platform_sync`)**:
   - Only flag `needs_platform_sync = True` in `Product.save()`, `add_platform_sync_reasons()`, and clarification signals when `has_active_external_links` is true (`listing_links.filter(is_active=True).exists()`).
   - Store-exclusive `PUBLISHED` items reflect title, description, price, and photo edits live on the public storefront immediately without false "Out of Sync" push notifications or badges.

## Key Assumptions to Validate
- [x] Removing the last external marketplace link still reverts formerly cross-listed items back to `READY`.
- [x] Incomplete products (missing title, description, or `sale_price <= 0`) cannot bypass `DRAFT` / `PRICE_PENDING` gates into store-exclusive `PUBLISHED`.

## MVP Scope
- `inventory/models.py`: `has_active_external_links`, `preserve_manual_published` support in `compute_lifecycle_status()`, `sync_lifecycle_status()`, `save()`, `_infer_status_trigger()`, `add_platform_sync_reasons()`, and `sync_product_on_clarification_save`.
- `tests/test_lifecycle.py` & `tests/test_published_platform_sync.py`: coverage for store-exclusive `PUBLISHED` persistence, edits, revert to `READY`, last-link deletion revert, and skipped `needs_platform_sync` alerts when 0 external links exist.

## Not Doing (and Why)
- **Not adding a new `ProductStatus` enum or DB migration** — `status == PUBLISHED` paired with `has_active_external_links` already represents store-exclusive vs. cross-listed items cleanly without fragmenting dashboard tabs.
- **Not auto-promoting all `is_public=True` items to `PUBLISHED` on pricing** — keeps new priced items in `Ready to Publish` so managers consciously decide between cross-posting or marking them `Published`.
