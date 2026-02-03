"""Analytics endpoints for detection statistics"""
from fastapi import APIRouter, HTTPException, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta
import logging

try:
    from ..database import Detection, Camera
    from ..routers.settings import get_setting
except ImportError:
    from database import Detection, Camera
    from routers.settings import get_setting

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_excluded_species_filter(query, db: Session):
    """Apply excluded species filter to query if configured"""
    excluded_species = get_setting(db, "excluded_species", default=[])
    if excluded_species and isinstance(excluded_species, list):
        # Filter out excluded species (case-insensitive)
        for excluded in excluded_species:
            if excluded and excluded.strip():
                query = query.filter(~func.lower(Detection.species).contains(excluded.lower().strip()))
    return query


def setup_analytics_router(limiter: Limiter, get_db) -> APIRouter:
    """Setup analytics router with rate limiting and dependencies"""
    
    @router.get("/api/analytics/species")
    @limiter.limit("60/minute")
    def get_species_analytics(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        camera_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """
        Get analytics data for species detections
        
        Returns:
        - Total detections per species
        - Average confidence per species
        - Detection count over time
        """
        try:
            query = db.query(Detection)
            
            # Apply filters
            if camera_id:
                query = query.filter(Detection.camera_id == camera_id)
            if start_date:
                try:
                    # Parse date string to datetime object
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp >= start_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                    try:
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp >= start_dt)
                    except ValueError:
                        logging.error(f"Could not parse start_date: {start_date}")
            if end_date:
                try:
                    # Parse date string to datetime object
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp <= end_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                    try:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp <= end_dt)
                    except ValueError:
                        logging.error(f"Could not parse end_date: {end_date}")
            
            # Apply excluded species filter
            query = _apply_excluded_species_filter(query, db)
            
            detections = query.all()
            
            # Group by species
            species_stats = {}
            for detection in detections:
                species = detection.species or "Unknown"
                if species not in species_stats:
                    species_stats[species] = {
                        "count": 0,
                        "total_confidence": 0.0,
                        "detections": []
                    }
                species_stats[species]["count"] += 1
                # Handle null confidence values
                confidence = detection.confidence if detection.confidence is not None else 0.0
                species_stats[species]["total_confidence"] += confidence
                species_stats[species]["detections"].append({
                    "id": detection.id,
                    "timestamp": detection.timestamp.isoformat() if detection.timestamp else None,
                    "confidence": confidence,
                    "camera_id": detection.camera_id
                })
            
            # Calculate averages and format response
            result = []
            for species, stats in species_stats.items():
                result.append({
                    "species": species,
                    "count": stats["count"],
                    "average_confidence": stats["total_confidence"] / stats["count"] if stats["count"] > 0 else 0.0,
                    "detections": stats["detections"][:10]  # Limit to 10 most recent
                })
            
            # Sort by count descending
            result.sort(key=lambda x: x["count"], reverse=True)
            
            return {
                "species": result,
                "total_detections": len(detections),
                "unique_species": len(result)
            }
        except Exception as e:
            logging.error(f"Failed to get species analytics: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

    @router.get("/api/analytics/timeline")
    @limiter.limit("60/minute")
    def get_timeline_analytics(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        camera_id: Optional[int] = None,
        interval: str = "day",  # day, week, month
        db: Session = Depends(get_db)
    ):
        """
        Get detection timeline analytics
        
        Returns detection counts grouped by time interval
        """
        try:
            query = db.query(Detection)
            
            # Apply filters
            if camera_id:
                query = query.filter(Detection.camera_id == camera_id)
            if start_date:
                try:
                    # Parse date string to datetime object
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp >= start_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                    try:
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp >= start_dt)
                    except ValueError:
                        logging.error(f"Could not parse start_date: {start_date}")
            if end_date:
                try:
                    # Parse date string to datetime object
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp <= end_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                    try:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp <= end_dt)
                    except ValueError:
                        logging.error(f"Could not parse end_date: {end_date}")
            
            # Apply excluded species filter
            query = _apply_excluded_species_filter(query, db)
            
            detections = query.all()
            
            # Group by time interval
            timeline = {}
            for detection in detections:
                dt = detection.timestamp
                
                if interval == "day":
                    key = dt.strftime("%Y-%m-%d")
                elif interval == "week":
                    # Get week start (Monday)
                    days_since_monday = dt.weekday()
                    week_start = dt - timedelta(days=days_since_monday)
                    key = week_start.strftime("%Y-W%W")
                elif interval == "month":
                    key = dt.strftime("%Y-%m")
                else:
                    key = dt.strftime("%Y-%m-%d")
                
                if key not in timeline:
                    timeline[key] = {
                        "date": key,
                        "count": 0,
                        "species": {}
                    }
                timeline[key]["count"] += 1
                
                # Track species in this interval
                species = detection.species or "Unknown"
                if species not in timeline[key]["species"]:
                    timeline[key]["species"][species] = 0
                timeline[key]["species"][species] += 1
            
            # Convert to list and sort
            result = sorted(timeline.values(), key=lambda x: x["date"])
            
            return {
                "timeline": result,
                "interval": interval,
                "total_points": len(result)
            }
        except Exception as e:
            logging.error(f"Failed to get timeline analytics: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get timeline analytics: {str(e)}")

    @router.get("/api/analytics/cameras")
    @limiter.limit("60/minute")
    def get_camera_analytics(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        """
        Get analytics data per camera
        
        Returns:
        - Detection count per camera
        - Most detected species per camera
        - Average confidence per camera
        """
        try:
            query = db.query(Detection)
            
            # Apply date filters
            if start_date:
                try:
                    # Parse date string to datetime object
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp >= start_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid start_date format: {start_date}, error: {e}")
                    try:
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp >= start_dt)
                    except ValueError:
                        logging.error(f"Could not parse start_date: {start_date}")
            if end_date:
                try:
                    # Parse date string to datetime object
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp <= end_dt)
                except (ValueError, AttributeError) as e:
                    logging.warning(f"Invalid end_date format: {end_date}, error: {e}")
                    try:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp <= end_dt)
                    except ValueError:
                        logging.error(f"Could not parse end_date: {end_date}")
            
            # Apply excluded species filter
            query = _apply_excluded_species_filter(query, db)
            
            detections = query.all()
            
            # Group by camera
            camera_stats = {}
            for detection in detections:
                camera_id = detection.camera_id
                if camera_id not in camera_stats:
                    camera_stats[camera_id] = {
                        "camera_id": camera_id,
                        "count": 0,
                        "total_confidence": 0.0,
                        "species": {}
                    }
                camera_stats[camera_id]["count"] += 1
                camera_stats[camera_id]["total_confidence"] += detection.confidence or 0.0
                
                # Track species
                species = detection.species or "Unknown"
                if species not in camera_stats[camera_id]["species"]:
                    camera_stats[camera_id]["species"][species] = 0
                camera_stats[camera_id]["species"][species] += 1
            
            # Get camera names
            cameras = {c.id: c.name for c in db.query(Camera).all()}
            
            # Format response
            result = []
            for camera_id, stats in camera_stats.items():
                # Get top species
                top_species = sorted(
                    stats["species"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
                
                result.append({
                    "camera_id": camera_id,
                    "camera_name": cameras.get(camera_id, f"Camera {camera_id}"),
                    "count": stats["count"],
                    "average_confidence": stats["total_confidence"] / stats["count"] if stats["count"] > 0 else 0.0,
                    "top_species": [{"species": s, "count": c} for s, c in top_species]
                })
            
            # Sort by count descending
            result.sort(key=lambda x: x["count"], reverse=True)
            
            return {
                "cameras": result,
                "total_detections": len(detections),
                "total_cameras": len(result)
            }
        except Exception as e:
            logging.error(f"Failed to get camera analytics: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get camera analytics: {str(e)}")

    @router.get("/api/analytics/time-patterns")
    @limiter.limit("60/minute")
    def get_time_patterns(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        camera_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """
        Get time-of-day and day-of-week patterns
        
        Returns:
        - Detections by hour of day (0-23)
        - Detections by day of week (Mon-Sun)
        - Detections by month
        """
        try:
            query = db.query(Detection)
            
            # Apply filters
            if camera_id:
                query = query.filter(Detection.camera_id == camera_id)
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp >= start_dt)
                except (ValueError, AttributeError):
                    try:
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp >= start_dt)
                    except ValueError:
                        pass
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(Detection.timestamp <= end_dt)
                except (ValueError, AttributeError):
                    try:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        query = query.filter(Detection.timestamp <= end_dt)
                    except ValueError:
                        pass
            
            # Apply excluded species filter
            query = _apply_excluded_species_filter(query, db)
            
            detections = query.all()
            
            # Initialize pattern arrays
            hour_pattern = {str(i): 0 for i in range(24)}
            day_pattern = {
                "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
                "Friday": 0, "Saturday": 0, "Sunday": 0
            }
            month_pattern = {str(i): 0 for i in range(1, 13)}
            
            # Process detections
            for detection in detections:
                dt = detection.timestamp
                
                # Hour of day (0-23)
                hour = dt.hour
                hour_pattern[str(hour)] = hour_pattern.get(str(hour), 0) + 1
                
                # Day of week
                day_name = dt.strftime("%A")
                day_pattern[day_name] = day_pattern.get(day_name, 0) + 1
                
                # Month (1-12)
                month = dt.month
                month_pattern[str(month)] = month_pattern.get(str(month), 0) + 1
            
            # Format hour pattern
            hour_data = [
                {"hour": i, "hour_label": f"{i:02d}:00", "count": hour_pattern[str(i)]}
                for i in range(24)
            ]
            
            # Format day pattern
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_data = [
                {"day": day, "count": day_pattern[day]}
                for day in day_order
            ]
            
            # Format month pattern
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_data = [
                {"month": i, "month_label": month_names[i-1], "count": month_pattern[str(i)]}
                for i in range(1, 13)
            ]
            
            return {
                "hour_pattern": hour_data,
                "day_pattern": day_data,
                "month_pattern": month_data,
                "total_detections": len(detections)
            }
        except Exception as e:
            logging.error(f"Failed to get time patterns: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get time patterns: {str(e)}")

    return router
