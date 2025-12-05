"""Real-time event management for SSE streams"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import psutil
import os

try:
    from ..services.motioneye import motioneye_client
    from ..services.speciesnet import speciesnet_processor
except ImportError:
    from services.motioneye import motioneye_client
    from services.speciesnet import speciesnet_processor

logger = logging.getLogger(__name__)


class EventManager:
    """Manages real-time event broadcasting to connected clients"""
    
    def __init__(self):
        self.clients: Dict[str, asyncio.Queue] = {}
        self.detection_queue = asyncio.Queue()
        self.system_queue = asyncio.Queue()
        self._background_tasks_started = False
    
    async def start_background_tasks(self):
        """Start background tasks for processing events"""
        if not self._background_tasks_started:
            try:
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
                system_data = await self._get_system_health_data()
                await self.broadcast_system_update(system_data)
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logging.error(f"Error broadcasting system health: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _get_system_health_data(self) -> Dict[str, Any]:
        """Get current system health data"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            try:
                root_path = 'C:\\' if os.name == 'nt' else '/'
                disk = psutil.disk_usage(root_path)
            except Exception:
                disk = psutil.disk_usage('.')
            
            motioneye_status = "unknown"
            cameras_count = 0
            try:
                loop = asyncio.get_event_loop()
                motioneye_status = await asyncio.wait_for(
                    loop.run_in_executor(None, motioneye_client.get_status),
                    timeout=30.0
                )
                if motioneye_status == "running":
                    try:
                        cameras = await asyncio.wait_for(
                            loop.run_in_executor(None, motioneye_client.get_cameras),
                            timeout=15.0
                        )
                        cameras_count = len(cameras) if cameras else 0
                    except Exception:
                        cameras_count = 0
            except asyncio.TimeoutError:
                motioneye_status = "timeout"
            except Exception:
                motioneye_status = "error"
            
            speciesnet_status = "unknown"
            try:
                speciesnet_status = await asyncio.wait_for(
                    loop.run_in_executor(None, speciesnet_processor.get_status),
                    timeout=40.0
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
        import uuid
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


# Singleton instance
_event_manager_instance: Optional[EventManager] = None

def get_event_manager() -> EventManager:
    """Get the singleton EventManager instance"""
    global _event_manager_instance
    if _event_manager_instance is None:
        _event_manager_instance = EventManager()
    return _event_manager_instance

