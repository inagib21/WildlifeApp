# AI Backend Testing Guide

This guide explains how to test and verify all AI backends in the system.

## Quick Test

Run the test script with an image:

```bash
cd wildlife-app/backend
python test_ai_backends.py path/to/image.jpg
```

Or let it auto-find a test image:

```bash
python test_ai_backends.py
```

The script will automatically look for images in:
- `./test_images/`
- `../test_images/`
- `./motioneye_media/`
- `../motioneye_media/`

## What the Test Does

1. **Lists all available backends** - Shows which AI models are loaded and ready
2. **Tests each backend** - Runs predictions on the test image
3. **Compares performance** - Shows speed and accuracy metrics
4. **Reports results** - Summary of successes and failures

## Example Output

```
============================================================
AI Backend Test Suite
============================================================
Using test image: test_images/deer.jpg
Image size: 245.67 KB

============================================================
Available Backends
============================================================
  ✓ speciesnet: SpeciesNet (YOLOv5)
  ✓ yolov11: YOLOv11 (Latest)
  ✓ yolov8: YOLOv8
  ✓ ensemble: Ensemble (4 models)

============================================================
Testing backend: yolov11
============================================================
  Backend name: YOLOv11 (Latest)
  Image: test_images/deer.jpg
  ✓ Prediction successful
  Duration: 45.23ms
  Confidence: 0.892
  Top predictions:
    1. deer: 0.892
    2. animal: 0.067
    3. mammal: 0.023

============================================================
Test Summary
============================================================
Total backends tested: 4
Successful: 4
Failed: 0

Successful backends:
  ✓ yolov11: 45.23ms, confidence: 0.892
  ✓ yolov8: 52.14ms, confidence: 0.876
  ✓ ensemble: 156.78ms, confidence: 0.934
  ✓ speciesnet: 89.45ms, confidence: 0.823

============================================================
Performance Comparison
============================================================

Fastest backends:
  1. yolov11: 45.23ms
  2. yolov8: 52.14ms
  3. speciesnet: 89.45ms

Most confident backends:
  1. ensemble: 0.934
  2. yolov11: 0.892
  3. yolov8: 0.876
```

## API Endpoints

### List Backends

```bash
curl http://localhost:8000/api/ai/backends
```

Returns:
```json
[
  {
    "name": "yolov11",
    "display_name": "YOLOv11 (Latest)",
    "available": true
  },
  ...
]
```

### Get Metrics

```bash
curl http://localhost:8000/api/ai/metrics
```

Returns performance metrics for all backends:
```json
{
  "summary": {
    "total_backends": 4,
    "total_predictions": 1234,
    "total_successful": 1200,
    "total_failed": 34,
    "overall_success_rate": 97.24,
    "fastest_backend": "yolov11",
    "most_accurate_backend": "ensemble",
    "most_used_backend": "yolov11"
  },
  "backends": {
    "yolov11": {
      "backend_name": "yolov11",
      "total_predictions": 500,
      "successful_predictions": 495,
      "failed_predictions": 5,
      "success_rate": 99.0,
      "avg_inference_time_ms": 45.23,
      "recent_avg_time_ms": 43.12,
      "avg_confidence": 0.892,
      "recent_avg_confidence": 0.901,
      "last_used": "2024-01-15T10:30:00",
      "error_counts": {
        "Model not available": 5
      }
    },
    ...
  }
}
```

### Get Metrics for Specific Backend

```bash
curl http://localhost:8000/api/ai/metrics?backend_name=yolov11
```

### Compare Models

Upload an image to compare all models:

```bash
curl -X POST http://localhost:8000/api/ai/compare \
  -F "file=@test_image.jpg"
```

Returns predictions from all available models with timing information.

## Troubleshooting

### Backend Not Available

If a backend shows as unavailable:

1. **YOLOv11/YOLOv8**: Install ultralytics
   ```bash
   pip install ultralytics
   ```

2. **CLIP/ViT (Hugging Face)**: Install transformers and torch
   ```bash
   pip install transformers torch
   ```
   **Note:** CLIP and ViT models are downloaded from Hugging Face Hub on first use (~500MB each). Internet connection required for initial download. Models are cached locally after download.
   
   See [`HUGGING_FACE_USAGE.md`](../HUGGING_FACE_USAGE.md) for detailed information about Hugging Face integration.

3. **SpeciesNet**: Make sure SpeciesNet server is running
   ```bash
   # Check if server is running
   curl http://localhost:8000/api/speciesnet/status
   # Or check health endpoint
   curl http://localhost:8000/health
   ```
   
   **Note:** SpeciesNet is the original wildlife classification backend from Google's CameraTrapAI. It uses YOLOv5 and is trained specifically on camera trap images. SpeciesNet is always available if the SpeciesNet server is running.

   **Testing SpeciesNet:**
   ```bash
   # Test with an image
   curl -X POST http://localhost:8000/predict \
     -F "file=@test_image.jpg"
   ```

4. **Face Recognition**: Install face-recognition (automatically installs dlib)
   ```bash
   # Important: Do NOT install dlib-binary separately - it's not needed and will fail on Windows
   # The face-recognition package automatically installs dlib
   pip install face-recognition
   ```
   **Note:** See `DLIB_BINARY_FIX.md` for details about why `dlib-binary` should not be installed separately.

### Test Script Errors

If the test script fails:

1. **Import errors**: Make sure you're running from the backend directory
   ```bash
   cd wildlife-app/backend
   python test_ai_backends.py
   ```

2. **Image not found**: Provide full path to image
   ```bash
   python test_ai_backends.py C:/path/to/image.jpg
   ```

3. **Permission errors**: Make sure you have read access to the image file

## Performance Benchmarks

Expected performance on a modern GPU:

| Backend | Avg Time | Accuracy | Best For |
|---------|----------|----------|----------|
| YOLOv11 | 40-60ms | 90-95% | Speed + Accuracy |
| YOLOv8 | 50-70ms | 85-90% | Good balance |
| SpeciesNet | 80-120ms | 75-80% | General wildlife |
| CLIP (Hugging Face) | 200-400ms | 80-85% | Rare species, zero-shot |
| ViT (Hugging Face) | 150-300ms | 85-90% | High accuracy |
| Ensemble | 300-600ms | 92-97% | Maximum accuracy |

*Times are for inference only, not including image loading*

## Continuous Monitoring

The system automatically tracks metrics for all backends. View real-time stats:

```python
from services.ai_metrics import ai_metrics_tracker

# Get summary
summary = ai_metrics_tracker.get_summary()
print(f"Total predictions: {summary['total_predictions']}")
print(f"Success rate: {summary['overall_success_rate']}%")

# Get metrics for specific backend
metrics = ai_metrics_tracker.get_metrics("yolov11")
print(f"Avg time: {metrics['avg_inference_time_ms']}ms")
print(f"Avg confidence: {metrics['avg_confidence']}")
```

## Next Steps

1. Run the test script to verify all backends work
2. Check metrics endpoint to see performance
3. Use compare endpoint to find best model for your images
4. Monitor metrics over time to track improvements

