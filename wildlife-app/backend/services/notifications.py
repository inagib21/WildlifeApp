"""Email notification service for wildlife detections"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from ..config import (
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
        NOTIFICATION_EMAIL_FROM, NOTIFICATION_EMAIL_TO,
        NOTIFICATION_ENABLED
    )
except ImportError:
    from config import (
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
        NOTIFICATION_EMAIL_FROM, NOTIFICATION_EMAIL_TO,
        NOTIFICATION_ENABLED
    )

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending email notifications"""
    
    def __init__(self):
        self.enabled = NOTIFICATION_ENABLED
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_user = SMTP_USER
        self.smtp_password = SMTP_PASSWORD
        self.from_email = NOTIFICATION_EMAIL_FROM
        self.to_emails = NOTIFICATION_EMAIL_TO.split(',') if NOTIFICATION_EMAIL_TO else []
    
    def send_detection_notification(
        self,
        species: str,
        confidence: float,
        camera_id: int,
        camera_name: Optional[str] = None,
        detection_id: Optional[int] = None,
        image_url: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Send email notification for a new wildlife detection
        
        Args:
            species: Detected species name
            confidence: Confidence score (0-1)
            camera_id: Camera ID
            camera_name: Camera name (optional)
            detection_id: Detection ID (optional)
            image_url: URL to view the image (optional)
            timestamp: Detection timestamp (optional)
        
        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping email")
            return False
        
        if not self.to_emails:
            logger.warning("No notification email addresses configured")
            return False
        
        try:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Wildlife Detection: {species} (Camera {camera_id})"
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            # Email body
            camera_display = camera_name or f"Camera {camera_id}"
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            confidence_percent = round(confidence * 100, 1)
            
            text_content = f"""
Wildlife Detection Alert

A new wildlife detection has been captured:

Species: {species}
Confidence: {confidence_percent}%
Camera: {camera_display} (ID: {camera_id})
Timestamp: {timestamp_str}
Detection ID: {detection_id or 'N/A'}

View in dashboard: http://localhost:3000/detections
            """.strip()
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
        .detection-info {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .button {{ background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🦌 Wildlife Detection Alert</h2>
    </div>
    <div class="content">
        <p>A new wildlife detection has been captured:</p>
        <div class="detection-info">
            <p><strong>Species:</strong> {species}</p>
            <p><strong>Confidence:</strong> {confidence_percent}%</p>
            <p><strong>Camera:</strong> {camera_display} (ID: {camera_id})</p>
            <p><strong>Timestamp:</strong> {timestamp_str}</p>
            <p><strong>Detection ID:</strong> {detection_id or 'N/A'}</p>
        </div>
        <a href="http://localhost:3000/detections" class="button">View in Dashboard</a>
    </div>
</body>
</html>
            """.strip()
            
            # Attach both plain text and HTML versions
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Detection notification sent: {species} from Camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send detection notification: {e}", exc_info=True)
            return False
    
    def send_system_alert(
        self,
        subject: str,
        message: str,
        alert_type: str = "warning"  # warning, error, info
    ) -> bool:
        """
        Send system alert email
        
        Args:
            subject: Email subject
            message: Alert message
            alert_type: Type of alert (warning, error, info)
        
        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        if not self.to_emails:
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[Wildlife System] {subject}"
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            text_content = f"""
System Alert: {alert_type.upper()}

{message}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: {'#f44336' if alert_type == 'error' else '#ff9800' if alert_type == 'warning' else '#2196F3'}; color: white; padding: 20px; }}
        .content {{ padding: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>System Alert: {alert_type.upper()}</h2>
    </div>
    <div class="content">
        <p>{message.replace(chr(10), '<br>')}</p>
        <p><small>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    </div>
</body>
</html>
            """.strip()
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"System alert sent: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send system alert: {e}", exc_info=True)
            return False


# Global notification service instance
notification_service = NotificationService()

