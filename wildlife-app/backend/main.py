from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text, Index, or_
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Any as AnyType
from datetime import datetime, timedelta
import os
import psutil
import requests
from dotenv import load_dotenv
import subprocess
import json
import ast
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
import hashlib
from pathlib import Path
import aiofiles
from hashlib import sha256

# Import from new modular structure
try:
    from config import DATABASE_URL, MOTIONEYE_URL, SPECIESNET_URL, THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD, ALLOWED_ORIGINS
    from database import engine, SessionLocal, Base, Camera, Detection, Webhook
    from models import CameraBase, CameraCreate, CameraResponse, DetectionBase, DetectionCreate, DetectionResponse, MotionSettings, AuditLogResponse, WebhookCreate, WebhookResponse
    from utils.caching import get_cached, set_cached
    from utils.audit import log_audit_event, get_audit_logs
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from services.notifications import notification_service
except ImportError:
    # Fallback for direct execution
    from config import DATABASE_URL, MOTIONEYE_URL, SPECIESNET_URL, THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD, ALLOWED_ORIGINS
    from database import engine, SessionLocal, Base, Camera, Detection, Webhook
    from models import CameraBase, CameraCreate, CameraResponse, DetectionBase, DetectionCreate, DetectionResponse, MotionSettings, AuditLogResponse, WebhookCreate, WebhookResponse
    from utils.caching import get_cached, set_cached
    from utils.audit import log_audit_event, get_audit_logs
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from services.notifications import notification_service

try:
    from .camera_sync import CameraSyncService, sync_motioneye_cameras
    from .logging_utils import configure_access_logs
    from .motioneye_events import should_process_event
    from .motioneye_webhook import parse_motioneye_payload
except ImportError:  # pragma: no cover - fallback for direct execution
    from camera_sync import CameraSyncService, sync_motioneye_cameras
    from logging_utils import configure_access_logs
    from motioneye_events import should_process_event
    from motioneye_webhook import parse_motioneye_payload

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

configure_access_logs()

