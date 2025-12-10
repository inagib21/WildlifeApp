"""Smart detection processing with enhanced AI logic"""
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SmartDetectionProcessor:
    """Enhanced detection processor with intelligent filtering and validation"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        # Confidence thresholds
        self.high_confidence_threshold = 0.7
        self.medium_confidence_threshold = 0.5
        self.low_confidence_threshold = 0.3
        # Minimum confidence to save detection (lowered to ensure more detections are saved)
        self.min_confidence_to_save = 0.15
        
        # Species name normalization rules
        self.species_aliases = {
            "human": ["person", "people", "human being"],
            "vehicle": ["car", "truck", "automobile", "motor vehicle"],
            "deer": ["white-tailed deer", "whitetail", "deer"],
            "raccoon": ["raccoon", "raccoon"],
            "squirrel": ["squirrel", "tree squirrel"],
            "bird": ["bird", "avian"],
            "cat": ["domestic cat", "house cat", "cat"],
            "dog": ["domestic dog", "dog", "canine"],
        }
        
        # Common false positives to filter
        self.false_positive_patterns = [
            "empty",
            "no detection",
            "background",
            "vegetation only",
            "motion only",
        ]
    
    def normalize_species_name(self, species: str) -> str:
        """Normalize species name to standard format"""
        if not species or species == "Unknown":
            return "Unknown"
        
        species_lower = species.lower().strip()
        
        # Check for false positives
        for pattern in self.false_positive_patterns:
            if pattern in species_lower:
                return "Unknown"
        
        # Check aliases
        for standard_name, aliases in self.species_aliases.items():
            if species_lower in aliases or species_lower == standard_name:
                return standard_name.title()
        
        # Handle taxonomy format (e.g., "Animalia;Chordata;Mammalia;Human")
        if ";" in species:
            parts = [p.strip() for p in species.split(";")]
            # Use the most specific (last) part, or second-to-last if it's more descriptive
            if len(parts) >= 2:
                # Prefer the species name (usually last or second-to-last)
                species_name = parts[-1] if len(parts[-1]) > 3 else parts[-2]
                return species_name.title()
            else:
                return parts[-1].title()
        
        # Capitalize first letter of each word
        return species.title()
    
    def analyze_predictions(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze SpeciesNet predictions and extract smart insights"""
        if "error" in predictions:
            return {
                "error": predictions["error"],
                "confidence": 0.0,
                "species": "Unknown",
                "quality": "error"
            }
        
        if not predictions.get("predictions"):
            # If no predictions, still return a valid analysis structure
            # but mark it as low confidence so it can be saved if needed
            logger.warning("No predictions returned from SpeciesNet, using fallback")
            return {
                "species": "Unknown",
                "confidence": 0.1,  # Very low but above absolute zero
                "quality": "no_predictions",
                "should_save": False,  # Will be overridden by fallback in webhook if needed
                "should_notify": False,
                "all_predictions": [],
                "error": "No predictions returned"
            }
        
        preds = predictions["predictions"]
        
        # Get top prediction
        top_pred = preds[0] if preds else {}
        top_species = self.normalize_species_name(top_pred.get("prediction", "Unknown"))
        top_confidence = float(top_pred.get("prediction_score", 0.0))
        
        # Get second prediction for comparison
        second_pred = preds[1] if len(preds) > 1 else {}
        second_species = self.normalize_species_name(second_pred.get("prediction", "Unknown"))
        second_confidence = float(second_pred.get("prediction_score", 0.0))
        
        # Calculate confidence gap (larger gap = more confident)
        confidence_gap = top_confidence - second_confidence if second_confidence > 0 else top_confidence
        
        # Determine prediction quality
        quality = self._assess_quality(top_confidence, confidence_gap, top_species)
        
        # Check if we should use ensemble (multiple predictions)
        use_ensemble = self._should_use_ensemble(preds, top_confidence, confidence_gap)
        
        # Final species determination
        if use_ensemble and len(preds) >= 2:
            # Use weighted average of top 2 if they're similar
            if top_species == second_species or confidence_gap < 0.15:
                # Combine similar predictions
                combined_confidence = (top_confidence * 0.7) + (second_confidence * 0.3)
                final_species = top_species
            else:
                # Use top prediction if gap is significant
                final_species = top_species
                combined_confidence = top_confidence
        else:
            final_species = top_species
            combined_confidence = top_confidence
        
        # Apply confidence boost based on quality
        if quality == "high":
            combined_confidence = min(1.0, combined_confidence * 1.05)  # 5% boost
        elif quality == "low":
            combined_confidence = combined_confidence * 0.95  # 5% penalty
        
        return {
            "species": final_species,
            "confidence": round(combined_confidence, 4),
            "quality": quality,
            "top_prediction": {
                "species": top_species,
                "confidence": top_confidence
            },
            "second_prediction": {
                "species": second_species,
                "confidence": second_confidence
            } if second_confidence > 0 else None,
            "confidence_gap": round(confidence_gap, 4),
            "all_predictions": [
                {
                    "species": self.normalize_species_name(p.get("prediction", "Unknown")),
                    "confidence": float(p.get("prediction_score", 0.0))
                }
                for p in preds[:5]  # Top 5 predictions
            ],
            "should_save": combined_confidence >= self.min_confidence_to_save,
            "should_notify": combined_confidence >= self.high_confidence_threshold
        }
    
    def _assess_quality(self, confidence: float, gap: float, species: str) -> str:
        """Assess the quality of a prediction"""
        # High quality: high confidence with good gap
        if confidence >= self.high_confidence_threshold and gap >= 0.2:
            return "high"
        
        # Medium quality: decent confidence
        if confidence >= self.medium_confidence_threshold:
            return "medium"
        
        # Low quality: low confidence or small gap
        if confidence < self.medium_confidence_threshold or gap < 0.1:
            return "low"
        
        return "medium"
    
    def _should_use_ensemble(self, preds: List[Dict], top_confidence: float, gap: float) -> bool:
        """Determine if ensemble prediction should be used"""
        # Use ensemble if:
        # 1. Top confidence is medium (0.5-0.7) and gap is small (< 0.15)
        # 2. Multiple predictions are similar
        if self.medium_confidence_threshold <= top_confidence < self.high_confidence_threshold:
            if gap < 0.15 and len(preds) >= 2:
                return True
        return False
    
    def get_temporal_context(self, camera_id: int, timestamp: datetime) -> Dict[str, Any]:
        """Get temporal context from recent detections for this camera"""
        if not self.db:
            return {}
        
        try:
            from database import Detection
            
            # Get detections from last hour
            one_hour_ago = timestamp - timedelta(hours=1)
            recent_detections = self.db.query(Detection).filter(
                Detection.camera_id == camera_id,
                Detection.timestamp >= one_hour_ago,
                Detection.timestamp <= timestamp
            ).order_by(Detection.timestamp.desc()).limit(10).all()
            
            if not recent_detections:
                return {}
            
            # Analyze recent species
            species_counts = {}
            total_confidence = 0.0
            for det in recent_detections:
                if det.species and det.species != "Unknown":
                    species_counts[det.species] = species_counts.get(det.species, 0) + 1
                if det.confidence:
                    total_confidence += det.confidence
            
            avg_confidence = total_confidence / len(recent_detections) if recent_detections else 0.0
            most_common_species = max(species_counts.items(), key=lambda x: x[1])[0] if species_counts else None
            
            return {
                "recent_count": len(recent_detections),
                "most_common_species": most_common_species,
                "species_counts": species_counts,
                "average_confidence": round(avg_confidence, 3)
            }
        except Exception as e:
            logger.warning(f"Error getting temporal context: {e}")
            return {}
    
    def apply_temporal_boost(self, analysis: Dict[str, Any], temporal_context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply temporal context to boost confidence if species matches recent detections"""
        if not temporal_context or not temporal_context.get("most_common_species"):
            return analysis
        
        current_species = analysis["species"]
        most_common = temporal_context["most_common_species"]
        
        # If current species matches recent pattern, boost confidence slightly
        if current_species == most_common and analysis["confidence"] >= self.medium_confidence_threshold:
            # Boost by up to 10% based on how common it is
            boost_factor = min(1.10, 1.0 + (temporal_context["species_counts"].get(current_species, 0) * 0.02))
            analysis["confidence"] = min(1.0, analysis["confidence"] * boost_factor)
            analysis["temporal_boost_applied"] = True
            analysis["boost_reason"] = f"Matches recent pattern ({temporal_context['species_counts'].get(current_species, 0)} detections in last hour)"
        else:
            analysis["temporal_boost_applied"] = False
        
        return analysis
    
    def process_detection(
        self,
        predictions: Dict[str, Any],
        camera_id: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Process a detection with smart analysis"""
        # Analyze predictions
        analysis = self.analyze_predictions(predictions)
        
        # Apply temporal context if available
        if camera_id and timestamp and self.db:
            temporal_context = self.get_temporal_context(camera_id, timestamp)
            if temporal_context:
                analysis = self.apply_temporal_boost(analysis, temporal_context)
                analysis["temporal_context"] = temporal_context
        
        return analysis
    
    def should_save_detection(self, analysis: Dict[str, Any]) -> bool:
        """Determine if detection should be saved to database"""
        if "error" in analysis:
            logger.debug("Not saving detection: error in analysis")
            return False  # Don't save errors
        
        # Check minimum confidence threshold
        confidence = analysis.get("confidence", 0.0)
        species = analysis.get("species", "Unknown")
        
        # Always save if confidence meets minimum threshold
        if confidence >= self.min_confidence_to_save:
            # Only filter out Unknown species if confidence is very low (< 0.2)
            if species == "Unknown" and confidence < 0.2:
                logger.debug(f"Not saving detection: Unknown species with very low confidence ({confidence:.3f})")
                return False
            logger.debug(f"Saving detection: {species} with confidence {confidence:.3f}")
            return True
        
        logger.debug(f"Not saving detection: confidence {confidence:.3f} below minimum {self.min_confidence_to_save}")
        return False
    
    def get_detection_data(self, analysis: Dict[str, Any], image_path: str, camera_id: int, timestamp: datetime) -> Dict[str, Any]:
        """Get detection data dictionary for database insertion"""
        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "species": analysis["species"],
            "confidence": analysis["confidence"],
            "image_path": image_path,
            "detections_json": json.dumps({
                "predictions": analysis.get("all_predictions", []),
                "quality": analysis.get("quality"),
                "confidence_gap": analysis.get("confidence_gap"),
                "temporal_context": analysis.get("temporal_context"),
                "temporal_boost_applied": analysis.get("temporal_boost_applied", False)
            }),
            "prediction_score": analysis["confidence"]
        }

