import logging
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import Product, ProductImage, ProductStatusLog

logger = logging.getLogger(__name__)


def get_trash_retention_days() -> int:
    """
    Returns the configured trash retention period in days (defaults to 30).
    """
    try:
        return int(getattr(settings, "TRASH_RETENTION_DAYS", 30))
    except (TypeError, ValueError):
        return 30


def get_trash_metrics(days: int | None = None) -> dict:
    """
    Returns operational metrics for soft-deleted items currently in the trash.
    """
    retention_days = days if days is not None else get_trash_retention_days()
    cutoff = timezone.now() - timedelta(days=retention_days)

    trash_qs = Product.objects.filter(is_deleted=True)
    trash_count = trash_qs.count()
    expired_count = trash_qs.filter(deleted_at__lte=cutoff).count()
    total_images = ProductImage.objects.filter(product__is_deleted=True).count()

    return {
        "trash_count": trash_count,
        "expired_count": expired_count,
        "total_images": total_images,
        "retention_days": retention_days,
    }


def purge_product_and_media(product: Product, user=None) -> dict:
    """
    Permanently purges a soft-deleted product and all its attached media from cloud storage.

    Safety invariants:
    1. Product must be soft-deleted (is_deleted=True). Active products cannot be purged directly.
    2. Physical image files (.webp) are deleted from default_storage (OCI bucket / media).
    3. An immutable ProductStatusLog tombstone is created before product record deletion.
    4. Database record is deleted with clean cascade.
    """
    if not getattr(product, "is_deleted", False):
        raise ValueError(_("Cannot permanently delete an active product. Move to trash first."))

    product_id = product.pk
    product_title = product.display_title
    from_status = product.status

    # Gather image file names prior to deletion
    image_names = [img.image.name for img in product.images.all() if img.image and img.image.name]

    # 1. Delete physical files from cloud/media storage
    deleted_files_count = 0
    for name in image_names:
        try:
            default_storage.delete(name)
            deleted_files_count += 1
        except Exception as exc:
            logger.warning("Failed to delete media file '%s' from storage for Product #%s: %s", name, product_id, exc)

    acting_user = user if (user and getattr(user, "is_authenticated", False)) else None
    notes = (
        f"Product #{product_id} '{product_title}' permanently purged from database and cloud storage "
        f"({deleted_files_count} photos removed)."
    )

    with transaction.atomic():
        # 2. Record permanent audit tombstone
        ProductStatusLog.objects.create(
            product=None,
            product_id_snapshot=product_id,
            product_title_snapshot=product_title,
            from_status=from_status,
            to_status=None,
            changed_by=acting_user,
            trigger="permanently_purged",
            notes=notes,
        )

        # 3. Delete product database record (cascading related links, images, clarifications)
        product.delete()

    logger.info("Successfully purged Product #%s ('%s') and %d photos.", product_id, product_title, deleted_files_count)
    return {
        "product_id": product_id,
        "title": product_title,
        "images_purged": deleted_files_count,
        "success": True,
    }


def purge_expired_trash(days: int | None = None, dry_run: bool = False, user=None) -> dict:
    """
    Purges all products soft-deleted prior to the retention cutoff date.
    When dry_run=True, simulates the operation without deleting any records or files.
    """
    retention_days = days if days is not None else get_trash_retention_days()
    cutoff = timezone.now() - timedelta(days=retention_days)

    expired_products = list(
        Product.objects.filter(is_deleted=True, deleted_at__lte=cutoff)
        .prefetch_related("images")
        .order_by("deleted_at")
    )

    if dry_run:
        total_images = sum(p.images.count() for p in expired_products)
        return {
            "dry_run": True,
            "retention_days": retention_days,
            "cutoff": cutoff,
            "eligible_count": len(expired_products),
            "eligible_images": total_images,
            "products": [
                {
                    "id": p.pk,
                    "title": p.display_title,
                    "deleted_at": p.deleted_at,
                    "images_count": p.images.count(),
                }
                for p in expired_products
            ],
        }

    purged_count = 0
    total_images_purged = 0
    for product in expired_products:
        res = purge_product_and_media(product, user=user)
        purged_count += 1
        total_images_purged += res.get("images_purged", 0)

    return {
        "dry_run": False,
        "retention_days": retention_days,
        "cutoff": cutoff,
        "purged_count": purged_count,
        "purged_images": total_images_purged,
    }


def empty_all_trash(user=None) -> dict:
    """
    Purges all products currently in the trash (is_deleted=True) regardless of deletion age.
    """
    all_trash = list(Product.objects.filter(is_deleted=True).prefetch_related("images"))
    purged_count = 0
    total_images_purged = 0

    for product in all_trash:
        res = purge_product_and_media(product, user=user)
        purged_count += 1
        total_images_purged += res.get("images_purged", 0)

    return {
        "purged_count": purged_count,
        "purged_images": total_images_purged,
    }
