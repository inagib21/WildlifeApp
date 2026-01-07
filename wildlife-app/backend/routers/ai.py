from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, Response
import shutil
import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from ..services.ai_backends import ai_backend_manager
    from ..services.ai_metrics import ai_metrics_tracker
    from ..services.behavioral_analysis import analyze_behavioral_consensus, enhance_predictions_with_behavior
except ImportError:
    from services.ai_backends import ai_backend_manager
    from services.ai_metrics import ai_metrics_tracker
    from services.behavioral_analysis import analyze_behavioral_consensus, enhance_predictions_with_behavior

router = APIRouter()
logger = logging.getLogger(__name__)

# Test images directory - try multiple possible locations
def get_test_images_dir():
    """Get the test images directory, trying multiple possible locations"""
    # Try relative to this file (backend/routers/ai.py -> backend/test_images)
    test_dir = Path(__file__).parent.parent / "test_images"
    if test_dir.exists():
        return test_dir
    
    # Try absolute path from backend directory
    backend_dir = Path(__file__).parent.parent
    test_dir = backend_dir / "test_images"
    if test_dir.exists():
        return test_dir
    
    # Try creating it if it doesn't exist
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir

TEST_IMAGES_DIR = get_test_images_dir()

@router.get("/api/ai/backends")
async def list_backends():
    """List all available AI backends"""
    return ai_backend_manager.list_backends()

@router.get("/api/ai/metrics")
async def get_metrics(backend_name: Optional[str] = None):
    """Get performance metrics for AI backends"""
    if backend_name:
        return ai_metrics_tracker.get_metrics(backend_name)
    else:
        return {
            "summary": ai_metrics_tracker.get_summary(),
            "backends": ai_metrics_tracker.get_metrics()
        }

@router.get("/api/ai/test-images")
async def list_test_images():
    """List all available test images and videos"""
    images = []
    videos = []
    
    logger.info(f"Looking for test images in: {TEST_IMAGES_DIR}")
    logger.info(f"Directory exists: {TEST_IMAGES_DIR.exists()}")
    
    if TEST_IMAGES_DIR.exists():
        # Find all images
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp"]:
            for img_file in TEST_IMAGES_DIR.glob(ext):
                images.append({
                    "filename": img_file.name,
                    "path": f"/api/ai/test-images/file/{img_file.name}",
                    "size": img_file.stat().st_size,
                    "type": "image"
                })
        
        # Find all videos
        for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv", "*.webm"]:
            for vid_file in TEST_IMAGES_DIR.glob(ext):
                videos.append({
                    "filename": vid_file.name,
                    "path": f"/api/ai/test-images/file/{vid_file.name}",
                    "size": vid_file.stat().st_size,
                    "type": "video"
                })
    
    return {
        "images": sorted(images, key=lambda x: x["filename"]),
        "videos": sorted(videos, key=lambda x: x["filename"]),
        "total": len(images) + len(videos)
    }

@router.get("/api/ai/test-images/file/{filename}")
async def get_test_file(filename: str):
    """Serve a test image or video file"""
    import mimetypes
    
    file_path = TEST_IMAGES_DIR / filename
    
    # Security: prevent directory traversal
    if not file_path.resolve().is_relative_to(TEST_IMAGES_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type from file extension
    media_type, _ = mimetypes.guess_type(filename)
    if not media_type:
        # Fallback to common types
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        media_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mkv': 'video/x-matroska',
            'webm': 'video/webm'
        }
        media_type = media_type_map.get(ext, 'application/octet-stream')
    
    # Read file and serve with CORS headers (FileResponse doesn't support custom headers well)
    with open(file_path, 'rb') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Access-Control-Allow-Origin": "*",  # Allow images to be loaded from frontend
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=3600"
        }
    )

from fastapi import Request
from pydantic import BaseModel

class FilePathRequest(BaseModel):
    file_path: str

