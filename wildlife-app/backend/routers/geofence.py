"""Geofencing endpoints for SpeciesNet geographic filtering"""
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging
import math

try:
    from ..database import get_db, Detection, Camera
    from ..routers.settings import get_setting, set_setting
except ImportError:
    from database import get_db, Detection, Camera
    from routers.settings import get_setting, set_setting

router = APIRouter()
logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula"""
    R = 6371  # Earth radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon / 2) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance


def point_in_polygon(lat: float, lon: float, polygon: List[Dict[str, float]]) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm
    
    Args:
        lat: Latitude of point
        lon: Longitude of point
        polygon: List of {latitude, longitude} dicts forming polygon
    
    Returns:
        True if point is inside polygon
    """
    if len(polygon) < 3:
        return False
    
    inside = False
    j = len(polygon) - 1
    
    for i in range(len(polygon)):
        xi, yi = polygon[i]["longitude"], polygon[i]["latitude"]
        xj, yj = polygon[j]["longitude"], polygon[j]["latitude"]
        
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        
        j = i
    
    return inside


def point_in_circle(lat: float, lon: float, center_lat: float, center_lon: float, radius_km: float) -> bool:
    """Check if a point is inside a circle"""
    distance = haversine_distance(lat, lon, center_lat, center_lon)
    return distance <= radius_km


