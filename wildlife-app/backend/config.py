"""Configuration and environment variables"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "wildlife")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Service URLs
MOTIONEYE_URL = os.getenv("MOTIONEYE_URL", "http://localhost:8765")
SPECIESNET_URL = os.getenv("SPECIESNET_URL", "http://localhost:8000")

# Camera authentication credentials
THINGINO_CAMERA_USERNAME = os.getenv("THINGINO_CAMERA_USERNAME", "root")
THINGINO_CAMERA_PASSWORD = os.getenv("THINGINO_CAMERA_PASSWORD", "ismart12")

# CORS configuration
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

# Email notification configuration (optional)
NOTIFICATION_ENABLED = os.getenv("NOTIFICATION_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFICATION_EMAIL_FROM = os.getenv("NOTIFICATION_EMAIL_FROM", "")
NOTIFICATION_EMAIL_TO = os.getenv("NOTIFICATION_EMAIL_TO", "")  # Comma-separated list

# Backup configuration
BACKUP_SCHEDULE_DAILY_HOUR = int(os.getenv("BACKUP_SCHEDULE_DAILY_HOUR", "2"))
BACKUP_SCHEDULE_WEEKLY_DAY_OF_WEEK = int(os.getenv("BACKUP_SCHEDULE_WEEKLY_DAY_OF_WEEK", "6"))  # Sunday
BACKUP_SCHEDULE_WEEKLY_HOUR = int(os.getenv("BACKUP_SCHEDULE_WEEKLY_HOUR", "3"))
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "10"))

# Image archival configuration
ARCHIVAL_ENABLED = os.getenv("ARCHIVAL_ENABLED", "false").lower() == "true"
ARCHIVAL_ROOT = os.getenv("ARCHIVAL_ROOT", "./archived_photos")
ARCHIVAL_RULES = {
    "min_confidence": float(os.getenv("ARCHIVAL_MIN_CONFIDENCE", "0.8")),
    "min_age_days": int(os.getenv("ARCHIVAL_MIN_AGE_DAYS", "30")),
    "archive_high_confidence": os.getenv("ARCHIVAL_HIGH_CONFIDENCE", "true").lower() == "true",
    "archive_by_species": os.getenv("ARCHIVAL_BY_SPECIES", "true").lower() == "true",
    "archive_by_camera": os.getenv("ARCHIVAL_BY_CAMERA", "true").lower() == "true",
    "archive_by_date": os.getenv("ARCHIVAL_BY_DATE", "true").lower() == "true",
    "species_whitelist": os.getenv("ARCHIVAL_SPECIES_WHITELIST", "").split(",") if os.getenv("ARCHIVAL_SPECIES_WHITELIST") else None,
    "species_blacklist": os.getenv("ARCHIVAL_SPECIES_BLACKLIST", "").split(",") if os.getenv("ARCHIVAL_SPECIES_BLACKLIST") else []
}

# API Key authentication configuration
API_KEY_ENABLED = os.getenv("API_KEY_ENABLED", "false").lower() == "true"

