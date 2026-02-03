"""Sensor data endpoints for ESP32 cameras"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

try:
    from ..database import get_db, Camera, Detection, SensorReading
    from ..models import DetectionResponse
    from ..utils.audit import log_audit_event
except ImportError:
    from database import get_db, Camera, Detection, SensorReading
    from models import DetectionResponse
    from utils.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_sensors_router(limiter, get_db) -> APIRouter:
    """Setup sensors router with rate limiting and dependencies"""
    
    @router.post("/api/sensors/reading")
    async def receive_sensor_reading(
        request: Request,
        camera_id: Optional[int] = None,
        camera_name: Optional[str] = None,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        pressure: Optional[float] = None,
        detection_id: Optional[int] = None,
        api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db)
    ):
        """
        Receive sensor data from ESP32 cameras
        
        ESP32 cameras should POST to this endpoint with:
        - camera_id or camera_name (for identification)
        - temperature (Celsius)
        - humidity (percentage)
        - pressure (optional, hPa)
        - detection_id (optional, to link to a specific detection)
        - X-API-Key header for authentication
        """
        try:
            # Validate data
            if temperature is None and humidity is None:
                raise HTTPException(
                    status_code=400,
                    detail="At least one sensor value (temperature or humidity) must be provided"
                )
            
            # Find camera by ID or name
            camera = None
            if camera_id:
                camera = db.query(Camera).filter(Camera.id == camera_id).first()
            elif camera_name:
                camera = db.query(Camera).filter(Camera.name == camera_name).first()
            
            if not camera:
                logger.warning(f"Camera not found: id={camera_id}, name={camera_name}")
                # Create sensor reading without camera link if camera not found
                # (ESP32 might send data before camera is registered)
            
            # Validate sensor values
            if temperature is not None and (temperature < -50 or temperature > 70):
                raise HTTPException(
                    status_code=400,
                    detail=f"Temperature out of valid range (-50 to 70): {temperature}"
                )
            
            if humidity is not None and (humidity < 0 or humidity > 100):
                raise HTTPException(
                    status_code=400,
                    detail=f"Humidity out of valid range (0 to 100): {humidity}"
                )
            
            # Create sensor reading
            sensor_reading = SensorReading(
                camera_id=camera.id if camera else None,
                temperature=temperature,
                humidity=humidity,
                pressure=pressure,
                detection_id=detection_id,
                timestamp=datetime.utcnow()
            )
            
            db.add(sensor_reading)
            db.commit()
            db.refresh(sensor_reading)
            
            # If linked to a detection, update detection with sensor data
            if detection_id:
                detection = db.query(Detection).filter(Detection.id == detection_id).first()
                if detection:
                    if temperature is not None:
                        detection.temperature = temperature
                    if humidity is not None:
                        detection.humidity = humidity
                    if pressure is not None:
                        detection.pressure = pressure
                    db.commit()
            
            # Log audit event
            log_audit_event(
                db=db,
                request=request,
                action="SENSOR_READING",
                resource_type="sensor",
                resource_id=sensor_reading.id,
                details={
                    "camera_id": camera.id if camera else None,
                    "temperature": temperature,
                    "humidity": humidity,
                    "pressure": pressure,
                    "detection_id": detection_id
                }
            )
            
            logger.info(f"Received sensor reading: camera={camera.name if camera else 'unknown'}, temp={temperature}, humidity={humidity}")
            
            return {
                "id": sensor_reading.id,
                "camera_id": sensor_reading.camera_id,
                "timestamp": sensor_reading.timestamp.isoformat(),
                "temperature": sensor_reading.temperature,
                "humidity": sensor_reading.humidity,
                "pressure": sensor_reading.pressure,
                "detection_id": sensor_reading.detection_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error receiving sensor reading: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/sensors/{camera_id}/readings")
    async def get_sensor_readings(
        camera_id: int,
        limit: Optional[int] = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """Get sensor readings for a specific camera"""
        query = db.query(SensorReading).filter(SensorReading.camera_id == camera_id)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(SensorReading.timestamp >= start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(SensorReading.timestamp <= end_dt)
            except ValueError:
                pass
        
        readings = query.order_by(SensorReading.timestamp.desc()).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "temperature": r.temperature,
                "humidity": r.humidity,
                "pressure": r.pressure,
                "detection_id": r.detection_id
            }
            for r in readings
        ]
    
    @router.get("/api/sensors/{camera_id}/latest")
    async def get_latest_sensor_reading(
        camera_id: int,
        db: Session = Depends(get_db)
    ):
        """Get latest sensor reading for a camera"""
        reading = db.query(SensorReading).filter(
            SensorReading.camera_id == camera_id
        ).order_by(SensorReading.timestamp.desc()).first()
        
        if not reading:
            raise HTTPException(status_code=404, detail="No sensor readings found for this camera")
        
        return {
            "id": reading.id,
            "timestamp": reading.timestamp.isoformat(),
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "pressure": reading.pressure,
            "detection_id": reading.detection_id
        }
    
    @router.post("/api/detections/{detection_id}/link-sensor")
    async def link_detection_to_sensor(
        detection_id: int,
        sensor_reading_id: Optional[int] = None,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        pressure: Optional[float] = None,
        db: Session = Depends(get_db),
        request: Request = None
    ):
        """Link sensor data to a detection"""
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        if sensor_reading_id:
            # Link to existing sensor reading
            sensor_reading = db.query(SensorReading).filter(SensorReading.id == sensor_reading_id).first()
            if not sensor_reading:
                raise HTTPException(status_code=404, detail="Sensor reading not found")
            
            sensor_reading.detection_id = detection_id
            detection.temperature = sensor_reading.temperature
            detection.humidity = sensor_reading.humidity
            detection.pressure = sensor_reading.pressure
        else:
            # Add sensor data directly to detection
            if temperature is not None:
                detection.temperature = temperature
            if humidity is not None:
                detection.humidity = humidity
            if pressure is not None:
                detection.pressure = pressure
        
        db.commit()
        db.refresh(detection)
        
        log_audit_event(
            db=db,
            request=request,
            action="LINK_SENSOR",
            resource_type="detection",
            resource_id=detection_id,
            details={"sensor_reading_id": sensor_reading_id}
        )
        
        return {
            "id": detection.id,
            "temperature": detection.temperature,
            "humidity": detection.humidity,
            "pressure": detection.pressure
        }
    
    return router

