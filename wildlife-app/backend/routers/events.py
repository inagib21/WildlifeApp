"""Server-Sent Events (SSE) endpoints for real-time updates"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from datetime import datetime
import asyncio
import json
import logging

try:
    from ..services.events import get_event_manager
except ImportError:
    from services.events import get_event_manager

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_events_router() -> APIRouter:
    """Setup events router for Server-Sent Events"""
    
    event_manager = get_event_manager()
    
    @router.get("/events/detections")
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

    @router.get("/events/system")
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

    return router

