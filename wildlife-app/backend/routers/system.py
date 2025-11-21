"""System health and status endpoints"""
from fastapi import APIRouter, Request
from slowapi import Limiter
from typing import Dict, Any
import asyncio
import os
import psutil
from datetime import datetime

try:
    from ..services.motioneye import motioneye_client
    from ..services.speciesnet import speciesnet_processor
    from ..utils.caching import get_cached, set_cached
except ImportError:
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor
    from utils.caching import get_cached, set_cached

router = APIRouter()


def setup_system_router(limiter: Limiter) -> APIRouter:
    """Setup system router with rate limiting"""
    
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
            try:
                disk_percent = psutil.disk_usage('/').percent
            except:
                # Windows might use different path
                disk_percent = psutil.disk_usage('C:\\').percent if os.name == 'nt' else 0
            
            # Prepare default statuses
            motioneye_status = "unknown"
            cameras_count = 0
            speciesnet_status = "unknown"
            
            # Run MotionEye and SpeciesNet checks concurrently with very short timeouts
            # Use asyncio.to_thread for better cancellation support (Python 3.9+)
            try:
                # Create tasks with very short individual timeouts
                motioneye_task = asyncio.create_task(
                    asyncio.wait_for(
                        asyncio.to_thread(motioneye_client.get_cameras) if hasattr(asyncio, 'to_thread')
                        else asyncio.get_event_loop().run_in_executor(None, motioneye_client.get_cameras),
                        timeout=0.8  # Very short timeout - don't block
                    )
                )
                
                speciesnet_task = asyncio.create_task(
                    asyncio.wait_for(
                        asyncio.to_thread(speciesnet_processor.get_status) if hasattr(asyncio, 'to_thread')
                        else asyncio.get_event_loop().run_in_executor(None, speciesnet_processor.get_status),
                        timeout=0.8  # Very short timeout - don't block
                    )
                )
            except AttributeError:
                # Fallback for older Python versions
                loop = asyncio.get_event_loop()
                motioneye_task = asyncio.create_task(
                    asyncio.wait_for(
                        loop.run_in_executor(None, motioneye_client.get_cameras),
                        timeout=0.8
                    )
                )
                speciesnet_task = asyncio.create_task(
                    asyncio.wait_for(
                        loop.run_in_executor(None, speciesnet_processor.get_status),
                        timeout=0.8
                    )
                )
            
            # Wait for both with a very short overall timeout
            try:
                motioneye_result, speciesnet_result = await asyncio.wait_for(
                    asyncio.gather(motioneye_task, speciesnet_task, return_exceptions=True),
                    timeout=1.0  # Total timeout for both checks - very short
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
            
            # Compose response immediately
            result = {
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
    
    return router

