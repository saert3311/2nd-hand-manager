import gzip
import os
import sqlite3
import tempfile
from datetime import datetime
from datetime import timezone as dt_timezone
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import BackupStatus, BackupTriggerType, DatabaseBackupLog
from inventory.services.backup_service import (
    backup_database,
    get_backup_storage,
    parse_backup_timestamp,
    prune_old_backups,
)

User = get_user_model()


class DatabaseBackupLogModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="manager1",
            password="password123",
            email="manager1@example.com",
        )

    def test_create_backup_log_defaults(self):
        """Test creating a backup log with default values."""
        log = DatabaseBackupLog.objects.create(
            filename="db_20261014_030000.sqlite3.gz",
            remote_path="backups/db/2026/10/db_20261014_030000.sqlite3.gz",
            file_size=2048576,
            duration_seconds=1.25,
        )
        self.assertEqual(log.status, BackupStatus.SUCCESS)
        self.assertEqual(log.trigger_type, BackupTriggerType.SCHEDULED)
        self.assertIsNone(log.triggered_by)
        self.assertEqual(log.error_message, "")
        self.assertIsNotNone(log.created_at)

    def test_create_manual_failed_backup_log(self):
        """Test creating a manual backup log that failed with error message."""
        log = DatabaseBackupLog.objects.create(
            filename="db_20261014_120000.sqlite3.gz",
            remote_path="",
            file_size=0,
            duration_seconds=0.45,
            status=BackupStatus.FAILED,
            trigger_type=BackupTriggerType.MANUAL,
            triggered_by=self.user,
            error_message="OCI Object Storage connection timeout",
        )
        self.assertEqual(log.status, BackupStatus.FAILED)
        self.assertEqual(log.trigger_type, BackupTriggerType.MANUAL)
        self.assertEqual(log.triggered_by, self.user)
        self.assertEqual(log.error_message, "OCI Object Storage connection timeout")

    def test_string_representation(self):
        """Test __str__ representation formatted with filename, status and timestamp."""
        log = DatabaseBackupLog.objects.create(
            filename="db_20261014_030000.sqlite3.gz",
            remote_path="backups/db/2026/10/db_20261014_030000.sqlite3.gz",
            file_size=1024,
            status=BackupStatus.SUCCESS,
        )
        expected_str = f"db_20261014_030000.sqlite3.gz - Success ({log.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
        self.assertEqual(str(log), expected_str)

    def test_string_representation_empty_filename(self):
        """Test __str__ when filename is empty."""
        log = DatabaseBackupLog.objects.create(
            filename="",
            remote_path="",
            status=BackupStatus.FAILED,
        )
        self.assertIn("Backup - Failed", str(log))

    def test_ordering(self):
        """Test that logs are ordered newest first (-created_at)."""
        log1 = DatabaseBackupLog.objects.create(filename="db_first.sqlite3.gz")
        log2 = DatabaseBackupLog.objects.create(filename="db_second.sqlite3.gz")
        logs = list(DatabaseBackupLog.objects.all()[:2])
        self.assertEqual(logs[0].pk, log2.pk)
        self.assertEqual(logs[1].pk, log1.pk)

    def test_file_size_display(self):
        """Test human-readable file size conversion."""
        log_b = DatabaseBackupLog(file_size=500)
        self.assertEqual(log_b.file_size_display, "500 B")

        log_kb = DatabaseBackupLog(file_size=1024 * 50)
        self.assertEqual(log_kb.file_size_display, "50.0 KB")

        log_mb = DatabaseBackupLog(file_size=1024 * 1024 * 3 + 512 * 1024)
        self.assertEqual(log_mb.file_size_display, "3.5 MB")

        log_gb = DatabaseBackupLog(file_size=1024 * 1024 * 1024 * 2)
        self.assertEqual(log_gb.file_size_display, "2.00 GB")


