"""Webhook management endpoints"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from sqlalchemy.orm import Session
import logging
import os

try:
    from ..services.thingino import ThinginoService
    from ..services.motioneye_webhook_handler import MotionEyeWebhookHandler
except (ImportError, ValueError):
    from services.thingino import ThinginoService
    from services.motioneye_webhook_handler import MotionEyeWebhookHandler

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_webhooks_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup webhooks router with rate limiting and dependencies"""
    
    @router.post("/api/thingino/webhook")
    async def thingino_webhook(request: Request, db: Session = Depends(get_db)):
        """Handle webhook notifications from Thingino camera for motion detection"""
        service = ThinginoService(db)
        try:
            data = await request.json()
            return await service.process_webhook(request, data)
        except Exception as e:
            logger.error(f"Thingino webhook error: {e}")
            return {"status": "error", "message": str(e)}

    @router.post("/api/motioneye/webhook")
    async def motioneye_webhook(request: Request, db: Session = Depends(get_db)):
        """Handle MotionEye webhook notifications for motion detection"""
        handler = MotionEyeWebhookHandler(db)
        
        # Get wildlife app dir for path resolution
        # wildlife-app/backend/routers/webhooks.py -> wildlife-app/
        current_file = os.path.abspath(__file__)
        routers_dir = os.path.dirname(current_file)
        backend_dir = os.path.dirname(routers_dir)
        wildlife_app_dir = os.path.dirname(backend_dir)
        
        return await handler.process_webhook(request, wildlife_app_dir)
            
    return router
