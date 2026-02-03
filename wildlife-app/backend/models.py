"""Pydantic models for API request/response validation"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Camera name")
    url: str = Field(..., min_length=1, max_length=500, description="Camera stream URL")
    is_active: bool = Field(True, description="Whether the camera is active")
    width: int = Field(1280, ge=320, le=7680, description="Video width in pixels")
    height: int = Field(720, ge=240, le=4320, description="Video height in pixels")
    framerate: int = Field(30, ge=1, le=120, description="Frames per second")
    stream_port: int = Field(8081, ge=1024, le=65535, description="Stream port number")
    stream_quality: int = Field(100, ge=1, le=100, description="Stream quality (1-100)")
    stream_maxrate: int = Field(30, ge=1, le=120, description="Maximum stream rate")
    stream_localhost: bool = Field(False, description="Restrict stream to localhost")
    detection_enabled: bool = Field(True, description="Enable motion detection")
    detection_threshold: int = Field(1500, ge=0, le=100000, description="Motion detection threshold")
    detection_smart_mask_speed: int = Field(10, ge=0, le=100, description="Smart mask speed")
    movie_output: bool = Field(True, description="Enable movie output")
    movie_quality: int = Field(100, ge=1, le=100, description="Movie quality (1-100)")
    movie_codec: str = Field("mkv", max_length=50, description="Movie codec")
    snapshot_interval: int = Field(0, ge=0, le=3600, description="Snapshot interval in seconds")
    target_dir: str = Field("./motioneye_media", max_length=500, description="Target directory for media")
    # Location fields
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Camera latitude (-90 to 90)")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Camera longitude (-180 to 180)")
    address: Optional[str] = Field(None, max_length=500, description="Camera address/location")
    # Geofencing fields (per-camera)
    geofence_enabled: Optional[bool] = Field(False, description="Enable geofencing for this camera")
    geofence_type: Optional[str] = Field(None, description="Geofence type: polygon, circle, or bounds")
    geofence_data: Optional[Dict[str, Any]] = Field(None, description="Geofence configuration data (JSON)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate camera name - strip whitespace and ensure not empty"""
        if not v or not v.strip():
            raise ValueError('Camera name cannot be empty')
        return v.strip()
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate camera URL format"""
        if not v or not v.strip():
            raise ValueError('Camera URL cannot be empty')
        v = v.strip()
        # Allow http, https, rtsp, rtmp, or file:// URLs
        if not v.startswith(('http://', 'https://', 'rtsp://', 'rtmp://', 'file://')):
            raise ValueError('Camera URL must start with http://, https://, rtsp://, rtmp://, or file://')
        return v
    
    @field_validator('movie_codec')
    @classmethod
    def validate_codec(cls, v):
        """Validate movie codec - handle MotionEye format like 'mp4:h264_v4l2m2m'"""
        if not v:
            return "mkv"
        v = v.lower().strip()
        # MotionEye can return values like "mp4:h264_v4l2m2m" - extract base codec
        if ':' in v:
            v = v.split(':')[0]
        # Truncate to max length (50)
        return v[:50]
    
    @field_validator('target_dir')
    @classmethod
    def validate_target_dir(cls, v):
        """Validate target directory path"""
        if not v or not v.strip():
            raise ValueError('Target directory cannot be empty')
        v = v.strip()
        # Prevent path traversal
        if '..' in v or v.startswith('/') or (len(v) > 1 and v[1] == ':'):
            # Allow relative paths but prevent absolute paths and traversal
            if '..' in v:
                raise ValueError('Target directory cannot contain path traversal (..)')
        return v
    
    @model_validator(mode='after')
    def validate_resolution(self):
        """Validate that resolution is reasonable"""
        width = self.width
        height = self.height
        
        # Check dimensions are reasonable
        if width < 320 or width > 7680:
            raise ValueError(f'Width must be between 320 and 7680, got {width}')
        if height < 240 or height > 4320:
            raise ValueError(f'Height must be between 240 and 4320, got {height}')
        
        # Check aspect ratio is reasonable (between 1:3 and 3:1)
        aspect_ratio = width / height if height > 0 else 1
        if aspect_ratio < 0.33 or aspect_ratio > 3.0:
            raise ValueError(f'Invalid aspect ratio: {aspect_ratio:.2f}. Width/height ratio should be between 0.33 and 3.0')
        return self


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int

    stream_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    detection_count: Optional[int] = None
    last_detection: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None  # Legacy field, use address instead
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

    class Config:
        from_attributes = True


class DetectionBase(BaseModel):
    camera_id: int = Field(..., ge=1, description="Camera ID (must be positive)")
    species: str = Field(..., min_length=1, max_length=200, description="Detected species name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    image_path: str = Field(..., min_length=1, max_length=1000, description="Path to the image file")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    image_width: Optional[int] = Field(None, ge=1, le=100000, description="Image width in pixels")
    image_height: Optional[int] = Field(None, ge=1, le=100000, description="Image height in pixels")
    image_quality: Optional[int] = Field(None, ge=0, le=100, description="Image quality (0-100)")
    prediction_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Prediction score (0.0-1.0)")
    detections_json: Optional[str] = Field(None, max_length=10000, description="Full detection data as JSON")
    # Audio support
    audio_path: Optional[str] = Field(None, max_length=1000, description="Path to audio file")
    # Video support
    video_path: Optional[str] = Field(None, max_length=1000, description="Path to video file")
    # Sensor data from ESP32
    temperature: Optional[float] = Field(None, ge=-50.0, le=70.0, description="Temperature in Celsius")
    humidity: Optional[float] = Field(None, ge=0.0, le=100.0, description="Humidity in percentage")
    pressure: Optional[float] = Field(None, ge=0.0, le=1500.0, description="Atmospheric pressure in hPa")
    
    @field_validator('species')
    @classmethod
    def validate_species(cls, v):
        """Validate species name"""
        if not v or not v.strip():
            raise ValueError('Species name cannot be empty')
        # Remove extra whitespace
        return ' '.join(v.strip().split())
    
    @field_validator('image_path')
    @classmethod
    def validate_image_path(cls, v):
        """Validate image path"""
        if not v or not v.strip():
            raise ValueError('Image path cannot be empty')
        v = v.strip()
        # Check for valid image extensions
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            # Allow paths without extension for temporary files
            if not any(c in v for c in ['/', '\\']):
                raise ValueError(f'Image path must have a valid extension or be a path. Valid extensions: {", ".join(valid_extensions)}')
        # Prevent path traversal
        if '..' in v:
            raise ValueError('Image path cannot contain path traversal (..)')
        return v
    
    @field_validator('detections_json')
    @classmethod
    def validate_detections_json(cls, v):
        """Validate JSON string if provided"""
        if v is not None:
            import json
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError('detections_json must be valid JSON')
        return v


class DetectionCreate(DetectionBase):
    pass


class SpeciesInfoResponse(BaseModel):
    """Species information response"""
    common_name: Optional[str] = None
    scientific_name: Optional[str] = None
    description: Optional[str] = None
    habitat: Optional[str] = None
    behavior: Optional[str] = None
    diet: Optional[str] = None
    size: Optional[str] = None
    weight: Optional[str] = None
    conservation_status: Optional[str] = None
    activity_pattern: Optional[str] = None
    geographic_range: Optional[str] = None
    interesting_facts: Optional[List[str]] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class RecognizedFaceResponse(BaseModel):
    """Recognized face information in detection response"""
    id: int
    name: str
    confidence: float
    known_face_id: Optional[int] = None
    recognition_confidence: float
    face_location: Dict[str, int]

    class Config:
        from_attributes = True


class DetectionResponse(DetectionBase):
    id: int
    timestamp: datetime
    full_taxonomy: Optional[str] = None  # Add full taxonomy field
    media_url: Optional[str] = None
    video_url: Optional[str] = None  # URL for video file
    thumbnail_url: Optional[str] = None  # URL for thumbnail image
    camera_name: str
    recognized_faces: Optional[List[RecognizedFaceResponse]] = Field(default_factory=list, description="Recognized faces in this detection")

    class Config:
        from_attributes = True


class MotionSettings(BaseModel):
    """Motion detection settings model with validation"""
    motion_detection: Optional[bool] = Field(None, description="Enable motion detection")
    motion_threshold: Optional[int] = Field(None, ge=0, le=100000, description="Motion threshold")
    motion_mask: Optional[str] = Field(None, max_length=10000, description="Motion mask")
    motion_smart_mask: Optional[bool] = Field(None, description="Enable smart mask")
    motion_noise_level: Optional[int] = Field(None, ge=0, le=100, description="Noise level")
    lightswitch_percent: Optional[int] = Field(None, ge=0, le=100, description="Lightswitch percent")
    despeckle_filter: Optional[str] = Field(None, max_length=50, description="Despeckle filter")
    minimum_motion_frames: Optional[int] = Field(None, ge=1, le=100, description="Minimum motion frames")
    smart_mask_speed: Optional[int] = Field(None, ge=0, le=100, description="Smart mask speed")
    
    @model_validator(mode='after')
    def validate_settings(self):
        """Ensure at least one setting is provided"""
        values = self.model_dump()
        if not any(v is not None for v in values.values()):
            raise ValueError('At least one motion setting must be provided')
        return self


class AuditLogResponse(BaseModel):
    """Audit log response model"""
    id: int
    timestamp: datetime
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: bool
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class WebhookBase(BaseModel):
    """Base webhook model"""
    name: str = Field(..., min_length=1, max_length=200, description="Webhook name")
    url: str = Field(..., min_length=1, max_length=500, description="Webhook URL")
    event_type: str = Field(..., description="Event type: detection, system_alert, or all")
    is_active: bool = Field(True, description="Whether webhook is active")
    secret: Optional[str] = Field(None, max_length=200, description="Optional secret for signing")
    headers: Optional[str] = Field(None, description="JSON string for custom headers")
    retry_count: int = Field(3, ge=0, le=10, description="Number of retry attempts")
    retry_delay: int = Field(5, ge=1, le=60, description="Delay between retries in seconds")
    timeout: int = Field(10, ge=1, le=60, description="Request timeout in seconds")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    filters: Optional[str] = Field(None, description="JSON string for event filters")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate webhook URL"""
        if not v or not v.strip():
            raise ValueError('Webhook URL cannot be empty')
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Webhook URL must start with http:// or https://')
        return v
    
    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v):
        """Validate event type"""
        valid_types = ['detection', 'system_alert', 'all']
        if v not in valid_types:
            raise ValueError(f'Event type must be one of: {", ".join(valid_types)}')
        return v


