import os
import time
import logging
import tempfile
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import video processing libraries
try:
    import cv2
    VIDEO_PROCESSING_AVAILABLE = True
except ImportError:
    VIDEO_PROCESSING_AVAILABLE = False
    logger.warning("OpenCV not available - video frame extraction will be disabled")

def extract_video_frame(video_path: str, frame_number: int = 0) -> Optional[str]:
    """
    Extract a frame from a video file
    
    Args:
        video_path: Path to video file
        frame_number: Frame number to extract (0 = first frame)
    
    Returns:
        Path to extracted frame image, or None if extraction failed
    """
    if not VIDEO_PROCESSING_AVAILABLE:
        return None
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video file: {video_path}")
            return None
        
        # Optimize: Set to read only keyframes for faster seeking (if supported)
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        except:
            pass  # Some codecs don't support frame seeking
        
        # Read frame with timeout protection
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            # Try reading first frame if seeking failed
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                logger.error(f"Could not read frame from video: {video_path}")
                return None
        
        # Save frame to temporary file as JPEG (ensure proper format for all backends)
        temp_frame = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_frame_path = temp_frame.name
        temp_frame.close()
        
        # Convert BGR to RGB for proper color (OpenCV uses BGR, PIL/others expect RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Save as JPEG with good quality
        success = cv2.imwrite(temp_frame_path, cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        if not success or not os.path.exists(temp_frame_path) or os.path.getsize(temp_frame_path) == 0:
            logger.error(f"Failed to save extracted frame to {temp_frame_path}")
            return None
        
        # Verify the file is valid
        file_size = os.path.getsize(temp_frame_path)
        if file_size < 100:  # Too small, probably corrupted
            logger.error(f"Extracted frame file too small ({file_size} bytes), likely corrupted")
            os.remove(temp_frame_path)
            return None
        
        logger.debug(f"Extracted frame from video: {temp_frame_path} ({file_size} bytes)")
        return temp_frame_path
        
    except Exception as e:
        logger.error(f"Error extracting frame from video: {e}")
        return None

def is_video_file(file_path: str) -> bool:
    """Check if file is a video based on extension"""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
    return Path(file_path).suffix.lower() in video_extensions


class AIBackend(ABC):
    """Base class for AI detection backends"""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available"""
        pass
    
    @abstractmethod
    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Predict species from image
        
        Returns:
            {
                "predictions": [
                    {"prediction": "species_name", "prediction_score": 0.95},
                    ...
                ],
                "model": "backend_name",
                "confidence": 0.95
            }
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get backend name"""
        pass


class SpeciesNetBackend(AIBackend):
    """SpeciesNet backend (current system)"""
    
    def __init__(self):
        try:
            from .speciesnet import speciesnet_processor
            self.processor = speciesnet_processor
            self.server_url = os.getenv("SPECIESNET_URL", "http://localhost:8000")
        except ImportError:
            from speciesnet import speciesnet_processor
            self.processor = speciesnet_processor
            self.server_url = os.getenv("SPECIESNET_URL", "http://localhost:8000")
    
    def is_available(self) -> bool:
        """Check if SpeciesNet is available"""
        try:
            status = self.processor.get_status()
            return status == "running"
        except:
            return False
    
    def predict(self, image_path: str) -> Dict[str, Any]:
        """Predict using SpeciesNet"""
        # Verify file exists and is valid before processing
        if not os.path.exists(image_path):
            return {
                "predictions": [],
                "model": "speciesnet",
                "error": f"Image file not found: {image_path}"
            }
        
        # Check file size (should be > 0)
        try:
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                return {
                    "predictions": [],
                    "model": "speciesnet",
                    "error": "Image file is empty"
                }
            if file_size < 100:  # Too small, probably corrupted
                return {
                    "predictions": [],
                    "model": "speciesnet",
                    "error": "Image file appears to be corrupted (too small)"
                }
        except Exception as e:
            logger.error(f"Error checking file size: {e}")
            return {
                "predictions": [],
                "model": "speciesnet",
                "error": f"Error accessing image file: {str(e)}"
            }
        
        result = self.processor.process_image(image_path)
        
        if "error" in result:
            return {
                "predictions": [],
                "model": "speciesnet",
                "error": result["error"]
            }
        
        # Format to standard structure and filter out invalid predictions
        predictions = result.get("predictions", [])
        formatted_predictions = []
        for pred in predictions:
            pred_text = str(pred.get("prediction", "Unknown")).strip()
            pred_score = float(pred.get("prediction_score", 0.0))
            
            # Filter out invalid predictions:
            # - UUIDs (like "f2efdae9-efb8-48fb-8a91-eccf79ab4ffb")
            # - Error messages (like "no cv result")
            # - Empty or very short strings
            # - Strings with semicolons (often error concatenations)
            is_valid = (
                pred_text and 
                len(pred_text) > 2 and
                not pred_text.startswith("f2efdae9") and  # Filter UUIDs
                "no cv result" not in pred_text.lower() and
                ";" not in pred_text and  # Filter concatenated errors
                not pred_text.replace("-", "").replace("_", "").isalnum() or len(pred_text) > 10  # Not just UUID-like
            )
            
            if is_valid:
                formatted_predictions.append({
                    "prediction": pred_text,
                    "prediction_score": pred_score
                })
            else:
                logger.debug(f"Filtered out invalid SpeciesNet prediction: {pred_text}")
        
        if not formatted_predictions:
            return {
                "predictions": [],
                "model": "speciesnet",
                "error": "No valid predictions returned from SpeciesNet (all predictions were filtered as invalid)"
            }
        
        return {
            "predictions": formatted_predictions,
            "model": "speciesnet",
            "confidence": float(formatted_predictions[0].get("prediction_score", 0.0)) if formatted_predictions else 0.0
        }
    
    def get_name(self) -> str:
        return "SpeciesNet (YOLOv5)"


class YOLOv8Backend(AIBackend):
    """YOLOv8 backend - faster and more accurate than YOLOv5"""
    
    def __init__(self, version: str = "8"):
        self.version = version
        self.model = None
        # Support YOLOv8, v9, v10, v11
        default_model = f"yolov{version}n.pt" if version != "11" else "yolo11n.pt"
        self.model_path = os.getenv(f"YOLOV{version}_MODEL_PATH", default_model)
        self.available = False
        self._try_load()
    
    def _try_load(self):
        """Try to load YOLO model"""
        try:
            from ultralytics import YOLO
            # Try to load model (will auto-download if not exists)
            try:
                self.model = YOLO(self.model_path)
                self.available = True
                logger.info(f"YOLOv{self.version} model loaded successfully")
            except Exception as e:
                # Try auto-downloading if file doesn't exist
                logger.info(f"Model not found locally, attempting to download YOLOv{self.version}...")
                try:
                    if self.version == "11":
                        self.model = YOLO("yolo11n.pt")  # YOLOv11 uses different naming
                    else:
                        self.model = YOLO(f"yolov{self.version}n.pt")
                    self.available = True
                    logger.info(f"YOLOv{self.version} model downloaded and loaded successfully")
                except Exception as e2:
                    logger.warning(f"Failed to load YOLOv{self.version}: {e2}")
        except ImportError:
            logger.warning("ultralytics not installed - YOLOv backend unavailable")
        except Exception as e:
            logger.warning(f"Failed to load YOLOv{self.version}: {e}")
    
    def is_available(self) -> bool:
        return self.available and self.model is not None
    
    def predict(self, image_path: str) -> Dict[str, Any]:
        """Predict using YOLO"""
        if not self.is_available():
            return {
                "predictions": [],
                "model": f"yolov{self.version}",
                "error": f"YOLOv{self.version} model not available"
            }
        
        try:
            results = self.model(image_path)
            
            # YOLO returns detections with class names and confidence
            predictions = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    class_name = result.names[class_id]
                    
                    predictions.append({
                        "prediction": class_name,
                        "prediction_score": confidence
                    })
            
            # Sort by confidence
            predictions.sort(key=lambda x: x["prediction_score"], reverse=True)
            
            return {
                "predictions": predictions[:5],  # Top 5
                "model": f"yolov{self.version}",
                "confidence": predictions[0]["prediction_score"] if predictions else 0.0
            }
        except Exception as e:
            logger.error(f"YOLOv{self.version} prediction error: {e}")
            return {
                "predictions": [],
                "model": f"yolov{self.version}",
                "error": str(e)
            }
    
    def get_name(self) -> str:
        return f"YOLOv{self.version}"


class YOLOv11Backend(YOLOv8Backend):
    """YOLOv11 backend - latest and most efficient version"""
    
    def __init__(self):
        super().__init__(version="11")
    
    def get_name(self) -> str:
        return "YOLOv11 (Latest)"


class CLIPBackend(AIBackend):
    """CLIP backend - zero-shot classification for rare species"""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.available = False
        self._try_load()
    
    def _try_load(self):
        """Try to load CLIP model"""
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = "openai/clip-vit-base-patch32"
            
            self.model = CLIPModel.from_pretrained(model_name).to(device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            self.device = device
            self.available = True
            
            logger.info("CLIP model loaded successfully")
        except ImportError:
            logger.warning("transformers not installed - CLIP backend unavailable")
        except Exception as e:
            logger.warning(f"Failed to load CLIP: {e}")
    
    def is_available(self) -> bool:
        return self.available and self.model is not None
    
    def predict(self, image_path: str, species_labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Predict using CLIP with zero-shot classification"""
        if not self.is_available():
            return {
                "predictions": [],
                "model": "clip",
                "error": "CLIP model not available"
            }
        
        try:
            from PIL import Image
            import torch
            
            # Extract frame if video file
            actual_image_path = image_path
            temp_frame_path = None
            if is_video_file(image_path):
                temp_frame_path = extract_video_frame(image_path)
                if temp_frame_path:
                    actual_image_path = temp_frame_path
                    logger.info(f"CLIP: Extracted frame from video for processing")
                else:
                    return {
                        "predictions": [],
                        "model": "clip",
                        "error": "Could not extract frame from video file"
                    }
            
            # Default species labels if not provided
            if not species_labels:
                species_labels = [
                    "deer", "raccoon", "squirrel", "bird", "cat", "dog",
                    "fox", "coyote", "opossum", "rabbit", "skunk", "human", "vehicle"
                ]
            
            # Load and process image
            image = Image.open(actual_image_path)
            inputs = self.processor(
                text=species_labels,
                images=image,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)
            
            # Format predictions
            predictions = []
            for i, label in enumerate(species_labels):
                predictions.append({
                    "prediction": label,
                    "prediction_score": float(probs[0][i])
                })
            
            # Sort by confidence
            predictions.sort(key=lambda x: x["prediction_score"], reverse=True)
            
            result = {
                "predictions": predictions[:5],  # Top 5
                "model": "clip",
                "confidence": predictions[0]["prediction_score"] if predictions else 0.0
            }
            
            # Clean up temporary frame file
            if temp_frame_path and os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except:
                    pass
            
            return result
        except Exception as e:
            logger.error(f"CLIP prediction error: {e}")
            
            # Clean up temporary frame file on error
            if temp_frame_path and os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except:
                    pass
            
            return {
                "predictions": [],
                "model": "clip",
                "error": str(e)
            }
    
    def get_name(self) -> str:
        return "CLIP (OpenAI)"


class ViTBackend(AIBackend):
    """ViT (Vision Transformer) backend - ImageNet classification"""
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.available = False
        self._try_load()
    
    def _try_load(self):
        """Try to load ViT model"""
        try:
            import torch
            from transformers import ViTImageProcessor, ViTForImageClassification
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = os.getenv("VIT_MODEL_NAME", "google/vit-base-patch16-224")
            
            logger.info(f"Loading ViT model: {model_name}...")
            self.processor = ViTImageProcessor.from_pretrained(model_name)
            self.model = ViTForImageClassification.from_pretrained(model_name).to(device)
            self.device = device
            self.available = True
            
            logger.info("ViT model loaded successfully")
        except ImportError:
            logger.warning("transformers not installed - ViT backend unavailable")
        except Exception as e:
            logger.warning(f"Failed to load ViT: {e}")
    
    def is_available(self) -> bool:
        return self.available and self.model is not None
    
    def predict(self, image_path: str) -> Dict[str, Any]:
        """Predict using ViT"""
        if not self.is_available():
            return {
                "predictions": [],
                "model": "vit",
                "error": "ViT model not available"
            }
        
        # Extract frame if video file
        actual_image_path = image_path
        temp_frame_path = None
        if is_video_file(image_path):
            temp_frame_path = extract_video_frame(image_path)
            if temp_frame_path:
                actual_image_path = temp_frame_path
                logger.info(f"ViT: Extracted frame from video for processing")
            else:
                return {
                    "predictions": [],
                    "model": "vit",
                    "error": "Could not extract frame from video file"
                }
        
        try:
            from PIL import Image
            import torch
            
            # Load and process image
            image = Image.open(actual_image_path)
            if image.mode != "RGB":
                image = image.convert("RGB")
                
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                # Apply softmax to get probabilities
                probs = torch.nn.functional.softmax(logits, dim=-1)[0]
                
                # Get top 5
                top5_prob, top5_catid = torch.topk(probs, 5)
            
            # Format predictions
            predictions = []
            for i in range(top5_prob.size(0)):
                score = float(top5_prob[i])
                label = self.model.config.id2label[int(top5_catid[i])]
                # Clean up label (ImageNet labels often have comma separated synonyms)
                # e.g., "red fox, Vulpes vulpes" -> "red fox"
                clean_label = label.split(",")[0]
                
                predictions.append({
                    "prediction": clean_label,
                    "prediction_score": score
                })
            
            result = {
                "predictions": predictions,
                "model": "vit",
                "confidence": predictions[0]["prediction_score"] if predictions else 0.0
            }
            
            # Clean up temporary frame file
            if temp_frame_path and os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except:
                    pass
            
            return result
        except Exception as e:
            logger.error(f"ViT prediction error: {e}")
            
            # Clean up temporary frame file on error
            if temp_frame_path and os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except:
                    pass
            
            return {
                "predictions": [],
                "model": "vit",
                "error": str(e)
            }
    
    def get_name(self) -> str:
        return "ViT (Google)"


class EnsembleBackend(AIBackend):
    """Ensemble backend - combines multiple models for best accuracy"""
    
    def __init__(self, backends: List[AIBackend]):
        self.backends = [b for b in backends if b.is_available()]
        logger.info(f"Ensemble backend initialized with {len(self.backends)} backends")
    
    def is_available(self) -> bool:
        return len(self.backends) > 0
    
    def predict(self, image_path: str) -> Dict[str, Any]:
        """Predict using ensemble of models"""
        if not self.is_available():
            return {
                "predictions": [],
                "model": "ensemble",
                "error": "No backends available"
            }
        
        # Get predictions from all backends
        all_predictions = {}
        model_names = []
        
        for backend in self.backends:
            try:
                result = backend.predict(image_path)
                if "error" not in result:
                    model_names.append(backend.get_name())
                    for pred in result.get("predictions", []):
                        species = pred["prediction"]
                        score = pred["prediction_score"]
                        
                        if species not in all_predictions:
                            all_predictions[species] = []
                        all_predictions[species].append(score)
            except Exception as e:
                logger.warning(f"Backend {backend.get_name()} failed: {e}")
        
        # Combine predictions (weighted average)
        combined = []
        for species, scores in all_predictions.items():
            # Average the scores from all models
            avg_score = sum(scores) / len(scores)
            # Boost if multiple models agree
            agreement_boost = len(scores) / len(self.backends)
            final_score = avg_score * (1 + agreement_boost * 0.1)
            final_score = min(1.0, final_score)
            
            combined.append({
                "prediction": species,
                "prediction_score": final_score
            })
        
        # Sort by confidence
        combined.sort(key=lambda x: x["prediction_score"], reverse=True)
        
        return {
            "predictions": combined[:5],  # Top 5
            "model": f"ensemble ({', '.join(model_names)})",
            "confidence": combined[0]["prediction_score"] if combined else 0.0,
            "models_used": model_names
        }
    
    def get_name(self) -> str:
        return f"Ensemble ({len(self.backends)} models)"


class AIBackendManager:
    """Manager for multiple AI backends"""
    
    def __init__(self):
        self.backends: Dict[str, AIBackend] = {}
        # Get default from config, but will be overridden by auto-detection if preferred backend not available
        try:
            from ..config import AI_BACKEND
        except ImportError:
            from config import AI_BACKEND
        self.default_backend = AI_BACKEND
        self._initialize_backends()
    
    def _initialize_backends(self):
        """Initialize all available backends with detailed logging"""
        logger.info("=" * 60)
        logger.info("Initializing AI Backend Manager")
        logger.info("=" * 60)
        logger.info(f"Configured default backend: {self.default_backend}")
        
        available_count = 0
        unavailable_count = 0
        
        # SpeciesNet (always available if server is running)
        logger.info("Checking SpeciesNet backend...")
        speciesnet = SpeciesNetBackend()
        if speciesnet.is_available():
            self.backends["speciesnet"] = speciesnet
            available_count += 1
            logger.info("  [OK] SpeciesNet backend registered and available")
        else:
            unavailable_count += 1
            logger.warning("  [FAIL] SpeciesNet backend not available (server may not be running)")
        
        # YOLOv11 (best choice - latest version)
        logger.info("Checking YOLOv11 backend...")
        yolov11 = YOLOv11Backend()
        if yolov11.is_available():
            self.backends["yolov11"] = yolov11
            available_count += 1
            logger.info("  [OK] YOLOv11 backend registered and available (BEST CHOICE)")
        else:
            unavailable_count += 1
            logger.warning("  [FAIL] YOLOv11 backend not available (ultralytics may not be installed or model failed to load)")
        
        # YOLOv8 (optional - fallback)
        logger.info("Checking YOLOv8 backend...")
        yolov8 = YOLOv8Backend()
        if yolov8.is_available():
            self.backends["yolov8"] = yolov8
            available_count += 1
            logger.info("  [OK] YOLOv8 backend registered and available")
        else:
            unavailable_count += 1
            logger.warning("  [FAIL] YOLOv8 backend not available")
        
        # CLIP (optional)
        logger.info("Checking CLIP backend...")
        clip = CLIPBackend()
        if clip.is_available():
            self.backends["clip"] = clip
            available_count += 1
            logger.info("  [OK] CLIP backend registered and available")
        else:
            unavailable_count += 1
            logger.warning("  [FAIL] CLIP backend not available (transformers/torch may not be installed)")
        
        # ViT (Vision Transformer)
        logger.info("Checking ViT backend...")
        vit = ViTBackend()
        if vit.is_available():
            self.backends["vit"] = vit
            available_count += 1
            logger.info("  [OK] ViT backend registered and available")
        else:
            unavailable_count += 1
            logger.warning("  [FAIL] ViT backend not available")
        
        # Ensemble (if multiple backends available)
        if len(self.backends) > 1:
            ensemble = EnsembleBackend(list(self.backends.values()))
            self.backends["ensemble"] = ensemble
            available_count += 1
            logger.info(f"  [OK] Ensemble backend registered (combining {len(self.backends) - 1} models)")
        else:
            logger.warning("  [FAIL] Ensemble backend not available (need at least 2 backends)")
        
        logger.info("-" * 60)
        logger.info(f"Backend Summary: {available_count} available, {unavailable_count} unavailable")
        logger.info(f"Available backends: {', '.join(self.backends.keys())}")
        
        # Set default based on config, but validate it's available
        # If configured backend is available, use it; otherwise fall back to auto-detection
        logger.info("-" * 60)
        logger.info("Selecting default backend...")
        if self.default_backend in self.backends:
            logger.info(f"  [OK] Using configured backend: '{self.default_backend}' (available)")
            logger.info(f"    Backend name: {self.backends[self.default_backend].get_name()}")
        else:
            logger.warning(f"  ✗ Configured backend '{self.default_backend}' not available")
            logger.info("  → Falling back to auto-detection...")
            # Fall back to auto-detection (prefer YOLOv11)
            if "yolov11" in self.backends:
                self.default_backend = "yolov11"
                logger.info("  [OK] YOLOv11 selected as default (BEST CHOICE)")
            elif "yolov8" in self.backends:
                self.default_backend = "yolov8"
                logger.info("  [OK] YOLOv8 selected as default")
            elif "ensemble" in self.backends:
                self.default_backend = "ensemble"
                logger.info("  [OK] Ensemble selected as default")
            elif "speciesnet" in self.backends:
                self.default_backend = "speciesnet"
                logger.info("  [OK] SpeciesNet selected as default")
            else:
                logger.error(f"  [FAIL] No backends available! Configured: '{self.default_backend}'")
        
        logger.info("=" * 60)
        logger.info(f"AI Backend Manager initialized - Default: {self.default_backend}")
        logger.info("=" * 60)
    
    def get_backend(self, name: Optional[str] = None) -> Optional[AIBackend]:
        """Get backend by name, or default if not specified"""
        if name is None:
            name = self.default_backend
        
        return self.backends.get(name)
    
    def list_backends(self) -> List[Dict[str, Any]]:
        """List all available backends"""
        return [
            {
                "name": name,
                "display_name": backend.get_name(),
                "available": backend.is_available()
            }
            for name, backend in self.backends.items()
        ]
    
    def compare_models(self, image_path: str) -> Dict[str, Any]:
        """Run all available backends on a single image for comparison"""
        results = {}
        
        # Run individual models
        for name, backend in self.backends.items():
            if name == "ensemble": 
                continue # Skip ensemble in the raw list, we'll run it separately or let the user deduce
            
            start_time = time.time()
            try:
                pred = backend.predict(image_path)
                duration = time.time() - start_time
                results[name] = {
                    "name": backend.get_name(),
                    "predictions": pred.get("predictions", []),
                    "confidence": pred.get("confidence", 0),
                    "inference_time_ms": round(duration * 1000, 2), # ms
                    "error": pred.get("error")
                }
            except Exception as e:
                results[name] = {"error": str(e), "name": backend.get_name()}
        
        # Also run ensemble explicitly if available
        if "ensemble" in self.backends:
            start_time = time.time()
            try:
                pred = self.backends["ensemble"].predict(image_path)
                duration = time.time() - start_time
                results["ensemble"] = {
                    "name": self.backends["ensemble"].get_name(),
                    "predictions": pred.get("predictions", []),
                    "confidence": pred.get("confidence", 0),
                    "inference_time_ms": round(duration * 1000, 2),
                    "models_used": pred.get("models_used", [])
                }
            except Exception as e:
                results["ensemble"] = {"error": str(e), "name": "Ensemble"}
                
        return results

    def predict(self, image_path: str, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Predict using specified backend or default with detailed logging and metrics"""
        backend_to_use = backend_name or self.default_backend
        logger.debug(f"Predicting with backend: '{backend_to_use}' (requested: {backend_name}, default: {self.default_backend})")
        
        backend = self.get_backend(backend_name)
        if not backend:
            logger.warning(f"Backend '{backend_to_use}' not available. Available backends: {list(self.backends.keys())}")
            # Record failed prediction
            try:
                from .ai_metrics import ai_metrics_tracker
                ai_metrics_tracker.record_prediction(
                    backend_name=backend_to_use,
                    inference_time=0.0,
                    success=False,
                    error=f"Backend not available"
                )
            except ImportError:
                pass
            
            return {
                "predictions": [],
                "error": f"Backend '{backend_to_use}' not available"
            }
        
        logger.debug(f"Using backend: {backend.get_name()}")
        start_time = time.time()
        
        try:
            result = backend.predict(image_path)
            duration = time.time() - start_time
            
            # Record metrics
            try:
                from .ai_metrics import ai_metrics_tracker
                success = "error" not in result
                confidence = result.get("confidence", 0.0) if success else None
                error = result.get("error") if not success else None
                
                ai_metrics_tracker.record_prediction(
                    backend_name=backend_to_use,
                    inference_time=duration,
                    success=success,
                    confidence=confidence,
                    error=error
                )
            except ImportError:
                pass
            
            # Log performance
            if "error" not in result:
                confidence = result.get("confidence", 0.0)
                num_predictions = len(result.get("predictions", []))
                logger.debug(f"Prediction completed in {duration*1000:.2f}ms - Confidence: {confidence:.2f}, Predictions: {num_predictions}")
            else:
                logger.warning(f"Prediction failed after {duration*1000:.2f}ms - Error: {result.get('error')}")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Prediction exception after {duration*1000:.2f}ms: {e}")
            
            # Record failed prediction
            try:
                from .ai_metrics import ai_metrics_tracker
                ai_metrics_tracker.record_prediction(
                    backend_name=backend_to_use,
                    inference_time=duration,
                    success=False,
                    error=str(e)
                )
            except ImportError:
                pass
            
            return {
                "predictions": [],
                "error": str(e)
            }


# Global manager instance
ai_backend_manager = AIBackendManager()