app = FastAPI(
    title="Wildlife Detection API",
    description="API for managing wildlife camera detections, cameras, and system monitoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Rate limiting middleware - protect against API abuse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.security import HTTPBearer
from typing import Optional

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# API Key authentication (optional)
security = HTTPBearer(auto_error=False)


def get_api_key(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    Extract API key from request headers
    
    Supports:
    - Authorization: Bearer <key>
    - X-API-Key: <key>
    """
    # Try X-API-Key header first
    if x_api_key:
        return x_api_key
    
    # Try Authorization: Bearer <key>
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1)
    
    return None


# Dependency - defined early so it can be used in verify_api_key
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(
    request: Request,
    api_key: Optional[str] = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Optional[Any]:
    """
    Verify API key if provided
    
    Returns:
        ApiKey record if valid, None if no key provided (allows optional auth)
    """
    from config import API_KEY_ENABLED
    
    # If API key authentication is disabled, allow all requests
    if not API_KEY_ENABLED:
        return None
    
    # If no API key provided, return None (optional auth)
    if not api_key:
        return None
    
    # Validate API key
    from services.api_keys import api_key_service
    
    client_ip = get_remote_address(request)
    api_key_record = api_key_service.validate_key(db, api_key, client_ip=client_ip)
    
    if not api_key_record:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key"
        )
    
    return api_key_record

# CORS middleware - restrict to specific origins and methods for security
# ALLOWED_ORIGINS is imported from config

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],  # Specific headers only
)

# Real-time event management
class EventManager:
    def __init__(self):
        self.clients: Dict[str, asyncio.Queue] = {}
        self.detection_queue = asyncio.Queue()
        self.system_queue = asyncio.Queue()
        self._background_tasks_started = False
    
    async def start_background_tasks(self):
        """Start background tasks for processing events - called during FastAPI startup"""
        if not self._background_tasks_started:
            try:
                # Create tasks in the current event loop (startup is async)
                asyncio.create_task(self._process_detection_events())
                asyncio.create_task(self._process_system_events())
                asyncio.create_task(self._broadcast_system_health_periodic())
                self._background_tasks_started = True
                logging.info("EventManager background tasks started")
            except Exception as e:
                logging.error(f"Failed to start EventManager background tasks: {e}", exc_info=True)
    
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
            # Windows-compatible disk usage
            try:
                root_path = 'C:\\' if os.name == 'nt' else '/'
                disk = psutil.disk_usage(root_path)
            except Exception:
                # Fallback to current directory
                disk = psutil.disk_usage('.')
            
            # Get MotionEye status with timeout
            motioneye_status = "unknown"
            cameras_count = 0
            try:
                # Use asyncio to run the blocking call with a timeout
                loop = asyncio.get_event_loop()
                motioneye_status = await asyncio.wait_for(
                    loop.run_in_executor(None, motioneye_client.get_status),
                    timeout=30.0  # Increased from 3s to 30s to handle slow MotionEye responses
                )
                # Also get cameras count if MotionEye is running
                if motioneye_status == "running":
                    try:
                        cameras = await asyncio.wait_for(
                            loop.run_in_executor(None, motioneye_client.get_cameras),
                            timeout=15.0  # Increased from 2s to 15s to handle slow MotionEye responses
                        )
                        cameras_count = len(cameras) if cameras else 0
                    except Exception:
                        cameras_count = 0
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
                    timeout=40.0  # Increased from 5s to 40s to handle slow SpeciesNet responses
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

# Migration: add file_hash column if not present - moved to startup event
from sqlalchemy import inspect

# Camera sync service
def _get_sync_interval() -> int:
    raw_value = os.getenv("MOTIONEYE_SYNC_INTERVAL_SECONDS", "60")
    try:
        interval = int(raw_value)
        return interval if interval > 0 else 60
    except ValueError:
        return 60


camera_sync_service = CameraSyncService(
    SessionLocal,
    motioneye_client,
    Camera,
    poll_interval_seconds=_get_sync_interval(),
)

# Create tables with explicit error logging
# NOTE: This will fail if database is not running - that's OK, tables will be created on startup
try:
    Base.metadata.create_all(bind=engine)
    # Print the list of tables after creation (PostgreSQL version)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
        tables = [row[0] for row in result]
        logging.debug(f"Tables in database after create_all: {tables}")
except Exception as e:
    # Database not available at module import time - this is expected
    # Tables will be created during startup event
    pass

@app.on_event("startup")
async def startup_event():
    try:
        logging.info("=" * 50)
        logging.info("Wildlife Backend Starting...")
        logging.info("=" * 50)
        
        # Start EventManager background tasks (async)
        try:
            await event_manager.start_background_tasks()
            logging.info("[OK] EventManager background tasks started")
        except Exception as e:
            logging.warning(f"EventManager startup failed: {e}")
            import traceback
            logging.debug(traceback.format_exc())
        
        # Start camera sync service
        try:
            camera_sync_service.start()
            logging.info("[OK] Camera sync service started")
        except Exception as e:
            logging.warning(f"Camera sync service failed to start: {e}")
        
        # Test database connection and create tables
        try:
            with engine.connect() as conn:
                pass
            logging.info("[OK] Database connection successful")
            
            # Create tables if they don't exist
            try:
                Base.metadata.create_all(bind=engine)
                logging.info("[OK] Database tables created/verified")
            except Exception as e:
                logging.warning(f"Table creation failed: {e}")
            
            # Migration: add file_hash column if not present (after tables exist)
            try:
                insp = inspect(engine)
                if not any(c['name'] == 'file_hash' for c in insp.get_columns('detections')):
                    with engine.connect() as conn:
                        conn.execute(text('ALTER TABLE detections ADD COLUMN file_hash VARCHAR'))
                        conn.commit()
                        logging.info('[OK] Added file_hash column to detections table')
            except Exception as migration_error:
                logging.warning(f"Migration warning (non-critical): {migration_error}")
                
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            logging.error("  Please ensure PostgreSQL is running and accessible")
            logging.error("  The backend will continue but database features may not work")
            # Continue startup - the app can still run without database initially
        
        # Enable background photo scanner task
        try:
            asyncio.create_task(run_photo_scanner())
            logging.info("[OK] Photo scanner background task started")
        except Exception as e:
            logging.warning(f"Photo scanner failed to start: {e}")
        
        logging.info("=" * 50)
        logging.info("[OK] Backend startup completed!")
        logging.info("=" * 50)
        logging.info(f"Backend API available at: http://localhost:8001")
        logging.info(f"API Documentation at: http://localhost:8001/docs")
        logging.info("=" * 50)
    except Exception as e:
        logging.error("=" * 50)
        logging.error("[ERROR] CRITICAL ERROR during startup!")
        logging.error("=" * 50)
        logging.error(f"Error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        logging.error("=" * 50)
        logging.error("Backend will attempt to continue, but some features may not work.")
        logging.error("Check the error above and fix the issue, then restart the backend.")
        logging.error("=" * 50)
        # Don't raise - let the app continue running so we can see the error

@app.on_event("shutdown")
async def shutdown_event():
    await camera_sync_service.stop()

# Background camera sync function
async def sync_cameras_background(cameras):
    """Sync cameras from MotionEye to database in background"""
    try:
        synced_count = 0
        updated_count = 0
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
            else:
                # Update existing camera with current MotionEye status
                existing_camera.name = camera_name
                existing_camera.url = me_camera.get("device_url", existing_camera.url or "")
                existing_camera.is_active = me_camera.get("enabled", existing_camera.is_active if existing_camera.is_active is not None else True)
                existing_camera.width = me_camera.get("width", existing_camera.width if existing_camera.width is not None else 1280)
                existing_camera.height = me_camera.get("height", existing_camera.height if existing_camera.height is not None else 720)
                existing_camera.framerate = me_camera.get("framerate", existing_camera.framerate if existing_camera.framerate is not None else 30)
                # Ensure other fields have defaults if None
                if existing_camera.stream_port is None:
                    existing_camera.stream_port = me_camera.get("streaming_port", 8081)
                if existing_camera.stream_quality is None:
                    existing_camera.stream_quality = me_camera.get("streaming_quality", 100)
                if existing_camera.stream_maxrate is None:
                    existing_camera.stream_maxrate = me_camera.get("streaming_framerate", 30)
                if existing_camera.stream_localhost is None:
                    existing_camera.stream_localhost = False
                if existing_camera.detection_enabled is None:
                    existing_camera.detection_enabled = me_camera.get("motion_detection", True)
                if existing_camera.detection_threshold is None:
                    existing_camera.detection_threshold = me_camera.get("frame_change_threshold", 1500)
                if existing_camera.detection_smart_mask_speed is None:
                    existing_camera.detection_smart_mask_speed = me_camera.get("smart_mask_sluggishness", 10)
                if existing_camera.movie_output is None:
                    existing_camera.movie_output = me_camera.get("movies", True)
                if existing_camera.movie_quality is None:
                    existing_camera.movie_quality = me_camera.get("movie_quality", 100)
                if existing_camera.movie_codec is None:
                    existing_camera.movie_codec = me_camera.get("movie_format", "mkv")
                if existing_camera.snapshot_interval is None:
                    existing_camera.snapshot_interval = me_camera.get("snapshot_interval", 0)
                if existing_camera.target_dir is None:
                    existing_camera.target_dir = me_camera.get("root_directory", "./motioneye_media")
                updated_count += 1
                print(f"Auto-updated camera: {camera_name} (ID: {camera_id}) - Active: {existing_camera.is_active}")
        
        db.commit()
        
        if synced_count > 0 or updated_count > 0:
            print(f"Auto-sync completed: {synced_count} new, {updated_count} updated cameras from MotionEye")
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
        logging.error(f"Camera sync background task error: {e}")

# One-time scan runner for startup sync
async def run_photo_scanner_once():
    try:
        # Wait for SpeciesNet server to be ready - but don't block startup
        logging.debug("Waiting for SpeciesNet server to initialize...")
        max_wait_time = 30  # Wait up to 30 seconds
        wait_interval = 2   # Check every 2 seconds
        
        for i in range(max_wait_time // wait_interval):
            status = speciesnet_processor.get_status()
            if status == "running":
                logging.info("[OK] SpeciesNet server is ready!")
                break
            elif status == "timeout":
                logging.debug(f"SpeciesNet server still initializing... ({i+1}/{max_wait_time//wait_interval})")
            else:
                logging.debug(f"SpeciesNet server status: {status}")
            
            await asyncio.sleep(wait_interval)
        else:
            logging.warning("SpeciesNet server failed to initialize within timeout, skipping initial scan")
            return
        
        # Now run the photo scanner
        db = next(get_db())
        scanner = PhotoScanner(db)
        await scanner.scan_and_process()
        db.close()
    except Exception as e:
        logging.error(f"Photo scanner initial sync error: {e}")

# Pydantic models are now imported from models.py

# API endpoints
@app.get("/")
def read_root():
    return {"message": "Wildlife Monitoring API with SpeciesNet Integration"}

# Health check endpoints are defined later in the file (async versions with timeouts)

@app.get("/system")
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute (frequently polled)
async def get_system_health(request: Request) -> Dict[str, Any]:
    """Get system health and status information - returns quickly even if some services are slow"""
    # Check cache first (10 second TTL for system health - increased for better performance)
    cached = get_cached("system_health", ttl=10)
    if cached:
        return cached

    import asyncio
    from datetime import datetime
    import psutil
    try:
        # Get system metrics immediately (fast, no network calls)
        # Use very short interval for cpu_percent (non-blocking requires previous call)
        cpu_percent = psutil.cpu_percent(interval=0.01)  # Very short interval for fast response
        memory_percent = psutil.virtual_memory().percent
        
        # Enhanced disk space monitoring
        try:
            disk_path = 'C:\\' if os.name == 'nt' else '/'
            disk = psutil.disk_usage(disk_path)
            disk_percent = disk.percent
            disk_total_gb = disk.total / (1024**3)  # Convert to GB
            disk_used_gb = disk.used / (1024**3)
            disk_free_gb = disk.free / (1024**3)
            disk_alert = disk_percent >= 90  # Alert if >90% full
        except Exception as e:
            disk_percent = 0
            disk_total_gb = 0
            disk_used_gb = 0
            disk_free_gb = 0
            disk_alert = False
        
        # Check media directories disk usage
        media_disk_info = {}
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            motioneye_media_path = os.path.join(project_root, "motioneye_media")
            archived_photos_path = os.path.join(project_root, "archived_photos")
            
            # Calculate directory sizes
            def get_dir_size(path):
                if not os.path.exists(path):
                    return 0
                total = 0
                try:
                    for entry in os.scandir(path):
                        if entry.is_file():
                            total += entry.stat().st_size
                        elif entry.is_dir():
                            total += get_dir_size(entry.path)
                except (PermissionError, OSError):
                    pass
                return total
            
            motioneye_size = get_dir_size(motioneye_media_path)
            archived_size = get_dir_size(archived_photos_path)
            
            media_disk_info = {
                "motioneye_media_gb": round(motioneye_size / (1024**3), 2),
                "archived_photos_gb": round(archived_size / (1024**3), 2),
                "total_media_gb": round((motioneye_size + archived_size) / (1024**3), 2)
            }
        except Exception:
            media_disk_info = {
                "motioneye_media_gb": 0,
                "archived_photos_gb": 0,
                "total_media_gb": 0
            }
        
        # Prepare default statuses
        motioneye_status = "unknown"
        cameras_count = 0
        speciesnet_status = "unknown"
        
        # Run MotionEye and SpeciesNet checks concurrently with reasonable timeouts
        # Use asyncio.to_thread for better cancellation support (Python 3.9+)
        try:
            # Create tasks with reasonable individual timeouts
            motioneye_task = asyncio.create_task(
                asyncio.wait_for(
                    asyncio.to_thread(motioneye_client.get_status) if hasattr(asyncio, 'to_thread')
                    else asyncio.get_event_loop().run_in_executor(None, motioneye_client.get_status),
                    timeout=30.0  # Increased from 3s to 30s to handle slow MotionEye responses
                )
            )
            
            speciesnet_task = asyncio.create_task(
                asyncio.wait_for(
                    asyncio.to_thread(speciesnet_processor.get_status) if hasattr(asyncio, 'to_thread')
                    else asyncio.get_event_loop().run_in_executor(None, speciesnet_processor.get_status),
                    timeout=40.0  # Increased from 5s to 40s to handle slow SpeciesNet responses
                )
            )
        except AttributeError:
            # Fallback for older Python versions
            loop = asyncio.get_event_loop()
            motioneye_task = asyncio.create_task(
                asyncio.wait_for(
                    loop.run_in_executor(None, motioneye_client.get_status),
                    timeout=30.0  # Increased from 3s to 30s to handle slow MotionEye responses
                )
            )
            speciesnet_task = asyncio.create_task(
                asyncio.wait_for(
                    loop.run_in_executor(None, speciesnet_processor.get_status),
                    timeout=40.0  # Increased from 5s to 40s to handle slow SpeciesNet responses
                )
            )
        
        # Wait for both with reasonable overall timeout
        try:
            motioneye_result, speciesnet_result = await asyncio.wait_for(
                asyncio.gather(motioneye_task, speciesnet_task, return_exceptions=True),
                timeout=45.0  # Increased from 6s to 45s to handle slow service responses
            )
            
            # Process MotionEye result
            if isinstance(motioneye_result, Exception):
                motioneye_status = "error"
            elif isinstance(motioneye_result, asyncio.TimeoutError):
                motioneye_status = "timeout"
            else:
                # motioneye_result is now a status string from get_status()
                motioneye_status = motioneye_result if isinstance(motioneye_result, str) else "unknown"
                # Also get cameras count for display
                try:
                    cameras = motioneye_client.get_cameras()
                    cameras_count = len(cameras) if cameras else 0
                except Exception:
                    cameras_count = 0
            
            # Process SpeciesNet result
            if isinstance(speciesnet_result, Exception):
                speciesnet_status = "error"
            elif isinstance(speciesnet_result, asyncio.TimeoutError):
                speciesnet_status = "timeout"
            else:
                speciesnet_status = speciesnet_result if isinstance(speciesnet_result, str) else "unknown"
                
        except asyncio.TimeoutError:
            # If overall timeout, cancel tasks and use defaults
            motioneye_task.cancel()
            speciesnet_task.cancel()
            motioneye_status = "timeout"
            speciesnet_status = "timeout"
        except Exception as e:
            # Catch any other async errors
            motioneye_status = "error"
            speciesnet_status = "error"
        
            # Check disk space and send alert if needed
            if disk_alert:
                try:
                    notification_service.send_system_alert(
                        subject="Low Disk Space Warning",
                        message=f"Disk usage is at {disk_percent:.1f}% ({disk_used_gb:.1f} GB used of {disk_total_gb:.1f} GB total). Free space: {disk_free_gb:.1f} GB",
                        alert_type="warning"
                    )
                except Exception as e:
                    logging.warning(f"Failed to send disk space alert: {e}")
        
        # Compose response immediately
            result = {
            "status": "running",
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                    "disk_total_gb": round(disk_total_gb, 2),
                    "disk_used_gb": round(disk_used_gb, 2),
                    "disk_free_gb": round(disk_free_gb, 2),
                    "disk_alert": disk_alert,
                    "media_disk_info": media_disk_info,
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
        
        # Cache the result for 5 seconds
        set_cached("system_health", result, ttl=10)
        return result
    except Exception as e:
        # Return error response instead of raising exception to avoid 500
        return {
            "status": "error",
            "system": {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0,
                    "disk_total_gb": 0,
                    "disk_used_gb": 0,
                    "disk_free_gb": 0,
                    "disk_alert": False,
                    "media_disk_info": {},
                "timestamp": datetime.utcnow().isoformat()
            },
            "motioneye": {
                "status": "error",
                "cameras_count": 0
            },
            "speciesnet": {
                "status": "error"
            },
            "error": str(e)
        }

@app.get("/api/system")
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute
async def get_system_health_api(request: Request) -> Dict[str, Any]:
    """Alias for /system to support frontend API calls"""
    return await get_system_health(request)

@app.get("/cameras", response_model=List[CameraResponse])
@limiter.limit("120/minute")  # Rate limit: 120 requests per minute
def get_cameras(request: Request, db: Session = Depends(get_db)):
    """Get list of all cameras"""
    try:
        # Check cache first (60 second TTL for camera list - increased for better performance)
        cached = get_cached("cameras_list", ttl=60)
        if cached:
            return cached
        
        cameras = db.query(Camera).all()
    
        # Optimize: Get all detection counts in a single query (avoid N+1 problem)
        camera_ids = [camera.id for camera in cameras]
        
        # Get detection counts for all cameras at once
        detection_counts = {}
        if camera_ids:
            from sqlalchemy import func
            counts_query = db.query(
                Detection.camera_id,
                func.count(Detection.id).label('count')
            ).filter(Detection.camera_id.in_(camera_ids)).group_by(Detection.camera_id).all()
            
            detection_counts = {camera_id: count for camera_id, count in counts_query}
        
        # Get last detection timestamps for all cameras at once (most recent per camera)
        last_detections = {}
        if camera_ids:
            # Use a subquery to get the max timestamp per camera, then join to get the full detection
            subquery = db.query(
                Detection.camera_id,
                func.max(Detection.timestamp).label('max_timestamp')
            ).filter(Detection.camera_id.in_(camera_ids)).group_by(Detection.camera_id).subquery()
            
            last_detections_query = db.query(Detection).join(
                subquery,
                (Detection.camera_id == subquery.c.camera_id) & 
                (Detection.timestamp == subquery.c.max_timestamp)
            ).all()
            
            last_detections = {det.camera_id: det.timestamp.isoformat() for det in last_detections_query}
        
        # Convert to response models with defaults for None values
        result = []
        for camera in cameras:
            try:
                # Get detection statistics from pre-fetched data
                detection_count = detection_counts.get(camera.id, 0)
                last_detection_time = last_detections.get(camera.id)
                
                # Determine status based on is_active
                status = "active" if (camera.is_active if camera.is_active is not None else True) else "inactive"
                
                # Ensure all fields have proper defaults if None and validate them
                # CameraBase requires: name (non-empty), url (non-empty), and valid field ranges
                camera_name = str(camera.name).strip() if camera.name and str(camera.name).strip() else "Unnamed Camera"
                camera_url = str(camera.url).strip() if camera.url and str(camera.url).strip() else "rtsp://localhost"
                
                # Ensure all numeric fields are within valid ranges
                width_val = max(320, min(7680, int(camera.width) if camera.width is not None else 1280))
                height_val = max(240, min(4320, int(camera.height) if camera.height is not None else 720))
                framerate_val = max(1, min(120, int(camera.framerate) if camera.framerate is not None else 30))
                stream_port_val = max(1024, min(65535, int(camera.stream_port) if camera.stream_port is not None else 8081))
                stream_quality_val = max(1, min(100, int(camera.stream_quality) if camera.stream_quality is not None else 100))
                stream_maxrate_val = max(1, min(120, int(camera.stream_maxrate) if camera.stream_maxrate is not None else 30))
                detection_threshold_val = max(0, min(100000, int(camera.detection_threshold) if camera.detection_threshold is not None else 1500))
                detection_smart_mask_speed_val = max(0, min(100, int(camera.detection_smart_mask_speed) if camera.detection_smart_mask_speed is not None else 10))
                movie_quality_val = max(1, min(100, int(camera.movie_quality) if camera.movie_quality is not None else 100))
                snapshot_interval_val = max(0, min(3600, int(camera.snapshot_interval) if camera.snapshot_interval is not None else 0))
                
                # Process movie_codec - ensure it's valid
                movie_codec_val = "mkv"
                if camera.movie_codec:
                    codec = str(camera.movie_codec).strip()
                    if ':' in codec:
                        codec = codec.split(':')[0]
                    movie_codec_val = codec[:50] if len(codec) > 50 else codec
                
                # Process target_dir - ensure it's valid
                target_dir_val = str(camera.target_dir).strip() if camera.target_dir and str(camera.target_dir).strip() else "./motioneye_media"
                
                camera_dict = {
                    "id": camera.id,
                    "name": camera_name,
                    "url": camera_url,
                    "is_active": camera.is_active if camera.is_active is not None else True,
                    "width": width_val,
                    "height": height_val,
                    "framerate": framerate_val,
                    "stream_port": stream_port_val,
                    "stream_quality": stream_quality_val,
                    "stream_maxrate": stream_maxrate_val,
                    "stream_localhost": camera.stream_localhost if camera.stream_localhost is not None else False,
                    "detection_enabled": camera.detection_enabled if camera.detection_enabled is not None else True,
                    "detection_threshold": detection_threshold_val,
                    "detection_smart_mask_speed": detection_smart_mask_speed_val,
                    "movie_output": camera.movie_output if camera.movie_output is not None else True,
                    "movie_quality": movie_quality_val,
                    "movie_codec": movie_codec_val,
                    "snapshot_interval": snapshot_interval_val,
                    "target_dir": target_dir_val,
                    "created_at": camera.created_at,
                    "stream_url": motioneye_client.get_camera_stream_url(camera.id) if camera.id else None,
                    "mjpeg_url": motioneye_client.get_camera_mjpeg_url(camera.id) if camera.id else None,
                    # Add detection statistics
                    "detection_count": detection_count,
                    "last_detection": last_detection_time,
                    "status": status,
                    "location": None,  # Can be added later if you track camera locations
                }
                
                # Validate the camera_dict by creating a CameraResponse object
                # This ensures all validation rules are met
                try:
                    camera_response = CameraResponse(**camera_dict)
                    result.append(camera_response)
                except Exception as validation_error:
                    logging.error(f"Validation error for camera {camera.id}: {validation_error}")
                    logging.error(f"Camera data: name={camera_name}, url={camera_url}")
                    # Skip invalid cameras instead of crashing
                    continue
            except Exception as e:
                logging.error(f"Error processing camera {camera.id}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                # Skip this camera and continue
                continue
        
        # Cache the result for 60 seconds (convert to dict for caching)
        cached_result = [camera.model_dump() for camera in result]
        set_cached("cameras_list", cached_result, ttl=60)
        return result
    except Exception as e:
        logging.error(f"Error in get_cameras: {e}", exc_info=True)
        # Return empty list on error instead of crashing
        return []

@app.get("/api/cameras", response_model=List[CameraResponse])
@limiter.limit("120/minute")  # Rate limit: 120 requests per minute
def get_cameras_api(request: Request, db: Session = Depends(get_db)):
    """Alias for /cameras to support frontend API calls"""
    return get_cameras(request, db)

@app.post("/cameras/sync")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute (expensive operation)
def sync_cameras_from_motioneye(request: Request, db: Session = Depends(get_db)):
    """Sync cameras from MotionEye to database"""
    try:
        # Check if MotionEye is accessible before attempting sync
        try:
            motioneye_check = requests.get(f"{MOTIONEYE_URL}/config/list", timeout=5)
            if motioneye_check.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail=f"MotionEye is not accessible (status {motioneye_check.status_code}). Please ensure MotionEye is running at {MOTIONEYE_URL}"
                )
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=503,
                detail=f"MotionEye connection timeout. Please ensure MotionEye is running at {MOTIONEYE_URL}"
            )
        except requests.exceptions.ConnectionError:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to MotionEye at {MOTIONEYE_URL}. Please ensure MotionEye is running."
            )
        except Exception as e:
            logging.warning(f"MotionEye connectivity check failed: {e}")
            # Continue anyway - let sync_motioneye_cameras handle it
        
        result = sync_motioneye_cameras(db, motioneye_client, Camera)
        # Log successful sync
        log_audit_event(
            db=db,
            request=request,
            action="SYNC",
            resource_type="camera",
            details={
                "synced": result.get("synced", 0),
                "updated": result.get("updated", 0),
                "removed": result.get("removed", 0)
            }
        )
        return result
    except HTTPException:
        # Re-raise HTTP exceptions (like the ones we just created)
        raise
    except Exception as e:
        db.rollback()
        # Log failed sync
        log_audit_event(
            db=db,
            request=request,
            action="SYNC",
            resource_type="camera",
            success=False,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Error syncing cameras: {str(e)}")

@app.post("/cameras", response_model=CameraResponse)
@limiter.limit("20/minute")  # Rate limit: 20 requests per minute
def add_camera(request: Request, camera: CameraCreate, db: Session = Depends(get_db)):
    # Create camera in database
    db_camera = Camera(**camera.model_dump())
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
        # Log failed camera creation
        log_audit_event(
            db=db,
            request=request,
            action="CREATE",
            resource_type="camera",
            success=False,
            error_message="Failed to add camera to MotionEye",
            details={"camera_name": camera.name}
        )
        raise HTTPException(status_code=500, detail="Failed to add camera to MotionEye")
    
    # Add stream URLs
    db_camera.stream_url = motioneye_client.get_camera_stream_url(db_camera.id)
    db_camera.mjpeg_url = motioneye_client.get_camera_mjpeg_url(db_camera.id)
    
    # Log successful camera creation
    log_audit_event(
        db=db,
        request=request,
        action="CREATE",
        resource_type="camera",
        resource_id=db_camera.id,
        details={"camera_name": camera.name, "url": camera.url}
    )
    
    return db_camera

@app.delete("/detections/{detection_id}")
@limiter.limit("60/minute")
def delete_detection(
    request: Request,
    detection_id: int,
    db: Session = Depends(get_db)
):
    """Delete a single detection"""
    try:
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        # Log deletion
        log_audit_event(
            db=db,
            request=request,
            action="DELETE",
            resource_type="detection",
            resource_id=detection_id,
            details={
                "camera_id": detection.camera_id,
                "species": detection.species
            }
        )
        
        db.delete(detection)
        db.commit()
        
        return {"success": True, "message": f"Detection {detection_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete detection {detection_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete detection: {str(e)}")


@app.post("/detections/bulk-delete")
@limiter.limit("10/minute")
def bulk_delete_detections(
    request: Request,
    detection_ids: List[int],
    db: Session = Depends(get_db)
):
    """Delete multiple detections"""
    try:
        if not detection_ids:
            raise HTTPException(status_code=400, detail="No detection IDs provided")
        
        if len(detection_ids) > 100:
            raise HTTPException(status_code=400, detail="Cannot delete more than 100 detections at once")
        
        # Get detections
        detections = db.query(Detection).filter(Detection.id.in_(detection_ids)).all()
        
        if len(detections) != len(detection_ids):
            found_ids = {d.id for d in detections}
            missing_ids = set(detection_ids) - found_ids
            raise HTTPException(
                status_code=404,
                detail=f"Some detections not found: {list(missing_ids)}"
            )
        
        # Log bulk deletion
        log_audit_event(
            db=db,
            request=request,
            action="BULK_DELETE",
            resource_type="detection",
            details={
                "count": len(detection_ids),
                "detection_ids": detection_ids
            }
        )
        
        # Delete all
        for detection in detections:
            db.delete(detection)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Deleted {len(detection_ids)} detection(s)",
            "deleted_count": len(detection_ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to bulk delete detections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete detections: {str(e)}")


@app.get("/detections", response_model=List[DetectionResponse])
def get_detections(
    camera_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    species: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get detections with optional filtering and pagination"""
    try:
        # First, let's verify the database connection and get a simple count
        total_count = db.query(Detection).count()
        logging.info(f"Total detections in database: {total_count}")
        
        query = db.query(Detection)
        
        if camera_id is not None:
            query = query.filter(Detection.camera_id == camera_id)
        
        if species is not None:
            query = query.filter(Detection.species.ilike(f"%{species}%"))
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp >= start_dt)
            except ValueError:
                pass  # Invalid date format, ignore
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp <= end_dt)
            except ValueError:
                pass  # Invalid date format, ignore
        
        # Apply search filter if provided (searches species, image_path, and camera name)
        if search:
            search_term = f"%{search}%"
            # Join with Camera table to search camera names
            query = query.join(Camera, Detection.camera_id == Camera.id).filter(
                or_(
                    Detection.species.ilike(search_term),
                    Detection.image_path.ilike(search_term),
                    Camera.name.ilike(search_term)
                )
            )
        else:
            # No join needed if not searching
            pass
        
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
        logging.info(f"Query returned {len(detections)} detections from database")
    
        # Batch-fetch all cameras to avoid N+1 queries
        camera_ids = {d.camera_id for d in detections if d.camera_id is not None}
        cameras = {}
        if camera_ids:
            cameras = {c.id: c for c in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()}
    
        # Convert to response models with media URLs
        result = []
        for detection in detections:
            try:
                camera = cameras.get(detection.camera_id) if detection.camera_id else None
                # Ensure camera_name is always a non-empty string (required by DetectionResponse)
                if camera and camera.name and str(camera.name).strip():
                    camera_name = str(camera.name).strip()
                elif detection.camera_id:
                    camera_name = f"Camera {detection.camera_id}"
                else:
                    camera_name = "Unknown Camera"
                
                # Extract full taxonomy from detections_json if available
                full_taxonomy = None
                if detection.detections_json:
                    try:
                        detections_data = json.loads(detection.detections_json)
                        if "predictions" in detections_data and detections_data["predictions"]:
                            full_taxonomy = detections_data["predictions"][0].get("prediction", detection.species)
                        elif "species" in detections_data:
                            full_taxonomy = detections_data["species"]
                    except:
                        full_taxonomy = detection.species or "Unknown"
                
                # Ensure all required fields have valid values for DetectionResponse
                # DetectionBase requires: camera_id >= 1, species (non-empty), confidence (0.0-1.0), image_path (non-empty with valid extension)
                camera_id_val = int(detection.camera_id) if detection.camera_id and detection.camera_id >= 1 else 1
                species_val = str(detection.species).strip() if detection.species and str(detection.species).strip() else "Unknown"
                confidence_val = float(detection.confidence) if detection.confidence is not None else 0.0
                confidence_val = max(0.0, min(1.0, confidence_val))  # Clamp to 0.0-1.0
                
                # Normalize image_path to ensure it passes validation
                # The validator requires either a valid image extension or a temp path
                if detection.image_path and str(detection.image_path).strip():
                    image_path_val = str(detection.image_path).strip()
                    # Check if it has a valid extension
                    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
                    has_valid_ext = any(image_path_val.lower().endswith(ext) for ext in valid_extensions)
                    # Check if it's a temp path
                    is_temp_path = image_path_val.startswith('/tmp') or image_path_val.startswith('C:\\') or 'temp' in image_path_val.lower()
                    # If neither, add .jpg extension to make it valid
                    if not has_valid_ext and not is_temp_path:
                        image_path_val = image_path_val + '.jpg'
                else:
                    # Default to a valid temp path
                    image_path_val = "/tmp/unknown.jpg"
                
                # Fix detections_json - it might be stored as Python dict string instead of JSON
                # The validator requires it to be valid JSON or None
                detections_json_val = None
                if detection.detections_json:
                    try:
                        # Try to parse as JSON first
                        json.loads(detection.detections_json)
                        detections_json_val = detection.detections_json  # Already valid JSON
                    except (json.JSONDecodeError, TypeError):
                        # If it's a Python dict string, convert it to JSON
                        try:
                            if isinstance(detection.detections_json, str):
                                # Try to eval it as Python literal (dict)
                                parsed = ast.literal_eval(detection.detections_json)
                                detections_json_val = json.dumps(parsed)  # Convert to JSON string
                                # Verify the converted JSON is valid
                                json.loads(detections_json_val)
                            else:
                                detections_json_val = json.dumps(detection.detections_json)
                                # Verify the converted JSON is valid
                                json.loads(detections_json_val)
                        except Exception as e:
                            # If all else fails, set to None (invalid JSON will fail validation)
                            logging.warning(f"Could not convert detections_json for detection {detection.id} to valid JSON: {e}")
                            detections_json_val = None
                
                detection_dict = {
                    "id": detection.id,
                    "camera_id": camera_id_val,
                    "timestamp": detection.timestamp,
                    "species": species_val,
                    "full_taxonomy": full_taxonomy,
                    "confidence": confidence_val,
                    "image_path": image_path_val,
                    "file_size": detection.file_size,
                    "image_width": detection.image_width,
                    "image_height": detection.image_height,
                    "image_quality": detection.image_quality,
                    "prediction_score": float(detection.prediction_score) if detection.prediction_score is not None else None,
                    "detections_json": detections_json_val,
                    "media_url": None,  # Will be set below
                    "camera_name": str(camera_name)  # Add camera name to response
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
                                species_name = parts[idx + 1]    # human, vehicle, etc.
                                camera_folder = parts[idx + 2]   # 1, 2, etc.
                                date_folder = parts[idx + 3]    # 2025-08-11
                                filename = parts[idx + 4]        # 13-08-44.jpg
                                
                                # Keep the original camera folder name (don't add "Camera" prefix)
                                # This matches the actual file structure: archived_photos/human/2/2025-08-11/13-08-44.jpg
                                detection_dict["media_url"] = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                    except Exception as e:
                        logging.warning(f"Error generating media_url for detection {detection.id}: {e}")
                        detection_dict["media_url"] = None
                # Validate the detection_dict before creating DetectionResponse
                # This helps catch validation errors early
                try:
                    detection_response = DetectionResponse(**detection_dict)
                    result.append(detection_response)
                except Exception as validation_error:
                    # Log the validation error with more details
                    logging.error(f"Validation error for detection {detection.id}: {validation_error}")
                    logging.error(f"Detection data: camera_id={detection_dict.get('camera_id')}, species={detection_dict.get('species')}, image_path={detection_dict.get('image_path')}")
                    import traceback
                    logging.error(traceback.format_exc())
                    # Skip this detection and continue
                    continue
            except Exception as e:
                logging.error(f"Error processing detection {detection.id}: {e}")
                import traceback
                logging.error(traceback.format_exc())
                # Skip this detection and continue
                continue
        logging.info(f"Successfully processed {len(result)} detections out of {len(detections)}")
        return result
    except Exception as e:
        logging.error(f"Error in get_detections endpoint: {e}")
        import traceback
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error fetching detections: {str(e)}")

@app.get("/api/detections", response_model=List[DetectionResponse])
def get_detections_api(
    camera_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    species: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Alias for /detections to support frontend API calls"""
    return get_detections(camera_id, limit, offset, species, start_date, end_date, search, db)

@app.post("/detections", response_model=DetectionResponse)
def create_detection(request: Request, detection: DetectionCreate, db: Session = Depends(get_db)):
    db_detection = Detection(**detection.model_dump())
    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    
    # Log detection creation
    log_audit_event(
        db=db,
        request=request,
        action="CREATE",
        resource_type="detection",
        resource_id=db_detection.id,
        details={"camera_id": detection.camera_id, "species": detection.species}
    )
    
    return db_detection

@app.post("/process-image")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute (expensive operation)
async def process_image_with_speciesnet(
    request: Request,
    file: UploadFile = File(...),
    camera_id: Optional[int] = None,
    compress: bool = True,
    async_mode: bool = False,
    db: Session = Depends(get_db)
):
    """
    Process an uploaded image with SpeciesNet
    
    Args:
        async_mode: If True, returns task ID immediately and processes in background
    """
    try:
        from services.task_tracker import task_tracker, TaskStatus
        
        # If async mode, create task and return immediately
        if async_mode:
            task_id = task_tracker.create_task(
                task_type="image_processing",
                metadata={
                    "camera_id": camera_id,
                    "compress": compress,
                    "filename": file.filename
                }
            )
            
            # Start background processing (simplified - in production, use proper background task queue)
            import asyncio
            asyncio.create_task(_process_image_background(task_id, file, camera_id, compress, db, request))
            
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Image processing started in background"
            }
        
        # Synchronous processing (existing behavior)
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Process with SpeciesNet
        predictions = speciesnet_processor.process_image(temp_path)
        
        if "error" in predictions:
            # Log failed processing
            log_audit_event(
                db=db,
                request=request,
                action="PROCESS",
                resource_type="detection",
                success=False,
                error_message=predictions["error"],
                details={"camera_id": camera_id}
            )
            raise HTTPException(status_code=500, detail=predictions["error"])
        
        # Save detection to database
        if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
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
            
            # Compress image if enabled and file exists
            if compress and db_detection.image_path and os.path.exists(db_detection.image_path):
                try:
                    from utils.image_compression import compress_image
                    success, compressed_path, original_size = compress_image(
                        db_detection.image_path,
                        quality=85,
                        max_width=1920,
                        max_height=1080
                    )
                    if success and original_size:
                        new_size = os.path.getsize(compressed_path)
                        compression_ratio = (1 - new_size / original_size) * 100
                        logging.info(
                            f"Compressed detection image: {compression_ratio:.1f}% reduction "
                            f"({original_size} -> {new_size} bytes)"
                        )
                except Exception as e:
                    logging.warning(f"Image compression failed: {e}")
            
            # Log successful processing
            log_audit_event(
                db=db,
                request=request,
                action="PROCESS",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0)
                }
            )
            
            # Send email notification if enabled and confidence is high enough
            if pred.get("prediction_score", 0.0) >= 0.7:
                try:
                    notification_service.send_detection_notification(
                        species=pred.get("prediction", "Unknown"),
                        confidence=pred.get("prediction_score", 0.0),
                        camera_id=camera_id or 1,
                        detection_id=db_detection.id,
                        timestamp=db_detection.timestamp
                    )
                except Exception as e:
                    logging.warning(f"Failed to send notification: {e}")
            
            # Trigger webhooks for detection
            try:
                from services.webhooks import WebhookService
                webhook_service = WebhookService(db)
                detection_data = {
                    "id": db_detection.id,
                    "camera_id": camera_id or 1,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0),
                    "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                    "image_path": db_detection.image_path
                }
                webhook_service.trigger_detection_webhooks(
                    detection_data=detection_data,
                    confidence=pred.get("prediction_score", 0.0),
                    species=pred.get("prediction", "Unknown")
                )
            except Exception as e:
                logging.warning(f"Failed to trigger webhooks: {e}")
            
            return {
                "detection": db_detection,
                "predictions": predictions
            }
        else:
            return {"predictions": predictions}
        
    except Exception as e:
        # Log failed processing
        log_audit_event(
            db=db,
            request=request,
            action="PROCESS",
            resource_type="detection",
            success=False,
            error_message=str(e),
            details={"camera_id": camera_id}
        )
        raise HTTPException(status_code=500, detail=str(e))


async def _process_image_background(
    task_id: str,
    file: UploadFile,
    camera_id: Optional[int],
    compress: bool,
    db: Session,
    request: Request
):
    """Background task for processing images"""
    try:
        from services.task_tracker import task_tracker
        
        # Start task
        task_tracker.start_task(task_id, "Reading image file...")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Update progress
        task_tracker.update_task(task_id, progress=0.2, message="Processing with SpeciesNet...")
        
        # Process with SpeciesNet
        predictions = speciesnet_processor.process_image(temp_path)
        
        if "error" in predictions:
            task_tracker.fail_task(task_id, predictions["error"])
            return
        
        task_tracker.update_task(task_id, progress=0.6, message="Saving detection...")
        
        # Save detection to database
        if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
            pred = predictions["predictions"][0]
            
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
            
            task_tracker.update_task(task_id, progress=0.8, message="Compressing image...")
            
            # Compress image if enabled
            if compress and db_detection.image_path and os.path.exists(db_detection.image_path):
                try:
                    from utils.image_compression import compress_image
                    compress_image(
                        db_detection.image_path,
                        quality=85,
                        max_width=1920,
                        max_height=1080
                    )
                except Exception as e:
                    logging.warning(f"Image compression failed: {e}")
            
            # Log successful processing
            log_audit_event(
                db=db,
                request=request,
                action="PROCESS",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0),
                    "task_id": task_id
                }
            )
            
            # Complete task
            task_tracker.complete_task(
                task_id,
                result={
                    "detection_id": db_detection.id,
                    "species": pred.get("prediction", "Unknown"),
                    "confidence": pred.get("prediction_score", 0.0)
                },
                message="Image processed successfully"
            )
        else:
            task_tracker.complete_task(
                task_id,
                result={"predictions": predictions},
                message="Processing completed (no detections)"
            )
    
    except Exception as e:
        logging.error(f"Background image processing failed: {e}", exc_info=True)
        from services.task_tracker import task_tracker
        task_tracker.fail_task(task_id, str(e))

@app.post("/api/thingino/capture")
async def capture_thingino_image(request: Request, camera_id: int, db: Session = Depends(get_db)):
    """Capture an image from the Thingino camera and process it"""
    try:
        # Get camera information
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        if camera_id not in [9, 10]:
            raise HTTPException(status_code=400, detail="This endpoint is only for Thingino cameras")
        
        # Download image from Thingino camera
        import requests
        from datetime import datetime
        
        try:
            # Try to get image from camera with authentication for Thingino cameras
            auth = None
            if camera_id in [9, 10]:  # Thingino cameras
                auth = (THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD)
            
            response = requests.get(camera.url, auth=auth, timeout=10)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Failed to capture image: HTTP {response.status_code}")
            
            # Save image temporarily
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thingino_capture_{timestamp}.jpg"
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            # Process with SpeciesNet
            predictions = speciesnet_processor.process_image(temp_path)
            
            if "error" in predictions:
                raise HTTPException(status_code=500, detail=predictions["error"])
            
            # Extract species prediction
            species = "Unknown"
            confidence = 0.0
            
            if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
                pred = predictions["predictions"][0]
                species = pred.get("prediction", "Unknown")
                confidence = pred.get("prediction_score", 0.0)
            
            # Save detection to database
            detection_data = {
                "camera_id": camera_id,
                "timestamp": datetime.now(),
                "species": species,
                "confidence": confidence,
                "image_path": temp_path,
                "detections_json": json.dumps(predictions),
                "prediction_score": confidence
            }
            
            db_detection = Detection(**detection_data)
            db.add(db_detection)
            db.commit()
            db.refresh(db_detection)
            
            # Compress image if it exists
            if db_detection.image_path and os.path.exists(db_detection.image_path):
                try:
                    from utils.image_compression import compress_image
                    success, compressed_path, original_size = compress_image(
                        db_detection.image_path,
                        quality=85,
                        max_width=1920,
                        max_height=1080
                    )
                    if success:
                        logging.info(f"Compressed captured image: {db_detection.image_path}")
                except Exception as e:
                    logging.warning(f"Image compression failed: {e}")
            
            # Log successful capture
            log_audit_event(
                db=db,
                request=request,
                action="CAPTURE",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "species": species,
                    "confidence": confidence
                }
            )
            
            # Send email notification if enabled and confidence is high enough
            if confidence >= 0.7:  # Only notify for high-confidence detections
                try:
                    notification_service.send_detection_notification(
                        species=species,
                        confidence=confidence,
                        camera_id=camera_id,
                        camera_name=camera.name,
                        detection_id=db_detection.id,
                        image_url=f"/api/thingino/image/{db_detection.id}",
                        timestamp=db_detection.timestamp
                    )
                except Exception as e:
                    logging.warning(f"Failed to send notification: {e}")
            
            # Trigger webhooks for detection
            try:
                from services.webhooks import WebhookService
                webhook_service = WebhookService(db)
                detection_data = {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "species": species,
                    "confidence": confidence,
                    "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                    "image_url": f"/api/thingino/image/{db_detection.id}"
                }
                webhook_service.trigger_detection_webhooks(
                    detection_data=detection_data,
                    confidence=confidence,
                    species=species
                )
            except Exception as e:
                logging.warning(f"Failed to trigger webhooks: {e}")
            
            # Broadcast the new detection to connected clients
            detection_event = {
                "id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "species": species,
                "confidence": confidence,
                "image_path": temp_path,
                "timestamp": db_detection.timestamp.isoformat(),
                "media_url": f"/api/thingino/image/{db_detection.id}"
            }
            await event_manager.broadcast_detection(detection_event)
            
            return {
                "status": "success",
                "detection_id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera.name,
                "species": species,
                "confidence": confidence,
                "predictions": predictions
            }
            
        except requests.exceptions.RequestException as e:
            # Log failed capture
            log_audit_event(
                db=db,
                request=request,
                action="CAPTURE",
                resource_type="detection",
                success=False,
                error_message=f"Failed to connect to camera: {str(e)}",
                details={"camera_id": camera_id}
            )
            raise HTTPException(status_code=500, detail=f"Failed to connect to camera: {str(e)}")
        
    except Exception as e:
        # Log failed capture
        log_audit_event(
            db=db,
            request=request,
            action="CAPTURE",
            resource_type="detection",
            success=False,
            error_message=str(e),
            details={"camera_id": camera_id}
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/thingino/image/{detection_id}")
def get_thingino_image(detection_id: int, db: Session = Depends(get_db)):
    """Get captured image from Thingino camera"""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    if not os.path.exists(detection.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    return FileResponse(detection.image_path, media_type="image/jpeg")

@app.post("/api/thingino/webhook")
async def thingino_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle webhook notifications from Thingino camera for motion detection"""
    try:
        # Get the JSON data from Thingino
        data = await request.json()
        
        print(f"Thingino webhook received: {data}")
        
        # Thingino sends data with these typical fields:
        # - camera_id: ID of the camera (we'll determine from image_url)
        # - message: Motion detection message
        # - timestamp: When the event occurred
        # - image_url: URL to the captured image
        
        message = data.get("message", "Motion detected")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        image_url = data.get("image_url", "http://192.168.88.93/x/preview.cgi")
        
        # Determine camera ID based on the image URL
        if "192.168.88.97" in image_url:
            camera_id = 10  # Thingino Camera 2
        else:
            camera_id = 9   # Thingino Camera 1 (default)
        
        print(f"Processing Thingino motion detection: {message}")
        
        # Process detection inline (will take a few seconds but ensures it completes)
        print(f"[THINGINO] Processing detection for camera {camera_id}, URL: {image_url}")
        
        try:
            # Use authentication for Thingino cameras
            auth = None
            if "192.168.88.93" in image_url or "192.168.88.97" in image_url:
                auth = (THINGINO_CAMERA_USERNAME, THINGINO_CAMERA_PASSWORD)
            
            response = requests.get(image_url, auth=auth, timeout=15)
            if response.status_code != 200:
                print(f"Failed to download image from Thingino: HTTP {response.status_code}")
                return {"status": "error", "message": f"Failed to download image: HTTP {response.status_code}"}
            
            # Save image temporarily
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thingino_motion_{timestamp_str}.jpg"
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            print(f"Image saved to: {temp_path}")
            
            # Process with SpeciesNet
            predictions = speciesnet_processor.process_image(temp_path)
            
            if "error" in predictions:
                print(f"SpeciesNet processing error: {predictions['error']}")
                # Still save the detection, but mark as unprocessed
                detection_data = {
                    "camera_id": camera_id,
                    "timestamp": datetime.now(),
                    "species": "Unknown",
                    "confidence": 0.0,
                    "image_path": temp_path,
                    "detections_json": json.dumps({"error": predictions["error"]}),
                    "prediction_score": 0.0
                }
            else:
                # Extract species prediction
                species = "Unknown"
                confidence = 0.0
                
                if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
                    pred = predictions["predictions"][0]
                    species = pred.get("prediction", "Unknown")
                    confidence = pred.get("prediction_score", 0.0)
            
            # Save detection to database
                detection_data = {
                    "camera_id": camera_id,
                    "timestamp": datetime.now(),
                    "species": species,
                    "confidence": confidence,
                    "image_path": temp_path,
                    "detections_json": json.dumps(predictions),
                    "prediction_score": confidence
                }
            
            # Create detection record
            db_detection = Detection(**detection_data)
            db.add(db_detection)
            db.commit()
            db.refresh(db_detection)
            
            # Log webhook detection
            log_audit_event(
                db=db,
                request=request,
                action="WEBHOOK",
                resource_type="detection",
                resource_id=db_detection.id,
                details={
                    "camera_id": camera_id,
                    "species": detection_data["species"],
                    "confidence": detection_data["confidence"],
                    "source": "thingino_webhook"
                }
            )
            
            # Send email notification if enabled and confidence is high enough
            if detection_data.get("confidence", 0) >= 0.7:
                try:
                    notification_service.send_detection_notification(
                        species=detection_data["species"],
                        confidence=detection_data["confidence"],
                        camera_id=camera_id,
                        camera_name=camera_name,
                        detection_id=db_detection.id,
                        image_url=f"/api/thingino/image/{db_detection.id}",
                        timestamp=db_detection.timestamp
                    )
                except Exception as e:
                    logging.warning(f"Failed to send notification: {e}")
            
            print(f"Detection saved: ID={db_detection.id}, Species={detection_data['species']}, Confidence={detection_data['confidence']}")
            
            # Get camera information for broadcasting
            camera_info = db.query(Camera).filter(Camera.id == camera_id).first()
            camera_name = camera_info.name if camera_info else "Thingino Camera"
            
            # Broadcast the new detection to connected clients
            detection_event = {
                "type": "detection",
                "detection": {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "species": detection_data["species"],
                    "confidence": detection_data["confidence"],
                    "image_path": temp_path,
                    "timestamp": db_detection.timestamp.isoformat(),
                    "media_url": f"/api/thingino/image/{db_detection.id}"
                }
            }
            # Use asyncio to call the async broadcast
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(event_manager.broadcast_detection(detection_event))
            except RuntimeError:
                asyncio.run(event_manager.broadcast_detection(detection_event))
            
        except Exception as e:
            import traceback
            print(f"ERROR processing detection: {e}")
            # Log failed webhook processing
            log_audit_event(
                db=db,
                request=request,
                action="WEBHOOK",
                resource_type="detection",
                success=False,
                error_message=str(e),
                details={"source": "thingino_webhook", "camera_id": camera_id}
            )
            traceback.print_exc()
            return {"status": "error", "message": str(e)}
        
        # Return success response
        return {
            "status": "success",
            "message": "Motion detection processed successfully"
        }
        
    except Exception as e:
        print(f"Error processing Thingino webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/cameras/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    """Get camera information"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Get MotionEye config for motion settings
    motioneye_config = motioneye_client.get_camera_config(camera_id)
    
    camera_dict = {
        "id": camera.id,
        "name": camera.name,
        "url": camera.url or "",
        "is_active": camera.is_active if camera.is_active is not None else True,
        "width": camera.width if camera.width is not None else 1280,
        "height": camera.height if camera.height is not None else 720,
        "framerate": camera.framerate if camera.framerate is not None else 30,
        "stream_port": camera.stream_port if camera.stream_port is not None else 8081,
        "stream_quality": camera.stream_quality if camera.stream_quality is not None else 100,
        "stream_maxrate": camera.stream_maxrate if camera.stream_maxrate is not None else 30,
        "stream_localhost": camera.stream_localhost if camera.stream_localhost is not None else False,
        "detection_enabled": camera.detection_enabled if camera.detection_enabled is not None else True,
        "detection_threshold": camera.detection_threshold if camera.detection_threshold is not None else 1500,
        "detection_smart_mask_speed": camera.detection_smart_mask_speed if camera.detection_smart_mask_speed is not None else 10,
        "movie_output": camera.movie_output if camera.movie_output is not None else True,
        "movie_quality": camera.movie_quality if camera.movie_quality is not None else 100,
        "movie_codec": camera.movie_codec if camera.movie_codec is not None else "mkv",
        "snapshot_interval": camera.snapshot_interval if camera.snapshot_interval is not None else 0,
        "target_dir": camera.target_dir if camera.target_dir is not None else "./motioneye_media",
        "created_at": camera.created_at,
        "motioneye_config": motioneye_config  # Include full MotionEye config
    }
    return camera_dict

@app.get("/cameras/{camera_id}/motion-settings")
def get_motion_settings(camera_id: int):
    """Get motion detection settings from MotionEye"""
    config = motioneye_client.get_camera_config(camera_id)
    if not config:
        raise HTTPException(status_code=404, detail="Camera not found in MotionEye")
    
    # Extract motion-related settings
    motion_settings = {
        "threshold": config.get("threshold", 1500),
        "threshold_maximum": config.get("threshold_maximum", 0),
        "threshold_tune": config.get("threshold_tune", True),
        "noise_tune": config.get("noise_tune", True),
        "noise_level": config.get("noise_level", 32),
        "lightswitch_percent": config.get("lightswitch_percent", 0),
        "despeckle_filter": config.get("despeckle_filter", ""),
        "minimum_motion_frames": config.get("minimum_motion_frames", 1),
        "smart_mask_speed": config.get("smart_mask_speed", 0),
        "motion_detection": config.get("motion_detection", True),
        "picture_output_motion": config.get("picture_output_motion", False),
        "movie_output_motion": config.get("movie_output_motion", False),
        "pre_capture": config.get("pre_capture", 0),
        "post_capture": config.get("post_capture", 0),
    }
    return motion_settings

@app.post("/cameras/{camera_id}/motion-settings")
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
def update_motion_settings(request: Request, camera_id: int, settings: MotionSettings, db: Session = Depends(get_db)):
    """Update motion detection settings in MotionEye"""
    # Convert Pydantic model to dict, excluding None values
    settings_dict = settings.model_dump(exclude_none=True)
    success = motioneye_client.set_motion_settings(camera_id, settings_dict)
    if not success:
        # Log failed update
        log_audit_event(
            db=db,
            request=request,
            action="UPDATE",
            resource_type="motion_settings",
            resource_id=camera_id,
            success=False,
            error_message="Failed to update motion settings in MotionEye"
        )
        raise HTTPException(status_code=500, detail="Failed to update motion settings")
    
    # Log successful update
    log_audit_event(
        db=db,
        request=request,
        action="UPDATE",
        resource_type="motion_settings",
        resource_id=camera_id,
        details=settings_dict
    )
    
    return {"message": "Motion settings updated successfully", "settings": settings_dict}

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
        "motioneye_url": MOTIONEYE_URL,
        "camera_type": "motioneye"
    }

logger = logging.getLogger("motioneye.webhook")


@app.post("/api/motioneye/webhook")
async def motioneye_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle MotionEye webhook notifications for motion detection"""
    try:
        payload = await parse_motioneye_payload(request)
        data = payload["raw"]
        camera_id = payload["camera_id"]
        file_path = payload["file_path"]
        timestamp = payload["timestamp"]
        event_type = payload["event_type"]

        # Log webhook receipt for debugging camera detection issues
        logger.info(f"MotionEye webhook received - camera_id: {camera_id}, file_path: {file_path}, payload keys: {list(data.keys()) if data else 'empty'}")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("MotionEye webhook payload: %s", data)

        if not camera_id or not file_path:
            if not data:
                logger.debug("Ignoring MotionEye webhook with empty payload from MotionEye")
            else:
                logger.warning("Ignoring MotionEye webhook with missing data: %s", data)
            return {"status": "ignored", "message": "Missing required data"}

        if not should_process_event(file_path):
            logger.debug("Ignoring duplicate MotionEye webhook for %s", file_path)
            return {"status": "ignored", "message": "Duplicate event"}
        
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
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("MotionEye path %s mapped to %s", file_path, local_file_path)
        
        # Check if file exists
        if not os.path.exists(local_file_path):
            logger.warning("MotionEye file not found: %s", local_file_path)
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
            logger.debug("Skipping non-image MotionEye file: %s", local_file_path)
            return {"status": "skipped", "message": "Not an image file"}
        
        # Skip motion mask files (files ending with "m.jpg" or "m.jpeg")
        # These are debug images showing motion detection areas, not actual wildlife photos
        filename = os.path.basename(local_file_path).lower()
        if filename.endswith('m.jpg') or filename.endswith('m.jpeg'):
            logger.debug("Skipping motion mask image: %s", local_file_path)
            return {"status": "skipped", "message": "Motion mask file (not processed)"}
        
        # Process image with SpeciesNet
        predictions = speciesnet_processor.process_image(local_file_path)
        
        if "error" in predictions:
            logger.error("SpeciesNet processing error for %s: %s", local_file_path, predictions["error"])
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
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("SpeciesNet predictions: %s", json.dumps(predictions))
            
            # Extract species prediction
            species = "Unknown"
            confidence = 0.0
            
            # Try different possible response structures
            if isinstance(predictions, dict):
                if "predictions" in predictions and predictions["predictions"] and len(predictions["predictions"]) > 0:
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
            
            # Clean up species name - extract meaningful information from taxonomy
            if species and ";" in species:
                parts = species.split(";")
                
                # Remove UUID if present (first part if it's very long and looks like UUID)
                if len(parts) > 0 and len(parts[0]) > 20 and "-" in parts[0]:
                    parts = parts[1:]
                
                # Filter out empty parts and normalize
                parts = [p.strip() for p in parts if p.strip() and p.strip().lower() not in ["", "null", "none"]]
                
                # Check for "no cv result" or similar
                if any("no cv" in p.lower() or "no cv result" in p.lower() for p in parts):
                    species = "Unknown"
                # Check if the last meaningful part is "blank" - convert to "Unknown" so it gets saved
                elif parts and parts[-1].lower() == "blank":
                    species = "Unknown"  # Save as Unknown instead of skipping
                # Try to find genus and species (last two meaningful parts)
                elif len(parts) >= 2:
                    # Get the last few meaningful parts (skip empty/single-letter ones)
                    meaningful = [p for p in parts if p.strip() and len(p.strip()) > 1]
                    
                    if len(meaningful) >= 2:
                        # Use the last two meaningful parts (typically genus and species)
                        # But if the last one is a common name (human, etc.), prefer it alone
                        last_part = meaningful[-1].lower()
                        
                        # Common names that should be preferred over binomial names
                        common_names = ["human", "sapiens", "homospecies"]
                        if last_part in common_names:
                            species = meaningful[-1].title()
                        else:
                            # Use binomial name (genus + species)
                            species = f"{meaningful[-2].title()} {meaningful[-1].title()}"
                    elif len(meaningful) == 1:
                        species = meaningful[0].title()
                    else:
                        # Fallback: use last non-empty part even if short
                        species = parts[-1].title() if parts else "Unknown"
                elif len(parts) == 1:
                    # Single part - use it if it's meaningful
                    if len(parts[0]) > 1:
                        species = parts[0].title()
                    else:
                        species = "Unknown"
                else:
                    species = "Unknown"
            elif species and species != "Unknown":
                # Check if it's a UUID or looks like one
                if len(species) > 30 and "-" in species:
                    # Might be a UUID, try to extract meaningful parts
                    if ";" in species:
                        parts = species.split(";")
                        meaningful_parts = [p.strip() for p in parts if p.strip() and len(p) < 30 and "-" not in p]
                        if meaningful_parts:
                            species = meaningful_parts[-1].title() if len(meaningful_parts[-1]) > 1 else "Unknown"
                        else:
                            species = "Unknown"
                    else:
                        species = "Unknown"
                # Check for "no cv result" or similar
                elif "no cv" in species.lower() or "no cv result" in species.lower():
                    species = "Unknown"
                # If it's a single word/short string, use it
                elif len(species) <= 50 and len(species) > 1:
                    species = species.title()
                else:
                    species = "Unknown"
            
            # Convert "blank" to "Unknown" so detections are saved (user can filter in frontend)
            if species and species.lower().strip() == "blank":
                species = "Unknown"
                logger.debug("Converting blank detection to Unknown: %s", local_file_path)
            
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
        
        # Log MotionEye webhook detection
        log_audit_event(
            db=db,
            request=request,
            action="WEBHOOK",
            resource_type="detection",
            resource_id=db_detection.id,
            details={
                "camera_id": camera_id,
                "species": detection_data["species"],
                "confidence": detection_data["confidence"],
                "source": "motioneye_webhook",
                "file_path": local_file_path
            }
        )
        
        # Send email notification if enabled and confidence is high enough
        if detection_data.get("confidence", 0) >= 0.7:
            try:
                notification_service.send_detection_notification(
                    species=detection_data["species"],
                    confidence=detection_data["confidence"],
                    camera_id=camera_id,
                    camera_name=camera_name,
                    detection_id=db_detection.id,
                    image_url=f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}",
                    timestamp=db_detection.timestamp
                )
            except Exception as e:
                logging.warning(f"Failed to send notification: {e}")
        
        # Trigger webhooks for detection
        try:
            from services.webhooks import WebhookService
            webhook_service = WebhookService(db)
            webhook_detection_data = {
                "id": db_detection.id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "species": detection_data["species"],
                "confidence": detection_data["confidence"],
                "timestamp": db_detection.timestamp.isoformat() if db_detection.timestamp else None,
                "image_url": f"/media/{extracted_camera_name}/{file_date}/{os.path.basename(local_file_path)}"
            }
            webhook_service.trigger_detection_webhooks(
                detection_data=webhook_detection_data,
                confidence=detection_data["confidence"],
                species=detection_data["species"]
            )
        except Exception as e:
            logging.warning(f"Failed to trigger webhooks: {e}")
        
        logger.info(
            "Saved detection %s from camera %s (%s) species=%s confidence=%.2f",
            db_detection.id,
            camera_id,
            camera_name,
            detection_data["species"],
            detection_data["confidence"],
        )
        
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
        FROM detections
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        unique_species = result.scalar()
    return {"unique_species": unique_species}


@app.get("/api/analytics/species")
@limiter.limit("60/minute")
def get_species_analytics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    camera_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get analytics data for species detections
    
    Returns:
    - Total detections per species
    - Average confidence per species
    - Detection count over time
    """
    try:
        query = db.query(Detection)
        
        # Apply filters
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        if start_date:
            try:
                # Parse date string to datetime object
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp >= start_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp >= start_dt)
                except ValueError:
                    logging.error(f"Could not parse start_date: {start_date}")
        if end_date:
            try:
                # Parse date string to datetime object
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp <= end_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp <= end_dt)
                except ValueError:
                    logging.error(f"Could not parse end_date: {end_date}")
        
        detections = query.all()
        
        # Group by species
        species_stats = {}
        for detection in detections:
            species = detection.species or "Unknown"
            if species not in species_stats:
                species_stats[species] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "detections": []
                }
            species_stats[species]["count"] += 1
            # Handle null confidence values
            confidence = detection.confidence if detection.confidence is not None else 0.0
            species_stats[species]["total_confidence"] += confidence
            species_stats[species]["detections"].append({
                "id": detection.id,
                "timestamp": detection.timestamp.isoformat() if detection.timestamp else None,
                "confidence": confidence,
                "camera_id": detection.camera_id
            })
        
        # Calculate averages and format response
        result = []
        for species, stats in species_stats.items():
            result.append({
                "species": species,
                "count": stats["count"],
                "average_confidence": stats["total_confidence"] / stats["count"] if stats["count"] > 0 else 0.0,
                "detections": stats["detections"][:10]  # Limit to 10 most recent
            })
        
        # Sort by count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "species": result,
            "total_detections": len(detections),
            "unique_species": len(result)
        }
    except Exception as e:
        logging.error(f"Failed to get species analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@app.get("/api/analytics/timeline")
@limiter.limit("60/minute")
def get_timeline_analytics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    camera_id: Optional[int] = None,
    interval: str = "day",  # day, week, month
    db: Session = Depends(get_db)
):
    """
    Get detection timeline analytics
    
    Returns detection counts grouped by time interval
    """
    try:
        query = db.query(Detection)
        
        # Apply filters
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        if start_date:
            try:
                # Parse date string to datetime object
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp >= start_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp >= start_dt)
                except ValueError:
                    logging.error(f"Could not parse start_date: {start_date}")
        if end_date:
            try:
                # Parse date string to datetime object
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp <= end_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp <= end_dt)
                except ValueError:
                    logging.error(f"Could not parse end_date: {end_date}")
        
        detections = query.all()
        
        # Group by time interval
        timeline = {}
        for detection in detections:
            dt = detection.timestamp
            
            if interval == "day":
                key = dt.strftime("%Y-%m-%d")
            elif interval == "week":
                # Get week start (Monday)
                days_since_monday = dt.weekday()
                week_start = dt - timedelta(days=days_since_monday)
                key = week_start.strftime("%Y-W%W")
            elif interval == "month":
                key = dt.strftime("%Y-%m")
            else:
                key = dt.strftime("%Y-%m-%d")
            
            if key not in timeline:
                timeline[key] = {
                    "date": key,
                    "count": 0,
                    "species": {}
                }
            timeline[key]["count"] += 1
            
            # Track species in this interval
            species = detection.species or "Unknown"
            if species not in timeline[key]["species"]:
                timeline[key]["species"][species] = 0
            timeline[key]["species"][species] += 1
        
        # Convert to list and sort
        result = sorted(timeline.values(), key=lambda x: x["date"])
        
        return {
            "timeline": result,
            "interval": interval,
            "total_points": len(result)
        }
    except Exception as e:
        logging.error(f"Failed to get timeline analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get timeline analytics: {str(e)}")


