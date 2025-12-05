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
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        camera_name = f"Camera{camera}" if camera.isdigit() else camera
        
        # First try to find the file in motioneye_media
        motioneye_path = os.path.join(
            project_root,
            "motioneye_media", camera_name, date, filename
        )
        
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
        
        logger.debug(f"Media request: camera={camera}, date={date}, filename={filename}")
        logger.debug(f"Looking for file in motioneye: {motioneye_path}")
        logger.debug(f"Looking for file in archive: {archive_path}")
        
        # Return the file from wherever it's found
        if os.path.exists(motioneye_path):
            return FileResponse(motioneye_path)
        elif archive_path and os.path.exists(archive_path):
            return FileResponse(archive_path)
        else:
            raise HTTPException(status_code=404, detail=f"File not found in motioneye_media or archive")

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

