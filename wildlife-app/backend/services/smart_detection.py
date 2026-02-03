"""
Smart detection processing with enhanced AI logic
"""
# pylint: disable=no-member, import-error, import-outside-toplevel, too-many-instance-attributes
# pylint: disable=broad-exception-caught, logging-fstring-interpolation

import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Image processing imports
try:
    import cv2
    import numpy as np
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False
    logger.warning(
        "Image processing libraries not available - some features will be disabled")


class SmartDetectionProcessor:
    """
    Smart detection processing with enhanced AI logic
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        # Confidence thresholds
        self.high_confidence_threshold = 0.7
        self.medium_confidence_threshold = 0.5
        self.low_confidence_threshold = 0.3
        # Minimum confidence to save detection (lowered further to capture more wildlife)
        # Even low confidence detections can be valuable for tracking activity
        self.min_confidence_to_save = 0.10

        # Non-living things classification (things to deprioritize)
        self.non_living_things = {
            "vehicle", "car", "truck", "automobile", "motor vehicle",
            "motorcycle", "bike", "bicycle",
            "building", "house", "structure", "wall", "fence", "gate", "door", "window",
            "object", "box", "container", "bag", "package",
            "sign", "post", "pole", "light", "lamp", "streetlight",
            "road", "pavement", "asphalt", "sidewalk", "path",
            "rock", "stone", "boulder", "log", "branch", "stick",
            "unknown", "other"
        }

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

        # Species-specific confidence thresholds (lower threshold = more
        # sensitive)
        self.species_thresholds = {
            "deer": 0.15,      # Common wildlife - lower threshold
            "raccoon": 0.15,
            "squirrel": 0.15,
            "bird": 0.20,      # Birds can be smaller/harder to detect
            "cat": 0.25,       # Domestic animals - slightly higher threshold
            "dog": 0.25,
            "human": 0.30,      # Humans - higher threshold to reduce false positives
            "vehicle": 0.30,    # Vehicles - higher threshold
        }

        # Time-of-day activity patterns (hour -> species activity multiplier)
        # Values > 1.0 = more active, < 1.0 = less active
        self.time_patterns = {
            "deer": {  # Most active at dawn/dusk
                **{h: 0.5 for h in range(10, 18)},  # Daytime: less active
                # Dawn/dusk: more active
                **{h: 1.2 for h in [5, 6, 7, 18, 19, 20]},
                # Night: moderate
                **{h: 0.8 for h in list(range(21, 24)) + list(range(0, 5))},
            },
            "raccoon": {  # Nocturnal
                **{h: 0.3 for h in range(8, 18)},  # Daytime: less active
                # Night: very active
                **{h: 1.3 for h in list(range(20, 24)) + list(range(0, 6))},
            },
            "bird": {  # Diurnal
                **{h: 1.2 for h in range(6, 10)},  # Morning: very active
                **{h: 0.9 for h in range(10, 18)},  # Daytime: active
                # Night: inactive
                **{h: 0.3 for h in list(range(18, 24)) + list(range(0, 6))},
            },
        }

        # Image quality thresholds
        self.min_blur_threshold = 100.0  # Laplacian variance - lower = more blurry
        self.min_brightness = 20  # Minimum average brightness (0-255)
        self.max_brightness = 240  # Maximum average brightness (0-255)
        # Minimum contrast (standard deviation of brightness)
        self.min_contrast = 10

        # Duplicate detection settings
        self.duplicate_time_window = timedelta(minutes=2)  # Within 2 minutes
        self.duplicate_similarity_threshold = 0.95  # 95% similar = duplicate

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
            # Use the most specific (last) part, or second-to-last if it's more
            # descriptive
            if len(parts) >= 2:
                # Prefer the species name (usually last or second-to-last)
                species_name = parts[-1] if len(parts[-1]) > 3 else parts[-2]
                return species_name.title()
            return parts[-1].title()

        # Capitalize first letter of each word
        return species.title()

    def is_living_thing(self, species: str) -> bool:
        """Check if a species is a living thing (not a vehicle, building, etc.)"""
        if not species:
            return False

        species_lower = species.lower().strip()

        # Check if it's in our non-living list
        if species_lower in self.non_living_things:
            return False

        # Check if it contains non-living keywords
        for non_living in self.non_living_things:
            if non_living in species_lower:
                return False

        # Check alias mappings - vehicles are non-living
        if species_lower in ["vehicle", "car", "truck", "automobile"]:
            return False

        # Default to living thing (animals, plants, etc.)
        return True

    def apply_living_priority(
            self,
            predictions: List[Dict[str, Any]],
            boost_factor: float = 0.15) -> List[Dict[str, Any]]:
        """
        Apply priority boost to living things over non-living things

        Args:
            predictions: List of prediction dicts with 'prediction' and 'prediction_score'
            boost_factor: Confidence boost multiplier for living things (default 0.15 = 15% boost)

        Returns:
            Re-sorted list with living things prioritized
        """
        try:
            # Get setting if available
            if self.db:
                try:
                    # Import here to avoid circular dependency
                    # When running from backend root (python main.py), routers
                    # is a top-level package or subpackage
                    try:
                        from routers.settings import get_setting
                    except ImportError:
                        # Try relative import if we are in a package
                        from ..routers.settings import get_setting

                    priority_enabled = get_setting(
                        self.db, "priority_living_things", default=True)
                except Exception:
                    priority_enabled = True  # Default to enabled
            else:
                priority_enabled = True  # Default to enabled

            if not priority_enabled:
                return predictions  # Return unchanged if priority disabled

            # Separate living and non-living predictions
            living_preds = []
            non_living_preds = []

            for pred in predictions:
                species = pred.get("prediction", "").strip()
                score = float(pred.get("prediction_score", 0.0))

                if self.is_living_thing(species):
                    # Boost confidence for living things
                    boosted_score = min(1.0, score * (1 + boost_factor))
                    living_preds.append({
                        **pred,
                        "prediction_score": boosted_score,
                        "original_score": score  # Keep original for reference
                    })
                else:
                    # Keep non-living predictions as-is (or slightly reduce)
                    non_living_preds.append(pred)

            # Combine: living things first (sorted by boosted score), then
            # non-living
            living_preds.sort(
                key=lambda x: x["prediction_score"],
                reverse=True)
            non_living_preds.sort(
                key=lambda x: x["prediction_score"],
                reverse=True)

            # Return living things first, then non-living
            return living_preds + non_living_preds

        except Exception as e:
            logger.warning("Error applying living priority: %s", e)
            return predictions  # Return unchanged on error

    def analyze_predictions(
            self, predictions: Dict[str, Any]) -> Dict[str, Any]:
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
                "should_save": False,  # Will be overridden by fallback if needed
                "should_notify": False,
                "all_predictions": [],
                "error": "No predictions returned"
            }

        preds = predictions["predictions"]

        # Apply living things priority rule
        preds = self.apply_living_priority(preds)

        # Get top prediction (now prioritized for living things)
        top_pred = preds[0] if preds else {}
        top_species = self.normalize_species_name(
            top_pred.get("prediction", "Unknown"))
        top_confidence = float(top_pred.get("prediction_score", 0.0))

        # Get original confidence if available (before boost)
        # original_top_confidence = float(top_pred.get("original_score", top_confidence))

        # Get second prediction for comparison
        second_pred = preds[1] if len(preds) > 1 else {}
        second_species = self.normalize_species_name(
            second_pred.get("prediction", "Unknown"))
        second_confidence = float(second_pred.get("prediction_score", 0.0))

        # Calculate confidence gap (larger gap = more confident)
        confidence_gap = top_confidence - \
            second_confidence if second_confidence > 0 else top_confidence

        # Determine prediction quality
        quality = self._assess_quality(
            top_confidence, confidence_gap, top_species)

        # Check if we should use ensemble (multiple predictions)
        use_ensemble = self._should_use_ensemble(
            preds, top_confidence, confidence_gap)

        # Final species determination
        if use_ensemble and len(preds) >= 2:
            # Use weighted average of top 2 if they're similar
            if top_species == second_species or confidence_gap < 0.15:
                # Combine similar predictions
                combined_confidence = (
                    top_confidence * 0.7) + (second_confidence * 0.3)
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
            combined_confidence = min(
                1.0, combined_confidence * 1.05)  # 5% boost
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

    def _assess_quality(self, confidence: float,
                        gap: float, species: str) -> str:
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

    def _should_use_ensemble(
            self, preds: List[Dict], top_confidence: float, gap: float) -> bool:
        """Determine if ensemble prediction should be used"""
        # Use ensemble if:
        # 1. Top confidence is medium (0.5-0.7) and gap is small (< 0.15)
        # 2. Multiple predictions are similar
        if self.medium_confidence_threshold <= top_confidence < self.high_confidence_threshold:
            if gap < 0.15 and len(preds) >= 2:
                return True
        return False

    def get_temporal_context(self, camera_id: int,
                             timestamp: datetime) -> Dict[str, Any]:
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
                    species_counts[det.species] = species_counts.get(
                        det.species, 0) + 1
                if det.confidence:
                    total_confidence += det.confidence

            avg_confidence = total_confidence / \
                len(recent_detections) if recent_detections else 0.0
            most_common_species = max(species_counts.items(), key=lambda x: x[1])[
                0] if species_counts else None

            return {
                "recent_count": len(recent_detections),
                "most_common_species": most_common_species,
                "species_counts": species_counts,
                "average_confidence": round(avg_confidence, 3)
            }
        except Exception as e:
            logger.warning("Error getting temporal context: %s", e)
            if self.db:
                try:
                    self.db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback DB session: {rollback_error}")
            return {}

    def apply_temporal_boost(
            self, analysis: Dict[str, Any], temporal_context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply temporal context to boost confidence if species matches recent detections"""
        if not temporal_context or not temporal_context.get(
                "most_common_species"):
            return analysis

        current_species = analysis["species"]
        most_common = temporal_context["most_common_species"]

        # If current species matches recent pattern, boost confidence slightly
        if (current_species == most_common and
                analysis["confidence"] >= self.medium_confidence_threshold):
            # Boost by up to 10% based on how common it is
            boost_factor = min(
                1.10, 1.0 + (temporal_context["species_counts"].get(current_species, 0) * 0.02))
            analysis["confidence"] = min(
                1.0, analysis["confidence"] * boost_factor)
            analysis["temporal_boost_applied"] = True
            species_count = temporal_context['species_counts'].get(current_species, 0)
            analysis["boost_reason"] = (
                f"Matches recent pattern ({species_count} detections in last hour)")
        else:
            analysis["temporal_boost_applied"] = False

        return analysis

    def analyze_image_quality(self, image_path: str) -> Dict[str, Any]:
        """Analyze image quality (blur, brightness, contrast)"""
        if not IMAGE_PROCESSING_AVAILABLE:
            return {"available": False}

        if not os.path.exists(image_path):
            return {"error": "Image file not found"}

        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                return {"error": "Could not read image"}

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Calculate blur (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            is_blurry = laplacian_var < self.min_blur_threshold

            # Calculate brightness (mean pixel value)
            brightness = np.mean(gray)
            is_too_dark = brightness < self.min_brightness
            is_too_bright = brightness > self.max_brightness

            # Calculate contrast (standard deviation of pixel values)
            contrast = np.std(gray)
            is_low_contrast = contrast < self.min_contrast

            # Overall quality score (0-1, higher is better)
            quality_score = 1.0
            if is_blurry:
                quality_score *= 0.7
            if is_too_dark or is_too_bright:
                quality_score *= 0.8
            if is_low_contrast:
                quality_score *= 0.6

            return {
                "available": True,
                "blur_score": float(round(laplacian_var, 2)),
                "is_blurry": bool(is_blurry),
                "brightness": float(round(brightness, 2)),
                "is_too_dark": bool(is_too_dark),
                "is_too_bright": bool(is_too_bright),
                "contrast": float(round(contrast, 2)),
                "is_low_contrast": bool(is_low_contrast),
                "quality_score": float(round(quality_score, 3)),
                "is_good_quality": bool(quality_score >= 0.7)
            }
        except Exception as e:
            logger.warning("Error analyzing image quality: %s", e)
            return {"error": str(e)}

    def check_duplicate_detection(
        self,
        image_path: str,
        camera_id: int,
        timestamp: datetime,
        species: str
    ) -> Dict[str, Any]:
        """Check if this detection is a duplicate of a recent one"""
        if not self.db:
            return {"is_duplicate": False}

        try:
            from database import Detection

            # Get recent detections from same camera
            time_window_start = timestamp - self.duplicate_time_window
            recent_detections = self.db.query(Detection).filter(
                Detection.camera_id == camera_id,
                Detection.timestamp >= time_window_start,
                Detection.timestamp <= timestamp,
                Detection.species == species
            ).order_by(Detection.timestamp.desc()).limit(5).all()

            if not recent_detections:
                return {"is_duplicate": False, "recent_count": 0}

            # Check image similarity if available
            if IMAGE_PROCESSING_AVAILABLE and os.path.exists(image_path):
                try:
                    current_img = cv2.imread(image_path)
                    if current_img is not None:
                        current_hash = self._calculate_image_hash(current_img)

                        for det in recent_detections:
                            if det.image_path and os.path.exists(
                                    det.image_path):
                                det_img = cv2.imread(det.image_path)
                                if det_img is not None:
                                    det_hash = self._calculate_image_hash(
                                        det_img)
                                    similarity = self._compare_image_hashes(
                                        current_hash, det_hash)

                                    if similarity >= self.duplicate_similarity_threshold:
                                        return {
                                            "is_duplicate": True,
                                            "similarity": similarity,
                                            "duplicate_of": det.id,
                                            "recent_count": len(recent_detections)
                                        }
                except Exception as e:
                    logger.debug("Error comparing images: %s", e)

            # If same species detected multiple times in short window, might be
            # duplicate
            if len(recent_detections) >= 3:
                return {
                    "is_duplicate": False,  # Not confirmed duplicate, but suspicious
                    "suspicious": True,
                    "recent_count": len(recent_detections),
                    "warning": f"Multiple {species} detections in short time window"
                }

            return {"is_duplicate": False,
                    "recent_count": len(recent_detections)}
        except Exception as e:
            logger.warning("Error checking duplicate detection: %s", e)
            if self.db:
                try:
                    self.db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback DB session: {rollback_error}")
            return {"is_duplicate": False, "error": str(e)}

    def _calculate_image_hash(self, img: np.ndarray) -> str:
        """Calculate perceptual hash of image"""
        # Resize to 8x8 for hash calculation
        small = cv2.resize(img, (8, 8))
        gray = cv2.cvtColor(
            small, cv2.COLOR_BGR2GRAY) if len(
            small.shape) == 3 else small
        avg = gray.mean()
        hash_bits = (gray > avg).flatten()
        return ''.join(['1' if bit else '0' for bit in hash_bits])

    def _compare_image_hashes(self, hash1: str, hash2: str) -> float:
        """Compare two image hashes and return similarity (0-1)"""
        if len(hash1) != len(hash2):
            return 0.0
        matches = sum(c1 == c2 for c1, c2 in zip(hash1, hash2))
        return matches / len(hash1)

    def apply_species_threshold(self, species: str,
                                confidence: float) -> float:
        """Apply species-specific confidence threshold"""
        species_lower = species.lower()

        # Check if we have a custom threshold for this species
        for species_key, threshold in self.species_thresholds.items():
            if species_key in species_lower:
                # Boost confidence if it meets species-specific threshold
                if confidence >= threshold:
                    return confidence
                # Reduce confidence if below species threshold
                return confidence * 0.8

        return confidence

    def apply_time_pattern_boost(
            self, species: str, confidence: float, timestamp: datetime) -> float:
        """Apply time-of-day pattern boost/penalty"""
        hour = timestamp.hour
        species_lower = species.lower()

        # Check if we have time patterns for this species
        for species_key, patterns in self.time_patterns.items():
            if species_key in species_lower:
                multiplier = patterns.get(hour, 1.0)
                adjusted_confidence = confidence * multiplier
                return min(1.0, adjusted_confidence)

        return confidence

    def process_detection(
        self,
        predictions: Dict[str, Any],
        camera_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a detection with smart analysis"""
        # Analyze predictions
        analysis = self.analyze_predictions(predictions)

        # Apply image quality analysis if image path provided
        if image_path:
            image_quality = self.analyze_image_quality(image_path)
            analysis["image_quality"] = image_quality

            # Adjust confidence based on image quality
            if image_quality.get("is_good_quality", True):
                # Good quality - slight boost
                analysis["confidence"] = min(
                    1.0, analysis["confidence"] * 1.02)
            elif image_quality.get("quality_score", 1.0) < 0.5:
                # Poor quality - reduce confidence
                analysis["confidence"] = analysis["confidence"] * 0.85
                analysis["quality_warning"] = "Poor image quality detected"

        # Apply species-specific threshold
        species = analysis.get("species", "Unknown")
        if species != "Unknown":
            analysis["confidence"] = self.apply_species_threshold(
                species, analysis["confidence"])

        # Apply time-of-day pattern if timestamp provided
        if timestamp and species != "Unknown":
            original_confidence = analysis["confidence"]
            analysis["confidence"] = self.apply_time_pattern_boost(
                species, analysis["confidence"], timestamp)
            if abs(analysis["confidence"] - original_confidence) > 0.01:
                analysis["time_pattern_applied"] = True

        # Check for duplicate detection
        if camera_id and timestamp and image_path and species != "Unknown":
            duplicate_check = self.check_duplicate_detection(
                image_path, camera_id, timestamp, species)
            analysis["duplicate_check"] = duplicate_check

            if duplicate_check.get("is_duplicate", False):
                # Mark as duplicate - reduce confidence significantly
                analysis["confidence"] = analysis["confidence"] * 0.5
                analysis["should_save"] = False  # Don't save duplicates
                analysis["duplicate_warning"] = (
                    f"Duplicate of detection {duplicate_check.get('duplicate_of')}")
            elif duplicate_check.get("suspicious", False):
                # Suspicious but not confirmed - slight penalty
                analysis["confidence"] = analysis["confidence"] * 0.9
                analysis["suspicious_duplicate"] = True

        # Apply temporal context if available
        if camera_id and timestamp and self.db:
            temporal_context = self.get_temporal_context(camera_id, timestamp)
            if temporal_context:
                analysis = self.apply_temporal_boost(
                    analysis, temporal_context)
                analysis["temporal_context"] = temporal_context

        return analysis

    def should_save_detection(self, analysis: Dict[str, Any]) -> bool:
        """Determine if detection should be saved to database"""
        if "error" in analysis:
            logger.debug("Not saving detection: error in analysis")
            return False  # Don't save errors

        # Check if marked as duplicate
        if analysis.get("duplicate_check", {}).get("is_duplicate", False):
            logger.debug("Not saving detection: duplicate detection")
            return False

        # Check image quality if available
        image_quality = analysis.get("image_quality", {})
        if image_quality.get("available", False):
            if image_quality.get("quality_score", 1.0) < 0.3:
                logger.debug("Not saving detection: very poor image quality (%.3f)", 
                             image_quality.get('quality_score', 0))
                return False

        # Check minimum confidence threshold
        confidence = analysis.get("confidence", 0.0)
        species = analysis.get("species", "Unknown")

        # Apply species-specific minimum threshold
        min_threshold = self.min_confidence_to_save
        if species != "Unknown":
            species_lower = species.lower()
            for species_key, threshold in self.species_thresholds.items():
                if species_key in species_lower:
                    min_threshold = threshold
                    break

        # Always save if confidence meets minimum threshold
        if confidence >= min_threshold:
            # Don't filter out "Blank" detections - they're valid detections that should be saved
            # Only filter out Unknown species if confidence is very low (< 0.2)
            if species == "Unknown" and confidence < 0.2:
                logger.debug(
                    "Not saving detection: Unknown species with very low confidence (%.3f)",
                    confidence)
                return False
            # Save blank detections (they indicate no wildlife was detected,
            # which is useful information)
            logger.debug(
                "Saving detection: %s with confidence %.3f (threshold: %.3f)",
                species, confidence, min_threshold)
            return True

        logger.debug(
            "Not saving detection: confidence %.3f below minimum %.3f",
            confidence, min_threshold)
        return False

    def get_detection_data(
            self,
            analysis: Dict[str, Any],
            image_path: str,
            camera_id: int,
            timestamp: datetime) -> Dict[str, Any]:
        """Get detection data dictionary for database insertion"""
        # Build enhanced metadata
        metadata = {
            "predictions": analysis.get("all_predictions", []),
            "quality": analysis.get("quality"),
            "confidence_gap": analysis.get("confidence_gap"),
            "temporal_context": analysis.get("temporal_context"),
            "temporal_boost_applied": analysis.get("temporal_boost_applied", False)
        }

        # Add image quality info if available
        if "image_quality" in analysis:
            metadata["image_quality"] = analysis["image_quality"]

        # Add duplicate check info if available
        if "duplicate_check" in analysis:
            metadata["duplicate_check"] = analysis["duplicate_check"]

        # Add time pattern info if applied
        if analysis.get("time_pattern_applied", False):
            metadata["time_pattern_applied"] = True

        # Add any warnings
        if "quality_warning" in analysis:
            metadata["quality_warning"] = analysis["quality_warning"]
        if "duplicate_warning" in analysis:
            metadata["duplicate_warning"] = analysis["duplicate_warning"]

        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "species": analysis["species"],
            "confidence": analysis["confidence"],
            "image_path": image_path,
            "detections_json": json.dumps(metadata),
            "prediction_score": analysis["confidence"]
        }