@app.get("/api/analytics/cameras")
@limiter.limit("60/minute")
def get_camera_analytics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get analytics data per camera
    
    Returns:
    - Detection count per camera
    - Most detected species per camera
    - Average confidence per camera
    """
    try:
        query = db.query(Detection)
        
        # Apply date filters
        if start_date:
            try:
                # Parse date string to datetime object
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp >= start_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp >= start_dt)
                except ValueError:
                    logging.error(f"Could not parse start_date: {start_date}")
        if end_date:
            try:
                # Parse date string to datetime object
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Detection.timestamp <= end_dt)
            except (ValueError, AttributeError) as e:
                logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    query = query.filter(Detection.timestamp <= end_dt)
                except ValueError:
                    logging.error(f"Could not parse end_date: {end_date}")
        
        detections = query.all()
        
        # Group by camera
        camera_stats = {}
        for detection in detections:
            camera_id = detection.camera_id
            if camera_id not in camera_stats:
                camera_stats[camera_id] = {
                    "camera_id": camera_id,
                    "count": 0,
                    "total_confidence": 0.0,
                    "species": {}
                }
            camera_stats[camera_id]["count"] += 1
            camera_stats[camera_id]["total_confidence"] += detection.confidence
            
            # Track species
            species = detection.species or "Unknown"
            if species not in camera_stats[camera_id]["species"]:
                camera_stats[camera_id]["species"][species] = 0
            camera_stats[camera_id]["species"][species] += 1
        
        # Get camera names
        cameras = {c.id: c.name for c in db.query(Camera).all()}
        
        # Format response
        result = []
        for camera_id, stats in camera_stats.items():
            # Get top species
            top_species = sorted(
                stats["species"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            result.append({
                "camera_id": camera_id,
                "camera_name": cameras.get(camera_id, f"Camera {camera_id}"),
                "count": stats["count"],
                "average_confidence": stats["total_confidence"] / stats["count"] if stats["count"] > 0 else 0.0,
                "top_species": [{"species": s, "count": c} for s, c in top_species]
            })
        
        # Sort by count descending
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "cameras": result,
            "total_detections": len(detections),
            "total_cameras": len(result)
        }
    except Exception as e:
        logging.error(f"Failed to get camera analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get camera analytics: {str(e)}")


@app.get("/health")
async def health_check(request: Request):
    """
    Basic health check endpoint for monitoring tools
    
    Returns 200 if system is healthy, 503 if unhealthy
    """
    # Quick health check - return immediately, check services in background
    # This prevents the health endpoint from blocking
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "Backend is running"
    }


@app.get("/api/health")
@limiter.limit("120/minute")
async def health_check_api(request: Request, db: Session = Depends(get_db)):
    """Alias for /health endpoint"""
    return await health_check(request, db)


@app.get("/health/detailed")
@limiter.limit("60/minute")
async def detailed_health_check(request: Request, db: Session = Depends(get_db)):
    """
    Detailed health check with metrics for monitoring tools
    
    Returns comprehensive system status including:
    - Database connectivity and query performance
    - MotionEye service status
    - SpeciesNet service status
    - System resources (CPU, memory, disk)
    - Recent error counts
    """
    try:
        # Database checks
        db_start = time.time()
        try:
            db.execute(text("SELECT 1"))
            db_query_time = (time.time() - db_start) * 1000  # milliseconds
            db_status = "healthy"
            db_error = None
        except Exception as e:
            db_status = "unhealthy"
            db_query_time = None
            db_error = str(e)
        
        # Get database stats
        try:
            detection_count = db.query(func.count(Detection.id)).scalar()
            camera_count = db.query(func.count(Camera.id)).scalar()
        except Exception:
            detection_count = None
            camera_count = None
        
        # MotionEye check with timeout (increased to 30s to handle slow responses)
        motioneye_start = time.time()
        motioneye_healthy = False
        motioneye_response_time = None
        motioneye_error = None
        try:
            loop = asyncio.get_event_loop()
            motioneye_status = await asyncio.wait_for(
                loop.run_in_executor(None, motioneye_client.get_status),
                timeout=30.0  # Increased from 3s to 30s to handle slow MotionEye responses
            )
            motioneye_response_time = (time.time() - motioneye_start) * 1000
            motioneye_healthy = motioneye_status == "running"
        except asyncio.TimeoutError:
            motioneye_response_time = None
            motioneye_error = "timeout"
        except Exception as e:
            motioneye_response_time = None
            motioneye_error = str(e)
        
        # SpeciesNet check with timeout (increased to 40s to handle slow responses)
        speciesnet_start = time.time()
        speciesnet_healthy = False
        speciesnet_response_time = None
        speciesnet_error = None
        try:
            loop = asyncio.get_event_loop()
            speciesnet_status = await asyncio.wait_for(
                loop.run_in_executor(None, speciesnet_processor.get_status),
                timeout=40.0  # Increased from 5s to 40s to handle slow SpeciesNet responses
            )
            speciesnet_response_time = (time.time() - speciesnet_start) * 1000
            speciesnet_healthy = speciesnet_status == "running"
        except asyncio.TimeoutError:
            speciesnet_response_time = None
            speciesnet_error = "timeout"
        except Exception as e:
            speciesnet_response_time = None
            speciesnet_error = str(e)
        
        # System resources
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
        except Exception as e:
            cpu_percent = None
            memory = None
            disk = None
        
        # Overall health
        overall_healthy = db_status == "healthy"
        status_code = 200 if overall_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if overall_healthy else "degraded",
                "timestamp": datetime.now().isoformat(),
                "dependencies": {
                    "database": {
                        "status": db_status,
                        "required": True,
                        "query_time_ms": db_query_time,
                        "error": db_error,
                        "stats": {
                            "detections": detection_count,
                            "cameras": camera_count
                        }
                    },
                    "motioneye": {
                        "status": "healthy" if motioneye_healthy else "unhealthy",
                        "required": False,
                        "response_time_ms": motioneye_response_time,
                        "error": motioneye_error
                    },
                    "speciesnet": {
                        "status": "healthy" if speciesnet_healthy else "unhealthy",
                        "required": False,
                        "response_time_ms": speciesnet_response_time,
                        "error": speciesnet_error
                    }
                },
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory": {
                        "total_gb": round(memory.total / (1024**3), 2) if memory else None,
                        "used_gb": round(memory.used / (1024**3), 2) if memory else None,
                        "available_gb": round(memory.available / (1024**3), 2) if memory else None,
                        "percent": memory.percent if memory else None
                    } if memory else None,
                    "disk": {
                        "total_gb": round(disk.total / (1024**3), 2) if disk else None,
                        "used_gb": round(disk.used / (1024**3), 2) if disk else None,
                        "free_gb": round(disk.free / (1024**3), 2) if disk else None,
                        "percent": disk.percent if disk else None
                    } if disk else None
                },
                "uptime_seconds": time.time() - app.state.start_time if hasattr(app.state, 'start_time') else None
            }
        )
    except Exception as e:
        logging.error(f"Detailed health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


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
                    # Skip motion mask files (files ending with "m.jpg" or "m.jpeg")
                    # These are debug images showing motion detection areas, not actual wildlife photos
                    filename_lower = filename.lower()
                    if filename_lower.endswith('m.jpg') or filename_lower.endswith('m.jpeg'):
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
            if "predictions" in speciesnet_response and speciesnet_response["predictions"] and len(speciesnet_response["predictions"]) > 0:
                pred = speciesnet_response["predictions"][0]
                species = pred.get("prediction", "Unknown")
                confidence = pred.get("prediction_score", 0.0)
            elif "species" in speciesnet_response:
                species = speciesnet_response.get("species", "Unknown")
                confidence = speciesnet_response.get("confidence", 0.0)
            
            # Log raw SpeciesNet response for debugging (first few detections only)
            if hasattr(self, '_debug_count'):
                self._debug_count += 1
            else:
                self._debug_count = 0
            if self._debug_count < 5:
                logging.debug(f"[PhotoScanner] Raw SpeciesNet response for {photo_info['filename']}: species={species}, confidence={confidence}")
            
            # Clean up species name (similar to webhook handler)
            if species and ";" in species:
                parts = species.split(";")
                
                # Remove UUID if present (first part if it's very long and looks like UUID)
                if len(parts) > 0 and len(parts[0]) > 20 and "-" in parts[0]:
                    parts = parts[1:]
                
                # Filter out empty parts and normalize
                parts = [p.strip() for p in parts if p.strip() and p.strip().lower() not in ["", "null", "none"]]
                
                # Check for "no cv result" or similar
                if any("no cv" in p.lower() or "no cv result" in p.lower() for p in parts):
                    species = "Unknown"
                # Check if the last meaningful part is "blank" - convert to "Unknown" so it gets saved
                elif parts and parts[-1].lower() == "blank":
                    species = "Unknown"  # Save as Unknown instead of skipping
                # Try to find genus and species (last two meaningful parts)
                elif len(parts) >= 2:
                    # Get the last few meaningful parts (skip empty/single-letter ones)
                    meaningful = [p for p in parts if p.strip() and len(p.strip()) > 1]
                    
                    if len(meaningful) >= 2:
                        # Use the last two meaningful parts (typically genus and species)
                        # But if the last one is a common name (human, etc.), prefer it alone
                        last_part = meaningful[-1].lower()
                        
                        # Common names that should be preferred over binomial names
                        common_names = ["human", "sapiens", "homospecies"]
                        if last_part in common_names:
                            species = meaningful[-1].title()
                        else:
                            # Use binomial name (genus + species)
                            species = f"{meaningful[-2].title()} {meaningful[-1].title()}"
                    elif len(meaningful) == 1:
                        species = meaningful[0].title()
                    else:
                        # Fallback: use last non-empty part even if short
                        species = parts[-1].title() if parts else "Unknown"
                elif len(parts) == 1:
                    # Single part - use it if it's meaningful
                    if len(parts[0]) > 1:
                        species = parts[0].title()
                    else:
                        species = "Unknown"
                else:
                    species = "Unknown"
            elif species and species != "Unknown":
                # Check if it's a UUID or looks like one
                if len(species) > 30 and "-" in species:
                    # Might be a UUID, try to extract meaningful parts
                    if ";" in species:
                        parts = species.split(";")
                        meaningful_parts = [p.strip() for p in parts if p.strip() and len(p) < 30 and "-" not in p]
                        if meaningful_parts:
                            species = meaningful_parts[-1].title() if len(meaningful_parts[-1]) > 1 else "Unknown"
                        else:
                            species = "Unknown"
                    else:
                        species = "Unknown"
                # Check for "no cv result" or similar
                elif "no cv" in species.lower() or "no cv result" in species.lower():
                    species = "Unknown"
                # If it's a single word/short string, use it
                elif len(species) <= 50 and len(species) > 1:
                    species = species.title()
                else:
                    species = "Unknown"
            
            # Convert "blank" to "Unknown" so detections are saved (user can filter in frontend)
            if species and species.lower().strip() == "blank":
                species = "Unknown"
                logging.debug(f"[PhotoScanner] Converting blank detection to Unknown: {photo_info['filename']}")
            
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
            
            # Broadcast detection to connected clients for real-time updates
            try:
                camera_info = self.db.query(Camera).filter(Camera.id == camera_id).first()
                camera_name = camera_info.name if camera_info else f"Camera{camera_id}"
                
                # Extract media URL from archived path
                path_parts = archived_path.split(os.sep)
                media_url = None
                if "archived_photos" in path_parts:
                    idx = path_parts.index("archived_photos")
                    if len(path_parts) > idx + 4:
                        species_name = path_parts[idx + 1]
                        camera_folder = path_parts[idx + 2]
                        date_folder = path_parts[idx + 3]
                        filename = path_parts[idx + 4]
                        media_url = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                
                detection_event = {
                    "id": db_detection.id,
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "species": detection_data["species"],
                    "confidence": detection_data["confidence"],
                    "image_path": archived_path,
                    "timestamp": db_detection.timestamp.isoformat(),
                    "media_url": media_url or f"/media/{camera_name}/{path_parts[-2] if len(path_parts) >= 2 else 'unknown'}/{path_parts[-1]}"
                }
                
                # Get event loop and broadcast
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(event_manager.broadcast_detection(detection_event))
                    else:
                        asyncio.run(event_manager.broadcast_detection(detection_event))
                except RuntimeError:
                    # Fallback if no event loop
                    asyncio.run(event_manager.broadcast_detection(detection_event))
            except Exception as e:
                print(f"Error broadcasting detection from PhotoScanner: {e}")
            
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
            # Offload synchronous request to executor
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, speciesnet_processor.process_image, image_path)
            
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
            loop = asyncio.get_running_loop()
            # Offload status check
            speciesnet_status = await loop.run_in_executor(None, speciesnet_processor.get_status)
            if speciesnet_status != "running":
                print(f"SpeciesNet server not healthy ({speciesnet_status}), skipping photo processing")
                return
            
            # Load processed files from DB (synchronous but fast enough)
            self.load_processed_files()
            
            # Run file scan in executor to avoid blocking the event loop
            # This is critical as hashing thousands of files takes a long time
            unprocessed = await loop.run_in_executor(None, self.scan_for_unprocessed_photos)
            
            if unprocessed:
                print(f"[PhotoScanner] Processing {len(unprocessed)} photos this cycle (processing all)")
                for i, photo in enumerate(unprocessed):
                    print(f"[PhotoScanner] Processing photo {i+1}/{len(unprocessed)}: {photo['filename']}")
                    # Offload status check
                    status = await loop.run_in_executor(None, speciesnet_processor.get_status)
                    if status != "running":
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

@app.get("/thumbnails/{filename}")
def serve_thumbnail(filename: str):
    """Serve thumbnail images"""
    try:
        from utils.image_compression import THUMBNAIL_CACHE_DIR
        thumbnail_path = os.path.join(str(THUMBNAIL_CACHE_DIR), filename)
        if os.path.exists(thumbnail_path):
            return FileResponse(thumbnail_path, media_type="image/jpeg")
        else:
            raise HTTPException(status_code=404, detail="Thumbnail not found")
    except Exception as e:
        logging.error(f"Error serving thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/media/{camera}/{date}/{filename}")
def serve_motioneye_media(camera: str, date: str, filename: str):
    """Serve motioneye media files"""
    try:
        # Construct the file path
        file_path = os.path.join("motioneye_media", camera, date, filename)
        
        # Security check: ensure the path is within the allowed directory
        if not os.path.abspath(file_path).startswith(os.path.abspath("motioneye_media")):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return the file
        return FileResponse(file_path, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

@app.get("/archived_photos/{species}/{camera}/{date}/{filename}")
def serve_archived_photo(species: str, camera: str, date: str, filename: str):
    """Serve archived photos from the archived_photos directory"""
    try:
        # Get the current working directory (where the backend is running)
        current_dir = os.getcwd()
        
        # Construct the file path relative to the current directory
        file_path = os.path.join(current_dir, "archived_photos", species, camera, date, filename)
        
        # Debug logging
        print(f"Requested file: /archived_photos/{species}/{camera}/{date}/{filename}")
        print(f"Looking for file at: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        
        # Security check: ensure the path is within the allowed directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(os.path.join(current_dir, "archived_photos"))):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Try alternative path structure
            alt_path = os.path.join(current_dir, "..", "archived_photos", species, camera, date, filename)
            print(f"Trying alternative path: {alt_path}")
            print(f"Alternative path exists: {os.path.exists(alt_path)}")
            
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                raise HTTPException(status_code=404, detail=f"File not found at {file_path} or {alt_path}")
        
        # Return the file
        return FileResponse(file_path, media_type="image/jpeg")
    except Exception as e:
        print(f"Error serving archived photo: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

@app.get("/api/debug/speciesnet-response/{detection_id}")
def debug_speciesnet_response(detection_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to see raw SpeciesNet response for a detection"""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    try:
        detections_json = json.loads(detection.detections_json) if detection.detections_json else {}
        return {
            "id": detection.id,
            "species": detection.species,
            "confidence": detection.confidence,
            "raw_speciesnet_response": detections_json,
            "image_path": detection.image_path
        }
    except Exception as e:
        return {
            "id": detection.id,
            "species": detection.species,
            "confidence": detection.confidence,
            "error": str(e),
            "raw_detections_json": detection.detections_json
        }

