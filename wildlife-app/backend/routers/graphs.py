"""Graph and visualization endpoints for AI model testing and performance analysis"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import logging

try:
    from ..database import get_db, Detection, Camera
    from ..services.ai_backends import ai_backend_manager
    from ..routers.settings import get_setting
except ImportError:
    from database import get_db, Detection, Camera
    from services.ai_backends import ai_backend_manager
    from routers.settings import get_setting

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_excluded_species_filter(query, db: Session):
    """Apply excluded species filter to query if configured"""
    excluded_species = get_setting(db, "excluded_species", default=[])
    if excluded_species and isinstance(excluded_species, list):
        for excluded in excluded_species:
            if excluded and excluded.strip():
                query = query.filter(~func.lower(Detection.species).contains(excluded.lower().strip()))
    return query


def setup_graphs_router(limiter, get_db) -> APIRouter:
    """Setup graphs router with rate limiting and dependencies"""
    
    @router.get("/api/ai/graphs/test")
    @limiter.limit("30/minute")
    async def get_test_graphs(
        request: Request,
        days: int = 30,
        db: Session = Depends(get_db)
    ):
        """
        Generate test graphs for AI model performance
        
        Returns graphs showing:
        - Accuracy over time
        - Confidence score distributions
        - Species detection rates
        - Model comparison charts
        - Inference time trends
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get detections from last N days
            query = db.query(Detection).filter(
                Detection.timestamp >= cutoff_date
            )
            
            # Apply excluded species filter
            query = _apply_excluded_species_filter(query, db)
            
            detections = query.all()
            
            # 1. Accuracy over time (confidence trends)
            accuracy_over_time = []
            daily_data = {}
            
            for det in detections:
                date_key = det.timestamp.date().isoformat()
                if date_key not in daily_data:
                    daily_data[date_key] = {"count": 0, "total_confidence": 0.0}
                daily_data[date_key]["count"] += 1
                daily_data[date_key]["total_confidence"] += (det.confidence or 0.0)
            
            for date, data in sorted(daily_data.items()):
                avg_confidence = data["total_confidence"] / data["count"] if data["count"] > 0 else 0
                accuracy_over_time.append({
                    "date": date,
                    "count": data["count"],
                    "avg_confidence": round(avg_confidence, 3)
                })
            
            # 2. Confidence score distribution
            confidence_buckets = {
                "0.0-0.2": 0,
                "0.2-0.4": 0,
                "0.4-0.6": 0,
                "0.6-0.8": 0,
                "0.8-1.0": 0
            }
            
            for det in detections:
                conf = det.confidence or 0.0
                if conf < 0.2:
                    confidence_buckets["0.0-0.2"] += 1
                elif conf < 0.4:
                    confidence_buckets["0.2-0.4"] += 1
                elif conf < 0.6:
                    confidence_buckets["0.4-0.6"] += 1
                elif conf < 0.8:
                    confidence_buckets["0.6-0.8"] += 1
                else:
                    confidence_buckets["0.8-1.0"] += 1
            
            confidence_distribution = [
                {"range": k, "count": v}
                for k, v in confidence_buckets.items()
            ]
            
            # 3. Species detection rates
            species_counts = {}
            for det in detections:
                species = det.species or "Unknown"
                species_counts[species] = species_counts.get(species, 0) + 1
            
            species_detection_rates = [
                {"species": species, "count": count, "percentage": round((count / len(detections)) * 100, 2)}
                for species, count in sorted(species_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            ]
            
            # 4. Model comparison (if we have model info in detections_json)
            model_performance = {}
            for det in detections:
                if det.detections_json:
                    try:
                        det_data = json.loads(det.detections_json)
                        model = det_data.get("model", "unknown")
                        if model not in model_performance:
                            model_performance[model] = {
                                "count": 0,
                                "total_confidence": 0.0,
                                "avg_confidence": 0.0
                            }
                        model_performance[model]["count"] += 1
                        model_performance[model]["total_confidence"] += (det.confidence or 0.0)
                    except:
                        pass
            
            # Calculate averages
            for model, data in model_performance.items():
                if data["count"] > 0:
                    data["avg_confidence"] = round(data["total_confidence"] / data["count"], 3)
            
            model_comparison = [
                {
                    "model": model,
                    "count": data["count"],
                    "avg_confidence": data["avg_confidence"]
                }
                for model, data in sorted(model_performance.items(), key=lambda x: x[1]["count"], reverse=True)
            ]
            
            # 5. Camera performance
            camera_performance = {}
            for det in detections:
                camera_id = det.camera_id
                if camera_id not in camera_performance:
                    camera_performance[camera_id] = {
                        "count": 0,
                        "total_confidence": 0.0,
                        "species": set()
                    }
                camera_performance[camera_id]["count"] += 1
                camera_performance[camera_id]["total_confidence"] += (det.confidence or 0.0)
                if det.species:
                    camera_performance[camera_id]["species"].add(det.species)
            
            camera_stats = []
            for camera_id, data in camera_performance.items():
                camera = db.query(Camera).filter(Camera.id == camera_id).first()
                camera_stats.append({
                    "camera_id": camera_id,
                    "camera_name": camera.name if camera else f"Camera {camera_id}",
                    "detection_count": data["count"],
                    "avg_confidence": round(data["total_confidence"] / data["count"], 3) if data["count"] > 0 else 0,
                    "unique_species": len(data["species"])
                })
            
            camera_stats.sort(key=lambda x: x["detection_count"], reverse=True)
            
            return {
                "period_days": days,
                "total_detections": len(detections),
                "accuracy_over_time": accuracy_over_time,
                "confidence_distribution": confidence_distribution,
                "species_detection_rates": species_detection_rates,
                "model_comparison": model_comparison,
                "camera_performance": camera_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating test graphs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/api/ai/graphs/confidence-trend")
    @limiter.limit("60/minute")
    async def get_confidence_trend(
        request: Request,
        days: int = 7,
        species: Optional[str] = None,
        camera_id: Optional[int] = None,
        db: Session = Depends(get_db)
    ):
        """Get confidence trend over time"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(Detection).filter(Detection.timestamp >= cutoff_date)
        
        if species:
            query = query.filter(Detection.species.ilike(f"%{species}%"))
        
        if camera_id:
            query = query.filter(Detection.camera_id == camera_id)
        
        # Apply excluded species filter
        query = _apply_excluded_species_filter(query, db)
        
        detections = query.all()
        
        # Group by hour
        hourly_data = {}
        for det in detections:
            hour_key = det.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {"count": 0, "total_confidence": 0.0}
            hourly_data[hour_key]["count"] += 1
            hourly_data[hour_key]["total_confidence"] += (det.confidence or 0.0)
        
        trend = [
            {
                "timestamp": hour,
                "count": data["count"],
                "avg_confidence": round(data["total_confidence"] / data["count"], 3) if data["count"] > 0 else 0
            }
            for hour, data in sorted(hourly_data.items())
        ]
        
        return {
            "period_days": days,
            "species": species,
            "camera_id": camera_id,
            "trend": trend
        }
    
    return router

