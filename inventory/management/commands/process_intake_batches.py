from django.core.management.base import BaseCommand

from inventory.services.intake_batch_service import (
    get_debounce_minutes,
    process_pending_intake_batches,
)


class Command(BaseCommand):
    help = "Processes expired intake upload sessions and dispatches consolidated Web Push notifications to managers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--debounce-minutes",
            type=int,
            default=None,
            help="Override inactivity window threshold in minutes (defaults to INTAKE_SESSION_DEBOUNCE_MINUTES).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate batch processing without sending Web Push alerts or updating database records.",
        )
        parser.add_argument(
            "--no-notify",
            action="store_true",
            help="Close expired batch sessions without dispatching Web Push alerts.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress standard console output (recommended for cron execution).",
        )

    def handle(self, *args, **options):
        debounce_minutes = options.get("debounce_minutes")
        dry_run = options.get("dry_run", False)
        no_notify = options.get("no_notify", False)
        quiet = options.get("quiet", False)

        effective_debounce = debounce_minutes if debounce_minutes is not None else get_debounce_minutes()

        results = process_pending_intake_batches(
            debounce_minutes=debounce_minutes,
            dry_run=dry_run,
            notify_managers=not no_notify,
        )

        if not quiet:
            prefix = "[DRY RUN] " if dry_run else ""
            if not results:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{prefix}No expired intake batch sessions found (window: {effective_debounce} min)."
                    )
                )
            else:
                total_products = sum(r["product_count"] for r in results)
                total_sent = sum(r["sent_notifications"] for r in results)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{prefix}Processed {len(results)} intake batch session(s) "
                        f"with {total_products} product(s). "
                        f"Dispatched {total_sent} push notification(s) to store managers."
                    )
                )
                for r in results:
                    self.stdout.write(
                        f"  - Session #{r['session_id']} by {r['assistant_display']}: "
                        f"{r['product_count']} items (last active: {r['last_activity_at']:%Y-%m-%d %H:%M:%S})"
                    )
