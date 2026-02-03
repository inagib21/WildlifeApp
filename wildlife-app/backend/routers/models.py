"""Model registry endpoints for managing AI models from Hugging Face, Kaggle, etc."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging

try:
    from ..database import get_db, ModelRegistry
    from ..utils.audit import log_audit_event
except ImportError:
    from database import get_db, ModelRegistry
    from utils.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_models_router(limiter, get_db) -> APIRouter:
    """Setup models router with rate limiting and dependencies"""
    
    @router.get("/api/models")
    async def list_models(
        enabled_only: Optional[bool] = False,
        model_type: Optional[str] = None,
        db: Session = Depends(get_db)
    ) -> List[Dict[str, Any]]:
        """List all registered models (optionally filtered)"""
        query = db.query(ModelRegistry)
        
        if enabled_only:
            query = query.filter(ModelRegistry.is_enabled == True)
        
        if model_type:
            query = query.filter(ModelRegistry.model_type == model_type)
        
        models = query.order_by(ModelRegistry.created_at.desc()).all()
        
        return [
            {
                "id": m.id,
                "name": m.name,
                "display_name": m.display_name,
                "source": m.source,
                "source_path": m.source_path,
                "model_type": m.model_type,
                "is_enabled": m.is_enabled,
                "version": m.version,
                "description": m.description,
                "requirements": json.loads(m.requirements) if m.requirements else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None
            }
            for m in models
        ]
    
    @router.get("/api/models/{model_id}")
    async def get_model(
        model_id: int,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Get details for a specific model"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return {
            "id": model.id,
            "name": model.name,
            "display_name": model.display_name,
            "source": model.source,
            "source_path": model.source_path,
            "model_type": model.model_type,
            "is_enabled": model.is_enabled,
            "version": model.version,
            "description": model.description,
            "requirements": json.loads(model.requirements) if model.requirements else None,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }
    
    @router.post("/api/models/add")
    @limiter.limit("10/minute")  # Rate limit model additions
    async def add_model(
        request: Request,
        name: str,
        display_name: str,
        source: str,  # huggingface, kaggle, custom
        source_path: str,
        model_type: str,  # image_classification, object_detection, audio, text
        description: Optional[str] = None,
        version: Optional[str] = None,
        requirements: Optional[List[str]] = None,
        is_enabled: bool = True,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Add a new model to the registry"""
        # Validate source
        valid_sources = ["huggingface", "kaggle", "custom"]
        if source.lower() not in valid_sources:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source. Must be one of: {', '.join(valid_sources)}"
            )
        
        # Validate model type
        valid_types = ["image_classification", "object_detection", "audio", "text"]
        if model_type.lower() not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Check if model name already exists
        existing = db.query(ModelRegistry).filter(ModelRegistry.name == name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Model with name '{name}' already exists")
        
        # Create model registry entry
        model = ModelRegistry(
            name=name,
            display_name=display_name,
            source=source.lower(),
            source_path=source_path,
            model_type=model_type.lower(),
            is_enabled=is_enabled,
            version=version,
            description=description,
            requirements=json.dumps(requirements) if requirements else None
        )
        
        db.add(model)
        db.commit()
        db.refresh(model)
        
        log_audit_event(
            db=db,
            request=request,
            action="ADD_MODEL",
            resource_type="model",
            resource_id=model.id,
            details={
                "name": name,
                "source": source,
                "model_type": model_type
            }
        )
        
        logger.info(f"Added model to registry: {name} ({source}:{source_path})")
        
        return {
            "id": model.id,
            "name": model.name,
            "display_name": model.display_name,
            "source": model.source,
            "source_path": model.source_path,
            "model_type": model.model_type,
            "is_enabled": model.is_enabled,
            "version": model.version,
            "description": model.description,
            "requirements": json.loads(model.requirements) if model.requirements else None,
            "created_at": model.created_at.isoformat() if model.created_at else None
        }
    
    @router.post("/api/models/{model_id}/enable")
    async def toggle_model(
        model_id: int,
        enabled: bool,
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Enable or disable a model"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        model.is_enabled = enabled
        model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        
        log_audit_event(
            db=db,
            request=request,
            action="TOGGLE_MODEL",
            resource_type="model",
            resource_id=model_id,
            details={"enabled": enabled, "model_name": model.name}
        )
        
        logger.info(f"Model {model.name} {'enabled' if enabled else 'disabled'}")
        
        return {
            "id": model.id,
            "name": model.name,
            "is_enabled": model.is_enabled,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }
    
    @router.put("/api/models/{model_id}")
    async def update_model(
        model_id: int,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        requirements: Optional[List[str]] = None,
        request: Request = None,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Update model metadata"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        if display_name is not None:
            model.display_name = display_name
        if description is not None:
            model.description = description
        if version is not None:
            model.version = version
        if requirements is not None:
            model.requirements = json.dumps(requirements)
        
        model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        
        log_audit_event(
            db=db,
            request=request,
            action="UPDATE_MODEL",
            resource_type="model",
            resource_id=model_id,
            details={"model_name": model.name}
        )
        
        return {
            "id": model.id,
            "name": model.name,
            "display_name": model.display_name,
            "description": model.description,
            "version": model.version,
            "requirements": json.loads(model.requirements) if model.requirements else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }
    
    @router.delete("/api/models/{model_id}")
    async def delete_model(
        model_id: int,
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """Remove a model from the registry"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        model_name = model.name
        db.delete(model)
        db.commit()
        
        log_audit_event(
            db=db,
            request=request,
            action="DELETE_MODEL",
            resource_type="model",
            resource_id=model_id,
            details={"model_name": model_name}
        )
        
        logger.info(f"Removed model from registry: {model_name}")
        
        return {"deleted": model_id, "name": model_name}
    
    return router
