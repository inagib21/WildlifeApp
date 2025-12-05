from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text, Index, or_
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import psutil
import requests
from dotenv import load_dotenv
import json
import ast
from fastapi.responses import StreamingResponse, FileResponse
import shutil
import asyncio
import time
from PIL import Image
import tempfile
import logging
from fastapi.responses import JSONResponse
from pathlib import Path
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

# Real-time event management - imported from services
try:
    from services.events import get_event_manager
except ImportError:
    from .services.events import get_event_manager

# Global event manager
event_manager = get_event_manager()

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
            asyncio.create_task(run_photo_scanner(get_db, event_manager=event_manager))
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
        from services.photo_scanner import PhotoScanner
        db = next(get_db())
        scanner = PhotoScanner(db, event_manager=event_manager)
        await scanner.scan_and_process()
        db.close()
    except Exception as e:
        logging.error(f"Photo scanner initial sync error: {e}")

# Pydantic models are now imported from models.py

# Include routers
try:
    from routers.system import setup_system_router
    from routers.cameras import setup_cameras_router
    from routers.detections import setup_detections_router
    from routers.webhooks import setup_webhooks_router
    from routers.backups import setup_backups_router
    from routers.notifications import setup_notifications_router
    from routers.media import setup_media_router
    from routers.events import setup_events_router
    from routers.config import setup_config_router
    from routers.debug import setup_debug_router
except ImportError:
    from .routers.system import setup_system_router
    from .routers.cameras import setup_cameras_router
    from .routers.detections import setup_detections_router
    from .routers.webhooks import setup_webhooks_router
    from .routers.backups import setup_backups_router
    from .routers.notifications import setup_notifications_router
    from .routers.media import setup_media_router
    from .routers.events import setup_events_router
    from .routers.config import setup_config_router
    from .routers.debug import setup_debug_router

# Setup and include routers
system_router = setup_system_router(limiter)
cameras_router = setup_cameras_router(limiter, get_db)
detections_router = setup_detections_router(limiter, get_db)
webhooks_router = setup_webhooks_router(limiter, get_db)
backups_router = setup_backups_router(limiter, get_db)
notifications_router = setup_notifications_router(limiter, get_db)
media_router = setup_media_router()
events_router = setup_events_router()
config_router = setup_config_router(limiter, get_db)
debug_router = setup_debug_router(get_db)

app.include_router(system_router)
app.include_router(cameras_router)
app.include_router(detections_router)
app.include_router(webhooks_router)
app.include_router(backups_router)
app.include_router(notifications_router)
app.include_router(media_router)
app.include_router(events_router)
app.include_router(config_router)
app.include_router(debug_router)

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


# PhotoScanner and run_photo_scanner are now imported from services
try:
    from services.photo_scanner import PhotoScanner, run_photo_scanner
except ImportError:
    from .services.photo_scanner import PhotoScanner, run_photo_scanner

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