from django.core.management.base import BaseCommand, CommandError

from inventory.models import BackupStatus, BackupTriggerType
from inventory.services.backup_service import backup_database


class Command(BaseCommand):
    help = "Creates a hot, consistent backup of the SQLite database and uploads it to OCI Object Storage with retention pruning."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=None,
            help="Number of days to retain backups before pruning (defaults to DB_BACKUP_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--no-compress",
            action="store_true",
            help="Disable gzip compression and store raw .sqlite3 archive.",
        )
        parser.add_argument(
            "--local-only",
            action="store_true",
            help="Save backup strictly to local filesystem (backups/ directory) without cloud upload.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate database backup and retention pruning without writing files or creating audit logs.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress standard console output (recommended for cron execution).",
        )

    def handle(self, *args, **options):
        retention_days = options.get("retention_days")
        compress = not options.get("no_compress", False)
        local_only = options.get("local_only", False)
        dry_run = options.get("dry_run", False)
        quiet = options.get("quiet", False)

        log = backup_database(
            retention_days=retention_days,
            compress=compress,
            local_only=local_only,
            dry_run=dry_run,
            trigger_type=BackupTriggerType.SCHEDULED,
        )

        if log.status == BackupStatus.FAILED:
            error_message = log.error_message or "Unknown backup error"
            if not quiet:
                self.stderr.write(self.style.ERROR(f"Database backup failed: {error_message}"))
            raise CommandError(f"Database backup failed: {error_message}")

        if not quiet:
            prefix = "[DRY RUN] " if dry_run else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prefix}Successfully created database backup: {log.filename} "
                    f"({log.file_size_display}, {log.duration_seconds:.2f}s)"
                )
            )
            self.stdout.write(f"Destination: {log.remote_path}")
