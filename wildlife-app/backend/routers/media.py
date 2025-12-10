"""Media serving endpoints"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def setup_media_router() -> APIRouter:
    """Setup media router for serving image files"""
    
    @router.get("/media/{camera}/{date}/{filename}")
    def get_media(camera: str, date: str, filename: str):
        """Serve media files from motioneye_media or archived_photos"""
        # Always resolve from the project root (wildlife-app)
        # __file__ is: wildlife-app/backend/routers/media.py
        # We need: wildlife-app/
        current_file = os.path.abspath(__file__)  # .../wildlife-app/backend/routers/media.py
        routers_dir = os.path.dirname(current_file)  # .../wildlife-app/backend/routers
        backend_dir = os.path.dirname(routers_dir)  # .../wildlife-app/backend
        project_root = os.path.dirname(backend_dir)  # .../wildlife-app
        
        # Handle both "Camera1" and "1" formats
        camera_name = f"Camera{camera}" if camera.isdigit() else camera
        
        # First try to find the file in motioneye_media
        motioneye_path = os.path.join(
            project_root,
            "motioneye_media", camera_name, date, filename
        )
        
        # Also try alternative paths (in case backend is running from different directory)
        alt_paths = [
            motioneye_path,
            os.path.join(os.getcwd(), "motioneye_media", camera_name, date, filename),
            os.path.join(os.getcwd(), "..", "motioneye_media", camera_name, date, filename),
            os.path.join(backend_dir, "..", "motioneye_media", camera_name, date, filename),
        ]
        
        # Also check in archived_photos (search all species folders)
        archive_path = None
        archive_root = os.path.join(project_root, "archived_photos")
        if os.path.exists(archive_root):
            # Search all subfolders (species folders) for the file
            for species_folder in os.listdir(archive_root):
                species_path = os.path.join(archive_root, species_folder, camera, date, filename)
                if os.path.exists(species_path):
                    archive_path = species_path
                    break
                # Also try with camera_name (CameraX) for robustness
                species_path_alt = os.path.join(archive_root, species_folder, camera_name, date, filename)
                if os.path.exists(species_path_alt):
                    archive_path = species_path_alt
                    break
        
        logger.info(f"Media request: camera={camera}, date={date}, filename={filename}")
        logger.info(f"Project root: {project_root}")
        logger.info(f"Camera name: {camera_name}")
        logger.info(f"Primary path: {motioneye_path}")
        logger.info(f"Primary path exists: {os.path.exists(motioneye_path)}")
        
        # Try all alternative paths
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                logger.info(f"Found file at: {alt_path}")
                return FileResponse(alt_path, media_type="image/jpeg")
        
        if archive_path and os.path.exists(archive_path):
            logger.info(f"Found file in archive: {archive_path}")
            return FileResponse(archive_path, media_type="image/jpeg")
        
        # If not found, provide detailed error
        error_detail = f"File not found. Searched paths:\n"
        error_detail += f"  - {motioneye_path}\n"
        for alt_path in alt_paths[1:]:
            error_detail += f"  - {alt_path}\n"
        if archive_path:
            error_detail += f"  - Archive: {archive_path}\n"
        error_detail += f"Project root: {project_root}\n"
        error_detail += f"Current working directory: {os.getcwd()}\n"
        error_detail += f"MotionEye media dir exists: {os.path.exists(os.path.join(project_root, 'motioneye_media'))}"
        
        logger.error(error_detail)
        raise HTTPException(status_code=404, detail=error_detail)

    @router.get("/archived_photos/{species}/{camera}/{date}/{filename}")
    def serve_archived_photo(species: str, camera: str, date: str, filename: str):
        """Serve archived photos from the archived_photos directory"""
        try:
            # Get the current working directory (where the backend is running)
            current_dir = os.getcwd()
            
            # Construct the file path relative to the current directory
            file_path = os.path.join(current_dir, "archived_photos", species, camera, date, filename)
            
            # Debug logging
            logger.debug(f"Requested file: /archived_photos/{species}/{camera}/{date}/{filename}")
            logger.debug(f"Looking for file at: {file_path}")
            logger.debug(f"File exists: {os.path.exists(file_path)}")
            
            # Security check: ensure the path is within the allowed directory
            if not os.path.abspath(file_path).startswith(os.path.abspath(os.path.join(current_dir, "archived_photos"))):
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Check if file exists
            if not os.path.exists(file_path):
                # Try alternative path structure
                alt_path = os.path.join(current_dir, "..", "archived_photos", species, camera, date, filename)
                logger.debug(f"Trying alternative path: {alt_path}")
                logger.debug(f"Alternative path exists: {os.path.exists(alt_path)}")
                
                if os.path.exists(alt_path):
                    file_path = alt_path
                else:
                    raise HTTPException(status_code=404, detail=f"File not found at {file_path} or {alt_path}")
            
            # Return the file
            return FileResponse(file_path, media_type="image/jpeg")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error serving archived photo: {e}")
            raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

    @router.get("/thumbnails/{filename}")
    def serve_thumbnail(filename: str):
        """Serve thumbnail images"""
        try:
            from utils.image_compression import THUMBNAIL_CACHE_DIR
            thumbnail_path = os.path.join(str(THUMBNAIL_CACHE_DIR), filename)
            if os.path.exists(thumbnail_path):
                return FileResponse(thumbnail_path, media_type="image/jpeg")
            else:
                raise HTTPException(status_code=404, detail="Thumbnail not found")
        except Exception as e:
            logger.error(f"Error serving thumbnail: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router