@router.post("/api/ai/compare-path")
async def compare_models_by_path(request: FilePathRequest):
    """Process a file directly from test_images by path (faster for videos)"""
    from pathlib import Path
    
    # Security: only allow files from test_images directory
    test_file_path = TEST_IMAGES_DIR / Path(request.file_path).name
    
    if not test_file_path.resolve().is_relative_to(TEST_IMAGES_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not test_file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if it's a video
    file_ext = test_file_path.suffix.lower()
    is_video = file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    
    if is_video:
        logger.info(f"Processing video directly from path: {test_file_path}")
        from services.ai_backends import extract_video_frame
        
        # Extract frame
        frame_path = extract_video_frame(str(test_file_path), frame_number=0)
        if not frame_path:
            raise HTTPException(status_code=400, detail="Could not extract frame from video")
        
        temp_path = frame_path
        video_temp_path = str(test_file_path)  # Don't delete original
    else:
        temp_path = str(test_file_path)
        video_temp_path = None
    
    try:
        logger.info(f"Running model comparison on: {test_file_path.name}")
        results = ai_backend_manager.compare_models(temp_path)
        
        # Perform behavioral analysis
        try:
            behavioral_analysis = analyze_behavioral_consensus(results)
            enhanced_results = {}
            for model_name, result in results.items():
                enhanced_results[model_name] = enhance_predictions_with_behavior(result, behavioral_analysis)
            
            enhanced_results["_behavioral_summary"] = {
                "all_behaviors": behavioral_analysis.get("behaviors", []),
                "consensus_behaviors": behavioral_analysis.get("consensus_behaviors", []),
                "unique_behaviors": behavioral_analysis.get("unique_behaviors", {}),
                "behavior_confidence": behavioral_analysis.get("confidence", {})
            }
            
            return enhanced_results
        except Exception as e:
            logger.warning(f"Behavioral analysis failed: {e}")
            return results
    except Exception as e:
        logger.error(f"Error in model comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Only clean up extracted frame, not original video
        if is_video and temp_path and os.path.exists(temp_path) and temp_path != str(test_file_path):
            os.remove(temp_path)

@router.post("/api/ai/compare")
async def compare_models(file: UploadFile = File(...)):
    """Upload an image or video and get predictions from all available models with behavioral analysis"""
    
    # Check if it's a video file
    file_ext = os.path.splitext(file.filename)[1].lower()
    is_video = file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    
    # Normalize file extension (jfif -> jpg, etc.)
    normalized_ext = file_ext.lower()
    if normalized_ext == '.jfif':
        normalized_ext = '.jpg'
    elif normalized_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif']:
        # If it's an image but not a standard format, convert to jpg
        if not is_video:
            normalized_ext = '.jpg'
    
    # For videos, extract a frame first (much faster than processing entire video)
    if is_video:
        logger.info(f"Video file detected: {file.filename}, extracting frame for processing...")
        try:
            from services.ai_backends import extract_video_frame
            
            # Save video temporarily (with size limit check)
            max_video_size = 100 * 1024 * 1024  # 100MB limit
            video_size = 0
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp:
                # Read in chunks to avoid memory issues
                chunk_size = 8192
                while True:
                    chunk = file.file.read(chunk_size)
                    if not chunk:
                        break
                    video_size += len(chunk)
                    if video_size > max_video_size:
                        raise HTTPException(status_code=400, detail=f"Video file too large (max 100MB)")
                    temp.write(chunk)
                video_path = temp.name
            
            logger.info(f"Video saved ({video_size / 1024 / 1024:.1f} MB), extracting frame...")
            
            # Extract first frame (fast operation)
            frame_path = extract_video_frame(video_path, frame_number=0)
            
            if not frame_path:
                # Clean up video file
                if os.path.exists(video_path):
                    os.remove(video_path)
                raise HTTPException(status_code=400, detail="Could not extract frame from video file")
            
            # Use extracted frame for processing
            temp_path = frame_path
            video_temp_path = video_path  # Keep track to clean up later
            logger.info(f"Extracted frame from video, processing frame instead of full video")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            raise HTTPException(status_code=500, detail=f"Video processing error: {str(e)}")
    else:
        # For images, save with normalized extension (jfif -> jpg)
        with tempfile.NamedTemporaryFile(delete=False, suffix=normalized_ext) as temp:
            shutil.copyfileobj(file.file, temp)
            temp_path = temp.name
        
        # If original was jfif, we need to convert it to jpg for YOLO compatibility
        if file_ext.lower() == '.jfif':
            try:
                from PIL import Image
                # Convert jfif to jpg
                img = Image.open(temp_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save as jpg
                jpg_path = temp_path.replace('.jfif', '.jpg')
                img.save(jpg_path, 'JPEG', quality=95)
                
                # Remove old jfif file
                os.remove(temp_path)
                temp_path = jpg_path
                logger.info(f"Converted .jfif to .jpg for YOLO compatibility")
            except Exception as e:
                logger.warning(f"Could not convert .jfif to .jpg: {e}, using original file")
        
        video_temp_path = None
    
    try:
        logger.info(f"Running model comparison on: {file.filename}")
        results = ai_backend_manager.compare_models(temp_path)
        
        # Perform behavioral analysis across all models
        try:
            behavioral_analysis = analyze_behavioral_consensus(results)
            
            # Enhance each model's results with behavioral info
            enhanced_results = {}
            for model_name, result in results.items():
                enhanced_results[model_name] = enhance_predictions_with_behavior(result, behavioral_analysis)
            
            # Add overall behavioral summary
            enhanced_results["_behavioral_summary"] = {
                "all_behaviors": behavioral_analysis.get("behaviors", []),
                "consensus_behaviors": behavioral_analysis.get("consensus_behaviors", []),
                "unique_behaviors": behavioral_analysis.get("unique_behaviors", {}),
                "behavior_confidence": behavioral_analysis.get("confidence", {})
            }
            
            return enhanced_results
        except Exception as e:
            logger.warning(f"Behavioral analysis failed: {e}, returning results without behavioral info")
            return results
        
    except Exception as e:
        logger.error(f"Error in model comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp files
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if video_temp_path and os.path.exists(video_temp_path):
            os.remove(video_temp_path)
