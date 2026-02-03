"""Animal sound detection service using audio classification models"""
import logging
import os
from typing import Dict, Any, Optional, List
import numpy as np

logger = logging.getLogger(__name__)

# Try to import audio processing libraries
try:
    import librosa
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    logger.warning("librosa not available - audio processing will be disabled")

try:
    import torch
    from transformers import (
        Wav2Vec2Processor, 
        Wav2Vec2ForSequenceClassification,
        AutoProcessor,
        AutoModelForAudioClassification
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available - audio classification models will be disabled")


class SoundDetectionService:
    """Service for detecting and classifying animal sounds from audio files"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize sound detection service with optional model name
        
        Args:
            model_name: Hugging Face model identifier. If None, uses default model.
                       Options:
                       - "MIT/ast-finetuned-audioset-10-10-0.4593" (AudioSet fine-tuned)
                       - "facebook/wav2vec2-base-960h" (Wav2Vec2 base)
                       - "facebook/wav2vec2-large-960h-lv60-self" (Wav2Vec2 large)
                       - Or any other audio classification model from Hugging Face
        """
        self.model = None
        self.processor = None
        self.model_name = model_name or os.getenv("AUDIO_MODEL_NAME", "MIT/ast-finetuned-audioset-10-10-0.4593")
        self.available = False
        self.device = "cuda" if TRANSFORMERS_AVAILABLE and torch.cuda.is_available() else "cpu"
        self.use_advanced_model = False
        self._try_load_model()
    
    def _try_load_model(self):
        """Try to load audio classification model from Hugging Face"""
        if not TRANSFORMERS_AVAILABLE:
            logger.info("Transformers not available - using basic audio feature classification")
            self.available = AUDIO_PROCESSING_AVAILABLE
            return
        
        try:
            logger.info(f"Loading audio classification model: {self.model_name}...")
            
            # Try to load as AutoModel first (works with most audio classification models)
            try:
                self.processor = AutoProcessor.from_pretrained(self.model_name)
                self.model = AutoModelForAudioClassification.from_pretrained(self.model_name)
                self.model.to(self.device)
                self.model.eval()  # Set to evaluation mode
                self.use_advanced_model = True
                logger.info(f"Loaded advanced audio classification model: {self.model_name} on {self.device}")
            except Exception as e1:
                logger.warning(f"Failed to load AutoModel, trying Wav2Vec2: {e1}")
                # Fallback to Wav2Vec2 if AutoModel fails
                try:
                    if "wav2vec2" in self.model_name.lower():
                        self.processor = Wav2Vec2Processor.from_pretrained(self.model_name)
                        # For Wav2Vec2, we'd need a fine-tuned model for classification
                        # For now, we'll use it for feature extraction
                        self.model = None
                        self.use_advanced_model = False
                        logger.info(f"Loaded Wav2Vec2 processor: {self.model_name} (using for feature extraction)")
                    else:
                        raise e1
                except Exception as e2:
                    logger.warning(f"Failed to load model {self.model_name}: {e2}")
                    logger.info("Falling back to basic audio feature classification")
                    self.model = None
                    self.processor = None
                    self.use_advanced_model = False
            
            self.available = AUDIO_PROCESSING_AVAILABLE
            logger.info(f"Sound detection service initialized (advanced model: {self.use_advanced_model})")
        except Exception as e:
            logger.warning(f"Failed to load audio model: {e}")
            logger.info("Using basic audio feature classification as fallback")
            self.model = None
            self.processor = None
            self.use_advanced_model = False
            self.available = AUDIO_PROCESSING_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if sound detection is available"""
        return self.available and AUDIO_PROCESSING_AVAILABLE
    
    def is_advanced_model_available(self) -> bool:
        """Check if advanced model-based classification is available"""
        return self.use_advanced_model and self.model is not None and self.processor is not None
    
    def detect_sounds(
        self,
        audio_path: str,
        species_labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Detect and classify animal sounds in audio file
        
        Args:
            audio_path: Path to audio file
            species_labels: Optional list of expected species/animal sounds
        
        Returns:
            Dictionary with detected sounds and confidence scores
        """
        if not self.is_available():
            return {
                "sounds": [],
                "error": "Sound detection not available (librosa or transformers not installed)"
            }
        
        if not os.path.exists(audio_path):
            return {
                "sounds": [],
                "error": f"Audio file not found: {audio_path}"
            }
        
        try:
            # Load audio file
            if not AUDIO_PROCESSING_AVAILABLE:
                return {
                    "sounds": [],
                    "error": "librosa not available for audio processing"
                }
            
            import librosa
            audio_data, sample_rate = librosa.load(audio_path, sr=16000)  # Resample to 16kHz
            duration = len(audio_data) / sample_rate
            
            # Try advanced model classification first
            if self.is_advanced_model_available():
                detected_sounds = self._classify_sounds_advanced(audio_data, sample_rate)
                if detected_sounds:
                    return {
                        "sounds": detected_sounds,
                        "duration": duration,
                        "sample_rate": sample_rate,
                        "model_used": self.model_name
                    }
                # If advanced model doesn't return results, fall back to basic
            
            # Fallback to basic sound classification using audio features
            detected_sounds = self._classify_sounds_basic(audio_data, sample_rate, duration)
            
            return {
                "sounds": detected_sounds,
                "duration": duration,
                "sample_rate": sample_rate,
                "model_used": "basic_features" if not self.use_advanced_model else self.model_name
            }
        except Exception as e:
            logger.error(f"Error detecting sounds in {audio_path}: {e}")
            return {
                "sounds": [],
                "error": str(e)
            }
    
    def _classify_sounds_advanced(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> List[Dict[str, Any]]:
        """Advanced sound classification using pre-trained model"""
        if not self.is_advanced_model_available():
            return []
        
        try:
            import torch
            import librosa
            
            # Prepare audio for model (different models may need different formats)
            # For AudioSet AST models, we need mel spectrogram
            if "ast" in self.model_name.lower() or "audioset" in self.model_name.lower():
                # Convert to mel spectrogram
                mel_spec = librosa.feature.melspectrogram(
                    y=audio_data, 
                    sr=sample_rate,
                    n_mels=128,
                    fmax=8000
                )
                mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
                
                # Normalize to [-1, 1] range
                mel_spec_db = (mel_spec_db + 80) / 80  # AudioSet normalization
                
                # Add channel dimension and batch dimension: (1, 1, 128, T)
                if len(mel_spec_db.shape) == 2:
                    mel_spec_db = mel_spec_db[np.newaxis, np.newaxis, :, :]
                
                # Ensure tensor shape matches model expectations
                if mel_spec_db.shape[-1] < 1024:  # Pad if too short
                    padding = 1024 - mel_spec_db.shape[-1]
                    mel_spec_db = np.pad(mel_spec_db, ((0, 0), (0, 0), (0, 0), (0, padding)), mode='constant')
                
                # Truncate if too long (AudioSet models typically expect fixed length)
                max_length = 1024
                if mel_spec_db.shape[-1] > max_length:
                    mel_spec_db = mel_spec_db[:, :, :, :max_length]
                
                inputs = torch.from_numpy(mel_spec_db).float().to(self.device)
                
            else:
                # For Wav2Vec2 or other raw audio models
                # Ensure audio is the right length
                target_length = 16000  # 1 second at 16kHz
                if len(audio_data) < target_length:
                    audio_data = np.pad(audio_data, (0, target_length - len(audio_data)), mode='constant')
                elif len(audio_data) > target_length:
                    audio_data = audio_data[:target_length]
                
                inputs = self.processor(audio_data, sampling_rate=sample_rate, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits if hasattr(outputs, 'logits') else outputs
            
            # Get predictions
            probs = torch.nn.functional.softmax(logits, dim=-1)
            top_probs, top_indices = torch.topk(probs, k=min(5, probs.shape[-1]))
            
            # Map indices to class labels
            detected_sounds = []
            id2label = getattr(self.model.config, 'id2label', {}) if hasattr(self.model, 'config') else {}
            
            for prob, idx in zip(top_probs[0], top_indices[0]):
                prob_float = float(prob.item())
                idx_int = int(idx.item())
                
                # Get label name
                if id2label and idx_int in id2label:
                    label = id2label[idx_int]
                else:
                    label = f"class_{idx_int}"
                
                # Filter out very low confidence predictions
                if prob_float < 0.1:
                    continue
                
                # Map AudioSet labels to wildlife-relevant categories
                sound_class = self._map_audioset_to_wildlife(label)
                
                detected_sounds.append({
                    "sound_class": sound_class,
                    "confidence": prob_float,
                    "raw_label": label,
                    "description": f"Detected: {label}"
                })
            
            # If model didn't return useful results, return empty list to fall back to basic
            if not detected_sounds or max(s.get("confidence", 0) for s in detected_sounds) < 0.3:
                return []
            
            return detected_sounds
            
        except Exception as e:
            logger.warning(f"Advanced model classification failed: {e}, falling back to basic classification")
            return []
    
    def _map_audioset_to_wildlife(self, label: str) -> str:
        """Map AudioSet labels to wildlife-relevant sound classes"""
        label_lower = label.lower()
        
        # Bird sounds
        if any(word in label_lower for word in ['bird', 'chirp', 'tweet', 'singing', 'songbird']):
            return "bird_like"
        
        # Mammal sounds
        if any(word in label_lower for word in ['dog', 'bark', 'howl', 'cat', 'meow', 'animal', 'mammal']):
            return "mammal_like"
        
        # Nature/wildlife sounds
        if any(word in label_lower for word in ['nature', 'wildlife', 'outdoor', 'animal']):
            return "wildlife"
        
        # Insect sounds
        if any(word in label_lower for word in ['insect', 'bee', 'buzz', 'cricket', 'cicada']):
            return "insect_like"
        
        # Water/rain sounds (often associated with wildlife activity)
        if any(word in label_lower for word in ['water', 'rain', 'stream', 'pond']):
            return "water_related"
        
        # Vehicle/noise
        if any(word in label_lower for word in ['vehicle', 'car', 'truck', 'engine', 'motor']):
            return "vehicle"
        
        # Human sounds
        if any(word in label_lower for word in ['speech', 'voice', 'human', 'talking', 'conversation']):
            return "human_speech"
        
        # Return as-is for unknown but valid classifications
        return "unknown_sound"
    
    def _classify_sounds_basic(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int, 
        duration: float
    ) -> List[Dict[str, Any]]:
        """Basic sound classification using audio features and heuristics"""
        if not AUDIO_PROCESSING_AVAILABLE:
            return []
        
        try:
            import librosa
            
            sounds = []
            
            # Calculate RMS energy (loudness)
            rms = librosa.feature.rms(y=audio_data)[0]
            avg_rms = float(np.mean(rms))
            max_rms = float(np.max(rms))
            
            # Calculate zero crossing rate (indicates speech-like or noise)
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            avg_zcr = float(np.mean(zcr))
            
            # Calculate spectral centroid (brightness/pitch)
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
            avg_centroid = float(np.mean(spectral_centroids))
            
            # Calculate spectral rolloff (high frequency content)
            rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)[0]
            avg_rolloff = float(np.mean(rolloff))
            
            # Detect silence or very quiet audio
            if avg_rms < 0.01:
                sounds.append({
                    "sound_class": "silence",
                    "confidence": 0.95,
                    "description": "Very quiet or silent audio"
                })
                return sounds
            
            # Detect noise/hissing (high ZCR, low RMS)
            if avg_zcr > 0.1 and avg_rms < 0.05:
                sounds.append({
                    "sound_class": "noise",
                    "confidence": 0.7,
                    "description": "Background noise or static"
                })
            
            # Detect animal-like sounds using heuristics
            # Birds typically have high frequency content and varying pitch
            if avg_centroid > 2000 and avg_rolloff > 4000:
                confidence = min(0.85, 0.5 + (avg_centroid / 10000))
                sounds.append({
                    "sound_class": "bird_like",
                    "confidence": float(confidence),
                    "description": "High-frequency sound possibly from birds or small animals"
                })
            
            # Detect low-frequency sounds (mammals, vehicles)
            if avg_centroid < 1000 and avg_rms > 0.03:
                confidence = min(0.80, 0.5 + (avg_rms * 10))
                sounds.append({
                    "sound_class": "low_frequency",
                    "confidence": float(confidence),
                    "description": "Low-frequency sound possibly from large mammals or vehicles"
                })
            
            # Detect human speech-like sounds (moderate ZCR, mid-range frequency)
            if 0.05 < avg_zcr < 0.15 and 1000 < avg_centroid < 3000:
                confidence = 0.75
                sounds.append({
                    "sound_class": "speech_like",
                    "confidence": confidence,
                    "description": "Human speech-like sound"
                })
            
            # If no specific classification, mark as unknown sound
            if not sounds and avg_rms > 0.02:
                sounds.append({
                    "sound_class": "unknown_sound",
                    "confidence": 0.5,
                    "description": "Detected sound activity but unable to classify"
                })
            
            # Sort by confidence (highest first)
            sounds.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            
            return sounds
            
        except Exception as e:
            logger.error(f"Error in basic sound classification: {e}")
            # Return a basic detection if classification fails
            return [{
                "sound_class": "unknown_sound",
                "confidence": 0.3,
                "description": f"Sound detected but classification failed: {str(e)}"
            }]
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not AUDIO_PROCESSING_AVAILABLE:
            return []
        return ['.wav', '.mp3', '.flac', '.ogg', '.m4a']
    
    def validate_audio_file(self, audio_path: str) -> tuple[bool, Optional[str]]:
        """Validate audio file format and accessibility"""
        if not os.path.exists(audio_path):
            return False, "File not found"
        
        if not AUDIO_PROCESSING_AVAILABLE:
            return False, "librosa not available"
        
        # Check file extension
        ext = os.path.splitext(audio_path)[1].lower()
        supported = self.get_supported_formats()
        if ext not in supported:
            return False, f"Unsupported format. Supported: {', '.join(supported)}"
        
        return True, None


# Global instance
sound_detection_service = SoundDetectionService()

