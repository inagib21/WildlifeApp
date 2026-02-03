"""System settings API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime
import json
import logging
import sys
import subprocess
import os

try:
    from ..database import get_db, SystemSettings
except ImportError:
    from database import get_db, SystemSettings

router = APIRouter()
logger = logging.getLogger(__name__)


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    """Get a system setting value"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if setting:
        try:
            # Try to parse as JSON first (for complex values)
            return json.loads(setting.value)
        except (json.JSONDecodeError, TypeError):
            # If not JSON, return as string or convert to appropriate type
            value = setting.value
            if value.lower() in ('true', 'false'):
                return value.lower() == 'true'
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return value
    return default


def set_setting(db: Session, key: str, value: Any, description: str = None) -> SystemSettings:
    """Set a system setting value"""
    # Convert value to JSON string
    if isinstance(value, (dict, list)):
        value_str = json.dumps(value)
    else:
        value_str = str(value)
    
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if setting:
        setting.value = value_str
        if description:
            setting.description = description
    else:
        setting = SystemSettings(
            key=key,
            value=value_str,
            description=description
        )
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    return setting


@router.get("/api/settings")
async def get_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get all system settings"""
    settings = db.query(SystemSettings).all()
    result = {}
    for setting in settings:
        try:
            result[setting.key] = json.loads(setting.value)
        except (json.JSONDecodeError, TypeError):
            result[setting.key] = setting.value
    return result


@router.get("/api/settings/models")
async def get_model_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get enabled/disabled status for all AI models"""
    try:
        models = {
            "speciesnet": get_setting(db, "model_speciesnet_enabled", default=True),
            "yolov11": get_setting(db, "model_yolov11_enabled", default=True),
            "yolov8": get_setting(db, "model_yolov8_enabled", default=True),
            "clip": get_setting(db, "model_clip_enabled", default=True),
            "vit": get_setting(db, "model_vit_enabled", default=True),
            "ensemble": get_setting(db, "model_ensemble_enabled", default=True)
        }
        return models
    except Exception as e:
        logger.error(f"Error getting model settings: {e}", exc_info=True)
        # Return all enabled as default on error
        return {
            "speciesnet": True,
            "yolov11": True,
            "yolov8": True,
            "clip": True,
            "vit": True,
            "ensemble": True
        }


