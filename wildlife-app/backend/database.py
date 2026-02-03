"""Database setup and models"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Index, event, DDL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL, DB_SCHEMA, ENVIRONMENT
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

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

# Set default schema for all connections
if DB_SCHEMA and DB_SCHEMA != "public":
    @event.listens_for(engine, "connect", insert=True)
    def set_search_path(dbapi_conn, connection_record):
        """Set the search_path for each connection to use the specified schema"""
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {DB_SCHEMA}, public")
        cursor.close()
        logger.info(f"Set database search_path to {DB_SCHEMA}")

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
    # Location fields (GPS and address)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String, nullable=True)  # Human-readable address
    # Geofencing fields (per-camera)
    geofence_enabled = Column(Boolean, default=False, nullable=False)
    geofence_type = Column(String, nullable=True)  # "polygon", "circle", "bounds"
    geofence_data = Column(Text, nullable=True)  # JSON string storing geofence configuration


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
    # Audio support
    audio_path = Column(String, nullable=True)  # Path to audio file if available
    # Video support
    video_path = Column(String, nullable=True)  # Path to video file if available
    # Sensor data from ESP32
    temperature = Column(Float, nullable=True)  # Temperature in Celsius
    humidity = Column(Float, nullable=True)  # Humidity in percentage
    pressure = Column(Float, nullable=True)  # Atmospheric pressure (optional)


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


class SensorReading(Base):
    """Sensor readings from ESP32 cameras (temperature, humidity, pressure)"""
    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index('idx_sensor_camera_timestamp', 'camera_id', 'timestamp'),
        Index('idx_sensor_timestamp', 'timestamp'),
    )
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), index=True, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    temperature = Column(Float, nullable=True)  # Temperature in Celsius
    humidity = Column(Float, nullable=True)  # Humidity in percentage
    pressure = Column(Float, nullable=True)  # Atmospheric pressure (hPa)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=True)  # Link to detection if available


class SoundDetection(Base):
    """Animal sound detections from audio files"""
    __tablename__ = "sound_detections"
    __table_args__ = (
        Index('idx_sound_detection_timestamp', 'timestamp'),
        Index('idx_sound_class', 'sound_class'),
    )
    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=True)  # Link to image detection
    camera_id = Column(Integer, ForeignKey("cameras.id"), index=True, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    sound_class = Column(String, index=True)  # Detected sound/animal
    confidence = Column(Float)  # Confidence score
    audio_path = Column(String)  # Path to audio file
    duration = Column(Float, nullable=True)  # Audio duration in seconds
    audio_features = Column(Text, nullable=True)  # JSON string with audio features


class ChatHistory(Base):
    """Chat history for interactive query interface"""
    __tablename__ = "chat_history"
    __table_args__ = (
        Index('idx_chat_timestamp', 'timestamp'),
    )
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    query = Column(Text)  # User query
    response = Column(Text, nullable=True)  # System response
    response_type = Column(String, nullable=True)  # Type: 'count', 'list', 'chart', 'text'
    response_data = Column(Text, nullable=True)  # JSON string with response data
    user_ip = Column(String, nullable=True)
    success = Column(Boolean, default=True)


class ModelRegistry(Base):
    """Registry of AI models from Hugging Face, Kaggle, etc."""
    __tablename__ = "model_registry"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # Model name/identifier
    display_name = Column(String)  # Human-readable name
    source = Column(String)  # 'huggingface', 'kaggle', 'custom'
    source_path = Column(String)  # Hugging Face model path, Kaggle dataset, or file path
    model_type = Column(String)  # 'image_classification', 'object_detection', 'audio', 'text'
    is_enabled = Column(Boolean, default=True)
    version = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)  # JSON string with dependencies
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    headers = Column(Text, nullable=True)


class SystemSettings(Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        Index('idx_settings_key', 'key'),
    )
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)  # Setting key (e.g., 'ai_enabled')
    value = Column(Text, nullable=False)  # Setting value (JSON string for complex values)
    description = Column(String, nullable=True)  # Human-readable description
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnownFace(Base):
    __tablename__ = "known_faces"
    __table_args__ = (
        Index('idx_face_name', 'name'),
        Index('idx_face_active', 'is_active'),
    )
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Person's name
    face_encoding = Column(Text, nullable=False)  # Face encoding (JSON array of floats)
    image_path = Column(String, nullable=True)  # Path to reference image
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)  # Optional notes about the person
    tolerance = Column(Float, default=0.6, nullable=True)  # Recognition tolerance (lower = stricter, default 0.6)


class FaceDetection(Base):
    __tablename__ = "face_detections"
    __table_args__ = (
        Index('idx_face_detection_detection', 'detection_id'),
        Index('idx_face_detection_known_face', 'known_face_id'),
    )
    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detections.id"), nullable=False, index=True)
    known_face_id = Column(Integer, ForeignKey("known_faces.id"), nullable=True, index=True)  # null if unknown
    confidence = Column(Float, nullable=False)  # Confidence score (0.0-1.0)
    face_location = Column(Text, nullable=True)  # Face bounding box (JSON: [top, right, bottom, left])
    face_encoding = Column(Text, nullable=True)  # Detected face encoding (JSON array)
    created_at = Column(DateTime, default=datetime.utcnow)  # JSON string for custom headers
    retry_count = Column(Integer, default=3)  # Number of retry attempts
    retry_delay = Column(Integer, default=5)  # Delay between retries in seconds
    timeout = Column(Integer, default=10)  # Request timeout in seconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_triggered_at = Column(DateTime, nullable=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)  # Optional description
    filters = Column(Text, nullable=True)  # JSON string for event filters (e.g., min_confidence, species)


# Schema creation function
def create_schema_if_not_exists(schema_name: str):
    """Create a database schema if it doesn't exist"""
    if schema_name == "public":
        return  # Public schema always exists
    
    try:
        with engine.connect() as conn:
            # Check if schema exists
            result = conn.execute(
                text(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{schema_name}'")
            )
            if not result.fetchone():
                # Create schema
                conn.execute(DDL(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                conn.commit()
                logger.info(f"Created database schema: {schema_name}")
            else:
                logger.info(f"Database schema {schema_name} already exists")
    except Exception as e:
        logger.warning(f"Could not create schema {schema_name}: {e}")

# Create schema on module import if not public
if DB_SCHEMA and DB_SCHEMA != "public" and ENVIRONMENT in ["test", "production"]:
    create_schema_if_not_exists(DB_SCHEMA)

# Add error handling for database connection
try:
    # Test the connection
    with engine.connect() as conn:
        # Verify schema is accessible
        if DB_SCHEMA and DB_SCHEMA != "public":
            result = conn.execute(
                text("SELECT current_schema()")
            )
            current_schema = result.fetchone()[0]
            logger.info(f"Connected to PostgreSQL database (schema: {current_schema})")
        else:
            logger.info("Successfully connected to PostgreSQL database")
except Exception as e:
    logger.warning(f"Error connecting to database: {e}")
    logger.warning("Database connection will be retried during startup")
