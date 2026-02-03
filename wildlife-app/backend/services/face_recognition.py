"""Face recognition service using face_recognition library with MediaPipe for better detection"""
import logging
import json
import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Try to import face_recognition library
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning("face_recognition library not available. Install with: pip install face-recognition")

# Try to import MediaPipe for better face detection
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    logger.info("MediaPipe not available. Install with: pip install mediapipe (optional, for better face detection)")

# Try to import cv2 for image processing
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Install with: pip install opencv-python")

# Try to import PIL for image preprocessing
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow not available. Install with: pip install pillow")


class FaceRecognitionService:
    """Service for face detection and recognition"""
    
    def __init__(self):
        self.known_faces = {}  # Cache of known faces: {face_id: encoding}
        self.known_face_names = {}  # Cache of face names: {face_id: name}
        self.known_face_tolerance = {}  # Cache of per-face tolerance: {face_id: tolerance}
        self.max_image_dimension = 800  # Maximum width or height for processing (maintains quality while improving speed)
        
        # MediaPipe will be initialized on first use if available
    
    def _preprocess_image(self, image_path: str) -> Optional[str]:
        """Resize large images to improve processing speed
        
        Returns:
            Path to preprocessed image (may be original if no resize needed), or None if error
        """
        if not PIL_AVAILABLE:
            return image_path
        
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Check if resize is needed
                max_dim = max(width, height)
                if max_dim <= self.max_image_dimension:
                    return image_path  # No resize needed
                
                # Calculate new dimensions maintaining aspect ratio
                if width > height:
                    new_width = self.max_image_dimension
                    new_height = int(height * (self.max_image_dimension / width))
                else:
                    new_height = self.max_image_dimension
                    new_width = int(width * (self.max_image_dimension / height))
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save to temporary file
                import tempfile
                file_ext = os.path.splitext(image_path)[1].lower() or '.jpg'
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                
                # Convert to RGB if necessary
                if resized_img.mode != 'RGB':
                    resized_img = resized_img.convert('RGB')
                
                # Save resized image
                resized_img.save(temp_file.name, quality=95, optimize=True)
                temp_file.close()
                
                logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height} for faster processing")
                return temp_file.name
                
        except Exception as e:
            logger.warning(f"Failed to preprocess image {image_path}: {e}, using original")
            return image_path
    
    def is_available(self) -> bool:
        """Check if face recognition is available"""
        return FACE_RECOGNITION_AVAILABLE
    
    def load_known_faces(self, db_session, known_faces_list=None):
        """Load known faces from database"""
        if not self.is_available():
            return
        
        try:
            from database import KnownFace
            
            if known_faces_list is None:
                known_faces_list = db_session.query(KnownFace).filter(
                    KnownFace.is_active == True
                ).all()
            
            self.known_faces = {}
            self.known_face_names = {}
            self.known_face_tolerance = {}
            
            for face in known_faces_list:
                try:
                    encoding = json.loads(face.face_encoding)
                    self.known_faces[face.id] = np.array(encoding)
                    self.known_face_names[face.id] = face.name
                    # Store per-face tolerance (default 0.6 if not set)
                    self.known_face_tolerance[face.id] = face.tolerance if face.tolerance is not None else 0.6
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to load face encoding for {face.name}: {e}")
            
            logger.info(f"Loaded {len(self.known_faces)} known faces")
        except Exception as e:
            logger.error(f"Error loading known faces: {e}")
    
    def _detect_faces_mediapipe(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect faces using MediaPipe (more accurate)"""
        if not MEDIAPIPE_AVAILABLE or not CV2_AVAILABLE:
            return []
        
        try:
            # Load image with OpenCV
            image = cv2.imread(image_path)
            if image is None:
                logger.warning(f"Could not load image: {image_path}")
                return []
            
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, _ = image_rgb.shape
            
            # Use MediaPipe face detection
            mp_face_detection = mp.solutions.face_detection
            with mp_face_detection.FaceDetection(
                model_selection=1,  # 0 for close-range, 1 for full-range
                min_detection_confidence=0.5
            ) as face_detection:
                results = face_detection.process(image_rgb)
                
                face_locations = []
                for detection in results.detections or []:
                    # Get bounding box
                    bbox = detection.location_data.relative_bounding_box
                    
                    # Convert to absolute coordinates (top, right, bottom, left)
                    x = int(bbox.xmin * width)
                    y = int(bbox.ymin * height)
                    w = int(bbox.width * width)
                    h = int(bbox.height * height)
                    
                    # MediaPipe format: (ymin, xmin, width, height)
                    # face_recognition format: (top, right, bottom, left)
                    top = y
                    left = x
                    bottom = y + h
                    right = x + w
                    
                    face_locations.append((top, right, bottom, left))
            
            if not face_locations:
                return []
            
            # Now use face_recognition to encode the faces (for compatibility with existing encodings)
            if not FACE_RECOGNITION_AVAILABLE:
                return []
            
            # Load image for face_recognition
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                logger.warning(f"Could not generate encodings for detected faces in {image_path}")
                return []
            
            results = []
            for i, (location, encoding) in enumerate(zip(face_locations, face_encodings)):
                encoding_list = encoding.tolist()
                
                face_location = {
                    "top": int(location[0]),
                    "right": int(location[1]),
                    "bottom": int(location[2]),
                    "left": int(location[3])
                }
                
                results.append({
                    "face_index": i,
                    "face_location": face_location,
                    "face_encoding": encoding_list,
                    "confidence": 1.0,
                    "detection_method": "mediapipe"
                })
            
            logger.info(f"Detected {len(results)} faces using MediaPipe in {image_path}")
            return results
            
        except Exception as e:
            logger.warning(f"MediaPipe face detection failed: {e}")
            return []
    
    def detect_faces(self, image_path: str, model: str = "hog") -> List[Dict[str, Any]]:
        """Detect faces in an image
        
        Args:
            image_path: Path to the image file
            model: Detection model to use - "hog" (faster, less accurate) or "cnn" (slower, more accurate)
                   MediaPipe will be tried first if available (best accuracy)
        """
        if not self.is_available():
            return []
        
        if not os.path.exists(image_path):
            logger.warning(f"Image not found: {image_path}")
            return []
        
        # Preprocess image (resize if too large)
        processed_image_path = self._preprocess_image(image_path)
        temp_file_created = processed_image_path != image_path
        
        try:
            # Try MediaPipe first (best accuracy)
            if MEDIAPIPE_AVAILABLE:
                mediapipe_results = self._detect_faces_mediapipe(processed_image_path)
                if mediapipe_results:
                    return mediapipe_results
                logger.info(f"MediaPipe didn't find faces, trying face_recognition library")
        
            # Fall back to face_recognition library
            # Load image (using preprocessed path)
            image = face_recognition.load_image_file(processed_image_path)
            
            # Try HOG model first (faster)
            face_locations = face_recognition.face_locations(image, model=model)
            
            # If no faces found with HOG, try CNN model (more accurate but slower)
            if not face_locations and model == "hog":
                logger.info(f"No faces found with HOG model, trying CNN model for {processed_image_path}")
                try:
                    face_locations = face_recognition.face_locations(image, model="cnn")
                except Exception as cnn_error:
                    logger.warning(f"CNN model failed: {cnn_error}, using HOG results")
            
            if not face_locations:
                logger.warning(f"No faces detected in {processed_image_path} with {model} model")
                return []
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                logger.warning(f"Could not generate encodings for detected faces in {processed_image_path}")
                return []
            
            results = []
            for i, (location, encoding) in enumerate(zip(face_locations, face_encodings)):
                # Convert encoding to list for JSON serialization
                encoding_list = encoding.tolist()
                
                # Format: (top, right, bottom, left)
                face_location = {
                    "top": int(location[0]),
                    "right": int(location[1]),
                    "bottom": int(location[2]),
                    "left": int(location[3])
                }
                
                results.append({
                    "face_index": i,
                    "face_location": face_location,
                    "face_encoding": encoding_list,
                    "confidence": 1.0,  # face_recognition doesn't provide confidence, assume high
                    "detection_method": model
                })
            
            logger.info(f"Detected {len(results)} faces in {processed_image_path}")
            return results
            
        except Exception as e:
            logger.error(f"Error detecting faces in {processed_image_path}: {e}", exc_info=True)
            return []
        finally:
            # Clean up temporary file if we created one
            if temp_file_created and processed_image_path and os.path.exists(processed_image_path):
                try:
                    os.remove(processed_image_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {processed_image_path}: {e}")
    
    def recognize_faces(
        self,
        image_path: str,
        tolerance: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Detect and recognize faces in an image"""
        if not self.is_available():
            return []
        
        # Detect faces first
        detected_faces = self.detect_faces(image_path)
        
        if not detected_faces:
            return []
        
        if not self.known_faces:
            # No known faces, return detections without recognition
            return [
                {
                    **face,
                    "known_face_id": None,
                    "name": "Unknown",
                    "recognition_confidence": 0.0
                }
                for face in detected_faces
            ]
        
            # Try to recognize each face
            results = []
            for face in detected_faces:
                face_encoding = np.array(face["face_encoding"])
                
                # Calculate distances to all known faces
                face_distances = face_recognition.face_distance(
                    list(self.known_faces.values()),
                    face_encoding
                )
                
                # Find best match using per-face tolerance
                best_match_index = None
                best_match_distance = float('inf')
                
                for i, (face_id, known_encoding) in enumerate(self.known_faces.items()):
                    distance = face_distances[i]
                    # Use per-face tolerance if available, otherwise use default
                    face_tolerance = self.known_face_tolerance.get(face_id, tolerance)
                    # Check if this face matches using its specific tolerance
                    if distance <= face_tolerance and distance < best_match_distance:
                        best_match_index = i
                        best_match_distance = distance
            
            if best_match_index is not None:
                # Found a match
                face_id = list(self.known_faces.keys())[best_match_index]
                name = self.known_face_names.get(face_id, "Unknown")
                confidence = 1.0 - best_match_distance  # Convert distance to confidence
                
                results.append({
                    **face,
                    "known_face_id": face_id,
                    "name": name,
                    "recognition_confidence": float(confidence)
                })
            else:
                # No match found
                results.append({
                    **face,
                    "known_face_id": None,
                    "name": "Unknown",
                    "recognition_confidence": 0.0
                })
        
        return results
    
    def add_known_face(
        self,
        db_session,
        name: str,
        image_path: str,
        notes: str = None,
        tolerance: float = 0.6
    ) -> Optional[int]:
        """Add a new known face from an image"""
        if not self.is_available():
            logger.error("Face recognition not available")
            return None
        
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return None
        
        try:
            from database import KnownFace
            
            # Detect faces - MediaPipe will be tried first if available, then face_recognition
            faces = self.detect_faces(image_path, model="hog")
            
            if not faces:
                logger.warning(f"No faces detected in {image_path}")
                logger.warning("Tips: Ensure the image contains a clear face that is well-lit. MediaPipe handles various angles better than dlib.")
                return None
            
            if len(faces) > 1:
                logger.warning(f"Multiple faces detected in {image_path}, using first face")
            
            # Use the first face
            face_encoding = faces[0]["face_encoding"]
            
            # Copy image to a permanent location (optional - you can store in a faces directory)
            # For now, we'll keep the original path or copy it
            permanent_path = image_path  # You can implement file copying here if needed
            
            # Save to database
            known_face = KnownFace(
                name=name,
                face_encoding=json.dumps(face_encoding),
                image_path=permanent_path,
                notes=notes,
                tolerance=tolerance,
                is_active=True
            )
            
            db_session.add(known_face)
            db_session.commit()
            db_session.refresh(known_face)
            
            # Update cache
            self.known_faces[known_face.id] = np.array(face_encoding)
            self.known_face_names[known_face.id] = name
            self.known_face_tolerance[known_face.id] = tolerance
            
            logger.info(f"Added known face: {name} (ID: {known_face.id})")
            return known_face.id
            
        except Exception as e:
            logger.error(f"Error adding known face: {e}")
            db_session.rollback()
            return None


# Global instance
face_recognition_service = FaceRecognitionService()
