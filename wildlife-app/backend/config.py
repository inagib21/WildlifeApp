"""Configuration and environment variables"""
import os
import secrets
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
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
).split(",")

# Email notification configuration (optional)
NOTIFICATION_ENABLED = os.getenv("NOTIFICATION_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFICATION_EMAIL_FROM = os.getenv("NOTIFICATION_EMAIL_FROM", "")
NOTIFICATION_EMAIL_TO = os.getenv("NOTIFICATION_EMAIL_TO", "")  # Comma-separated list

# SMS notification configuration (optional, via Twilio)
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
SMS_PHONE_NUMBERS = os.getenv("SMS_PHONE_NUMBERS", "")  # Comma-separated list of phone numbers

# Backup configuration
BACKUP_SCHEDULE_MONTHLY_DAY = int(os.getenv("BACKUP_SCHEDULE_MONTHLY_DAY", "1"))  # 1st of month
BACKUP_SCHEDULE_MONTHLY_HOUR = int(os.getenv("BACKUP_SCHEDULE_MONTHLY_HOUR", "2"))  # 2 AM
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

# Authentication configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))  # Generate random key if not set
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))  # Session expires after 24 hours

