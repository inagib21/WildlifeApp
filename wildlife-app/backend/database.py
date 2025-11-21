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
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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


# Add error handling for database connection
try:
    # Test the connection
    with engine.connect() as conn:
        pass
    print("Successfully connected to PostgreSQL database")
except Exception as e:
    print(f"Warning: Error connecting to database: {e}")
    print("Database connection will be retried during startup")

