from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, Any
import os
import sys
from dotenv import load_dotenv
import asyncio
import logging

# Import from new modular structure
try:
    from config import MOTIONEYE_URL, SPECIESNET_URL, ALLOWED_ORIGINS
    from database import engine, SessionLocal, Base, Camera, Detection, Webhook
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from services.notifications import notification_service
except ImportError:
    # Fallback for direct execution
    from config import MOTIONEYE_URL, SPECIESNET_URL, ALLOWED_ORIGINS
    from database import engine, SessionLocal, Base, Camera, Detection, Webhook
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from services.notifications import notification_service

try:
    from .camera_sync import CameraSyncService
    from .logging_utils import configure_access_logs
except ImportError:  # pragma: no cover - fallback for direct execution
    from camera_sync import CameraSyncService
    from logging_utils import configure_access_logs

load_dotenv()

# Configure logging with enhanced format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set debug level for specific modules
logging.getLogger("wildlife-app.backend").setLevel(logging.DEBUG)
logging.getLogger("wildlife-app.backend.routers").setLevel(logging.DEBUG)
logging.getLogger("wildlife-app.backend.services").setLevel(logging.DEBUG)

configure_access_logs()

app = FastAPI(
    title="Wildlife Detection API",
    description="API for managing wildlife camera detections, cameras, and system monitoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Basic health check - must be before routers so it works even if routers fail
@app.get("/health")
def health_check():
    """Basic health check endpoint - works even if database is down"""
    return {"status": "healthy", "service": "wildlife-backend"}


# Rate limiting middleware - protect against API abuse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Real-time event management
try:
    from services.events import get_event_manager
except ImportError:
    from .services.events import get_event_manager

# PhotoScanner and run_photo_scanner - imported early for startup event
try:
    from services.photo_scanner import PhotoScanner, run_photo_scanner
except ImportError:
    from .services.photo_scanner import PhotoScanner, run_photo_scanner

# Global event manager
event_manager = get_event_manager()

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
from sqlalchemy import inspect

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

# Background camera sync function (legacy - kept for compatibility)
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

# Background camera sync task (legacy - kept for compatibility)
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

# One-time scan runner for startup sync (legacy - kept for compatibility)
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
    from routers.analytics import setup_analytics_router
    from routers.auth import setup_auth_router
    from routers.audit import setup_audit_router
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
    from .routers.analytics import setup_analytics_router
    from .routers.auth import setup_auth_router
    from .routers.audit import setup_audit_router

# Setup and include routers
system_router = setup_system_router(limiter, get_db)
cameras_router = setup_cameras_router(limiter, get_db)
detections_router = setup_detections_router(limiter, get_db)
webhooks_router = setup_webhooks_router(limiter, get_db)
backups_router = setup_backups_router(limiter, get_db)
notifications_router = setup_notifications_router(limiter, get_db)
media_router = setup_media_router()
events_router = setup_events_router()
config_router = setup_config_router(limiter, get_db)
debug_router = setup_debug_router(get_db)
analytics_router = setup_analytics_router(limiter, get_db)
auth_router = setup_auth_router(limiter, get_db)
audit_router = setup_audit_router(limiter, get_db)

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
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(audit_router)

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