class WebhookCreate(WebhookBase):
    pass


class WebhookResponse(WebhookBase):
    id: int
    created_at: datetime
    last_triggered_at: Optional[datetime] = None
    trigger_count: int
    success_count: int
    failure_count: int
    
    class Config:
        from_attributes = True


class SoundDetectionBase(BaseModel):
    """Base model for sound detection"""
    camera_id: Optional[int] = Field(None, ge=1, description="Camera ID (optional)")
    detection_id: Optional[int] = Field(None, ge=1, description="Link to image detection (optional)")
    sound_class: str = Field(..., min_length=1, max_length=200, description="Detected sound/animal class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    audio_path: str = Field(..., min_length=1, max_length=1000, description="Path to audio file")
    duration: Optional[float] = Field(None, ge=0.0, description="Audio duration in seconds")
    audio_features: Optional[Dict[str, Any]] = Field(None, description="Audio features as JSON")
    
    @field_validator('sound_class')
    @classmethod
    def validate_sound_class(cls, v):
        """Validate sound class name"""
        if not v or not v.strip():
            raise ValueError('Sound class cannot be empty')
        return v.strip()
    
    @field_validator('audio_path')
    @classmethod
    def validate_audio_path(cls, v):
        """Validate audio path"""
        if not v or not v.strip():
            raise ValueError('Audio path cannot be empty')
        v = v.strip()
        # Prevent path traversal
        if '..' in v:
            raise ValueError('Audio path cannot contain path traversal (..)')
        return v


class SoundDetectionCreate(SoundDetectionBase):
    pass


class SoundDetectionResponse(SoundDetectionBase):
    id: int
    timestamp: datetime
    audio_url: Optional[str] = None
    camera_name: Optional[str] = None
    detection_species: Optional[str] = None  # Species from linked detection if available
    
    class Config:
        from_attributes = True
