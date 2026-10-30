import logging

from django.core.management.base import BaseCommand

from inventory.services.trash_service import (
    empty_all_trash,
    get_trash_retention_days,
    purge_expired_trash,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Purges soft-deleted products and their photos from cloud storage after the retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override trash retention threshold in days (defaults to TRASH_RETENTION_DAYS, e.g. 30).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Purge ALL soft-deleted products immediately regardless of deletion age.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate purge without deleting database records or cloud storage files.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress standard console output (recommended for automated cron execution).",
        )

    def handle(self, *args, **options):
        days = options.get("days")
        purge_all = options.get("all", False)
        dry_run = options.get("dry_run", False)
        quiet = options.get("quiet", False)

        if purge_all and dry_run:
            from inventory.models import Product, ProductImage

            all_trash_count = Product.objects.filter(is_deleted=True).count()
            all_images_count = ProductImage.objects.filter(product__is_deleted=True).count()
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Would purge ALL {all_trash_count} soft-deleted products and "
                        f"{all_images_count} photos from cloud storage."
                    )
                )
            return

        if purge_all:
            results = empty_all_trash()
            purged_count = results["purged_count"]
            purged_images = results["purged_images"]
            if not quiet:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully purged ALL {purged_count} soft-deleted products and "
                        f"{purged_images} photos from cloud storage."
                    )
                )
            return

        effective_days = days if days is not None else get_trash_retention_days()
        results = purge_expired_trash(days=days, dry_run=dry_run)

        if dry_run:
            eligible_count = results["eligible_count"]
            eligible_images = results["eligible_images"]
            if not quiet:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY RUN] Found {eligible_count} products (older than {effective_days} days) "
                        f"with {eligible_images} photos eligible for permanent purge."
                    )
                )
        else:
            purged_count = results["purged_count"]
            purged_images = results["purged_images"]
            if not quiet:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully purged {purged_count} expired products (older than {effective_days} days) "
                        f"and {purged_images} photos from cloud storage."
                    )
                )
