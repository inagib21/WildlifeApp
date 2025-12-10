"""Database setup and models"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL
from sqlalchemy.pool import QueuePool

# Configure connection pooling for better performance
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Number of connections to maintain
    max_overflow=20,        # Additional connections when pool is exhausted
    pool_pre_ping=True,     # Verify connections before using
    pool_recycle=3600,      # Recycle connections after 1 hour
    connect_args={
        "connect_timeout": 5,  # 5 second timeout for initial connection
        "options": "-c statement_timeout=30000"  # 30 second timeout for queries (increased for large datasets)
    },
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Database Models
class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # MotionEye configuration fields
    width = Column(Integer, default=1280)
    height = Column(Integer, default=720)
    framerate = Column(Integer, default=30)
    stream_port = Column(Integer, default=8081)
    stream_quality = Column(Integer, default=100)
    stream_maxrate = Column(Integer, default=30)
    stream_localhost = Column(Boolean, default=False)
    detection_enabled = Column(Boolean, default=True)
    detection_threshold = Column(Integer, default=1500)
    detection_smart_mask_speed = Column(Integer, default=10)
    movie_output = Column(Boolean, default=True)
    movie_quality = Column(Integer, default=100)
    movie_codec = Column(String, default="mkv")
    snapshot_interval = Column(Integer, default=0)
    target_dir = Column(String, default="./motioneye_media")


class Detection(Base):
    __tablename__ = "detections"
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('idx_detection_camera_timestamp', 'camera_id', 'timestamp'),
        Index('idx_detection_timestamp_desc', 'timestamp'),
        Index('idx_detection_species', 'species'),
        # Index for file hash deduplication (already has index=True on column)
    )
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), index=True)  # Add index for foreign key lookups
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # Add index for time-based queries
    species = Column(String, index=True)  # Add index for species filtering
    confidence = Column(Float)
    image_path = Column(String)
    file_size = Column(Integer, nullable=True)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    image_quality = Column(Integer, nullable=True)
    # SpeciesNet specific fields
    prediction_score = Column(Float, nullable=True)
    detections_json = Column(Text, nullable=True)  # Store full detection data as JSON
    file_hash = Column(String, nullable=True, index=True)  # SHA256 hash of file for deduplication


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_user_ip', 'user_ip'),
        Index('idx_audit_resource_type', 'resource_type'),
    )
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    action = Column(String, index=True, nullable=False)  # CREATE, UPDATE, DELETE, SYNC, etc.
    resource_type = Column(String, index=True, nullable=False)  # camera, detection, motion_settings, etc.
    resource_id = Column(Integer, nullable=True)  # ID of the affected resource
    user_ip = Column(String, nullable=True)  # IP address of the user making the change
    user_agent = Column(String, nullable=True)  # User agent string
    endpoint = Column(String, nullable=True)  # API endpoint that was called
    details = Column(Text, nullable=True)  # JSON string with additional details
    success = Column(Boolean, default=True)  # Whether the action succeeded
    error_message = Column(Text, nullable=True)  # Error message if action failed
    # Note: user_id column removed - not in actual database table
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Link to user who made the change


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index('idx_api_key_hash', 'key_hash'),
        Index('idx_api_key_user', 'user_name'),
        Index('idx_api_key_active', 'is_active'),
    )
    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)  # SHA256 hash of the API key
    user_name = Column(String, index=True, nullable=False)  # User/application name
    description = Column(String, nullable=True)  # Optional description
    is_active = Column(Boolean, default=True, index=True)  # Can be revoked
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)  # Track last usage
    expires_at = Column(DateTime, nullable=True)  # Optional expiration date
    usage_count = Column(Integer, default=0)  # Track usage
    rate_limit_per_minute = Column(Integer, default=60)  # Per-key rate limiting
    allowed_ips = Column(Text, nullable=True)  # Comma-separated list of allowed IPs (optional)
    extra_metadata = Column(Text, nullable=True)  # JSON string for additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_username', 'username'),
    )
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)  # bcrypt hashed password
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_superuser = Column(Boolean, default=False)  # Admin role
    role = Column(String, default="viewer")  # viewer, editor, admin
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)  # Track failed login attempts
    locked_until = Column(DateTime, nullable=True)  # Account lockout until this time


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index('idx_session_token', 'token'),
        Index('idx_session_user', 'user_id'),
        Index('idx_session_expires', 'expires_at'),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, unique=True, index=True, nullable=False)  # JWT or session token
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class Webhook(Base):
    __tablename__ = "webhooks"
    __table_args__ = (
        Index('idx_webhook_active', 'is_active'),
        Index('idx_webhook_event_type', 'event_type'),
    )
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name
    url = Column(String, nullable=False)  # Webhook URL
    event_type = Column(String, nullable=False)  # detection, system_alert, etc.
    is_active = Column(Boolean, default=True, index=True)
    secret = Column(String, nullable=True)  # Optional secret for signing payloads
    headers = Column(Text, nullable=True)  # JSON string for custom headers
    retry_count = Column(Integer, default=3)  # Number of retry attempts
    retry_delay = Column(Integer, default=5)  # Delay between retries in seconds
    timeout = Column(Integer, default=10)  # Request timeout in seconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_triggered_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)  # Optional description
    filters = Column(Text, nullable=True)  # JSON string for event filters (e.g., min_confidence, species)


# Add error handling for database connection
try:
    # Test the connection
    with engine.connect() as conn:
        pass
    print("Successfully connected to PostgreSQL database")
except Exception as e:
    print(f"Warning: Error connecting to database: {e}")
    print("Database connection will be retried during startup")
