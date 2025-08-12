from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, func, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import psutil
import requests
from dotenv import load_dotenv
import subprocess
import json
from fastapi.responses import StreamingResponse, FileResponse
import configparser
import shutil
import glob
import asyncio
import threading
import time
import cv2
import numpy as np
from PIL import Image
import tempfile
import logging
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import queue
import uuid
from collections import defaultdict
from sqlalchemy import text
import hashlib
from pathlib import Path
import aiofiles
from hashlib import sha256

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Real-time event management
class EventManager:
    def __init__(self):
        self.clients: Dict[str, asyncio.Queue] = {}
        self.detection_queue = asyncio.Queue()
        self.system_queue = asyncio.Queue()
        self._background_tasks_started = False
    
    def start_background_tasks(self):
        """Start background tasks for processing events - called during FastAPI startup"""
        if not self._background_tasks_started:
            asyncio.create_task(self._process_detection_events())
            asyncio.create_task(self._process_system_events())
            asyncio.create_task(self._broadcast_system_health_periodic())
            self._background_tasks_started = True
    
    async def _process_detection_events(self):
        """Process detection events and broadcast to clients"""
        while True:
            try:
                event = await self.detection_queue.get()
                await self._broadcast_event("detection", event)
            except Exception as e:
                logging.error(f"Error processing detection event: {e}")
    
    async def _process_system_events(self):
        """Process system events and broadcast to clients"""
        while True:
            try:
                event = await self.system_queue.get()
                await self._broadcast_event("system", event)
            except Exception as e:
                logging.error(f"Error processing system event: {e}")
    
    async def _broadcast_system_health_periodic(self):
        """Periodically broadcast system health updates"""
        while True:
            try:
                # Get system health data
                system_data = await self._get_system_health_data()
                await self.broadcast_system_update(system_data)
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logging.error(f"Error broadcasting system health: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _get_system_health_data(self) -> Dict[str, Any]:
        """Get current system health data"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get MotionEye status with timeout
            motioneye_status = "unknown"
            cameras_count = 0
            try:
                # Use asyncio to run the blocking call with a timeout
                loop = asyncio.get_event_loop()
                cameras = await asyncio.wait_for(
                    loop.run_in_executor(None, motioneye_client.get_cameras),
                    timeout=2.0  # Shorter timeout to prevent blocking
                )
                cameras_count = len(cameras)
                motioneye_status = "running" if cameras_count > 0 else "no_cameras"
            except asyncio.TimeoutError:
                motioneye_status = "timeout"
            except Exception:
                motioneye_status = "error"
            
            # Get SpeciesNet status with timeout
            speciesnet_status = "unknown"
            try:
                # Use asyncio to run the blocking call with a timeout
                speciesnet_status = await asyncio.wait_for(
                    loop.run_in_executor(None, speciesnet_processor.get_status),
                    timeout=2.0  # Very short timeout to prevent blocking
                )
            except asyncio.TimeoutError:
                speciesnet_status = "timeout"
            except Exception:
                speciesnet_status = "error"
            
            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "motioneye": {
                    "status": motioneye_status,
                    "cameras_count": cameras_count
                },
                "speciesnet": {
                    "status": speciesnet_status
                }
            }
        except Exception as e:
            logging.error(f"Error getting system health: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _broadcast_event(self, event_type: str, data: Any):
        """Broadcast event to all connected clients"""
        event_data = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Remove disconnected clients
        disconnected = []
        for client_id, client_queue in self.clients.items():
            try:
                await client_queue.put(event_data)
            except Exception:
                disconnected.append(client_id)
        
        for client_id in disconnected:
            del self.clients[client_id]
    
    async def add_client(self) -> str:
        """Add a new client and return client ID"""
        client_id = str(uuid.uuid4())
        self.clients[client_id] = asyncio.Queue()
        return client_id
    
    async def remove_client(self, client_id: str):
        """Remove a client"""
        if client_id in self.clients:
            del self.clients[client_id]
    
    async def get_client_queue(self, client_id: str) -> Optional[asyncio.Queue]:
        """Get client queue by ID"""
        return self.clients.get(client_id)
    
    async def broadcast_detection(self, detection: Dict[str, Any]):
        """Broadcast a new detection to all clients"""
        await self.detection_queue.put(detection)
    
    async def broadcast_system_update(self, system_data: Dict[str, Any]):
        """Broadcast system update to all clients"""
        await self.system_queue.put(system_data)

# Global event manager
event_manager = EventManager()

# Database setup - PostgreSQL (Docker)
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/wildlife"
MOTIONEYE_URL = os.getenv("MOTIONEYE_URL", "http://localhost:8765")
SPECIESNET_URL = os.getenv("SPECIESNET_URL", "http://localhost:8000")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Add error handling for database connection
try:
    # Test the connection
    with engine.connect() as conn:
        pass
    print("Successfully connected to PostgreSQL database")
except Exception as e:
    print(f"Warning: Error connecting to database: {e}")
    print("Database connection will be retried during startup")
    # Don't raise here - let the startup event handle it

# Migration: add file_hash column if not present - moved to startup event
from sqlalchemy import inspect

# SpeciesNet integration
class SpeciesNetProcessor:
    def __init__(self):
        self.confidence_threshold = 0.5
        self.server_url = SPECIESNET_URL
        self.session = requests.Session()
        # Configure connection pooling with NO retries
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # No retries, fail fast
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        try:
            if not os.path.exists(image_path):
                raise ValueError(f"Could not read image: {image_path}")
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
                response = self.session.post(
                    f"{self.server_url}/predict",
                    files=files,
                    timeout=(1, 1)  # 1s connect, 1s read
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logging.error(f"SpeciesNet server error: {response.status_code} - {response.text}")
                    return {"error": f"Server error: {response.status_code}"}
        except requests.exceptions.Timeout:
            logging.error(f"SpeciesNet timeout for {image_path}")
            return {"error": "Request timeout"}
        except Exception as e:
            logging.error(f"Error processing image {image_path}: {str(e)}")
            return {"error": str(e)}
    
    def get_status(self) -> str:
        try:
            response = self.session.get(f"{self.server_url}/health", timeout=(1, 1))
            if response.status_code == 200:
                return "running"
            else:
                return "error"
        except requests.exceptions.Timeout:
            return "timeout"
        except Exception:
            return "not_available"

# Global SpeciesNet processor
speciesnet_processor = SpeciesNetProcessor()

# MotionEye integration
class MotionEyeClient:
    def __init__(self, base_url: str = MOTIONEYE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # No retries, fail fast
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def get_cameras(self) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(f"{self.base_url}/config/list", timeout=(1, 1))
            if response.status_code == 200:
                data = response.json()
                return data.get("cameras", [])
            return []
        except Exception as e:
            print(f"Error getting cameras from MotionEye: {e}")
            return []
    
    def add_camera(self, camera_config: Dict[str, Any]) -> bool:
        """Add a camera to MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/add", json=camera_config)
            return response.status_code == 200
        except Exception as e:
            print(f"Error adding camera to MotionEye: {e}")
            return False
    
    def update_camera(self, camera_id: int, camera_config: Dict[str, Any]) -> bool:
        """Update a camera in MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/{camera_id}/set", json=camera_config)
            return response.status_code == 200
        except Exception as e:
            print(f"Error updating camera in MotionEye: {e}")
            return False
    
    def delete_camera(self, camera_id: int) -> bool:
        """Delete a camera from MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/{camera_id}/remove")
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting camera from MotionEye: {e}")
            return False
    
    def get_camera_stream_url(self, camera_id: int) -> str:
        """Get the stream URL for a camera"""
        return f"http://localhost:8765/picture/{camera_id}/current/"
    
    def get_camera_mjpeg_url(self, camera_id: int) -> str:
        """Get the MJPEG stream URL for a camera"""
        return f"http://localhost:8765/picture/{camera_id}/current/"

# Global MotionEye client
motioneye_client = MotionEyeClient()

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
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    species = Column(String)
    confidence = Column(Float)
    image_path = Column(String)
    file_size = Column(Integer, nullable=True)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    image_quality = Column(Integer, nullable=True)
    # SpeciesNet specific fields
    prediction_score = Column(Float, nullable=True)
    detections_json = Column(Text, nullable=True)  # Store full detection data as JSON
    file_hash = Column(String, nullable=True, index=True)  # New: SHA256 hash of file

# Create tables with explicit error logging
try:
    Base.metadata.create_all(bind=engine)
    # Print the list of tables after creation
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
        tables = [row[0] for row in result]
        print(f"Tables in database after create_all: {tables}")
except Exception as e:
    import traceback
    print("Error during table creation:")
    traceback.print_exc()

@app.on_event("startup")
async def startup_event():
    try:
        # Start EventManager background tasks
        event_manager.start_background_tasks()
        print("EventManager background tasks started")
        # Test database connection and create tables
        try:
            with engine.connect() as conn:
                pass
            print("Database connection successful")
            # Create tables if they don't exist
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully")
            
            # Migration: add file_hash column if not present (after tables exist)
            try:
                insp = inspect(engine)
                if not any(c['name'] == 'file_hash' for c in insp.get_columns('detections')):
                    with engine.connect() as conn:
                        conn.execute(text('ALTER TABLE detections ADD COLUMN file_hash VARCHAR'))
                        print('Added file_hash column to detections table')
            except Exception as migration_error:
                print(f"Migration warning (non-critical): {migration_error}")
                
        except Exception as e:
            print(f"Database connection failed: {e}")
            print("Please ensure PostgreSQL is running and accessible")
            # Continue startup - the app can still run without database initially
        
        # Enable background camera sync task (periodic)
        asyncio.create_task(periodic_camera_sync())
        print("Camera sync background task started")
        # Enable background photo scanner task
        asyncio.create_task(run_photo_scanner())
        print("Photo scanner background task started")
        print("Backend startup completed successfully!")
    except Exception as e:
        print(f"Error during startup: {e}")
        # Don't raise - let the app continue running

# Background camera sync function
async def sync_cameras_background(cameras):
    """Sync cameras from MotionEye to database in background"""
    try:
        synced_count = 0
        db = SessionLocal()
        for me_camera in cameras:
            camera_id = me_camera.get("id")
            camera_name = me_camera.get("name", f"Camera{camera_id}")
            
            # Check if camera already exists in database
            existing_camera = db.query(Camera).filter(Camera.id == camera_id).first()
            
            if not existing_camera:
                # Create new camera in database
                camera_data = {
                    "id": camera_id,
                    "name": camera_name,
                    "url": me_camera.get("device_url", ""),  # MotionEye uses device_url
                    "is_active": me_camera.get("enabled", True),
                    "width": me_camera.get("width", 1280),
                    "height": me_camera.get("height", 720),
                    "framerate": me_camera.get("framerate", 30),
                    "stream_port": me_camera.get("streaming_port", 8081),
                    "stream_quality": me_camera.get("streaming_quality", 100),
                    "stream_maxrate": me_camera.get("streaming_framerate", 30),
                    "stream_localhost": False,  # MotionEye doesn't have this field
                    "detection_enabled": me_camera.get("motion_detection", True),
                    "detection_threshold": me_camera.get("frame_change_threshold", 1500),
                    "detection_smart_mask_speed": me_camera.get("smart_mask_sluggishness", 10),
                    "movie_output": me_camera.get("movies", True),
                    "movie_quality": me_camera.get("movie_quality", 100),
                    "movie_codec": me_camera.get("movie_format", "mkv"),
                    "snapshot_interval": me_camera.get("snapshot_interval", 0),
                    "target_dir": me_camera.get("root_directory", "./motioneye_media")
                }
                
                db_camera = Camera(**camera_data)
                db.add(db_camera)
                synced_count += 1
                print(f"Auto-synced camera: {camera_name} (ID: {camera_id})")
        
        db.commit()
        
        if synced_count > 0:
            print(f"Auto-synced {synced_count} cameras from MotionEye")
    except Exception as e:
        print(f"Error syncing cameras: {e}")
    finally:
        db.close()
                    
# Background camera sync task (periodic)
async def periodic_camera_sync():
    """Periodically sync cameras from MotionEye every 2 minutes"""
    while True:
        try:
            await sync_cameras_background_task()
        except Exception as e:
            print(f"Camera sync periodic task error: {e}")
        await asyncio.sleep(120)  # 2 minutes

async def sync_cameras_background_task():
    """Background task to sync cameras from MotionEye"""
    try:
        # Wait a bit for MotionEye to be ready
        await asyncio.sleep(5)
        
        # Try to get cameras from MotionEye
        try:
            loop = asyncio.get_event_loop()
            cameras = await asyncio.wait_for(
                loop.run_in_executor(None, motioneye_client.get_cameras),
                timeout=5.0
            )
            if cameras:
                print(f"MotionEye connection successful. Found {len(cameras)} cameras")
                await sync_cameras_background(cameras)
            else:
                print("No cameras found in MotionEye")
        except asyncio.TimeoutError:
            print("MotionEye connection timeout - will retry later")
        except Exception as e:
            print(f"MotionEye connection failed: {e}")
    except Exception as e:
        print(f"Camera sync background task error: {e}")

# One-time scan runner for startup sync
async def run_photo_scanner_once():
    try:
        # Wait for SpeciesNet server to be ready - but don't block startup
        print("Waiting for SpeciesNet server to initialize...")
        max_wait_time = 30  # Wait up to 30 seconds
        wait_interval = 2   # Check every 2 seconds
        
        for i in range(max_wait_time // wait_interval):
            status = speciesnet_processor.get_status()
            if status == "running":
                print("SpeciesNet server is ready!")
                break
            elif status == "timeout":
                print(f"SpeciesNet server still initializing... ({i+1}/{max_wait_time//wait_interval})")
            else:
                print(f"SpeciesNet server status: {status}")
            
            await asyncio.sleep(wait_interval)
        else:
            print("SpeciesNet server failed to initialize within timeout, skipping initial scan")
            return
        
        # Now run the photo scanner
        db = next(get_db())
        scanner = PhotoScanner(db)
        await scanner.scan_and_process()
        db.close()
    except Exception as e:
        print(f"Photo scanner initial sync error: {e}")

# Pydantic models
class CameraBase(BaseModel):
    name: str
    url: str
    is_active: bool = True
    width: int = 1280
    height: int = 720
    framerate: int = 30
    stream_port: int = 8081
    stream_quality: int = 100
    stream_maxrate: int = 30
    stream_localhost: bool = False
    detection_enabled: bool = True
    detection_threshold: int = 1500
    detection_smart_mask_speed: int = 10
    movie_output: bool = True
    movie_quality: int = 100
    movie_codec: str = "mkv"
    snapshot_interval: int = 0
    target_dir: str = "./motioneye_media"

class CameraCreate(CameraBase):
    pass

class CameraResponse(CameraBase):
    id: int
    created_at: datetime
    stream_url: Optional[str] = None
    mjpeg_url: Optional[str] = None

    class Config:
        from_attributes = True

class DetectionBase(BaseModel):
    camera_id: int
    species: str
    confidence: float
    image_path: str
    file_size: Optional[int] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    image_quality: Optional[int] = None
    prediction_score: Optional[float] = None
    detections_json: Optional[str] = None

class DetectionCreate(DetectionBase):
    pass

class DetectionResponse(DetectionBase):
    id: int
    timestamp: datetime
    media_url: Optional[str] = None
    camera_name: str

    class Config:
        from_attributes = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API endpoints
@app.get("/")
def read_root():
    return {"message": "Wildlife Monitoring API with SpeciesNet Integration"}

@app.get("/health")
def health_check():
    """Simple health check that responds immediately"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/health")
def health_check_api():
    """API health check endpoint"""
    return health_check()

@app.get("/system")
async def get_system_health() -> Dict[str, Any]:
    """Get system health and status information"""
    import asyncio
    from datetime import datetime
    import psutil
    try:
        # Get system metrics immediately
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        # Prepare default statuses
        motioneye_status = "unknown"
        cameras_count = 0
        speciesnet_status = "unknown"
        loop = asyncio.get_event_loop()
        # Try to get MotionEye status with a longer timeout
        try:
            cameras = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: motioneye_client.get_cameras()),
                timeout=2.0
            )
            cameras_count = len(cameras)
            motioneye_status = "running" if cameras_count > 0 else "no_cameras"
        except asyncio.TimeoutError:
            motioneye_status = "timeout"
        except Exception as e:
            print(f"MotionEye connection failed: {e}")
            motioneye_status = "error"
        # Try to get SpeciesNet status with a longer timeout
        try:
            speciesnet_status = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: speciesnet_processor.get_status()),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            speciesnet_status = "timeout"
        except Exception as e:
            print(f"SpeciesNet status check failed: {e}")
            speciesnet_status = "error"
        # Compose response
        return {
            "status": "running",
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "timestamp": datetime.utcnow().isoformat()
            },
            "motioneye": {
                "status": motioneye_status,
                "cameras_count": cameras_count
            },
            "speciesnet": {
                "status": speciesnet_status
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system health: {str(e)}")

@app.get("/api/system")
async def get_system_health_api() -> Dict[str, Any]:
    """Alias for /system to support frontend API calls"""
    return await get_system_health()

@app.get("/cameras", response_model=List[CameraResponse])
def get_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()
    return cameras

@app.get("/api/cameras", response_model=List[CameraResponse])
def get_cameras_api(db: Session = Depends(get_db)):
    """Alias for /cameras to support frontend API calls"""
    return get_cameras(db)

@app.post("/cameras/sync")
def sync_cameras_from_motioneye(db: Session = Depends(get_db)):
    """Sync cameras from MotionEye to database"""
    try:
        # Get cameras from MotionEye
        motioneye_cameras = motioneye_client.get_cameras()
        
        if not motioneye_cameras:
            return {"message": "No cameras found in MotionEye", "synced": 0}
        
        synced_count = 0
        
        for me_camera in motioneye_cameras:
            camera_id = me_camera.get("id")
            camera_name = me_camera.get("name", f"Camera{camera_id}")
            
            # Check if camera already exists in database
            existing_camera = db.query(Camera).filter(Camera.id == camera_id).first()
            
            if not existing_camera:
                # Create new camera in database
                camera_data = {
                    "id": camera_id,
                    "name": camera_name,
                    "url": me_camera.get("device_url", ""),  # MotionEye uses device_url
                    "is_active": me_camera.get("enabled", True),
                    "width": me_camera.get("width", 1280),
                    "height": me_camera.get("height", 720),
                    "framerate": me_camera.get("framerate", 30),
                    "stream_port": me_camera.get("streaming_port", 8081),
                    "stream_quality": me_camera.get("streaming_quality", 100),
                    "stream_maxrate": me_camera.get("streaming_framerate", 30),
                    "stream_localhost": False,  # MotionEye doesn't have this field
                    "detection_enabled": me_camera.get("motion_detection", True),
                    "detection_threshold": me_camera.get("frame_change_threshold", 1500),
                    "detection_smart_mask_speed": me_camera.get("smart_mask_sluggishness", 10),
                    "movie_output": me_camera.get("movies", True),
                    "movie_quality": me_camera.get("movie_quality", 100),
                    "movie_codec": me_camera.get("movie_format", "mkv"),
                    "snapshot_interval": me_camera.get("snapshot_interval", 0),
                    "target_dir": me_camera.get("root_directory", "./motioneye_media")
                }
                
                db_camera = Camera(**camera_data)
                db.add(db_camera)
                synced_count += 1
                print(f"Synced camera: {camera_name} (ID: {camera_id})")
            else:
                # Update existing camera
                existing_camera.name = camera_name
                existing_camera.url = me_camera.get("device_url", existing_camera.url)
                existing_camera.is_active = me_camera.get("enabled", existing_camera.is_active)
                existing_camera.width = me_camera.get("width", existing_camera.width)
                existing_camera.height = me_camera.get("height", existing_camera.height)
                existing_camera.framerate = me_camera.get("framerate", existing_camera.framerate)
                print(f"Updated camera: {camera_name} (ID: {camera_id})")
        
        db.commit()
        
        return {
            "message": f"Successfully synced {synced_count} cameras from MotionEye",
            "synced": synced_count,
            "total_cameras": len(motioneye_cameras)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing cameras: {str(e)}")

@app.post("/cameras", response_model=CameraResponse)
def add_camera(camera: CameraCreate, db: Session = Depends(get_db)):
    # Create camera in database
    db_camera = Camera(**camera.dict())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    
    # Add camera to MotionEye
    motioneye_config = {
        "name": camera.name,
        "netcam_url": camera.url,
        "width": camera.width,
        "height": camera.height,
        "framerate": camera.framerate,
        "stream_quality": camera.stream_quality,
        "stream_maxrate": camera.stream_maxrate,
        "stream_localhost": camera.stream_localhost,
        "motion_detection": camera.detection_enabled,
        "motion_threshold": camera.detection_threshold,
        "motion_smart_mask_speed": camera.detection_smart_mask_speed,
        "movie_output": camera.movie_output,
        "movie_quality": camera.movie_quality,
        "movie_codec": camera.movie_codec,
        "snapshot_interval": camera.snapshot_interval,
        "target_dir": camera.target_dir
    }
    
    success = motioneye_client.add_camera(motioneye_config)
    if not success:
        # Rollback database if MotionEye fails
        db.delete(db_camera)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to add camera to MotionEye")
    
    # Add stream URLs
    db_camera.stream_url = motioneye_client.get_camera_stream_url(db_camera.id)
    db_camera.mjpeg_url = motioneye_client.get_camera_mjpeg_url(db_camera.id)
    
    return db_camera

@app.get("/detections", response_model=List[DetectionResponse])
def get_detections(
    camera_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get detections with optional filtering and pagination"""
    query = db.query(Detection)
    
    if camera_id is not None:
        query = query.filter(Detection.camera_id == camera_id)
    
    # Apply ordering first
    query = query.order_by(Detection.timestamp.desc())
    
    # Apply offset if provided
    if offset is not None:
        query = query.offset(offset)
    
    # Apply limit if provided, otherwise default to 50
    if limit is not None:
        query = query.limit(limit)
    else:
        query = query.limit(50)
    
    detections = query.all()
    
    # Batch-fetch all cameras to avoid N+1 queries
    camera_ids = {d.camera_id for d in detections}
    cameras = {c.id: c for c in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()}
    
    # Convert to response models with media URLs
    result = []
    for detection in detections:
        camera = cameras.get(detection.camera_id)
        camera_name = camera.name if camera else f"Camera {detection.camera_id}"
        
        detection_dict = {
            "id": detection.id,
            "camera_id": detection.camera_id,
            "timestamp": detection.timestamp,
            "species": detection.species,
            "confidence": detection.confidence,
            "image_path": detection.image_path,
            "file_size": detection.file_size,
            "image_width": detection.image_width,
            "image_height": detection.image_height,
            "image_quality": detection.image_quality,
            "prediction_score": detection.prediction_score,
            "detections_json": detection.detections_json,
            "media_url": None,  # Will be set below
            "camera_name": camera_name  # Add camera name to response
        }
        
        # Generate media URL from image path
        if detection.image_path:
            try:
                # Normalize path for both Windows and Linux
                path = detection.image_path.replace("\\", "/")
                parts = path.split("/")
                # Look for motioneye_media/CameraX/date/filename or archived_photos/common_name/camera/date/filename
                if "motioneye_media" in parts:
                    idx = parts.index("motioneye_media")
                    if len(parts) > idx + 3:
                        camera_folder = parts[idx + 1]  # Camera1
                        date_folder = parts[idx + 2]    # 2025-07-15
                        filename = parts[idx + 3]       # 11-00-07.jpg
                        detection_dict["media_url"] = f"/media/{camera_folder}/{date_folder}/{filename}"
                elif "archived_photos" in parts:
                    idx = parts.index("archived_photos")
                    if len(parts) > idx + 4:
                        # archived_photos/common_name/camera/date/filename
                        camera_folder = parts[idx + 2]  # 1 or Camera1
                        date_folder = parts[idx + 3]    # 2025-07-15
                        filename = parts[idx + 4]       # 11-00-07.jpg
                        # Use CameraX format for consistency
                        if not str(camera_folder).startswith("Camera"):
                            camera_folder = f"Camera{camera_folder}"
                        detection_dict["media_url"] = f"/media/{camera_folder}/{date_folder}/{filename}"
            except Exception as e:
                print(f"Error generating media_url for detection {detection.id}: {e}")
                detection_dict["media_url"] = None
        result.append(DetectionResponse(**detection_dict))
    return result

@app.get("/api/detections", response_model=List[DetectionResponse])
def get_detections_api(
    camera_id: Optional[int] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Alias for /detections to support frontend API calls"""
    return get_detections(camera_id, limit, db)

@app.post("/detections", response_model=DetectionResponse)
def create_detection(detection: DetectionCreate, db: Session = Depends(get_db)):
    db_detection = Detection(**detection.dict())
    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    return db_detection

@app.post("/process-image")
async def process_image_with_speciesnet(
    file: UploadFile = File(...),
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Process an uploaded image with SpeciesNet"""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Process with SpeciesNet
        predictions = speciesnet_processor.process_image(temp_path)
        
        if "error" in predictions:
            raise HTTPException(status_code=500, detail=predictions["error"])
        
        # Save detection to database
        if "predictions" in predictions and predictions["predictions"]:
            pred = predictions["predictions"][0]
            
            # Create detection record
            detection_data = {
                "camera_id": camera_id or 1,
                "species": pred.get("prediction", "Unknown"),
                "confidence": pred.get("prediction_score", 0.0),
                "image_path": temp_path,
                "detections_json": json.dumps(predictions),
                "prediction_score": pred.get("prediction_score", 0.0)
            }
            
            db_detection = Detection(**detection_data)
            db.add(db_detection)
            db.commit()
            db.refresh(db_detection)
            
            return {
                "detection": db_detection,
                "predictions": predictions
            }
        else:
            return {"predictions": predictions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{camera_id}")
def get_camera_stream(camera_id: int, db: Session = Depends(get_db)):
    """Get camera stream information"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return {
        "camera_id": camera_id,
        "camera_name": camera.name,
        "rtsp_url": camera.url,
        "stream_url": motioneye_client.get_camera_stream_url(camera_id),
        "mjpeg_url": motioneye_client.get_camera_mjpeg_url(camera_id),
        "motioneye_url": MOTIONEYE_URL
    }

@app.post("/api/motioneye/webhook")
async def motioneye_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle MotionEye webhook notifications for motion detection"""
    try:
        # Get the JSON data from MotionEye
        data = await request.json()
        
        print(f"MotionEye webhook received: {data}")
        
        # MotionEye sends JSON with these typical fields:
        # - camera_id: ID of the camera
        # - file_path: Path to the saved image/video file
        # - timestamp: When the event occurred
        # - type: Type of event (picture_save, movie_end, etc.)
        
        camera_id = data.get("camera_id")
        file_path = data.get("file_path")
        timestamp = data.get("timestamp")
        event_type = data.get("type", "unknown")
        
        print(f"Event type: {event_type}, Camera ID: {camera_id}, File: {file_path}")
        
        if not camera_id or not file_path:
            print(f"Missing camera_id or file_path in webhook data: {data}")
            return {"status": "error", "message": "Missing required data"}
        
        # Convert MotionEye file path to local path
        # MotionEye stores files in /var/lib/motioneye inside the container
        # We need to map this to our local motioneye_media directory
        # Get the absolute path to the wildlife-app directory
        wildlife_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Extract the relative path from MotionEye's path
        # MotionEye sends: /var/lib/motioneye/Camera1/2025-06-26/13-57-02.jpg
        # We want: motioneye_media/Camera1/2025-06-26/13-57-02.jpg
        if file_path.startswith("/var/lib/motioneye/"):
            relative_path = file_path[len("/var/lib/motioneye/"):]
            local_file_path = os.path.join(wildlife_app_dir, "motioneye_media", relative_path)
        else:
            # Fallback: try direct replacement
            local_file_path = file_path.replace("/var/lib/motioneye", os.path.join(wildlife_app_dir, "motioneye_media"))
        
        print(f"Original MotionEye path: {file_path}")
        print(f"Converted local path: {local_file_path}")
        
        # Check if file exists
        if not os.path.exists(local_file_path):
            print(f"File not found: {local_file_path}")
            return {"status": "error", "message": "File not found"}
        
        # Extract date and camera name from the file path for media URL
        path_parts = local_file_path.split(os.sep)
        extracted_camera_name = None
        file_date = None
        
        # Find camera name and date in the path
        for i, part in enumerate(path_parts):
            if part == "motioneye_media" and i + 1 < len(path_parts):
                extracted_camera_name = path_parts[i + 1]  # Camera1, Camera2, etc.
            if extracted_camera_name and i + 1 < len(path_parts) and "-" in part and len(part) == 10:
                file_date = part  # 2025-06-26
                break
        
        # If we couldn't extract date from path, use current date as fallback
        if not file_date:
            file_date = datetime.now().strftime('%Y-%m-%d')
        
        # If we couldn't extract camera name, use camera_id as fallback
        if not extracted_camera_name:
            extracted_camera_name = f"Camera{camera_id}"
        
        # Only process image files (not videos for now)
        if not local_file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            print(f"Skipping non-image file: {local_file_path}")
            return {"status": "skipped", "message": "Not an image file"}
        
        # Process image with SpeciesNet
        predictions = speciesnet_processor.process_image(local_file_path)
        
        if "error" in predictions:
            print(f"SpeciesNet processing error: {predictions['error']}")
            # Still save the detection, but mark as unprocessed
            detection_data = {
                "camera_id": camera_id,
                "species": "Unknown",
                "confidence": 0.0,
                "image_path": local_file_path,
                "detections_json": json.dumps({"error": predictions["error"]}),
                "prediction_score": 0.0
            }
        else:
            # Debug: Print the actual predictions structure
            print(f"SpeciesNet predictions: {json.dumps(predictions, indent=2)}")
            
            # Extract species prediction
            species = "Unknown"
            confidence = 0.0
            
            # Try different possible response structures
            if isinstance(predictions, dict):
                if "predictions" in predictions and predictions["predictions"]:
                    pred = predictions["predictions"][0]
                    species = pred.get("prediction", "Unknown")
                    confidence = pred.get("prediction_score", 0.0)
                elif "instances" in predictions:
                    # Direct response format
                    for instance in predictions["instances"]:
                        if "prediction" in instance:
                            species = instance["prediction"]
                            confidence = instance.get("prediction_score", 0.0)
                            break
                elif "results" in predictions:
                    # Another possible format
                    results = predictions["results"]
                    if results and len(results) > 0:
                        result = results[0]
                        species = result.get("prediction", "Unknown")
                        confidence = result.get("confidence", 0.0)
                else:
                    # Try to find any prediction-like field
                    for key, value in predictions.items():
                        if "prediction" in key.lower() and isinstance(value, str):
                            species = value
                            break
                        if "confidence" in key.lower() and isinstance(value, (int, float)):
                            confidence = value
            
            # Clean up species name - extract common name from taxonomy
            if species and ";" in species:
                # Take the last part after semicolons (common name)
                species = species.split(";")[-1].title()
            elif species and species != "Unknown":
                # If it's a UUID or complex format, try to extract meaningful part
                if len(species) > 50:  # Likely a complex taxonomy string
                    parts = species.split(";")
                    if len(parts) > 1:
                        species = parts[-1].title()  # Use last part
                    else:
                        species = "Unknown"
            
            # Save detection to database
            detection_data = {
                "camera_id": camera_id,
                "timestamp": datetime.now(),
                "species": species,
                "confidence": confidence,
                "image_path": local_file_path,
                "detections_json": json.dumps(predictions),
                "prediction_score": confidence
            }
        
        # Create detection record
        db_detection = Detection(**detection_data)
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        print(f"Detection saved: ID={db_detection.id}, Species={detection_data['species']}, Confidence={detection_data['confidence']}")
        
        # Get camera information for the response - use database name if available, otherwise use extracted name
        camera_info = db.query(Camera).filter(Camera.id == camera_id).first()
        camera_name = camera_info.name if camera_info else extracted_camera_name
        
        # Broadcast the new detection to connected clients
        detection_event = {
            "id": db_detection.id,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "species": detection_data["species"],
            "confidence": detection_data["confidence"],
            "image_path": local_file_path,
            "timestamp": db_detection.timestamp.isoformat(),
            "media_url": f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}"
        }
        await event_manager.broadcast_detection(detection_event)
        
        return {
            "status": "success",
            "detection_id": db_detection.id,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "species": detection_data["species"],
            "confidence": detection_data["confidence"],
            "file_path": local_file_path,
            "media_url": f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}"
        }
        
    except Exception as e:
        print(f"Error processing MotionEye webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events/detections")
async def stream_detections():
    """Server-Sent Events endpoint for real-time detection updates"""
    async def event_generator():
        client_id = await event_manager.add_client()
        try:
            while True:
                try:
                    # Get event from client queue
                    client_queue = await event_manager.get_client_queue(client_id)
                    if not client_queue:
                        break
                    
                    event = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    yield f"data: {json.dumps(event)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                except Exception as e:
                    logging.error(f"Error in detection stream: {e}")
                    break
        finally:
            await event_manager.remove_client(client_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.get("/events/system")
async def stream_system_updates():
    """Server-Sent Events endpoint for real-time system updates"""
    async def event_generator():
        client_id = await event_manager.add_client()
        try:
            while True:
                try:
                    # Get event from client queue
                    client_queue = await event_manager.get_client_queue(client_id)
                    if not client_queue:
                        break
                    
                    event = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    
                    # Format as SSE
                    yield f"data: {json.dumps(event)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
                except Exception as e:
                    logging.error(f"Error in system stream: {e}")
                    break
        finally:
            await event_manager.remove_client(client_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.get("/media/{camera}/{date}/{filename}")
def get_media(camera: str, date: str, filename: str):
    # Always resolve from the project root (wildlife-app)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    camera_name = f"Camera{camera}" if camera.isdigit() else camera
    
    # First try to find the file in motioneye_media
    motioneye_path = os.path.join(
        project_root,
        "motioneye_media", camera_name, date, filename
    )
    
    # Also check in archived_photos (search all species folders)
    archive_path = None
    archive_root = os.path.join(project_root, "archived_photos")
    if os.path.exists(archive_root):
        # Search all subfolders (species folders) for the file
        for species_folder in os.listdir(archive_root):
            species_path = os.path.join(archive_root, species_folder, camera, date, filename)
            if os.path.exists(species_path):
                archive_path = species_path
                break
            # Also try with camera_name (CameraX) for robustness
            species_path_alt = os.path.join(archive_root, species_folder, camera_name, date, filename)
            if os.path.exists(species_path_alt):
                archive_path = species_path_alt
                break
    
    print(f"Media request: camera={camera}, date={date}, filename={filename}")
    print(f"Looking for file in motioneye: {motioneye_path}")
    print(f"Looking for file in archive: {archive_path}")
    
    # Return the file from wherever it's found
    if os.path.exists(motioneye_path):
        return FileResponse(motioneye_path)
    elif archive_path and os.path.exists(archive_path):
        return FileResponse(archive_path)
    else:
        raise HTTPException(status_code=404, detail=f"File not found in motioneye_media or archive")

@app.get("/detections/count")
def get_detections_count(
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get total count of detections"""
    query = db.query(Detection)
    if camera_id:
        query = query.filter(Detection.camera_id == camera_id)
    count = query.count()
    return {"count": count}

@app.get("/api/detections/count")
def get_detections_count_api(
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Alias for /detections/count to support frontend API calls"""
    return get_detections_count(camera_id, db)

@app.get("/detections/species-counts")
def get_species_counts(
    range: str = "all",  # "week", "month", "all"
    db: Session = Depends(get_db)
):
    """Get species counts for different time ranges"""
    from datetime import datetime, timedelta
    
    # Base query
    query = db.query(Detection.species, func.count(Detection.id).label('count'))
    
    # Apply time filter
    if range == "week":
        week_ago = datetime.now() - timedelta(days=7)
        query = query.filter(Detection.timestamp >= week_ago)
    elif range == "month":
        month_ago = datetime.now() - timedelta(days=30)
        query = query.filter(Detection.timestamp >= month_ago)
    
    # Group by species and get counts
    results = query.group_by(Detection.species).order_by(func.count(Detection.id).desc()).limit(10).all()
    
    # Format results
    species_counts = []
    for species, count in results:
        species_counts.append({
            "species": species or "Unknown",
            "count": count
        })
    
    return species_counts

@app.get("/detections/unique-species-count")
def analytics_detections_unique_species_count(
    days: int = 30
):
    """Return the number of unique species detected in the last N days."""
    sql = f"""
        SELECT COUNT(DISTINCT species) as unique_species
        FROM detections_iceberg
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        unique_species = result.scalar()
    return {"unique_species": unique_species}

class PhotoScanner:
    def __init__(self, db: Session):
        self.db = db
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.media_root = os.path.join(self.project_root, "motioneye_media")
        self.archive_root = os.path.join(self.project_root, "archived_photos")  # New archive folder
        self.processed_files = set()
        
        # Create archive directory if it doesn't exist
        os.makedirs(self.archive_root, exist_ok=True)
        
        self.load_processed_files()
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file"""
        h = sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def load_processed_files(self):
        """Load set of already processed file hashes from database"""
        detections = self.db.query(Detection).all()
        self.processed_hashes = set()
        for detection in detections:
            if detection.file_hash:
                self.processed_hashes.add(detection.file_hash)
        print(f"[PhotoScanner] Loaded {len(self.processed_hashes)} processed file hashes from database.")

    def get_file_id(self, file_path: str) -> str:
        """Create unique identifier for a file"""
        # Use camera + date + filename as unique ID
        path_parts = file_path.split(os.sep)
        if len(path_parts) >= 3:
            camera = path_parts[-3]  # Camera1, Camera2, etc.
            date = path_parts[-2]    # 2025-06-20
            filename = path_parts[-1] # 17-40-48.jpg
            return f"{camera}_{date}_{filename}"
        return file_path
    
    def archive_photo(self, original_path: str, species: str, camera_id: int) -> str:
        """Archive a photo to the archive folder with species-based organization"""
        try:
            # Skip archiving if species is "Unknown"
            if species.lower() == "unknown":
                return original_path

            # Use only the common name (last part after semicolons) for the species folder
            common_name = species.split(';')[-1].strip() if ';' in species else species.strip()

            # Create archive path: archived_photos/species/camera_id/date/filename
            path_parts = original_path.split(os.sep)
            if len(path_parts) >= 3:
                date = path_parts[-2]  # 2025-06-20
                filename = path_parts[-1]  # 17-40-48.jpg

                # Create archive directory structure
                archive_dir = os.path.join(self.archive_root, common_name.lower(), str(camera_id), date)
                os.makedirs(archive_dir, exist_ok=True)

                # Archive file path
                archive_path = os.path.join(archive_dir, filename)

                # Copy the file to archive
                if os.path.exists(original_path):
                    shutil.copy2(original_path, archive_path)
                    print(f"Archived photo: {original_path} -> {archive_path}")
                    return archive_path
                else:
                    print(f"Original photo not found: {original_path}")
                    return original_path
            else:
                print(f"Invalid path structure: {original_path}")
                return original_path

        except Exception as e:
            print(f"Error archiving photo {original_path}: {e}")
            return original_path
    
    def scan_for_unprocessed_photos(self) -> list:
        """Scan motioneye_media folders for photos not in database (by file hash)"""
        unprocessed_photos = []
        if not os.path.exists(self.media_root):
            print(f"[PhotoScanner] media_root does not exist: {self.media_root}")
            return unprocessed_photos
        for camera_folder in os.listdir(self.media_root):
            camera_path = os.path.join(self.media_root, camera_folder)
            if not os.path.isdir(camera_path):
                continue
            for date_folder in os.listdir(camera_path):
                date_path = os.path.join(camera_path, date_folder)
                if not os.path.isdir(date_path) or len(date_folder) != 10:
                    continue
                for filename in os.listdir(date_path):
                    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    file_path = os.path.join(date_path, filename)
                    try:
                        file_hash = self.compute_file_hash(file_path)
                    except Exception as e:
                        print(f"[PhotoScanner] Error hashing {file_path}: {e}")
                        continue
                    if file_hash not in self.processed_hashes:
                        unprocessed_photos.append({
                            'file_path': file_path,
                            'camera': camera_folder,
                            'date': date_folder,
                            'filename': filename,
                            'file_hash': file_hash
                        })
                    else:
                        print(f"[PhotoScanner] Skipping already processed file (by hash): {file_path}")
        print(f"[PhotoScanner] Found {len(unprocessed_photos)} unprocessed photos.")
        return unprocessed_photos
    
    async def process_photo(self, photo_info: dict):
        """Process a single photo with SpeciesNet, using file hash deduplication"""
        try:
            camera_id = int(photo_info['camera'].replace('Camera', ''))
            camera = self.db.query(Camera).filter(Camera.id == camera_id).first()
            if not camera:
                print(f"Camera {camera_id} not found in database, skipping {photo_info['filename']}")
                return
            file_hash = photo_info.get('file_hash')
            if not file_hash:
                file_hash = self.compute_file_hash(photo_info['file_path'])
            # Double-check hash not in DB (race condition safety)
            if self.db.query(Detection).filter(Detection.file_hash == file_hash).first():
                print(f"[PhotoScanner] File hash already in DB, skipping: {photo_info['file_path']}")
                return
            speciesnet_response = await self.call_speciesnet(photo_info['file_path'])
            if not speciesnet_response:
                print(f"SpeciesNet processing failed for {photo_info['filename']}")
                return
            species = "Unknown"
            confidence = 0.0
            if "predictions" in speciesnet_response and speciesnet_response["predictions"]:
                pred = speciesnet_response["predictions"][0]
                species = pred.get("prediction", "Unknown")
                confidence = pred.get("prediction_score", 0.0)
            elif "species" in speciesnet_response:
                species = speciesnet_response.get("species", "Unknown")
                confidence = speciesnet_response.get("confidence", 0.0)
            archived_path = self.archive_photo(photo_info['file_path'], species, camera_id)
            detection_data = {
                "camera_id": camera_id,
                "timestamp": datetime.now(),
                "species": species,
                "confidence": confidence,
                "image_path": archived_path,
                "detections_json": str(speciesnet_response),
                "file_hash": file_hash
            }
            db_detection = Detection(**detection_data)
            self.db.add(db_detection)
            self.db.commit()
            self.db.refresh(db_detection)
            self.processed_hashes.add(file_hash)
            if species.lower() != "unknown":
                print(f"Processed and archived photo: {photo_info['filename']} -> {detection_data['species']} ({detection_data['confidence']:.2f})")
            else:
                print(f"Processed photo (not archived - unknown species): {photo_info['filename']} -> {detection_data['species']} ({detection_data['confidence']:.2f})")
        except Exception as e:
            print(f"Error processing {photo_info['filename']}: {e}")
    
    async def call_speciesnet(self, image_path: str) -> dict:
        """Call SpeciesNet server to process image with proper rate limiting"""
        try:
            # Use the existing SpeciesNet processor that already works
            result = speciesnet_processor.process_image(image_path)
            
            # Check if the result contains an error
            if "error" in result:
                print(f"SpeciesNet error for {os.path.basename(image_path)}: {result['error']}")
                return None
            
            return result
                        
        except Exception as e:
            print(f"SpeciesNet call failed for {os.path.basename(image_path)}: {e}")
            return None
    
    async def scan_and_process(self):
        """Main scanning and processing function with intelligent rate limiting"""
        print("Starting photo scanner...")
        try:
            speciesnet_status = speciesnet_processor.get_status()
            if speciesnet_status != "running":
                print(f"SpeciesNet server not healthy ({speciesnet_status}), skipping photo processing")
                return
            self.load_processed_files()
            unprocessed = self.scan_for_unprocessed_photos()
            if unprocessed:
                print(f"[PhotoScanner] Processing {len(unprocessed)} photos this cycle (processing all)")
                for i, photo in enumerate(unprocessed):
                    print(f"[PhotoScanner] Processing photo {i+1}/{len(unprocessed)}: {photo['filename']}")
                    if speciesnet_processor.get_status() != "running":
                        print("SpeciesNet server became unhealthy, stopping processing")
                        break
                    await self.process_photo(photo)
                print(f"[PhotoScanner] Completed processing {len(unprocessed)} photos this cycle")
                print("[PhotoScanner] Waiting 5 seconds after batch...")
                await asyncio.sleep(5)
            else:
                print("[PhotoScanner] No unprocessed photos found")
        except Exception as e:
            print(f"Photo scanner error: {e}")

# Background task to run photo scanner
async def run_photo_scanner():
    """Background task that runs photo scanner periodically"""
    while True:
        try:
            # Check if SpeciesNet server is ready before processing
            status = speciesnet_processor.get_status()
            if status != "running":
                print(f"SpeciesNet server not ready ({status}), skipping photo processing cycle")
                await asyncio.sleep(300)  # Wait 5 minutes before checking again
                continue
            
            # Get database session
            db = next(get_db())
            scanner = PhotoScanner(db)
            await scanner.scan_and_process()
            db.close()
        except Exception as e:
            print(f"Photo scanner background task error: {e}")
        
        # Wait 15 minutes before next scan (much more conservative)
        print("Photo scanner sleeping for 15 minutes...")
        await asyncio.sleep(900)  # 15 minutes

@app.get("/api/trigger-photo-scan")
async def trigger_photo_scan():
    """Manually trigger photo scanner to process unprocessed photos"""
    try:
        # Get database session
        db = next(get_db())
        scanner = PhotoScanner(db)
        await scanner.scan_and_process()
        db.close()
        return {"message": "Photo scan completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Photo scan failed: {str(e)}")

@app.get("/api/photo-scan-status")
async def get_photo_scan_status():
    """Get status of photo scanner and statistics"""
    try:
        db = next(get_db())
        scanner = PhotoScanner(db)
        
        # Load current processed files
        scanner.load_processed_files()
        
        # Scan for unprocessed photos
        unprocessed = scanner.scan_for_unprocessed_photos()
        
        # Count total photos in media folders
        total_photos = 0
        if os.path.exists(scanner.media_root):
            for camera_folder in os.listdir(scanner.media_root):
                camera_path = os.path.join(scanner.media_root, camera_folder)
                if not os.path.isdir(camera_path):
                    continue
                    
                for date_folder in os.listdir(camera_path):
                    date_path = os.path.join(camera_path, date_folder)
                    if not os.path.isdir(date_path) or len(date_folder) != 10:
                        continue
                    
                    for filename in os.listdir(date_path):
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                            total_photos += 1
        
        processed_count = len(scanner.processed_files)
        unprocessed_count = len(unprocessed)
        
        return {
            "total_photos": total_photos,
            "processed_photos": processed_count,
            "unprocessed_photos": unprocessed_count,
            "last_scan": "Background scanner runs every 15 minutes",
            "scanner_active": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scan status: {str(e)}")
    finally:
        db.close()

@app.get("/analytics/detections/timeseries")
def analytics_detections_timeseries(
    interval: str = "hour",  # "hour" or "day"
    days: int = 7
):
    """Return detection counts grouped by hour or day for the last N days."""
    if interval not in ("hour", "day"):
        return JSONResponse(status_code=400, content={"error": "Invalid interval. Use 'hour' or 'day'."})
    group_expr = "date_trunc('{}', timestamp)".format(interval)
    sql = f"""
        SELECT {group_expr} as bucket, COUNT(*) as count
        FROM detections_iceberg
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
        GROUP BY bucket
        ORDER BY bucket ASC
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        data = [{"bucket": str(row[0]), "count": row[1]} for row in result]
    return data

@app.get("/analytics/detections/top_species")
def analytics_detections_top_species(
    limit: int = 5,
    days: int = 30
):
    """Return the top N species detected in the last N days."""
    sql = f"""
        SELECT species, COUNT(*) as count
        FROM detections_iceberg
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
        GROUP BY species
        ORDER BY count DESC
        LIMIT {limit}
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        data = [{"species": row[0], "count": row[1]} for row in result]
    return data

@app.get("/analytics/detections/unique_species_count")
def analytics_detections_unique_species_count(
    days: int = 30
):
    """Return the number of unique species detected in the last N days."""
    sql = f"""
        SELECT COUNT(DISTINCT species) as unique_species
        FROM detections_iceberg
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        unique_species = result.scalar()
    return {"unique_species": unique_species}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 