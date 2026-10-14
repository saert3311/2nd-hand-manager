# Product Requirements Document (PRD): SQLite Automated Cloud Backup to OCI Object Storage

## 1. Executive Summary
Implement an automated, zero-downtime, daily backup system for the application's primary SQLite database file (`db.sqlite3`), transferring compressed, timestamped point-in-time snapshots directly into our Oracle Cloud Infrastructure (OCI) Object Storage bucket. Backups utilize SQLite's native online backup API to guarantee database consistency without locking concurrent web transactions or risking partial write corruption. The feature includes automated retention pruning (default 30 days), a CLI management command (`python manage.py backup_db`), audit logging in Django Administration (`DatabaseBackupLog`), and support for on-demand backups triggered by store managers.

---

## 2. Problem Statement
1. **Critical Single Point of Failure:** The 2ndHand Staging Hub persists all domain records—intake notes, inventory listings, pricing, marketplace links, AI prompt configurations, and clarification threads—in a local SQLite database (`db.sqlite3`).
2. **Disaster Recovery Risk:** Without automated off-site backups, server hardware failure, filesystem corruption, or accidental Docker volume deletion results in permanent, catastrophic loss of cataloging and sales data.
3. **Hot-Backup Integrity Risk:** Directly copying an active SQLite file (`cp db.sqlite3 ...`) while Django processes write to it can produce corrupted copies due to torn pages or half-committed WAL (Write-Ahead Logging) transactions.
4. **Storage Accumulation:** Unmonitored daily backups will consume unbounded cloud storage over time without an automated lifecycle retention policy.

---

## 3. User Personas & Scenarios

### Persona 1: Store Manager / Business Owner (User B)
- **Scenario 1 (Peace of Mind & Visibility):** The manager logs into Django Administration (`/admin/`) and reviews the "Database Backups" log table to verify that the daily automated backup ran successfully overnight, viewing timestamp, compressed file size, duration, and cloud storage URI.
- **Scenario 2 (Pre-Maintenance On-Demand Backup):** Before performing bulk product updates or administrative user changes, the manager triggers a manual "Backup Database Now" action from Django Admin to capture an immediate restore point.
- **Scenario 3 (Disaster Recovery):** Following a server migration or system failure, the manager or sysadmin can download the latest snapshot from OCI Object Storage, decompress it, and restore full operational state in minutes.

### Persona 2: Sourcing Assistant (User A)
- **Scenario (Uninterrupted Operations):** While the backup runs (e.g. at 03:00 UTC or mid-day), assistants continue cataloging intake items, answering clarification doubts, and uploading images without experiencing lockouts, timeouts, or 500 errors.

### Persona 3: DevOps / Automation Runner
- **Scenario (Headless Scheduling):** A scheduled task (cron job, systemd timer, or container runner) executes `python manage.py backup_db` once daily. The command completes cleanly, prunes snapshots older than 30 days from the bucket, and records structured execution metrics.

---

## 4. Scope & Functional Requirements

### 4.1 Online Hot-Backup Service (`inventory/services/backup_service.py`)
- **Native Online Backup API:**
  - Opens a connection to the active SQLite database.
  - Uses `sqlite3.Connection.backup()` to copy database pages into a temporary file.
  - Guarantees ACID consistency across concurrent writes without locking out web requests.
- **Gzip Compression:**
  - Compresses the backup snapshot using Python's standard library `gzip`.
  - Typical SQLite text/metadata compression ratio is 75–90%, reducing a 10MB database to ~1–2MB.
  - Snapshot naming convention: `db_%Y%m%d_%H%M%S.sqlite3.gz`.
- **Cloud Storage Upload:**
  - Uploads the compressed file directly to the configured OCI Object Storage bucket using the existing `OCIObjectStorage` backend or boto3 S3 client.
  - Remote storage prefix: `backups/db/%Y/%m/db_%Y%m%d_%H%M%S.sqlite3.gz` (configurable via `DB_BACKUP_PREFIX`).
- **Retention Lifecycle & Pruning:**
  - After a successful upload, queries existing objects under the backup prefix.
  - Deletes backups whose creation timestamp exceeds the retention window (`DB_BACKUP_RETENTION_DAYS`, default 30 days).
- **Execution Summary:**
  - Returns a dataclass `BackupResult(success=True/False, filename=..., file_size=..., duration_seconds=..., remote_url=..., pruned_count=..., error=...)`.