class BackupTimestampParsingTests(TestCase):
    def test_parse_valid_compressed_filename(self):
        ts = parse_backup_timestamp("db_20261014_030000.sqlite3.gz")
        self.assertEqual(ts, datetime(2026, 10, 14, 3, 0, 0, tzinfo=dt_timezone.utc))

    def test_parse_valid_uncompressed_filename(self):
        ts = parse_backup_timestamp("db_20260501_183045.sqlite3")
        self.assertEqual(ts, datetime(2026, 5, 1, 18, 30, 45, tzinfo=dt_timezone.utc))

    def test_parse_with_directory_prefix(self):
        ts = parse_backup_timestamp("backups/db/2026/10/db_20261014_030000.sqlite3.gz")
        self.assertEqual(ts, datetime(2026, 10, 14, 3, 0, 0, tzinfo=dt_timezone.utc))

    def test_parse_invalid_filename(self):
        self.assertIsNone(parse_backup_timestamp("random_file.sqlite3"))
        self.assertIsNone(parse_backup_timestamp(""))
        self.assertIsNone(parse_backup_timestamp("db_invalid.gz"))


class GetBackupStorageTests(TestCase):
    def test_custom_storage_override(self):
        custom = InMemoryStorage()
        storage = get_backup_storage(custom_storage=custom)
        self.assertIs(storage, custom)

    def test_local_only_returns_none(self):
        storage = get_backup_storage(local_only=True)
        self.assertIsNone(storage)

    @override_settings(
        OCI_STORAGE_BUCKET_NAME="my-bucket",
        OCI_STORAGE_ACCESS_KEY="my-key",
        OCI_STORAGE_SECRET_KEY="my-secret",
    )
    def test_oci_storage_configured(self):
        storage = get_backup_storage()
        from inventory.services.storage import OCIObjectStorage
        self.assertIsInstance(storage, OCIObjectStorage)


class PruneOldBackupsTests(TestCase):
    def test_prune_in_memory_storage(self):
        storage = InMemoryStorage()
        # Old backup (40 days ago)
        old_key = "backups/db/2026/09/db_20260901_000000.sqlite3.gz"
        # Recent backup (2 days ago)
        recent_key = "backups/db/2026/10/db_20261012_000000.sqlite3.gz"

        storage.save(old_key, ContentFile(b"old-data"))
        storage.save(recent_key, ContentFile(b"recent-data"))

        pruned = prune_old_backups(retention_days=30, storage=storage)
        self.assertIn(old_key, pruned)
        self.assertNotIn(recent_key, pruned)
        self.assertFalse(storage.exists(old_key))
        self.assertTrue(storage.exists(recent_key))

    def test_prune_boto3_mock_bucket(self):
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.bucket = mock_bucket

        obj_old = MagicMock()
        obj_old.key = "backups/db/2026/08/db_20260801_000000.sqlite3.gz"

        obj_recent = MagicMock()
        obj_recent.key = "backups/db/2026/10/db_20261014_000000.sqlite3.gz"

        mock_bucket.objects.filter.return_value = [obj_old, obj_recent]

        pruned = prune_old_backups(retention_days=30, storage=mock_storage)
        self.assertIn(obj_old.key, pruned)
        self.assertNotIn(obj_recent.key, pruned)
        obj_old.delete.assert_called_once()
        obj_recent.delete.assert_not_called()

    def test_prune_dry_run_does_not_delete(self):
        storage = InMemoryStorage()
        old_key = "backups/db/2026/09/db_20260901_000000.sqlite3.gz"
        storage.save(old_key, ContentFile(b"old-data"))

        pruned = prune_old_backups(retention_days=30, storage=storage, dry_run=True)
        self.assertIn(old_key, pruned)
        self.assertTrue(storage.exists(old_key))


class BackupDatabaseServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="manager_service",
            password="password123",
            email="manager_service@example.com",
        )
        self.storage = InMemoryStorage()

    def test_backup_database_compressed_success(self):
        """Test creating a full gzip-compressed hot backup in storage."""
        log = backup_database(storage=self.storage, retention_days=30, compress=True)

        self.assertEqual(log.status, BackupStatus.SUCCESS)
        self.assertTrue(log.filename.endswith(".sqlite3.gz"))
        self.assertGreater(log.file_size, 0)
        self.assertEqual(log.error_message, "")
        self.assertIsNotNone(log.pk)

        # Verify the file is in storage and is a valid gzipped SQLite database
        self.assertTrue(self.storage.exists(log.remote_path))
        with self.storage.open(log.remote_path, "rb") as f:
            decompressed = gzip.decompress(f.read())
            self.assertGreater(len(decompressed), 0)

            # Test sqlite integrity by opening the decompressed bytes
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
                tmp.write(decompressed)
                tmp_path = tmp.name

            try:
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                self.assertEqual(cursor.fetchone()[0], 1)
                conn.close()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def test_backup_database_uncompressed(self):
        """Test backup without compression produces raw .sqlite3 archive."""
        log = backup_database(storage=self.storage, compress=False)

        self.assertEqual(log.status, BackupStatus.SUCCESS)
        self.assertTrue(log.filename.endswith(".sqlite3"))
        self.assertFalse(log.filename.endswith(".gz"))
        self.assertTrue(self.storage.exists(log.remote_path))

    def test_backup_database_dry_run(self):
        """Test dry run mode does not write to storage or create DB record."""
        log = backup_database(storage=self.storage, dry_run=True)

        self.assertEqual(log.status, BackupStatus.SUCCESS)
        self.assertIsNone(log.pk)  # Not saved to DB
        self.assertFalse(self.storage.exists(log.remote_path))

    def test_backup_database_manual_trigger(self):
        """Test backup with manual trigger and user attribution."""
        log = backup_database(
            storage=self.storage,
            trigger_type=BackupTriggerType.MANUAL,
            triggered_by=self.user,
        )
        self.assertEqual(log.trigger_type, BackupTriggerType.MANUAL)
        self.assertEqual(log.triggered_by, self.user)

    def test_backup_database_local_only(self):
        """Test local_only mode writes backup into BASE_DIR / backups."""
        log = backup_database(local_only=True)

        self.assertEqual(log.status, BackupStatus.SUCCESS)
        self.assertTrue(os.path.exists(log.remote_path))

        # Cleanup local test backup
        try:
            if os.path.exists(log.remote_path):
                os.remove(log.remote_path)
        except OSError:
            pass

    @patch("inventory.services.backup_service.sqlite3.connect")
    def test_backup_database_sqlite_exception(self, mock_connect):
        """Test handling SQLite connection or backup exception gracefully."""
        mock_connect.side_effect = sqlite3.OperationalError("Database disk image is malformed")

        log = backup_database(storage=self.storage)

        self.assertEqual(log.status, BackupStatus.FAILED)
        self.assertIn("OperationalError", log.error_message)
        self.assertIn("Database disk image is malformed", log.error_message)
        self.assertEqual(log.file_size, 0)
        self.assertIsNotNone(log.pk)

    @override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "mydb"}})
    def test_backup_database_unsupported_engine(self):
        """Test attempting backup on non-SQLite database logs failure."""
        log = backup_database(storage=self.storage)

        self.assertEqual(log.status, BackupStatus.FAILED)
        self.assertIn("Automated backups only support SQLite engines", log.error_message)


class BackupDbCommandTests(TestCase):
    def test_command_dry_run_local(self):
        """Test backup_db --dry-run --local-only outputs success message."""
        out = StringIO()
        call_command("backup_db", "--dry-run", "--local-only", stdout=out)
        output = out.getvalue()
        self.assertIn("[DRY RUN]", output)
        self.assertIn("Successfully created database backup", output)
        self.assertIn(".sqlite3.gz", output)

    def test_command_quiet_mode(self):
        """Test backup_db --quiet suppresses stdout."""
        out = StringIO()
        call_command("backup_db", "--dry-run", "--local-only", "--quiet", stdout=out)
        self.assertEqual(out.getvalue(), "")

    def test_command_no_compress(self):
        """Test backup_db --no-compress creates uncompressed filename."""
        out = StringIO()
        call_command("backup_db", "--dry-run", "--local-only", "--no-compress", stdout=out)
        output = out.getvalue()
        self.assertIn(".sqlite3", output)
        self.assertNotIn(".sqlite3.gz", output)

    @patch("inventory.management.commands.backup_db.backup_database")
    def test_command_retention_days_passed(self, mock_backup):
        """Test --retention-days argument is passed to service."""
        mock_backup.return_value = DatabaseBackupLog(
            filename="db_mock.sqlite3.gz",
            file_size=1024,
            duration_seconds=0.1,
            status=BackupStatus.SUCCESS,
            remote_path="backups/mock",
        )
        call_command("backup_db", "--dry-run", "--retention-days=15", "--quiet")
        mock_backup.assert_called_once_with(
            retention_days=15,
            compress=True,
            local_only=False,
            dry_run=True,
            trigger_type=BackupTriggerType.SCHEDULED,
        )

    @patch("inventory.management.commands.backup_db.backup_database")
    def test_command_failure_raises_command_error(self, mock_backup):
        """Test command failure raises CommandError with error message."""
        mock_backup.return_value = DatabaseBackupLog(
            filename="",
            file_size=0,
            duration_seconds=0.2,
            status=BackupStatus.FAILED,
            error_message="Storage bucket unavailable",
        )
        with self.assertRaises(CommandError) as ctx:
            call_command("backup_db", "--quiet")
        self.assertIn("Storage bucket unavailable", str(ctx.exception))


class DatabaseBackupAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        from inventory.permissions import ROLE_ASSISTANT, ROLE_MANAGER

        self.manager_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.assistant_group, _ = Group.objects.get_or_create(name=ROLE_ASSISTANT)

        self.manager = User.objects.create_user(
            username="manager_admin",
            password="password123",
            is_staff=True,
        )
        self.manager.groups.add(self.manager_group)

        self.assistant = User.objects.create_user(
            username="assistant_user",
            password="password123",
            is_staff=False,
        )
        self.assistant.groups.add(self.assistant_group)

    def test_changelist_accessible_to_manager(self):
        """Test manager can view DatabaseBackupLog changelist with on-demand trigger button."""
        self.client.force_login(self.manager)
        url = reverse("admin:inventory_databasebackuplog_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Backup Now")

    def test_changelist_forbidden_to_assistant(self):
        """Test assistant is forbidden (403) from accessing admin changelist."""
        self.client.force_login(self.assistant)
        url = reverse("admin:inventory_databasebackuplog_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_trigger_backup_view_get_renders_confirmation(self):
        """Test GET on trigger_backup renders confirmation page."""
        self.client.force_login(self.manager)
        url = reverse("admin:inventory_databasebackuplog_trigger_backup")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create On-Demand Database Backup")
        self.assertContains(response, "Yes, Create Backup Now")

    @patch("inventory.admin.backup_database")
    def test_trigger_backup_view_post_creates_manual_backup(self, mock_backup):
        """Test POST on trigger_backup invokes backup_database with manual trigger type."""
        mock_backup.return_value = DatabaseBackupLog.objects.create(
            filename="db_manual.sqlite3.gz",
            file_size=512000,
            duration_seconds=0.35,
            status=BackupStatus.SUCCESS,
            trigger_type=BackupTriggerType.MANUAL,
            triggered_by=self.manager,
        )
        self.client.force_login(self.manager)
        url = reverse("admin:inventory_databasebackuplog_trigger_backup")
        response = self.client.post(url)
        self.assertRedirects(response, reverse("admin:inventory_databasebackuplog_changelist"))
        mock_backup.assert_called_once_with(
            trigger_type=BackupTriggerType.MANUAL,
            triggered_by=self.manager,
        )

    def test_failure_banner_rendered_when_latest_backup_failed(self):
        """Test admin pages render warning banner when the last backup failed."""
        DatabaseBackupLog.objects.create(
            filename="db_failed.sqlite3.gz",
            status=BackupStatus.FAILED,
            error_message="OCI Object Storage 503 Service Unavailable",
        )
        self.client.force_login(self.manager)
        url = reverse("admin:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "backup-failure-alert")
        self.assertContains(response, "Warning: The most recent automated database backup failed!")
        self.assertContains(response, "OCI Object Storage 503 Service Unavailable")

    def test_failure_banner_hidden_when_latest_backup_succeeded(self):
        """Test admin pages do NOT render warning banner when the last backup succeeded."""
        # Create an older failed backup
        DatabaseBackupLog.objects.create(
            filename="db_old_failed.sqlite3.gz",
            status=BackupStatus.FAILED,
            error_message="Old error",
        )
        # Create a newer successful backup
        DatabaseBackupLog.objects.create(
            filename="db_recent_success.sqlite3.gz",
            status=BackupStatus.SUCCESS,
        )
        self.client.force_login(self.manager)
        url = reverse("admin:index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "backup-failure-alert")


