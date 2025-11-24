# Environment Variables Setup

## Required Environment Variables

Create a `.env` file in the `wildlife-app/backend/` directory with the following variables:

```env
# Database Configuration
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=wildlife
# Or use full DATABASE_URL
# DATABASE_URL=postgresql://user:password@host:port/database

# Service URLs
MOTIONEYE_URL=http://localhost:8765
SPECIESNET_URL=http://localhost:8000

# Camera Authentication (Thingino cameras)
THINGINO_CAMERA_USERNAME=root
THINGINO_CAMERA_PASSWORD=your_camera_password_here

# CORS Configuration (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# API Security (optional - leave empty to disable)
API_KEY=your_api_key_here

# MotionEye Sync Interval (seconds)
MOTIONEYE_SYNC_INTERVAL_SECONDS=60

# Email Notifications (optional)
NOTIFICATION_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL_FROM=your_email@gmail.com
NOTIFICATION_EMAIL_TO=recipient1@example.com,recipient2@example.com

# Scheduled Backups (optional - uses APScheduler)
# Backups run automatically at:
# - Daily: 2:00 AM (configurable via API)
# - Weekly: Sunday 3:00 AM (configurable via API)
# Backups are stored in: wildlife-app/backend/backups/
# Old backups are automatically cleaned up (keeps 30 most recent)
```

## Security Notes

- **Never commit `.env` files to git** - they contain sensitive credentials
- Use strong passwords for database and camera authentication
- In production, use a secrets management service (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate credentials regularly
- Use different credentials for development and production environments

## Default Values

If environment variables are not set, the application will use these defaults (for local development only):

- Database: `postgres:postgres@localhost:5432/wildlife`
- Thingino Camera: `root:ismart12`
- CORS: `http://localhost:3000,http://127.0.0.1:3000`

**⚠️ Warning:** Defaults are for local development only. Always set proper environment variables in production!

