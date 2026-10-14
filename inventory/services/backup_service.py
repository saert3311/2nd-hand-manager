import gzip
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime
from datetime import timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from inventory.models import BackupStatus, BackupTriggerType, DatabaseBackupLog

logger = logging.getLogger(__name__)

BACKUP_FILENAME_REGEX = re.compile(
    r"db_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.sqlite3(?:\.gz)?$"
)


def parse_backup_timestamp(filename_or_key: str) -> datetime | None:
    """
    Extract UTC datetime from a backup archive filename or remote storage key.
    Expected pattern: db_YYYYMMDD_HHMMSS.sqlite3[.gz]
    """
    basename = os.path.basename(filename_or_key)
    match = BACKUP_FILENAME_REGEX.search(basename)
    if not match:
        return None
    year, month, day, hour, minute, second = map(int, match.groups())
    return datetime(year, month, day, hour, minute, second, tzinfo=dt_timezone.utc)


def get_backup_storage(local_only: bool = False, custom_storage=None):
    """
    Determine the storage backend to use for database backups.
    Returns None if local-only is specified or if no cloud credentials exist.
    """
    if custom_storage is not None:
        return custom_storage
    if local_only:
        return None

    # Check for configured OCI credentials
    if (
        getattr(settings, "OCI_STORAGE_BUCKET_NAME", None)
        and getattr(settings, "OCI_STORAGE_ACCESS_KEY", None)
        and getattr(settings, "OCI_STORAGE_SECRET_KEY", None)
    ):
        from .storage import OCIObjectStorage

        return OCIObjectStorage()

    # In testing environment or when custom backend is in STORAGES
    if getattr(settings, "IS_TESTING", False):
        return default_storage

    return None


def walk_storage_files(storage, base_path: str = ""):
    """Recursively list all file paths in any Django Storage backend."""
    try:
        dirs, files = storage.listdir(base_path)
    except Exception as exc:
        logger.debug("Error listing storage path %s: %s", base_path, exc)
        return

    for file in files:
        yield f"{base_path}/{file}".lstrip("/")
    for directory in dirs:
        sub_path = f"{base_path}/{directory}".lstrip("/")
        yield from walk_storage_files(storage, sub_path)


def prune_old_backups(
    retention_days: int | None = None,
    storage=None,
    local_only: bool = False,
    dry_run: bool = False,
    prefix: str | None = None,
) -> list[str]:
    """
    Prune backup snapshots older than the specified retention window (in days).
    Returns a list of pruned filenames/paths.
    """
    if retention_days is None:
        retention_days = getattr(settings, "DB_BACKUP_RETENTION_DAYS", 30)

    if retention_days <= 0:
        return []

    cutoff = timezone.now() - timezone.timedelta(days=retention_days)
    pruned: list[str] = []

    # 1. Local filesystem pruning (when local_only=True or storage is None)
    if local_only or storage is None:
        local_dir = Path(settings.BASE_DIR) / "backups"
        if not local_dir.exists():
            return []

        for root, _, files in os.walk(local_dir):
            for file in files:
                file_path = os.path.join(root, file)
                ts = parse_backup_timestamp(file)
                if ts and ts < cutoff:
                    pruned.append(file_path)
                    if not dry_run:
                        try:
                            os.remove(file_path)
                            logger.info("Pruned old local backup: %s", file_path)
                        except OSError as exc:
                            logger.warning("Failed to delete local backup %s: %s", file_path, exc)
        return pruned

    # 2. Remote storage pruning (OCI / S3 boto3 backend)
    if hasattr(storage, "bucket") and storage.bucket is not None:
        base_prefix = prefix or getattr(settings, "DB_BACKUP_PREFIX", "backups/db/").strip("/")
        try:
            for obj in storage.bucket.objects.filter(Prefix=base_prefix):
                ts = parse_backup_timestamp(obj.key)
                if ts and ts < cutoff:
                    pruned.append(obj.key)
                    if not dry_run:
                        obj.delete()
                        logger.info("Pruned old remote backup: %s", obj.key)
        except Exception as exc:
            logger.warning("Error pruning remote backups with boto3 bucket: %s", exc)
        return pruned

    # 3. General Django storage pruning (InMemoryStorage, FileSystemStorage, etc.)
    base_prefix = prefix or getattr(settings, "DB_BACKUP_PREFIX", "backups/db/").strip("/")
    for file_path in walk_storage_files(storage, ""):
        if base_prefix and not file_path.startswith(base_prefix):
            continue
        ts = parse_backup_timestamp(file_path)
        if ts and ts < cutoff:
            pruned.append(file_path)
            if not dry_run:
                try:
                    storage.delete(file_path)
                    logger.info("Pruned old backup from storage: %s", file_path)
                except Exception as exc:
                    logger.warning("Failed to delete %s from storage: %s", file_path, exc)
    return pruned


