# Storage Management & Backup Policy

This document explains how storage, backups, and data retention work in the Wildlife Camera System.

## Storage Overview

The system manages three main types of storage:

1. **Database Storage** - PostgreSQL database containing detections, cameras, and metadata
2. **Media Storage** - Image files from cameras (MotionEye media)
3. **Archived Photos** - Organized photos by species in `archived_photos/` directory

## Database Backups

### Automatic Backups

The system performs **automatic database backups** on a schedule:

- **Monthly Backups**: On the 1st of each month at 2:00 AM (configurable via `BACKUP_SCHEDULE_MONTHLY_DAY` and `BACKUP_SCHEDULE_MONTHLY_HOUR`)

### Backup Location

Backups are stored in: `wildlife-app/backend/backups/`

Backup files are named: `wildlife_backup_YYYYMMDD_HHMMSS.sql`

### Backup Retention

- **Default**: Keeps the **10 most recent backups** (configurable via `BACKUP_RETENTION_COUNT`)
- **Automatic Cleanup**: Old backups are automatically deleted when new ones are created
- **Manual Cleanup**: You can manually trigger cleanup via `/api/backup/cleanup` endpoint

### Manual Backups

You can create manual backups at any time:

**API Endpoint**: `POST /api/backup/create`

**Example**:
```bash
curl -X POST http://localhost:8001/api/backup/create
```

### Listing Backups

**API Endpoint**: `GET /api/backup/list`

Returns information about all available backups including:
- Filename
- Creation date
- File size
- Full path

### Restoring Backups

Backups can be restored using the backup service (requires direct database access):

```python
from services.backup import backup_service
from pathlib import Path

backup_path = Path("backups/wildlife_backup_20250101_020000.sql")
backup_service.restore_backup(backup_path)
```

⚠️ **Warning**: Restoring a backup will **overwrite** the current database. Make sure to backup the current database first!

## Data Retention & Deletion

### Detections

**Current Policy**: Detections are **NOT automatically deleted**. All detection records are kept indefinitely.

**Manual Deletion**:
- Individual detections can be deleted via the UI or API
- Bulk deletion is available via the detections list page
- API endpoint: `DELETE /detections/{detection_id}` or `POST /detections/bulk-delete`

**Future Enhancement**: Automatic deletion policies based on age or storage limits may be added.

### Audit Logs

**Current Policy**: Audit logs are automatically cleaned up monthly.

- **Schedule**: 1st of each month at 3:30 AM
- **Retention**: 90 days (logs older than 90 days are deleted)
- **Purpose**: Audit logs track system events, API calls, and user actions for security and debugging

**Manual Cleanup**: You can manually trigger cleanup via the API endpoint: `POST /api/audit-logs/cleanup`

### Media Files

**MotionEye Media** (`motioneye_media/`):
- Files are managed by MotionEye
- No automatic deletion by the Wildlife app
- Files remain until manually deleted or MotionEye's retention settings remove them

**Archived Photos** (`archived_photos/`):
- Photos are archived when processed (if species is not "Unknown")
- Organized by: `archived_photos/{species}/{camera_id}/{date}/{filename}`
- **No automatic deletion** - archived photos are kept permanently
- These are considered valuable curated photos

### Photo Archival Process

When a detection is processed:
1. If species is **not "Unknown"**, the photo is copied to `archived_photos/`
2. Original remains in `motioneye_media/` (managed by MotionEye)
3. Archive structure: `archived_photos/{species}/{camera_id}/{date}/{filename}`

**Note**: Only photos with identified species (not "Unknown") are archived.

## Disk Space Monitoring

The system monitors disk space and provides alerts:

- **Alert Threshold**: 90% disk usage
- **Monitoring**: Real-time disk usage is shown in the System Health dashboard
- **Media Tracking**: Tracks size of:
  - MotionEye media directory
  - Archived photos directory
  - Total media storage

**API Endpoint**: `GET /system` or `GET /api/system`

## Configuration

Storage and backup settings can be configured in `.env` file:

```env
# Backup Configuration
BACKUP_SCHEDULE_MONTHLY_DAY=1             # Day of month for backup (1-31)
BACKUP_SCHEDULE_MONTHLY_HOUR=2            # Hour for monthly backup (0-23)
BACKUP_RETENTION_COUNT=10                 # Number of backups to keep

# Archival Configuration (if implemented)
ARCHIVAL_ENABLED=true                     # Enable/disable photo archival
ARCHIVAL_ROOT=./archived_photos           # Archive directory
ARCHIVAL_MIN_CONFIDENCE=0.8              # Minimum confidence for archival
ARCHIVAL_MIN_AGE_DAYS=30                 # Minimum age before archival
```

## Backup Best Practices

1. **Regular Monitoring**: Check backup directory periodically to ensure backups are being created
2. **Off-Site Storage**: Consider copying backups to external storage or cloud backup
3. **Test Restores**: Periodically test restoring from backups to ensure they work
4. **Retention Policy**: Adjust `BACKUP_RETENTION_COUNT` based on your storage capacity and needs
5. **Disk Space**: Monitor disk usage - backups take space, and old backups are automatically cleaned up

## Storage Locations

| Type | Location | Purpose | Auto-Delete |
|------|----------|---------|-------------|
| Database Backups | `wildlife-app/backend/backups/` | PostgreSQL backups | Yes (keeps 10 most recent) |
| MotionEye Media | `wildlife-app/motioneye_media/` | Raw camera captures | No (managed by MotionEye) |
| Archived Photos | `wildlife-app/archived_photos/` | Curated photos by species | No |
| Database | PostgreSQL | Detection records, camera config | No |

## API Endpoints

### Backup Management

- `POST /api/backup/create` - Create a manual backup
- `GET /api/backup/list` - List all backups
- `POST /api/backup/cleanup?keep_count=10` - Clean up old backups

### Storage Information

- `GET /system` - Get system health including disk usage
- `GET /api/system` - Same as above
- `GET /health/detailed` - Detailed health check with storage metrics

## Troubleshooting

### Backups Not Running

1. Check scheduler is running (should start automatically with backend)
2. Verify PostgreSQL `pg_dump` is available in PATH
3. Check backup directory permissions
4. Review backend logs for backup errors

### Disk Space Issues

1. Check System Health dashboard for disk usage
2. Clean up old backups: `POST /api/backup/cleanup?keep_count=5`
3. Review MotionEye media directory for old files
4. Consider archiving old detections (manual process currently)

### Missing Backups

1. Verify `BACKUP_SCHEDULE_DAILY_HOUR` is set correctly
2. Check that scheduler service is running
3. Review backend logs for backup creation errors
4. Ensure backup directory exists and is writable

## Future Enhancements

Potential improvements to storage management:

- **Automatic Detection Deletion**: Configurable retention policies (e.g., delete detections older than X days)
- **Media File Cleanup**: Automatic cleanup of old MotionEye media files
- **Compressed Backups**: Compress backup files to save space
- **Cloud Backup Integration**: Automatic upload to cloud storage (S3, Google Drive, etc.)
- **Storage Quotas**: Set limits and automatic cleanup when quotas are reached
- **Smart Archival**: More sophisticated archival rules based on confidence, species rarity, etc.

