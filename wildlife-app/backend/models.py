"""Pydantic models for API request/response validation"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
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
        # Check for valid URL schemes
        valid_schemes = ['rtsp://', 'http://', 'https://', 'rtmp://', 'file://']
        if not any(v.lower().startswith(scheme) for scheme in valid_schemes):
            raise ValueError(f'URL must start with one of: {", ".join(valid_schemes)}')
        # Check for path traversal attempts
        if '..' in v or '//' in v.replace('://', '').replace('//', ''):
            raise ValueError('Invalid URL format - path traversal detected')
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
        # Check aspect ratio is reasonable (between 1:3 and 3:1)
        aspect_ratio = width / height if height > 0 else 1
        if aspect_ratio < 0.33 or aspect_ratio > 3.0:
            raise ValueError(f'Invalid aspect ratio: {aspect_ratio:.2f}. Width/height ratio should be between 0.33 and 3.0')
        return self


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int
    created_at: datetime
    stream_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    detection_count: Optional[int] = None
    last_detection: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None

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
            if not v.startswith('/tmp') and not v.startswith('C:\\') and 'temp' not in v.lower():
                raise ValueError(f'Image path should have a valid image extension: {", ".join(valid_extensions)}')
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


class DetectionResponse(DetectionBase):
    id: int
    timestamp: datetime
    full_taxonomy: Optional[str] = None  # Add full taxonomy field
    media_url: Optional[str] = None
    camera_name: str

    class Config:
        from_attributes = True


class MotionSettings(BaseModel):
    """Motion detection settings model with validation"""
    motion_detection: Optional[bool] = Field(None, description="Enable motion detection")
    motion_threshold: Optional[int] = Field(None, ge=0, le=100000, description="Motion threshold")
    motion_mask: Optional[str] = Field(None, max_length=10000, description="Motion mask")
    motion_gap: Optional[int] = Field(None, ge=0, le=3600, description="Motion gap in seconds")
    motion_event_gap: Optional[int] = Field(None, ge=0, le=3600, description="Motion event gap in seconds")
    motion_pre_capture: Optional[int] = Field(None, ge=0, le=60, description="Pre-capture frames")
    motion_post_capture: Optional[int] = Field(None, ge=0, le=60, description="Post-capture frames")
    noise_level: Optional[int] = Field(None, ge=0, le=100, description="Noise level")
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

