# Smart Detection System

The Wildlife Detection System now includes an enhanced AI detection processor that makes predictions smarter and more accurate.

## Features

### 1. **Intelligent Species Normalization**
- Normalizes species names from taxonomy format (e.g., "Animalia;Chordata;Mammalia;Human" → "Human")
- Handles common aliases (e.g., "person" → "Human", "car" → "Vehicle")
- Filters out false positives (e.g., "empty", "background", "vegetation only")
- Prefers common names over scientific names when appropriate

### 2. **Multi-Prediction Analysis**
- Analyzes top 5 predictions from SpeciesNet
- Calculates confidence gap between top and second prediction
- Uses ensemble prediction when confidence gap is small (< 0.15)
- Weighted averaging of similar predictions for better accuracy

### 3. **Quality Assessment**
- **High Quality**: Confidence ≥ 0.7 with gap ≥ 0.2 (very confident)
- **Medium Quality**: Confidence ≥ 0.5 (decent confidence)
- **Low Quality**: Confidence < 0.5 or gap < 0.1 (uncertain)
- Applies confidence boost/penalty based on quality

### 4. **Temporal Context Awareness**
- Analyzes recent detections from the same camera (last hour)
- Identifies most common species in recent detections
- Applies temporal boost (up to 10%) if current detection matches recent pattern
- Helps improve accuracy for consistent wildlife patterns

### 5. **Smart Filtering**
- Minimum confidence threshold (0.2) to save detections
- Filters out "Unknown" species with very low confidence (< 0.3)
- Prevents saving obviously incorrect predictions
- Still saves low-confidence detections for review if they meet minimum threshold

### 6. **Enhanced Metadata**
- Stores all top 5 predictions in `detections_json`
- Includes quality assessment, confidence gap, and temporal context
- Provides detailed analysis for debugging and review

## Configuration

The smart detection processor uses these thresholds (configurable in `smart_detection.py`):

```python
high_confidence_threshold = 0.7    # High confidence (notifications sent)
medium_confidence_threshold = 0.5  # Medium confidence
low_confidence_threshold = 0.3     # Low confidence
min_confidence_to_save = 0.2       # Minimum to save detection
```

## Usage

The smart detection processor is automatically used in:
- MotionEye webhook processing (`/api/motioneye/webhook`)
- Manual image processing (`/process-image`)
- Background photo scanning

## Example Analysis Output

```json
{
  "species": "Human",
  "confidence": 0.85,
  "quality": "high",
  "top_prediction": {
    "species": "Human",
    "confidence": 0.82
  },
  "second_prediction": {
    "species": "Vehicle",
    "confidence": 0.15
  },
  "confidence_gap": 0.67,
  "all_predictions": [
    {"species": "Human", "confidence": 0.82},
    {"species": "Vehicle", "confidence": 0.15},
    {"species": "Deer", "confidence": 0.02}
  ],
  "should_save": true,
  "should_notify": true,
  "temporal_context": {
    "recent_count": 5,
    "most_common_species": "Human",
    "species_counts": {"Human": 4, "Vehicle": 1},
    "average_confidence": 0.78
  },
  "temporal_boost_applied": true,
  "boost_reason": "Matches recent pattern (4 detections in last hour)"
}
```

## Benefits

1. **Better Accuracy**: Ensemble predictions and temporal context improve detection accuracy
2. **Fewer False Positives**: Smart filtering reduces incorrect detections
3. **Better Species Names**: Normalization provides consistent, readable species names
4. **Context Awareness**: Temporal patterns help identify consistent wildlife behavior
5. **Quality Assessment**: Quality metrics help users understand prediction reliability

## Future Enhancements

Potential improvements:
- Camera-specific species patterns (learn what species each camera typically sees)
- Time-of-day patterns (some species more active at certain times)
- Weather-based adjustments (if weather data available)
- Multi-camera correlation (if same species detected on multiple cameras)
- Machine learning model to learn from user corrections