@router.get("/api/settings/{key}")
async def get_setting_value(key: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific system setting"""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    
    try:
        value = json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        value = setting.value
    
    return {
        "key": setting.key,
        "value": value,
        "description": setting.description,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


@router.get("/api/settings/priority/living-things")
async def get_living_priority_setting(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get living things priority setting"""
    enabled = get_setting(db, "priority_living_things", default=True)
    boost_factor = get_setting(db, "priority_living_things_boost", default=0.15)
    
    return {
        "enabled": enabled,
        "boost_factor": boost_factor,
        "description": "When enabled, living things (animals, plants) are prioritized over non-living things (vehicles, buildings, objects) in AI predictions"
    }


@router.post("/api/settings/priority/living-things")
async def set_living_priority_setting(
    enabled: bool,
    boost_factor: float = 0.15,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Enable/disable living things priority and set boost factor"""
    if boost_factor < 0 or boost_factor > 1.0:
        raise HTTPException(status_code=400, detail="Boost factor must be between 0 and 1.0")
    
    set_setting(db, "priority_living_things", enabled, 
                "Prioritize living things over non-living things in AI predictions")
    set_setting(db, "priority_living_things_boost", boost_factor,
                "Confidence boost multiplier for living things (0.15 = 15% boost)")
    
    return {
        "enabled": enabled,
        "boost_factor": boost_factor,
        "message": "Living things priority setting updated"
    }


@router.put("/api/settings/{key}")
async def update_setting(
    key: str,
    value: Any,
    description: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update a system setting"""
    setting = set_setting(db, key, value, description)
    
    try:
        parsed_value = json.loads(setting.value)
    except (json.JSONDecodeError, TypeError):
        parsed_value = setting.value
    
    return {
        "key": setting.key,
        "value": parsed_value,
        "description": setting.description,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


@router.get("/api/settings/ai/enabled")
async def get_ai_enabled(db: Session = Depends(get_db)) -> Dict[str, bool]:
    """Get AI processing enabled status"""
    try:
        enabled = get_setting(db, "ai_enabled", default=True)
        return {"enabled": bool(enabled)}
    except Exception as e:
        logger.error(f"Error getting AI enabled status: {e}", exc_info=True)
        # Return default value on error
        return {"enabled": True}


@router.put("/api/settings/ai/enabled")
async def set_ai_enabled(
    enabled: bool,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Set AI processing enabled status"""
    setting = set_setting(
        db,
        "ai_enabled",
        enabled,
        description="Enable/disable AI processing for detections"
    )
    logger.info(f"AI processing {'enabled' if enabled else 'disabled'}")
    return {
        "enabled": bool(enabled),
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


@router.put("/api/settings/models/{model_name}/enabled")
async def set_model_enabled(
    model_name: str,
    enabled: bool,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Enable or disable a specific AI model"""
    valid_models = ["speciesnet", "yolov11", "yolov8", "clip", "vit", "ensemble"]
    if model_name.lower() not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name. Must be one of: {', '.join(valid_models)}"
        )
    
    setting_key = f"model_{model_name.lower()}_enabled"
    setting = set_setting(
        db,
        setting_key,
        enabled,
        description=f"Enable/disable {model_name} AI model"
    )
    logger.info(f"{model_name} model {'enabled' if enabled else 'disabled'}")
    return {
        "model": model_name,
        "enabled": bool(enabled),
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


@router.get("/api/settings/filters/excluded_species")
async def get_excluded_species(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get list of excluded species (species to filter out)"""
    excluded = get_setting(db, "excluded_species", default=[])
    if not isinstance(excluded, list):
        excluded = []
    return {"excluded_species": excluded}


@router.put("/api/settings/filters/excluded_species")
async def set_excluded_species(
    excluded_species: List[str],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Set list of excluded species (species to filter out)"""
    # Normalize species names (lowercase, strip)
    normalized = [s.lower().strip() for s in excluded_species if s.strip()]
    
    setting = set_setting(
        db,
        "excluded_species",
        normalized,
        description="List of species to exclude from detections (e.g., human, vehicle, car)"
    )
    logger.info(f"Excluded species updated: {normalized}")
    return {
        "excluded_species": normalized,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


@router.get("/api/settings/auto-zip")
async def get_auto_zip_settings(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get auto-zip configuration"""
    enabled = get_setting(db, "auto_zip_enabled", default=False)
    retention_months = get_setting(db, "auto_zip_retention_months", default=3)
    return {
        "enabled": bool(enabled),
        "retention_months": int(retention_months)
    }


@router.put("/api/settings/auto-zip")
async def set_auto_zip_settings(
    enabled: bool,
    retention_months: int = 3,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Configure auto-zip settings"""
    valid_retentions = [1, 2, 3, 6]
    if retention_months not in valid_retentions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid retention_months. Must be one of: {', '.join(map(str, valid_retentions))}"
        )
    
    set_setting(db, "auto_zip_enabled", enabled, description="Enable automatic zipping of old images")
    set_setting(db, "auto_zip_retention_months", retention_months, description="Months before images are zipped")
    
    logger.info(f"Auto-zip {'enabled' if enabled else 'disabled'} with {retention_months} month retention")
    return {
        "enabled": bool(enabled),
        "retention_months": retention_months,
        "updated_at": datetime.utcnow().isoformat()
    }


@router.get("/api/settings/auto-zip/status")
async def get_auto_zip_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get auto-zip service status and statistics"""
    try:
        try:
            from ..services.auto_zip import auto_zip_service
        except ImportError:
            from services.auto_zip import auto_zip_service
        
        status = auto_zip_service.get_zip_status(db)
        
        # Add absolute path to zip folder
        import os
        from pathlib import Path
        zip_root = Path(auto_zip_service.zip_root)
        if not zip_root.is_absolute():
            # Make path absolute relative to backend directory
            backend_dir = Path(__file__).parent.parent
            zip_root = (backend_dir / zip_root).resolve()
        
        status["zip_folder_path"] = str(zip_root)
        status["zip_folder_exists"] = zip_root.exists()
        
        return status
    except Exception as e:
        logger.error(f"Error getting auto-zip status: {e}", exc_info=True)
        # Return default status on error
        return {
            "enabled": False,
            "retention_months": 3,
            "images_to_zip": 0,
            "zip_files_count": 0,
            "total_zip_size_mb": 0,
            "zip_files": [],
            "zip_folder_path": None,
            "zip_folder_exists": False
        }


@router.post("/api/settings/auto-zip/open-folder")
async def open_zip_folder(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Open the zip folder in file explorer (Windows/Linux/Mac)"""
    try:
        from ..services.auto_zip import auto_zip_service
    except ImportError:
        from services.auto_zip import auto_zip_service
    
    import os
    import subprocess
    from pathlib import Path
    
    zip_root = Path(auto_zip_service.zip_root)
    if not zip_root.is_absolute():
        backend_dir = Path(__file__).parent.parent
        zip_root = (backend_dir / zip_root).resolve()
    
    # Create folder if it doesn't exist
    zip_root.mkdir(parents=True, exist_ok=True)
    
    try:
        # Open folder in file explorer based on OS
        if os.name == 'nt':  # Windows
            os.startfile(str(zip_root))
        elif os.name == 'posix':  # Linux/Mac
            if sys.platform == 'darwin':  # Mac
                subprocess.run(['open', str(zip_root)])
            else:  # Linux
                subprocess.run(['xdg-open', str(zip_root)])
        else:
            return {"success": False, "error": "Unsupported operating system"}
        
        return {
            "success": True,
            "message": f"Opening folder: {zip_root}",
            "path": str(zip_root)
        }
    except Exception as e:
        logger.error(f"Error opening folder: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "path": str(zip_root),
            "message": f"Could not open folder automatically. Path: {zip_root}"
        }
