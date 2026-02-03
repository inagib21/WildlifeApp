"""Configuration and environment variables"""
import os
import secrets
from dotenv import load_dotenv

# Load environment-specific .env file
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
if ENVIRONMENT == "test":
    env_file = ".env.test"
elif ENVIRONMENT == "production":
    env_file = ".env.production"
else:
    env_file = ".env"

# Try to load environment-specific file, fallback to .env
load_dotenv(env_file)
load_dotenv()  # Also load .env as fallback

# Database configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "wildlife")
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

# Build DATABASE_URL with schema support
base_url = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Add schema to connection string if not default
if DB_SCHEMA and DB_SCHEMA != "public":
    if "?" in base_url:
        DATABASE_URL = f"{base_url}&options=-csearch_path%3D{DB_SCHEMA}"
    else:
        DATABASE_URL = f"{base_url}?options=-csearch_path%3D{DB_SCHEMA}"
else:
    DATABASE_URL = base_url

# Service URLs
MOTIONEYE_URL = os.getenv("MOTIONEYE_URL", "http://localhost:8765")
SPECIESNET_URL = os.getenv("SPECIESNET_URL", "http://localhost:8000")

# AI Backend Configuration
AI_BACKEND = os.getenv("AI_BACKEND", "ensemble")  # Options: speciesnet, yolov11, yolov8, clip, ensemble
YOLOV11_MODEL_PATH = os.getenv("YOLOV11_MODEL_PATH", "yolo11n.pt")
YOLOV8_MODEL_PATH = os.getenv("YOLOV8_MODEL_PATH", "yolov8n.pt")
VIT_MODEL_NAME = os.getenv("VIT_MODEL_NAME", "google/vit-base-patch16-224")

# Camera authentication credentials
THINGINO_CAMERA_USERNAME = os.getenv("THINGINO_CAMERA_USERNAME", "root")
THINGINO_CAMERA_PASSWORD = os.getenv("THINGINO_CAMERA_PASSWORD", "ismart12")

# CORS configuration
ALLOWED_ORIGINS = [
    origin.strip() 
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    ).split(",")
    if origin.strip()  # Remove empty strings
]
# Ensure localhost:3000 is always included
if "http://localhost:3000" not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append("http://localhost:3000")
if "http://127.0.0.1:3000" not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append("http://127.0.0.1:3000")

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

# Environment-specific settings
DEBUG = ENVIRONMENT != "production"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if ENVIRONMENT != "production" else "INFO")

# Validation: Prevent production settings in test environment
if ENVIRONMENT == "test":
    if os.getenv("DB_NAME", "").endswith("_prod"):
        raise ValueError("Cannot use production database name in test environment")
    if DB_SCHEMA == "production":
        raise ValueError("Cannot use production schema in test environment")

# Validation: Warn about insecure settings in production
if ENVIRONMENT == "production":
    if DB_PASSWORD == "postgres" or DB_PASSWORD == "":
        raise ValueError("Production environment requires a strong database password")
    if JWT_SECRET_KEY == secrets.token_urlsafe(32) or "CHANGE_THIS" in JWT_SECRET_KEY:
        raise ValueError("Production environment requires a custom JWT_SECRET_KEY")
    if "localhost" in ALLOWED_ORIGINS and len(ALLOWED_ORIGINS) == 1:
        raise ValueError("Production environment should not allow localhost in CORS")
