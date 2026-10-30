# Trash Retention Policy & OCI Bucket Permanent Cleanup

## Problem Statement
How might we automatically and manually purge soft-deleted products and their media files from Oracle Cloud Object Storage (OCI S3 bucket) after a defined retention window, freeing up storage quota and costs without risking accidental unrecoverable data loss?

## Recommended Direction
Implement a **Coordinated Two-Tier Purge System**:
1. **Permanent Delete Action (Item-Level)**: A high-visibility, destructive button ("🗑️ Eliminar definitivamente") in `#erasedProductBanner` on `product_detail.html` for soft-deleted products (`is_deleted=True`), requiring confirmation via `#actionConfirmModal`.
2. **Bulk & Expired Empty Trash (Dashboard-Level)**: An "Empty Expired Trash" button on the staging dashboard's Trash tab (`?status=erased`) that purges all items soft-deleted more than 30 days ago.
3. **Automated Scheduled Management Command**: `purge_expired_trash` command parameterized with `--days=30` (read from `TRASH_RETENTION_DAYS=30` in `.env`).
4. **Storage-Safe Purge & Tombstone Audit**: Iterates over all attached `ProductImage` records, deletes actual `.webp` files from the OCI Object Storage bucket via `default_storage.delete()`, records a permanent audit tombstone log entry with manager ID and freed byte/image counts, and removes the product database record cleanly.

## Key Assumptions to Validate
- [ ] OCI S3 API handles batch/sequential object deletion reliably without throttling on bulk purges.
- [ ] Audit logs retain historical visibility even when foreign key `product_id` is set to null or snapshotted.
- [ ] Mobile confirmation modal renders with zero overflow down to 320px width (OPPO A74 baseline).

## MVP Scope
- `TRASH_RETENTION_DAYS = 30` setting in `config/settings.py` and `.env.example`.
- Domain service `purge_product_and_media(product, user=None)` encapsulating OCI bucket file deletion + DB cascade + tombstone log.
- `purge_expired_trash` management command with `--days`, `--dry-run`, and `--quiet` flags.
- View endpoint `product_permanent_delete_view` (POST-only, manager-only).
- View endpoint `dashboard_empty_trash_view` (POST-only, manager-only).
- UI buttons in `inventory/templates/inventory/product_detail.html` and `dashboard.html`.
- Full automated test suite covering storage mocks, permission guards, dry-runs, and Spanish translations.

## Not Doing (and Why)
- **Moving to an S3 "Glacier/Cold" Archive**: You explicitly want to reclaim bucket space and avoid paying for useless junk; archiving still incurs costs and adds complexity.
- **Assistant Trash Access**: Assistants only manage intake and doubts; permanent destruction remains strictly restricted to Store Managers.
- **Client-side instant deletion without server audit**: All purges must leave an immutable tombstone record in the audit trail.

## Open Questions
- None (clarified: 30 days default retention, dual detail/dashboard UI controls, storage-first purge with audit tombstone).
