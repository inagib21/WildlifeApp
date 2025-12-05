"""Webhook service for sending notifications to external systems"""
import json
import logging
import time
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
import requests
from sqlalchemy.orm import Session

try:
    from ..database import Webhook
except ImportError:
    from database import Webhook

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for managing and triggering webhooks"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def trigger_webhook(
        self,
        webhook: Webhook,
        payload: Dict[str, Any],
        event_type: str
    ) -> bool:
        """
        Trigger a webhook with retry logic
        
        Args:
            webhook: Webhook database record
            payload: Payload to send
            event_type: Type of event (detection, system_alert, etc.)
        
        Returns:
            True if webhook triggered successfully, False otherwise
        """
        if not webhook.is_active:
            return False
        
        # Check if event type matches
        if webhook.event_type != event_type and webhook.event_type != "all":
            return False
        
        # Apply filters if configured
        if webhook.filters:
            try:
                filters = json.loads(webhook.filters)
                if not self._matches_filters(payload, filters):
                    return False
            except Exception as e:
                logger.error(f"Error parsing webhook filters: {e}")
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Wildlife-App-Webhook/1.0",
            "X-Webhook-Event": event_type,
            "X-Webhook-Id": str(webhook.id),
            "X-Webhook-Timestamp": datetime.utcnow().isoformat()
        }
        
        # Add custom headers if configured
        if webhook.headers:
            try:
                custom_headers = json.loads(webhook.headers)
                headers.update(custom_headers)
            except Exception as e:
                logger.error(f"Error parsing webhook headers: {e}")
        
        # Sign payload if secret is configured
        if webhook.secret:
            signature = self._sign_payload(payload, webhook.secret)
            headers["X-Webhook-Signature"] = signature
        
        # Retry logic
        max_retries = webhook.retry_count
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=webhook.timeout
                )
                
                # Consider 2xx status codes as success
                if 200 <= response.status_code < 300:
                    webhook.last_triggered_at = datetime.utcnow()
                    webhook.success_count += 1
                    self.db.commit()
                    logger.info(f"Webhook {webhook.id} ({webhook.name}) triggered successfully")
                    return True
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
            except requests.exceptions.ConnectionError:
                last_error = "Connection error"
            except Exception as e:
                last_error = str(e)
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                time.sleep(webhook.retry_delay)
        
        # All retries failed
        webhook.last_triggered_at = datetime.utcnow()
        webhook.failure_count += 1
        self.db.commit()
        logger.error(f"Webhook {webhook.id} ({webhook.name}) failed after {max_retries + 1} attempts: {last_error}")
        return False
    
    def trigger_detection_webhooks(
        self,
        detection_data: Dict[str, Any],
        confidence: float,
        species: str
    ) -> int:
        """
        Trigger all active detection webhooks
        
        Args:
            detection_data: Detection data dictionary
            confidence: Detection confidence score
            species: Detected species
        
        Returns:
            Number of webhooks successfully triggered
        """
        webhooks = self.db.query(Webhook).filter(
            Webhook.is_active == True,
            Webhook.event_type.in_(["detection", "all"])
        ).all()
        
        success_count = 0
        for webhook in webhooks:
            payload = {
                "event": "detection",
                "detection": detection_data,
                "species": species,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if self.trigger_webhook(webhook, payload, "detection"):
                success_count += 1
        
        return success_count
    
    def trigger_system_alert_webhooks(
        self,
        alert_type: str,
        subject: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Trigger all active system alert webhooks
        
        Args:
            alert_type: Type of alert (warning, error, info)
            subject: Alert subject
            message: Alert message
            details: Optional additional details
        
        Returns:
            Number of webhooks successfully triggered
        """
        webhooks = self.db.query(Webhook).filter(
            Webhook.is_active == True,
            Webhook.event_type.in_(["system_alert", "all"])
        ).all()
        
        success_count = 0
        for webhook in webhooks:
            payload = {
                "event": "system_alert",
                "alert_type": alert_type,
                "subject": subject,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if self.trigger_webhook(webhook, payload, "system_alert"):
                success_count += 1
        
        return success_count
    
    def _matches_filters(self, payload: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if payload matches webhook filters"""
        # Check confidence threshold
        if "min_confidence" in filters:
            confidence = payload.get("confidence", payload.get("detection", {}).get("confidence", 0))
            if confidence < filters["min_confidence"]:
                return False
        
        # Check species filter
        if "species" in filters:
            species = payload.get("species", payload.get("detection", {}).get("species", ""))
            allowed_species = filters["species"]
            if isinstance(allowed_species, list):
                if species not in allowed_species:
                    return False
            elif species != allowed_species:
                return False
        
        # Check camera filter
        if "camera_ids" in filters:
            camera_id = payload.get("camera_id", payload.get("detection", {}).get("camera_id"))
            if camera_id not in filters["camera_ids"]:
                return False
        
        return True
    
    def _sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload"""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