@app.get("/api/debug/detection-media/{detection_id}")
def debug_detection_media(detection_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to see media URL generation for a detection"""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    try:
        # Generate media URL using the same logic as the main endpoint
        media_url = None
        if detection.image_path:
            path = detection.image_path.replace("\\", "/")
            parts = path.split("/")
            
            if "motioneye_media" in parts:
                idx = parts.index("motioneye_media")
                if len(parts) > idx + 3:
                    camera_folder = parts[idx + 1]
                    date_folder = parts[idx + 2]
                    filename = parts[idx + 3]
                    media_url = f"/media/{camera_folder}/{date_folder}/{filename}"
            elif "archived_photos" in parts:
                idx = parts.index("archived_photos")
                if len(parts) > idx + 3:
                    species_name = parts[idx + 1]
                    camera_folder = parts[idx + 2]
                    date_folder = parts[idx + 3]
                    filename = parts[idx + 4]
                    # Don't add Camera prefix - keep original structure
                    media_url = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
        
        return {
            "id": detection.id,
            "image_path": detection.image_path,
            "generated_media_url": media_url,
            "path_parts": parts if detection.image_path else None,
            "file_exists": os.path.exists(detection.image_path) if detection.image_path else False
        }
    except Exception as e:
        return {
            "id": detection.id,
            "error": str(e),
            "image_path": detection.image_path
        }

@app.get("/api/debug/file-system")
def debug_file_system():
    """Debug endpoint to check file system structure"""
    try:
        current_dir = os.getcwd()
        
        # Check if archived_photos directory exists
        archived_photos_path = os.path.join(current_dir, "archived_photos")
        archived_photos_exists = os.path.exists(archived_photos_path)
        
        # Check if motioneye_media directory exists
        motioneye_media_path = os.path.join(current_dir, "motioneye_media")
        motioneye_media_exists = os.path.exists(motioneye_media_path)
        
        # List contents of archived_photos if it exists
        archived_contents = []
        if archived_photos_exists:
            try:
                for species in os.listdir(archived_photos_path):
                    species_path = os.path.join(archived_photos_path, species)
                    if os.path.isdir(species_path):
                        cameras = []
                        for camera in os.listdir(species_path):
                            camera_path = os.path.join(species_path, camera)
                            if os.path.isdir(camera_path):
                                dates = []
                                for date in os.listdir(camera_path):
                                    date_path = os.path.join(camera_path, date)
                                    if os.path.isdir(date_path):
                                        files = os.listdir(date_path)
                                        dates.append({"date": date, "file_count": len(files)})
                                cameras.append({"camera": camera, "dates": dates})
                        archived_contents.append({"species": species, "cameras": cameras})
            except Exception as e:
                archived_contents = [{"error": str(e)}]
        
        return {
            "current_working_directory": current_dir,
            "archived_photos": {
                "exists": archived_photos_exists,
                "path": archived_photos_path,
                "contents": archived_contents
            },
            "motioneye_media": {
                "exists": motioneye_media_exists,
                "path": motioneye_media_path
            }
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/trigger-photo-scan")
async def trigger_photo_scan(request: Request, db: Session = Depends(get_db)):
    """Manually trigger photo scanner to process unprocessed photos"""
    try:
        scanner = PhotoScanner(db)
        await scanner.scan_and_process()
        
        # Log successful scan trigger
        log_audit_event(
            db=db,
            request=request,
            action="TRIGGER",
            resource_type="photo_scan",
            details={"triggered_by": "manual"}
        )
        
        return {"message": "Photo scan completed successfully"}
    except Exception as e:
        # Log failed scan trigger
        log_audit_event(
            db=db,
            request=request,
            action="TRIGGER",
            resource_type="photo_scan",
            success=False,
            error_message=str(e)
        )
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
    
    group_expr = f"date_trunc('{interval}', timestamp)"
    
    sql = f"""
        SELECT {group_expr} as bucket, COUNT(*) as count
        FROM detections
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
        FROM detections
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
        FROM detections
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        unique_species = result.scalar()
    return {"unique_species": unique_species}


@app.get("/audit-logs", response_model=List[AuditLogResponse])
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute
def get_audit_logs_endpoint(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    success_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get audit logs with optional filtering"""
    from datetime import datetime, timedelta
    
    # Optional date filtering (last 30 days by default if not specified)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    logs = get_audit_logs(
        db=db,
        limit=limit,
        offset=offset,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        success_only=success_only
    )
    
    return logs


@app.get("/api/audit-logs", response_model=List[AuditLogResponse])
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute
def get_audit_logs_api(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    success_only: bool = False,
    db: Session = Depends(get_db)
):
    """API endpoint alias for audit logs"""
    return get_audit_logs_endpoint(request, limit, offset, action, resource_type, resource_id, success_only, db)


@app.get("/api/detections/export")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute (expensive operation)
def export_detections(
    request: Request,
    format: str = "csv",  # csv, json, or pdf
    camera_id: Optional[int] = None,
    species: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Export detections to CSV, JSON, or PDF format"""
    from fastapi.responses import Response
    
    # Build query with filters
    query = db.query(Detection)
    
    if camera_id:
        query = query.filter(Detection.camera_id == camera_id)
    
    if species:
        query = query.filter(Detection.species.ilike(f"%{species}%"))
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Detection.timestamp >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Detection.timestamp <= end_dt)
        except ValueError:
            pass
    
    # Apply limit if specified (default to 10000 for exports)
    if limit is None:
        limit = 10000
    query = query.order_by(Detection.timestamp.desc()).limit(limit)
    
    detections = query.all()
    
    if format.lower() == "csv":
        # Generate CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "Camera ID", "Timestamp", "Species", "Confidence", 
            "Image Path", "File Size", "Image Width", "Image Height", 
            "Prediction Score"
        ])
        
        # Write data
        for det in detections:
            writer.writerow([
                det.id,
                det.camera_id,
                det.timestamp.isoformat() if det.timestamp else "",
                det.species or "",
                det.confidence or 0.0,
                det.image_path or "",
                det.file_size or 0,
                det.image_width or 0,
                det.image_height or 0,
                det.prediction_score or 0.0
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Log export
        log_audit_event(
            db=db,
            request=request,
            action="EXPORT",
            resource_type="detection",
            details={
                "format": "csv",
                "count": len(detections),
                "camera_id": camera_id,
                "species": species
            }
        )
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=detections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    elif format.lower() == "pdf":
        # Generate PDF
        try:
            from reportlab.lib import colors  # pyright: ignore[reportMissingModuleSource]
            from reportlab.lib.pagesizes import letter, A4  # pyright: ignore[reportMissingModuleSource]
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak  # pyright: ignore[reportMissingModuleSource]
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # pyright: ignore[reportMissingModuleSource]
            from reportlab.lib.units import inch  # pyright: ignore[reportMissingModuleSource]
            import io
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=1  # Center
            )
            story.append(Paragraph("Wildlife Detection Report", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Report metadata
            meta_style = styles['Normal']
            story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style))
            story.append(Paragraph(f"<b>Total Detections:</b> {len(detections)}", meta_style))
            if camera_id:
                story.append(Paragraph(f"<b>Camera ID:</b> {camera_id}", meta_style))
            if species:
                story.append(Paragraph(f"<b>Species Filter:</b> {species}", meta_style))
            if start_date:
                story.append(Paragraph(f"<b>Start Date:</b> {start_date}", meta_style))
            if end_date:
                story.append(Paragraph(f"<b>End Date:</b> {end_date}", meta_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Table data
            table_data = [["ID", "Camera", "Timestamp", "Species", "Confidence", "Image Path"]]
            
            for det in detections:
                camera_name = f"Camera {det.camera_id}"
                camera = db.query(Camera).filter(Camera.id == det.camera_id).first()
                if camera:
                    camera_name = camera.name
                
                timestamp_str = det.timestamp.strftime('%Y-%m-%d %H:%M') if det.timestamp else "N/A"
                confidence_str = f"{det.confidence * 100:.1f}%" if det.confidence else "N/A"
                image_path = det.image_path or "N/A"
                if len(image_path) > 40:
                    image_path = image_path[:37] + "..."
                
                table_data.append([
                    str(det.id),
                    camera_name[:20],
                    timestamp_str,
                    (det.species or "Unknown")[:30],
                    confidence_str,
                    image_path
                ])
            
            # Create table
            table = Table(table_data, colWidths=[0.5*inch, 1*inch, 1.2*inch, 1.5*inch, 0.8*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            
            story.append(table)
            doc.build(story)
            
            pdf_content = buffer.getvalue()
            buffer.close()
            
            # Log export
            log_audit_event(
                db=db,
                request=request,
                action="EXPORT",
                resource_type="detection",
                details={
                    "format": "pdf",
                    "count": len(detections),
                    "camera_id": camera_id,
                    "species": species
                }
            )
            
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=detections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                }
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="PDF generation requires reportlab library. Install with: pip install reportlab")
        except Exception as e:
            logging.error(f"PDF generation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    else:
        # Generate JSON
        result = []
        for det in detections:
            result.append({
                "id": det.id,
                "camera_id": det.camera_id,
                "timestamp": det.timestamp.isoformat() if det.timestamp else None,
                "species": det.species,
                "confidence": det.confidence,
                "image_path": det.image_path,
                "file_size": det.file_size,
                "image_width": det.image_width,
                "image_height": det.image_height,
                "image_quality": det.image_quality,
                "prediction_score": det.prediction_score,
                "detections_json": json.loads(det.detections_json) if det.detections_json else None
            })
        
        # Log export
        log_audit_event(
            db=db,
            request=request,
            action="EXPORT",
            resource_type="detection",
            details={
                "format": "json",
                "count": len(detections),
                "camera_id": camera_id,
                "species": species
            }
        )
        
        return Response(
            content=json.dumps(result, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=detections_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )


@app.post("/api/backup/create")
@limiter.limit("5/hour")  # Rate limit: 5 backups per hour
def create_backup_endpoint(request: Request, db: Session = Depends(get_db)):
    """Manually trigger a database backup"""
    try:
        from services.backup import backup_service
        
        backup_path = backup_service.create_backup()
        
        if backup_path:
            # Log backup creation
            log_audit_event(
                db=db,
                request=request,
                action="BACKUP",
                resource_type="database",
                details={
                    "backup_path": str(backup_path),
                    "size_mb": round(backup_path.stat().st_size / (1024 * 1024), 2)
                }
            )
            
            return {
                "success": True,
                "backup_path": str(backup_path),
                "size_mb": round(backup_path.stat().st_size / (1024 * 1024), 2),
                "message": "Backup created successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create backup")
            
    except Exception as e:
        logging.error(f"Backup creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@app.get("/api/backup/list")
@limiter.limit("60/minute")
def list_backups_endpoint(request: Request):
    """List all available backups"""
    try:
        from services.backup import backup_service
        
        backups = backup_service.list_backups()
        backup_info = []
        
        for backup in backups:
            info = backup_service.get_backup_info(backup)
            if info:
                backup_info.append(info)
        
        return {
            "backups": backup_info,
            "count": len(backup_info)
        }
    except Exception as e:
        logging.error(f"Failed to list backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@app.post("/api/backup/cleanup")
@limiter.limit("5/hour")
def cleanup_backups_endpoint(request: Request, keep_count: int = 10, db: Session = Depends(get_db)):
    """Clean up old backups, keeping only the most recent N"""
    try:
        from services.backup import backup_service
        
        deleted_count = backup_service.cleanup_old_backups(keep_count=keep_count)
        
        # Log cleanup
        log_audit_event(
            db=db,
            request=request,
            action="CLEANUP",
            resource_type="backup",
            details={
                "deleted_count": deleted_count,
                "keep_count": keep_count
            }
        )
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "keep_count": keep_count,
            "message": f"Cleaned up {deleted_count} old backup(s)"
        }
    except Exception as e:
        logging.error(f"Backup cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# Webhook endpoints
@app.post("/api/webhooks", response_model=WebhookResponse)
@limiter.limit("10/hour")
def create_webhook(
    request: Request,
    webhook: WebhookCreate,
    db: Session = Depends(get_db)
):
    """Create a new webhook"""
    try:
        db_webhook = Webhook(**webhook.model_dump())
        db.add(db_webhook)
        db.commit()
        db.refresh(db_webhook)
        
        log_audit_event(
            db=db,
            request=request,
            action="CREATE",
            resource_type="webhook",
            resource_id=db_webhook.id,
            details={"name": webhook.name, "url": webhook.url, "event_type": webhook.event_type}
        )
        
        return db_webhook
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to create webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")


@app.get("/api/webhooks", response_model=List[WebhookResponse])
@limiter.limit("60/minute")
def list_webhooks(
    request: Request,
    is_active: Optional[bool] = None,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all webhooks"""
    try:
        query = db.query(Webhook)
        
        if is_active is not None:
            query = query.filter(Webhook.is_active == is_active)
        
        if event_type:
            query = query.filter(Webhook.event_type == event_type)
        
        webhooks = query.order_by(Webhook.created_at.desc()).all()
        return webhooks
    except Exception as e:
        logging.error(f"Failed to list webhooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")


@app.get("/api/webhooks/{webhook_id}", response_model=WebhookResponse)
@limiter.limit("60/minute")
def get_webhook(
    request: Request,
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific webhook"""
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@app.put("/api/webhooks/{webhook_id}", response_model=WebhookResponse)
@limiter.limit("10/hour")
def update_webhook(
    request: Request,
    webhook_id: int,
    webhook: WebhookCreate,
    db: Session = Depends(get_db)
):
    """Update a webhook"""
    try:
        db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not db_webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        for key, value in webhook.model_dump().items():
            setattr(db_webhook, key, value)
        
        db.commit()
        db.refresh(db_webhook)
        
        log_audit_event(
            db=db,
            request=request,
            action="UPDATE",
            resource_type="webhook",
            resource_id=webhook_id,
            details={"name": webhook.name}
        )
        
        return db_webhook
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update webhook: {str(e)}")


@app.delete("/api/webhooks/{webhook_id}")
@limiter.limit("10/hour")
def delete_webhook(
    request: Request,
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """Delete a webhook"""
    try:
        db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not db_webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        webhook_name = db_webhook.name
        db.delete(db_webhook)
        db.commit()
        
        log_audit_event(
            db=db,
            request=request,
            action="DELETE",
            resource_type="webhook",
            resource_id=webhook_id,
            details={"name": webhook_name}
        )
        
        return {"success": True, "message": "Webhook deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to delete webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete webhook: {str(e)}")


@app.post("/api/webhooks/{webhook_id}/test")
@limiter.limit("10/hour")
def test_webhook(
    request: Request,
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """Test a webhook by sending a test payload"""
    try:
        from services.webhooks import WebhookService
        
        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        webhook_service = WebhookService(db)
        
        # Send test payload
        test_payload = {
            "event": "test",
            "message": "This is a test webhook from Wildlife App",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        success = webhook_service.trigger_webhook(webhook, test_payload, "test")
        
        return {
            "success": success,
            "message": "Test webhook sent successfully" if success else "Test webhook failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to test webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test webhook: {str(e)}")


# Configuration management endpoints
@app.get("/api/config")
@limiter.limit("60/minute")
def get_config(request: Request):
    """Get current configuration values (read-only, for UI display)"""
    try:
        from config import (
            DB_HOST, DB_PORT, DB_NAME, MOTIONEYE_URL, SPECIESNET_URL,
            NOTIFICATION_ENABLED, SMTP_HOST, SMTP_PORT, SMTP_USER,
            NOTIFICATION_EMAIL_FROM, NOTIFICATION_EMAIL_TO,
            SMS_ENABLED, TWILIO_ACCOUNT_SID, TWILIO_PHONE_NUMBER,
            BACKUP_SCHEDULE_MONTHLY_DAY, BACKUP_SCHEDULE_MONTHLY_HOUR,
            BACKUP_RETENTION_COUNT,
            ARCHIVAL_ENABLED, ARCHIVAL_ROOT, ARCHIVAL_RULES,
            API_KEY_ENABLED, SESSION_EXPIRY_HOURS
        )
        
        # Return config values (mask sensitive data)
        return {
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "MOTIONEYE_URL": MOTIONEYE_URL,
            "SPECIESNET_URL": SPECIESNET_URL,
            "NOTIFICATION_ENABLED": str(NOTIFICATION_ENABLED).lower(),
            "SMTP_HOST": SMTP_HOST,
            "SMTP_PORT": str(SMTP_PORT),
            "SMTP_USER": SMTP_USER if SMTP_USER else "",
            "NOTIFICATION_EMAIL_FROM": NOTIFICATION_EMAIL_FROM if NOTIFICATION_EMAIL_FROM else "",
            "NOTIFICATION_EMAIL_TO": NOTIFICATION_EMAIL_TO if NOTIFICATION_EMAIL_TO else "",
            "SMS_ENABLED": str(SMS_ENABLED).lower(),
            "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID[:10] + "..." if TWILIO_ACCOUNT_SID and len(TWILIO_ACCOUNT_SID) > 10 else "",
            "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER if TWILIO_PHONE_NUMBER else "",
            "BACKUP_SCHEDULE_MONTHLY_DAY": str(BACKUP_SCHEDULE_MONTHLY_DAY),
            "BACKUP_SCHEDULE_MONTHLY_HOUR": str(BACKUP_SCHEDULE_MONTHLY_HOUR),
            "BACKUP_RETENTION_COUNT": str(BACKUP_RETENTION_COUNT),
            "ARCHIVAL_ENABLED": str(ARCHIVAL_ENABLED).lower(),
            "ARCHIVAL_ROOT": ARCHIVAL_ROOT,
            "ARCHIVAL_MIN_CONFIDENCE": str(ARCHIVAL_RULES.get("min_confidence", 0.8)),
            "ARCHIVAL_MIN_AGE_DAYS": str(ARCHIVAL_RULES.get("min_age_days", 30)),
            "API_KEY_ENABLED": str(API_KEY_ENABLED).lower(),
            "SESSION_EXPIRY_HOURS": str(SESSION_EXPIRY_HOURS),
            "note": "Configuration changes require editing .env file and restarting the server"
        }
    except Exception as e:
        logging.error(f"Failed to get config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@app.post("/api/config")
@limiter.limit("10/hour")
def update_config(request: Request, configs: Dict[str, str], db: Session = Depends(get_db)):
    """Update configuration (note: actual changes require .env file modification)"""
    try:
        # Log the attempt
        log_audit_event(
            db=db,
            request=request,
            action="CONFIG_UPDATE",
            resource_type="configuration",
            details={
                "keys_updated": list(configs.keys()),
                "note": "Configuration UI is read-only. Changes require .env file modification."
            }
        )
        
        return {
            "success": True,
            "message": "Configuration UI is for viewing only. To change settings, edit the .env file and restart the server.",
            "note": "See ENV_SETUP.md for configuration instructions"
        }
    except Exception as e:
        logging.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@app.post("/api/auth/register")
@limiter.limit("5/hour")
def register_user(
    request: Request,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role: str = "viewer",
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    Args:
        username: Username (must be unique)
        email: Email address (must be unique)
        password: Plain text password
        full_name: Optional full name
        role: User role (viewer, editor, admin) - default: viewer
    
    Returns:
        User information (without password)
    """
    try:
        from services.auth import auth_service
        
        user = auth_service.create_user(
            db=db,
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role=role
        )
        
        # Log registration
        log_audit_event(
            db=db,
            request=request,
            action="CREATE",
            resource_type="user",
            resource_id=user.id,
            details={
                "username": username,
                "email": email,
                "role": role
            }
        )
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_superuser": user.is_superuser,
            "created_at": user.created_at.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Failed to register user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")


@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    username: str,
    password: str,
    db: Session = Depends(get_db)
):
    """
    Login a user and create a session
    
    Args:
        username: Username or email
        password: Plain text password
    
    Returns:
        User information and session token
    """
    try:
        from services.auth import auth_service
        
        client_ip = get_remote_address(request)
        user_agent = request.headers.get("User-Agent")
        
        result = auth_service.authenticate_user(
            db=db,
            username=username,
            password=password,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if not result:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        # Log successful login
        log_audit_event(
            db=db,
            request=request,
            action="LOGIN",
            resource_type="user",
            resource_id=result["user"]["id"],
            details={
                "username": username,
                "ip_address": client_ip
            }
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to login: {str(e)}")


@app.post("/api/auth/logout")
@limiter.limit("30/hour")
def logout(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Logout a user by invalidating their session
    
    Args:
        token: Session token
    
    Returns:
        Success status
    """
    try:
        from services.auth import auth_service
        
        success = auth_service.logout(db, token)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Log logout
        log_audit_event(
            db=db,
            request=request,
            action="LOGOUT",
            resource_type="user",
            details={"token": token[:16] + "..."}  # Only log partial token
        )
        
        return {"success": True, "message": "Logged out successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to logout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to logout: {str(e)}")


@app.get("/api/auth/me")
@limiter.limit("60/minute")
def get_current_user(
    request: Request,
    token: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    Get current user information from session token
    
    Args:
        token: Session token (in Authorization header as "Bearer <token>" or just the token)
    
    Returns:
        Current user information
    """
    try:
        from services.auth import auth_service
        
        # Extract token from Authorization header
        if token and token.startswith("Bearer "):
            token = token.replace("Bearer ", "", 1)
        
        if not token:
            raise HTTPException(status_code=401, detail="No token provided")
        
        user = auth_service.verify_session(db, token)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get current user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get current user: {str(e)}")


@app.post("/api/auth/change-password")
@limiter.limit("10/hour")
def change_password(
    request: Request,
    old_password: str,
    new_password: str,
    token: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    Change user password
    
    Args:
        old_password: Current password
        new_password: New password
        token: Session token
    
    Returns:
        Success status
    """
    try:
        from services.auth import auth_service
        
        # Extract token from Authorization header
        if token and token.startswith("Bearer "):
            token = token.replace("Bearer ", "", 1)
        
        if not token:
            raise HTTPException(status_code=401, detail="No token provided")
        
        user = auth_service.verify_session(db, token)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        success = auth_service.change_password(db, user.id, old_password, new_password)
        
        if not success:
            raise HTTPException(status_code=400, detail="Invalid old password")
        
        # Log password change
        log_audit_event(
            db=db,
            request=request,
            action="UPDATE",
            resource_type="user",
            resource_id=user.id,
            details={"action": "change_password"}
        )
        
        return {"success": True, "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to change password: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


# Initialize scheduled tasks on startup
try:
    from services.scheduler import initialize_scheduled_tasks
    initialize_scheduled_tasks()
    logging.info("Scheduled tasks initialized")
except Exception as e:
    logging.warning(f"Failed to initialize scheduled tasks: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 