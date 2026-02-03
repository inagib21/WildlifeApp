"""Map and hotspot endpoints for visualizing animal detections"""
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

try:
    from ..database import get_db, Detection, Camera
    from ..routers.settings import get_setting
except ImportError:
    from database import get_db, Detection, Camera
    from routers.settings import get_setting

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_map_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup map router with rate limiting and dependencies"""
    
    @router.get("/api/map/hotspots")
    @limiter.limit("60/minute")
    async def get_animal_hotspots(
        request: Request,
        days: int = 30,
        species: Optional[str] = None,
        min_detections: int = 3,
        grid_size: float = 0.01,  # ~1km grid cells at equator
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get animal hotspots for map visualization
        
        Returns detection density heatmap data grouped by geographic grid cells
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get detections with camera locations
            query = db.query(Detection, Camera).join(
                Camera, Detection.camera_id == Camera.id
            ).filter(
                Detection.timestamp >= cutoff_date,
                Camera.latitude.isnot(None),
                Camera.longitude.isnot(None)
            )
            
            # Apply species filter
            if species:
                query = query.filter(Detection.species.ilike(f"%{species}%"))
            
            # Apply excluded species filter
            # Note: query is a join, so we need to filter on Detection.species
            excluded_species = get_setting(db, "excluded_species", default=[])
            if excluded_species and isinstance(excluded_species, list):
                for excluded in excluded_species:
                    if excluded and excluded.strip():
                        query = query.filter(~func.lower(Detection.species).contains(excluded.lower().strip()))
            
            results = query.all()
            
            if not results:
                return {
                    "hotspots": [],
                    "total_detections": 0,
                    "period_days": days,
                    "species": species
                }
            
            # Group by grid cells (rounded to grid_size)
            grid_cells = {}
            for detection, camera in results:
                if not camera.latitude or not camera.longitude:
                    continue
                
                # Round to grid_size for clustering
                lat = round(camera.latitude / grid_size) * grid_size
                lon = round(camera.longitude / grid_size) * grid_size
                cell_key = f"{lat:.6f},{lon:.6f}"
                
                if cell_key not in grid_cells:
                    grid_cells[cell_key] = {
                        "latitude": lat,
                        "longitude": lon,
                        "detections": [],
                        "species_count": {},
                        "total_detections": 0,
                        "avg_confidence": 0.0,
                        "cameras": set()
                    }
                
                grid_cells[cell_key]["detections"].append(detection)
                grid_cells[cell_key]["total_detections"] += 1
                grid_cells[cell_key]["cameras"].add(camera.id)
                
                # Track species
                species_name = detection.species or "Unknown"
                if species_name not in grid_cells[cell_key]["species_count"]:
                    grid_cells[cell_key]["species_count"][species_name] = 0
                grid_cells[cell_key]["species_count"][species_name] += 1
                
                # Track confidence
                conf = detection.confidence or 0.0
                grid_cells[cell_key]["avg_confidence"] += conf
            
            # Build hotspots (only cells with min_detections or more)
            hotspots = []
            for cell_key, cell_data in grid_cells.items():
                if cell_data["total_detections"] < min_detections:
                    continue
                
                # Calculate average confidence
                if cell_data["total_detections"] > 0:
                    cell_data["avg_confidence"] = round(
                        cell_data["avg_confidence"] / cell_data["total_detections"], 
                        3
                    )
                
                # Get top species
                top_species = sorted(
                    cell_data["species_count"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                
                # Calculate intensity (0-1) based on detection count
                max_detections = max(c["total_detections"] for c in grid_cells.values())
                intensity = min(1.0, cell_data["total_detections"] / max_detections) if max_detections > 0 else 0
                
                hotspots.append({
                    "latitude": cell_data["latitude"],
                    "longitude": cell_data["longitude"],
                    "total_detections": cell_data["total_detections"],
                    "unique_species": len(cell_data["species_count"]),
                    "cameras": list(cell_data["cameras"]),
                    "avg_confidence": cell_data["avg_confidence"],
                    "top_species": [
                        {"species": s, "count": c}
                        for s, c in top_species
                    ],
                    "intensity": round(intensity, 3),  # 0-1 for heatmap visualization
                    "grid_size_degrees": grid_size
                })
            
            # Sort by detection count (hottest first)
            hotspots.sort(key=lambda x: x["total_detections"], reverse=True)
            
            return {
                "hotspots": hotspots,
                "total_hotspots": len(hotspots),
                "total_detections": sum(h["total_detections"] for h in hotspots),
                "period_days": days,
                "species": species,
                "grid_size_degrees": grid_size,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting animal hotspots: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/map/detections")
    @limiter.limit("60/minute")
    async def get_map_detections(
        request: Request,
        days: int = 7,
        species: Optional[str] = None,
        camera_id: Optional[int] = None,
        limit: int = 1000,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get detection locations for map markers
        
        Returns individual detection points with camera coordinates
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = db.query(Detection, Camera).join(
                Camera, Detection.camera_id == Camera.id
            ).filter(
                Detection.timestamp >= cutoff_date,
                Camera.latitude.isnot(None),
                Camera.longitude.isnot(None)
            )
            
            if species:
                query = query.filter(Detection.species.ilike(f"%{species}%"))
            
            if camera_id:
                query = query.filter(Detection.camera_id == camera_id)
            
            # Apply excluded species filter
            excluded_species = get_setting(db, "excluded_species", default=[])
            if excluded_species and isinstance(excluded_species, list):
                for excluded in excluded_species:
                    if excluded and excluded.strip():
                        query = query.filter(~func.lower(Detection.species).contains(excluded.lower().strip()))
            
            results = query.order_by(Detection.timestamp.desc()).limit(limit).all()
            
            detections = []
            for detection, camera in results:
                detections.append({
                    "id": detection.id,
                    "species": detection.species,
                    "confidence": detection.confidence,
                    "timestamp": detection.timestamp.isoformat() if detection.timestamp else None,
                    "camera_id": detection.camera_id,
                    "camera_name": camera.name,
                    "latitude": camera.latitude,
                    "longitude": camera.longitude,
                    "address": camera.address
                })
            
            return {
                "detections": detections,
                "total": len(detections),
                "period_days": days,
                "species": species,
                "camera_id": camera_id
            }
            
        except Exception as e:
            logger.error(f"Error getting map detections: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/map/cameras")
    @limiter.limit("60/minute")
    async def get_map_cameras(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Get all cameras with location data for map"""
        try:
            cameras = db.query(Camera).filter(
                Camera.latitude.isnot(None),
                Camera.longitude.isnot(None)
            ).all()
            
            camera_locations = []
            for camera in cameras:
                # Get recent detection count
                recent_count = db.query(func.count(Detection.id)).filter(
                    Detection.camera_id == camera.id,
                    Detection.timestamp >= datetime.utcnow() - timedelta(days=7)
                ).scalar()
                
                camera_locations.append({
                    "id": camera.id,
                    "name": camera.name,
                    "latitude": camera.latitude,
                    "longitude": camera.longitude,
                    "address": camera.address,
                    "is_active": camera.is_active,
                    "recent_detections": recent_count or 0
                })
            
            return {
                "cameras": camera_locations,
                "total": len(camera_locations)
            }
            
        except Exception as e:
            logger.error(f"Error getting map cameras: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return router