### 4.2 Django Management Command (`inventory/management/commands/backup_db.py`)
- Executable via standard Django CLI:
  `python manage.py backup_db`
- Supported Arguments:
  - `--retention-days <N>`: Custom retention window in days (defaults to `settings.DB_BACKUP_RETENTION_DAYS` or 30).
  - `--no-compress`: Store raw uncompressed `.sqlite3` file.
  - `--local-only`: Store backup in a local directory (`backups/`) without uploading to cloud (useful for offline environments).
  - `--dry-run`: Simulate backup and retention pruning without writing to cloud storage or deleting old backups.
  - `--quiet`: Suppress stdout output, suitable for silent cron jobs.
- Return exit code 0 on success, 1 on failure.

### 4.3 Database Backup Audit Log (`DatabaseBackupLog`)
- Model tracking backup history in Django:
  | Field | Type | Description |
  |---|---|---|
  | `id` | AutoField | Unique record ID |
  | `filename` | CharField(255) | Name of the backup file (e.g. `db_20261014_030000.sqlite3.gz`) |
  | `remote_path` | CharField(500) | Full object key path in OCI Object Storage |
  | `file_size` | BigIntegerField | Compressed file size in bytes |
  | `duration_seconds` | FloatField | Execution time in seconds |
  | `status` | CharField(20) | `success` or `failed` |
  | `trigger_type` | CharField(20) | `scheduled` (cron/CLI) or `manual` (admin UI) |
  | `triggered_by` | ForeignKey(User) | User who triggered the backup (null for scheduled/CLI) |
  | `error_message` | TextField | Error details if backup failed |
  | `created_at` | DateTimeField | Timestamp when backup occurred |

### 4.4 Django Admin Management (`DatabaseBackupLogAdmin`)
- Registered under `ManagerAdminSite` (restricted exclusively to `is_manager(user)`).
- List view shows: Status badge (`Success` / `Failed`), Timestamp, Filename, Size (formatted in KB/MB), Duration, Trigger Type, and Triggered By.
- Custom Admin Action / View: "Crear copia de seguridad ahora" / "Backup Database Now" button allowing managers to trigger an immediate hot backup.
- Read-only historical entries to maintain audit log integrity.

### 4.5 Configuration & Environment Variables (`config/settings.py` & `.env.example`)
- Settings variables:
  - `DB_BACKUP_ENABLED`: Boolean toggle (defaults to `True` when OCI Object Storage credentials are present).
  - `DB_BACKUP_RETENTION_DAYS`: Retention period in days (default: 30).
  - `DB_BACKUP_PREFIX`: Storage key prefix (default: `backups/db/`).
  - `DB_BACKUP_COMPRESSION`: Boolean toggle for gzip compression (default: `True`).

---

## 5. Non-Functional & Security Requirements
1. **Zero Web Disruption:** Hot backup runs in background without blocking active HTTP requests or causing transaction lockouts.
2. **Data Integrity:** Backup executes via SQLite's atomic backup API, preventing corruption from in-flight writes.
3. **Zero Secret Leakage:** Storage access credentials remain strictly in environment variables.
4. **Offline Testability:** All automated unit and integration tests must run 100% offline using in-memory SQLite databases and mocked S3 storage with zero network dependencies.
5. **Storage Hygiene:** Automatic retention pruning stops backups from exhausting cloud storage quota.

---

## 6. Acceptance Criteria
- [ ] Hot backup creates a valid, uncorrupted copy of the active SQLite database file.
- [ ] Backup snapshot is compressed using gzip (`.sqlite3.gz`) and uploaded to the OCI Object Storage bucket.
- [ ] Backups older than the configured retention days (default 30) are automatically pruned from the cloud bucket.
- [ ] Management command `python manage.py backup_db` runs cleanly and exits with code 0 on success.
- [ ] `DatabaseBackupLog` records every backup attempt (status, size, duration, key, error).
- [ ] Store managers can inspect backup logs and trigger on-demand backups from Django Administration.
- [ ] All new user-facing strings and admin labels are localized in Spanish (`es`) and English (`en`).
- [ ] Comprehensive unit and integration tests added in `tests/test_backup.py` pass offline.
- [ ] All 187+ existing tests continue to pass with 0 regressions.