def backup_database(
    retention_days: int | None = None,
    compress: bool = True,
    local_only: bool = False,
    dry_run: bool = False,
    trigger_type: str = BackupTriggerType.SCHEDULED,
    triggered_by=None,
    storage=None,
) -> DatabaseBackupLog:
    """
    Execute a consistent, zero-downtime hot backup of the SQLite database.

    1. Obtains the SQLite database file path from settings.
    2. Uses sqlite3.Connection.backup() to create an uncorrupted point-in-time copy.
    3. Optionally compresses the snapshot using gzip (.sqlite3.gz).
    4. Transfers archive to OCI Object Storage (or local backups/ directory).
    5. Prunes backups older than retention_days.
    6. Logs the operation to DatabaseBackupLog.
    """
    start_time = time.time()
    now = timezone.now()

    if retention_days is None:
        retention_days = getattr(settings, "DB_BACKUP_RETENTION_DAYS", 30)

    # Resolve database location
    db_config = settings.DATABASES.get("default", {})
    engine = db_config.get("ENGINE", "")
    db_name = db_config.get("NAME")

    if not db_name or ("sqlite" not in engine and not str(db_name).endswith((".sqlite", ".sqlite3", ".db"))):
        duration = round(time.time() - start_time, 2)
        error_msg = f"Automated backups only support SQLite engines (configured: {engine})"
        logger.error(error_msg)
        if dry_run:
            return DatabaseBackupLog(
                filename="",
                remote_path="",
                file_size=0,
                duration_seconds=duration,
                status=BackupStatus.FAILED,
                trigger_type=trigger_type,
                triggered_by=triggered_by,
                error_message=error_msg,
            )
        return DatabaseBackupLog.objects.create(
            filename="",
            remote_path="",
            file_size=0,
            duration_seconds=duration,
            status=BackupStatus.FAILED,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            error_message=error_msg,
        )

    db_path = Path(db_name)
    if not db_path.is_absolute():
        db_path = Path(settings.BASE_DIR) / db_path

    # Construct filenames and paths
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    base_filename = f"db_{timestamp_str}.sqlite3"
    archive_filename = f"{base_filename}.gz" if compress else base_filename
    date_path = now.strftime("%Y/%m")
    base_prefix = getattr(settings, "DB_BACKUP_PREFIX", "backups/db/").strip("/")
    remote_key = f"{base_prefix}/{date_path}/{archive_filename}" if base_prefix else f"{date_path}/{archive_filename}"

    temp_dir = tempfile.mkdtemp(prefix="sqlite_backup_")

    try:
        raw_temp_path = os.path.join(temp_dir, base_filename)

        # 1. Atomic Hot Backup using sqlite3.Connection.backup()
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(raw_temp_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        # 2. Compression Pipeline
        if compress:
            compressed_temp_path = os.path.join(temp_dir, archive_filename)
            with open(raw_temp_path, "rb") as f_in, gzip.open(
                compressed_temp_path, "wb", compresslevel=9
            ) as f_out:
                shutil.copyfileobj(f_in, f_out)
            final_backup_path = compressed_temp_path
        else:
            final_backup_path = raw_temp_path

        file_size = os.path.getsize(final_backup_path)

        # 3. Storage Resolution
        active_storage = get_backup_storage(local_only=local_only, custom_storage=storage)

        # 4. Dry-run Mode Check
        if dry_run:
            duration = round(time.time() - start_time, 2)
            pruned_items = prune_old_backups(
                retention_days=retention_days,
                storage=active_storage,
                local_only=local_only,
                dry_run=True,
                prefix=base_prefix,
            )
            logger.info(
                "Dry run backup completed: file=%s, size=%d bytes, duration=%.2fs, would prune %d items",
                archive_filename,
                file_size,
                duration,
                len(pruned_items),
            )
            return DatabaseBackupLog(
                filename=archive_filename,
                remote_path=remote_key if active_storage is not None else f"backups/{date_path}/{archive_filename}",
                file_size=file_size,
                duration_seconds=duration,
                status=BackupStatus.SUCCESS,
                trigger_type=trigger_type,
                triggered_by=triggered_by,
                error_message="",
            )

        # 5. Persist Backup File
        if active_storage is not None:
            with open(final_backup_path, "rb") as f:
                saved_key = active_storage.save(remote_key, ContentFile(f.read()))
            final_path = saved_key
            logger.info("Database backup uploaded to cloud storage: %s (%d bytes)", saved_key, file_size)
        else:
            local_target_dir = Path(settings.BASE_DIR) / "backups" / date_path
            local_target_dir.mkdir(parents=True, exist_ok=True)
            local_target_file = local_target_dir / archive_filename
            shutil.copy2(final_backup_path, local_target_file)
            final_path = str(local_target_file)
            logger.info("Database backup saved locally: %s (%d bytes)", final_path, file_size)

        # 6. Retention Pruning
        prune_old_backups(
            retention_days=retention_days,
            storage=active_storage,
            local_only=local_only,
            dry_run=False,
            prefix=base_prefix,
        )

        duration = round(time.time() - start_time, 2)

        # 7. Audit Log Entry
        log = DatabaseBackupLog.objects.create(
            filename=archive_filename,
            remote_path=final_path,
            file_size=file_size,
            duration_seconds=duration,
            status=BackupStatus.SUCCESS,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            error_message="",
        )
        return log

    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.exception("Database backup failed: %s", error_msg)

        if dry_run:
            return DatabaseBackupLog(
                filename=archive_filename if "archive_filename" in locals() else "",
                remote_path="",
                file_size=0,
                duration_seconds=duration,
                status=BackupStatus.FAILED,
                trigger_type=trigger_type,
                triggered_by=triggered_by,
                error_message=error_msg,
            )

        log = DatabaseBackupLog.objects.create(
            filename=archive_filename if "archive_filename" in locals() else "",
            remote_path="",
            file_size=0,
            duration_seconds=duration,
            status=BackupStatus.FAILED,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            error_message=error_msg,
        )
        return log

    finally:
        # Clean up temporary working directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