def setup_geofence_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup geofence router with rate limiting and dependencies"""
    
    @router.get("/api/geofence/settings")
    @limiter.limit("60/minute")
    async def get_geofence_settings(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Get geofencing settings"""
        enabled = get_setting(db, "geofence_enabled", default=False)
        geofence_type = get_setting(db, "geofence_type", default=None)  # "polygon", "circle", "bounds"
        geofence_data = get_setting(db, "geofence_data", default=None)
        
        result = {
            "enabled": bool(enabled),
            "type": geofence_type,
            "data": None
        }
        
        if geofence_data:
            try:
                result["data"] = json.loads(geofence_data) if isinstance(geofence_data, str) else geofence_data
            except:
                result["data"] = geofence_data
        
        return result
    
    @router.post("/api/geofence/settings")
    @limiter.limit("10/minute")
    async def set_geofence_settings(
        request: Request,
        enabled: bool,
        geofence_type: str,  # "polygon", "circle", "bounds"
        geofence_data: Dict[str, Any],
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Set geofencing settings
        
        geofence_type options:
        - "polygon": List of {latitude, longitude} points
        - "circle": {latitude, longitude, radius_km}
        - "bounds": {min_latitude, max_latitude, min_longitude, max_longitude}
        """
        valid_types = ["polygon", "circle", "bounds"]
        if geofence_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid geofence_type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Validate geofence data
        if geofence_type == "polygon":
            if not isinstance(geofence_data, list) or len(geofence_data) < 3:
                raise HTTPException(
                    status_code=400,
                    detail="Polygon requires at least 3 points"
                )
            for point in geofence_data:
                if "latitude" not in point or "longitude" not in point:
                    raise HTTPException(
                        status_code=400,
                        detail="Each polygon point must have latitude and longitude"
                    )
        
        elif geofence_type == "circle":
            required = ["latitude", "longitude", "radius_km"]
            for key in required:
                if key not in geofence_data:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Circle requires: {', '.join(required)}"
                    )
        
        elif geofence_type == "bounds":
            required = ["min_latitude", "max_latitude", "min_longitude", "max_longitude"]
            for key in required:
                if key not in geofence_data:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Bounds requires: {', '.join(required)}"
                    )
        
        # Save settings
        set_setting(db, "geofence_enabled", enabled, description="Enable geofencing for SpeciesNet")
        set_setting(db, "geofence_type", geofence_type, description="Geofence type")
        set_setting(db, "geofence_data", json.dumps(geofence_data), description="Geofence data")
        
        logger.info(f"Geofencing {'enabled' if enabled else 'disabled'} with type: {geofence_type}")
        
        return {
            "enabled": enabled,
            "type": geofence_type,
            "data": geofence_data,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @router.post("/api/geofence/validate")
    @limiter.limit("60/minute")
    async def validate_location(
        request: Request,
        latitude: float,
        longitude: float,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Validate if a location is within the configured geofence
        
        Used by SpeciesNet to check if detections should be processed
        """
        enabled = get_setting(db, "geofence_enabled", default=False)
        
        if not enabled:
            return {
                "valid": True,
                "reason": "Geofencing disabled"
            }
        
        geofence_type = get_setting(db, "geofence_type", default=None)
        geofence_data_str = get_setting(db, "geofence_data", default=None)
        
        if not geofence_type or not geofence_data_str:
            return {
                "valid": True,
                "reason": "No geofence configured"
            }
        
        try:
            geofence_data = json.loads(geofence_data_str) if isinstance(geofence_data_str, str) else geofence_data_str
            
            valid = False
            
            if geofence_type == "polygon":
                valid = point_in_polygon(latitude, longitude, geofence_data)
            
            elif geofence_type == "circle":
                center_lat = geofence_data["latitude"]
                center_lon = geofence_data["longitude"]
                radius_km = geofence_data["radius_km"]
                valid = point_in_circle(latitude, longitude, center_lat, center_lon, radius_km)
            
            elif geofence_type == "bounds":
                min_lat = geofence_data["min_latitude"]
                max_lat = geofence_data["max_latitude"]
                min_lon = geofence_data["min_longitude"]
                max_lon = geofence_data["max_longitude"]
                valid = (min_lat <= latitude <= max_lat) and (min_lon <= longitude <= max_lon)
            
            return {
                "valid": valid,
                "latitude": latitude,
                "longitude": longitude,
                "geofence_type": geofence_type,
                "reason": "inside" if valid else "outside"
            }
            
        except Exception as e:
            logger.error(f"Error validating location: {e}", exc_info=True)
            # Default to valid if there's an error
            return {
                "valid": True,
                "reason": f"Validation error: {str(e)}"
            }
    
    @router.get("/api/geofence/stats")
    @limiter.limit("60/minute")
    async def get_geofence_stats(
        request: Request,
        days: int = 30,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Get statistics on detections filtered by geofence"""
        enabled = get_setting(db, "geofence_enabled", default=False)
        
        if not enabled:
            return {
                "enabled": False,
                "message": "Geofencing disabled"
            }
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all detections with camera locations
        detections = db.query(Detection, Camera).join(
            Camera, Detection.camera_id == Camera.id
        ).filter(
            Detection.timestamp >= cutoff_date,
            Camera.latitude.isnot(None),
            Camera.longitude.isnot(None)
        ).all()
        
        geofence_type = get_setting(db, "geofence_type", default=None)
        geofence_data_str = get_setting(db, "geofence_data", default=None)
        
        inside_count = 0
        outside_count = 0
        
        if geofence_type and geofence_data_str:
            try:
                geofence_data = json.loads(geofence_data_str) if isinstance(geofence_data_str, str) else geofence_data_str
                
                for detection, camera in detections:
                    if not camera.latitude or not camera.longitude:
                        continue
                    
                    valid = False
                    if geofence_type == "polygon":
                        valid = point_in_polygon(camera.latitude, camera.longitude, geofence_data)
                    elif geofence_type == "circle":
                        center_lat = geofence_data["latitude"]
                        center_lon = geofence_data["longitude"]
                        radius_km = geofence_data["radius_km"]
                        valid = point_in_circle(camera.latitude, camera.longitude, center_lat, center_lon, radius_km)
                    elif geofence_type == "bounds":
                        min_lat = geofence_data["min_latitude"]
                        max_lat = geofence_data["max_latitude"]
                        min_lon = geofence_data["min_longitude"]
                        max_lon = geofence_data["max_longitude"]
                        valid = (min_lat <= camera.latitude <= max_lat) and (min_lon <= camera.longitude <= max_lon)
                    
                    if valid:
                        inside_count += 1
                    else:
                        outside_count += 1
            except Exception as e:
                logger.error(f"Error calculating geofence stats: {e}", exc_info=True)
        
        return {
            "enabled": True,
            "period_days": days,
            "total_detections": inside_count + outside_count,
            "inside_geofence": inside_count,
            "outside_geofence": outside_count,
            "filter_rate": round((outside_count / (inside_count + outside_count)) * 100, 2) if (inside_count + outside_count) > 0 else 0
        }
    
    return router

