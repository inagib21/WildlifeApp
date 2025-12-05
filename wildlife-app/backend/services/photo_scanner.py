"""Photo scanner service for processing unprocessed photos"""
import os
import shutil
import asyncio
import logging
from datetime import datetime
from hashlib import sha256
from sqlalchemy.orm import Session

try:
    from ..database import Detection, Camera
    from ..services.speciesnet import speciesnet_processor
    from ..services.events import EventManager
except ImportError:
    from database import Detection, Camera
    from services.speciesnet import speciesnet_processor
    from services.events import EventManager

logger = logging.getLogger(__name__)


class PhotoScanner:
    """Scans and processes unprocessed photos from motioneye_media"""
    
    def __init__(self, db: Session, event_manager: EventManager = None):
        self.db = db
        self.event_manager = event_manager
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.media_root = os.path.join(self.project_root, "motioneye_media")
        self.archive_root = os.path.join(self.project_root, "archived_photos")
        self.processed_files = set()
        
        # Create archive directory if it doesn't exist
        os.makedirs(self.archive_root, exist_ok=True)
        
        self.load_processed_files()
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file"""
        h = sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def load_processed_files(self):
        """Load set of already processed file hashes from database"""
        detections = self.db.query(Detection).all()
        self.processed_hashes = set()
        for detection in detections:
            if detection.file_hash:
                self.processed_hashes.add(detection.file_hash)
        logger.info(f"[PhotoScanner] Loaded {len(self.processed_hashes)} processed file hashes from database.")

    def get_file_id(self, file_path: str) -> str:
        """Create unique identifier for a file"""
        path_parts = file_path.split(os.sep)
        if len(path_parts) >= 3:
            camera = path_parts[-3]
            date = path_parts[-2]
            filename = path_parts[-1]
            return f"{camera}_{date}_{filename}"
        return file_path
    
    def archive_photo(self, original_path: str, species: str, camera_id: int) -> str:
        """Archive a photo to the archive folder with species-based organization"""
        try:
            if species.lower() == "unknown":
                return original_path

            common_name = species.split(';')[-1].strip() if ';' in species else species.strip()
            path_parts = original_path.split(os.sep)
            if len(path_parts) >= 3:
                date = path_parts[-2]
                filename = path_parts[-1]

                archive_dir = os.path.join(self.archive_root, common_name.lower(), str(camera_id), date)
                os.makedirs(archive_dir, exist_ok=True)
                archive_path = os.path.join(archive_dir, filename)

                if os.path.exists(original_path):
                    shutil.copy2(original_path, archive_path)
                    logger.info(f"Archived photo: {original_path} -> {archive_path}")
                    return archive_path
                else:
                    logger.warning(f"Original photo not found: {original_path}")
                    return original_path
            else:
                logger.warning(f"Invalid path structure: {original_path}")
                return original_path
        except Exception as e:
            logger.error(f"Error archiving photo {original_path}: {e}")
            return original_path
    
    def scan_for_unprocessed_photos(self) -> list:
        """Scan motioneye_media folders for photos not in database (by file hash)"""
        unprocessed_photos = []
        if not os.path.exists(self.media_root):
            logger.warning(f"[PhotoScanner] media_root does not exist: {self.media_root}")
            return unprocessed_photos
        for camera_folder in os.listdir(self.media_root):
            camera_path = os.path.join(self.media_root, camera_folder)
            if not os.path.isdir(camera_path):
                continue
            for date_folder in os.listdir(camera_path):
                date_path = os.path.join(camera_path, date_folder)
                if not os.path.isdir(date_path) or len(date_folder) != 10:
                    continue
                for filename in os.listdir(date_path):
                    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        continue
                    filename_lower = filename.lower()
                    if filename_lower.endswith('m.jpg') or filename_lower.endswith('m.jpeg'):
                        continue
                    file_path = os.path.join(date_path, filename)
                    try:
                        file_hash = self.compute_file_hash(file_path)
                    except Exception as e:
                        logger.error(f"[PhotoScanner] Error hashing {file_path}: {e}")
                        continue
                    if file_hash not in self.processed_hashes:
                        unprocessed_photos.append({
                            'file_path': file_path,
                            'camera': camera_folder,
                            'date': date_folder,
                            'filename': filename,
                            'file_hash': file_hash
                        })
                    else:
                        logger.debug(f"[PhotoScanner] Skipping already processed file (by hash): {file_path}")
        logger.info(f"[PhotoScanner] Found {len(unprocessed_photos)} unprocessed photos.")
        return unprocessed_photos
    
    async def process_photo(self, photo_info: dict):
        """Process a single photo with SpeciesNet, using file hash deduplication"""
        try:
            camera_id = int(photo_info['camera'].replace('Camera', ''))
            camera = self.db.query(Camera).filter(Camera.id == camera_id).first()
            if not camera:
                logger.warning(f"Camera {camera_id} not found in database, skipping {photo_info['filename']}")
                return
            file_hash = photo_info.get('file_hash')
            if not file_hash:
                file_hash = self.compute_file_hash(photo_info['file_path'])
            if self.db.query(Detection).filter(Detection.file_hash == file_hash).first():
                logger.debug(f"[PhotoScanner] File hash already in DB, skipping: {photo_info['file_path']}")
                return
            speciesnet_response = await self.call_speciesnet(photo_info['file_path'])
            if not speciesnet_response:
                logger.warning(f"SpeciesNet processing failed for {photo_info['filename']}")
                return
            species = "Unknown"
            confidence = 0.0
            if "predictions" in speciesnet_response and speciesnet_response["predictions"] and len(speciesnet_response["predictions"]) > 0:
                pred = speciesnet_response["predictions"][0]
                species = pred.get("prediction", "Unknown")
                confidence = pred.get("prediction_score", 0.0)
            elif "species" in speciesnet_response:
                species = speciesnet_response.get("species", "Unknown")
                confidence = speciesnet_response.get("confidence", 0.0)
            
            # Clean up species name (similar to webhook handler)
            species = self._clean_species_name(species)
            
            archived_path = self.archive_photo(photo_info['file_path'], species, camera_id)
            detection_data = {
                "camera_id": camera_id,
                "timestamp": datetime.now(),
                "species": species,
                "confidence": confidence,
                "image_path": archived_path,
                "detections_json": str(speciesnet_response),
                "file_hash": file_hash
            }
            db_detection = Detection(**detection_data)
            self.db.add(db_detection)
            self.db.commit()
            self.db.refresh(db_detection)
            self.processed_hashes.add(file_hash)
            
            # Broadcast detection if event_manager is available
            if self.event_manager:
                try:
                    camera_info = self.db.query(Camera).filter(Camera.id == camera_id).first()
                    camera_name = camera_info.name if camera_info else f"Camera{camera_id}"
                    
                    path_parts = archived_path.split(os.sep)
                    media_url = None
                    if "archived_photos" in path_parts:
                        idx = path_parts.index("archived_photos")
                        if len(path_parts) > idx + 4:
                            species_name = path_parts[idx + 1]
                            camera_folder = path_parts[idx + 2]
                            date_folder = path_parts[idx + 3]
                            filename = path_parts[idx + 4]
                            media_url = f"/archived_photos/{species_name}/{camera_folder}/{date_folder}/{filename}"
                    
                    detection_event = {
                        "id": db_detection.id,
                        "camera_id": camera_id,
                        "camera_name": camera_name,
                        "species": detection_data["species"],
                        "confidence": detection_data["confidence"],
                        "image_path": archived_path,
                        "timestamp": db_detection.timestamp.isoformat(),
                        "media_url": media_url or f"/media/{camera_name}/{path_parts[-2] if len(path_parts) >= 2 else 'unknown'}/{path_parts[-1]}"
                    }
                    
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(self.event_manager.broadcast_detection(detection_event))
                        else:
                            asyncio.run(self.event_manager.broadcast_detection(detection_event))
                    except RuntimeError:
                        asyncio.run(self.event_manager.broadcast_detection(detection_event))
                except Exception as e:
                    logger.error(f"Error broadcasting detection from PhotoScanner: {e}")
            
            if species.lower() != "unknown":
                logger.info(f"Processed and archived photo: {photo_info['filename']} -> {detection_data['species']} ({detection_data['confidence']:.2f})")
            else:
                logger.info(f"Processed photo (not archived - unknown species): {photo_info['filename']} -> {detection_data['species']} ({detection_data['confidence']:.2f})")
        except Exception as e:
            logger.error(f"Error processing {photo_info['filename']}: {e}")
    
    def _clean_species_name(self, species: str) -> str:
        """Clean and normalize species name from SpeciesNet response"""
        if not species or species == "Unknown":
            return "Unknown"
        
        if ";" in species:
            parts = species.split(";")
            if len(parts) > 0 and len(parts[0]) > 20 and "-" in parts[0]:
                parts = parts[1:]
            
            parts = [p.strip() for p in parts if p.strip() and p.strip().lower() not in ["", "null", "none"]]
            
            if any("no cv" in p.lower() or "no cv result" in p.lower() for p in parts):
                return "Unknown"
            elif parts and parts[-1].lower() == "blank":
                return "Unknown"
            elif len(parts) >= 2:
                meaningful = [p for p in parts if p.strip() and len(p.strip()) > 1]
                if len(meaningful) >= 2:
                    last_part = meaningful[-1].lower()
                    common_names = ["human", "sapiens", "homospecies"]
                    if last_part in common_names:
                        return meaningful[-1].title()
                    else:
                        return f"{meaningful[-2].title()} {meaningful[-1].title()}"
                elif len(meaningful) == 1:
                    return meaningful[0].title()
                else:
                    return parts[-1].title() if parts else "Unknown"
            elif len(parts) == 1:
                return parts[0].title() if len(parts[0]) > 1 else "Unknown"
            else:
                return "Unknown"
        elif len(species) > 30 and "-" in species:
            if ";" in species:
                parts = species.split(";")
                meaningful_parts = [p.strip() for p in parts if p.strip() and len(p) < 30 and "-" not in p]
                if meaningful_parts:
                    return meaningful_parts[-1].title() if len(meaningful_parts[-1]) > 1 else "Unknown"
            return "Unknown"
        elif "no cv" in species.lower() or "no cv result" in species.lower():
            return "Unknown"
        elif len(species) <= 50 and len(species) > 1:
            return species.title()
        else:
            return "Unknown"
    
    async def call_speciesnet(self, image_path: str) -> dict:
        """Call SpeciesNet server to process image"""
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, speciesnet_processor.process_image, image_path)
            
            if "error" in result:
                logger.error(f"SpeciesNet error for {os.path.basename(image_path)}: {result['error']}")
                return None
            
            return result
        except Exception as e:
            logger.error(f"SpeciesNet call failed for {os.path.basename(image_path)}: {e}")
            return None
    
    async def scan_and_process(self):
        """Main scanning and processing function"""
        logger.info("Starting photo scanner...")
        try:
            loop = asyncio.get_running_loop()
            speciesnet_status = await loop.run_in_executor(None, speciesnet_processor.get_status)
            if speciesnet_status != "running":
                logger.warning(f"SpeciesNet server not healthy ({speciesnet_status}), skipping photo processing")
                return
            
            self.load_processed_files()
            unprocessed = await loop.run_in_executor(None, self.scan_for_unprocessed_photos)
            
            if unprocessed:
                logger.info(f"[PhotoScanner] Processing {len(unprocessed)} photos this cycle")
                for i, photo in enumerate(unprocessed):
                    logger.info(f"[PhotoScanner] Processing photo {i+1}/{len(unprocessed)}: {photo['filename']}")
                    status = await loop.run_in_executor(None, speciesnet_processor.get_status)
                    if status != "running":
                        logger.warning("SpeciesNet server became unhealthy, stopping processing")
                        break
                    await self.process_photo(photo)
                logger.info(f"[PhotoScanner] Completed processing {len(unprocessed)} photos this cycle")
                await asyncio.sleep(5)
            else:
                logger.info("[PhotoScanner] No unprocessed photos found")
        except Exception as e:
            logger.error(f"Photo scanner error: {e}", exc_info=True)


# Background task to run photo scanner
async def run_photo_scanner(get_db, event_manager=None):
    """Background task that runs photo scanner periodically"""
    while True:
        try:
            try:
                from ..services.speciesnet import speciesnet_processor
            except ImportError:
                from services.speciesnet import speciesnet_processor
            
            # Check if SpeciesNet server is ready before processing
            status = speciesnet_processor.get_status()
            if status != "running":
                logger.warning(f"SpeciesNet server not ready ({status}), skipping photo processing cycle")
                await asyncio.sleep(300)  # Wait 5 minutes before checking again
                continue
            
            # Get database session
            db = next(get_db())
            scanner = PhotoScanner(db, event_manager=event_manager)
            await scanner.scan_and_process()
            db.close()
        except Exception as e:
            logger.error(f"Photo scanner background task error: {e}", exc_info=True)
        
        # Wait 15 minutes before next scan
        logger.info("Photo scanner sleeping for 15 minutes...")
        await asyncio.sleep(900)  # 15 minutes

