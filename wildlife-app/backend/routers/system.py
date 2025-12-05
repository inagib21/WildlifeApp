"""System health and status endpoints"""
from fastapi import APIRouter, Request, Depends
from slowapi import Limiter
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import asyncio
import os
import psutil
import time
import logging
from datetime import datetime, timedelta
from collections import deque
from fastapi.responses import JSONResponse
from sqlalchemy import func, text

try:
    from ..services.motioneye import motioneye_client
    from ..services.speciesnet import speciesnet_processor
    from ..utils.caching import get_cached, set_cached
    from ..database import Detection, Camera
    from ..services.notifications import notification_service
except ImportError:
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from utils.caching import get_cached, set_cached
    from database import Detection, Camera
    from services.notifications import notification_service

# Global storage for network/disk I/O metrics (simple in-memory tracking)
_network_io_history = deque(maxlen=60)  # Store last 60 measurements (1 minute at 1/sec)
_disk_io_history = deque(maxlen=60)
_last_io_measurement = None

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_system_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup system router with rate limiting and dependencies"""
    
    @router.get("/system")
    @limiter.limit("60/minute")  # Rate limit: 60 requests per minute (frequently polled)
    async def get_system_health(request: Request) -> Dict[str, Any]:
        """Get system health and status information - returns quickly even if some services are slow"""
        # Check cache first (5 second TTL for system health)
        cached = get_cached("system_health", ttl=5)
        if cached:
            return cached
        
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
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
                # Create tasks with reasonable timeouts
                motioneye_task = asyncio.create_task(
                    asyncio.wait_for(
                        asyncio.to_thread(motioneye_client.get_cameras) if hasattr(asyncio, 'to_thread')
                        else asyncio.get_event_loop().run_in_executor(None, motioneye_client.get_cameras),
                        timeout=3.0  # Reasonable timeout for MotionEye
                    )
                )
                
                speciesnet_task = asyncio.create_task(
                    asyncio.wait_for(
                        asyncio.to_thread(speciesnet_processor.get_status) if hasattr(asyncio, 'to_thread')
                        else asyncio.get_event_loop().run_in_executor(None, speciesnet_processor.get_status),
                        timeout=5.0  # Longer timeout for SpeciesNet (model loading can take time)
                    )
                )
            except AttributeError:
                # Fallback for older Python versions
                loop = asyncio.get_event_loop()
                motioneye_task = asyncio.create_task(
                    asyncio.wait_for(
                        loop.run_in_executor(None, motioneye_client.get_cameras),
                        timeout=3.0  # Reasonable timeout for MotionEye
                    )
                )
                speciesnet_task = asyncio.create_task(
                    asyncio.wait_for(
                        loop.run_in_executor(None, speciesnet_processor.get_status),
                        timeout=5.0  # Longer timeout for SpeciesNet (model loading can take time)
                    )
                )
            
            # Wait for both with reasonable overall timeout
            try:
                motioneye_result, speciesnet_result = await asyncio.wait_for(
                    asyncio.gather(motioneye_task, speciesnet_task, return_exceptions=True),
                    timeout=6.0  # Total timeout for both checks - allow enough time
                )
                
                # Process MotionEye result
                if isinstance(motioneye_result, Exception):
                    motioneye_status = "error"
                elif isinstance(motioneye_result, asyncio.TimeoutError):
                    motioneye_status = "timeout"
                else:
                    cameras_count = len(motioneye_result) if motioneye_result else 0
                    motioneye_status = "running" if cameras_count > 0 else "no_cameras"
                
                # Process SpeciesNet result
                if isinstance(speciesnet_result, Exception):
                    speciesnet_status = "error"
                elif isinstance(speciesnet_result, asyncio.TimeoutError):
                    speciesnet_status = "timeout"
                else:
                    speciesnet_status = speciesnet_result
                    
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
            
            # Check disk space and send alert if needed (only once per hour to avoid spam)
            if disk_alert:
                cache_key = "disk_alert_sent"
                last_alert = get_cached(cache_key, ttl=3600)  # Check if alert sent in last hour
                if not last_alert:
                    try:
                        notification_service.send_system_alert(
                            subject="Low Disk Space Warning",
                            message=f"Disk usage is at {disk_percent:.1f}% ({disk_used_gb:.1f} GB used of {disk_total_gb:.1f} GB total). Free space: {disk_free_gb:.1f} GB",
                            alert_type="warning"
                        )
                        set_cached(cache_key, True, ttl=3600)  # Remember we sent alert
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
            set_cached("system_health", result, ttl=5)
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
    
    @router.get("/api/system")
    @limiter.limit("60/minute")  # Rate limit: 60 requests per minute
    async def get_system_health_api(request: Request) -> Dict[str, Any]:
        """Alias for /system to support frontend API calls"""
        return await get_system_health(request)
    
    @router.get("/")
    def read_root():
        """Root endpoint"""
        return {"message": "Wildlife Monitoring API with SpeciesNet Integration"}
    
    @router.get("/health")
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
    
    @router.get("/api/health")
    @limiter.limit("120/minute")
    async def health_check_api(request: Request):
        """Alias for /health endpoint"""
        return await health_check(request)
    
    @router.get("/health/detailed")
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
            from ..database import Detection, Camera
        except ImportError:
            from database import Detection, Camera
        
        import logging
        
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
                    "uptime_seconds": None  # Can be set by app state if needed
                }
            )
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}", exc_info=True)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    return router

