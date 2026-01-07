# Quick Test Guide

## 🚀 Fastest Way to Test

### Option 1: Interactive Menu (Easiest)

```bash
cd wildlife-app/backend
test_all.bat
```

This opens a menu where you can:
- [1] Test Images
- [2] Test Videos  
- [3] Test Both
- [4] Exit

### Option 2: Direct Commands

**Test Images:**
```bash
cd wildlife-app/backend
python test_ai_backends.py test_images/test_deer_1.jpg
```

**Test Videos:**
```bash
cd wildlife-app/backend
python test_video_backends.py test_images/test_deer_1.mp4
```

## Complete Workflow

### Step 1: Download Test Media
```bash
cd wildlife-app/backend
download_media.bat
```
Downloads 15 images + 5 videos automatically.

### Step 2: Test Everything
```bash
test_all.bat
```
Select option [3] to test both images and videos.

## What Gets Tested

### Images
- All available AI backends (YOLOv11, YOLOv8, CLIP, ViT, Ensemble)
- Performance comparison
- Accuracy comparison
- Speed metrics

### Videos
- Frame extraction (10 frames by default)
- Each frame tested with all backends
- Success rates
- Average confidence
- Performance stats

## Example Output

### Image Test
```
============================================================
AI Backend Test Suite
============================================================
Testing backend: yolov11
  ✓ Prediction successful
  Duration: 45.23ms
  Confidence: 0.892
  Top predictions:
    1. deer: 0.892
    2. animal: 0.067
```

### Video Test
```
============================================================
AI Backend Video Test Suite
============================================================
Video: test_images/test_deer_1.mp4
Extracting 10 frames from video...

Frame 1/10
  yolov11: deer (0.892) - 45.2ms
  yolov8: deer (0.876) - 52.1ms
  ...

Video Test Summary
yolov11:
  Success rate: 100.0% (10/10)
  Avg time: 45.2ms per frame
  Avg confidence: 0.892
```

## Quick Commands Reference

```bash
# Download media
download_media.bat

# Test everything (interactive)
test_all.bat

# Test specific image
python test_ai_backends.py test_images/test_deer_1.jpg

# Test specific video
python test_video_backends.py test_images/test_deer_1.mp4

# Test video with more frames
python test_video_backends.py test_images/test_deer_1.mp4 --frames 20

# Test specific backend
python test_video_backends.py test_images/test_deer_1.mp4 --backend yolov11
```

## Troubleshooting

### "No test images found"
**Fix:** Run `download_media.bat` first

### "OpenCV not available" (for videos)
**Fix:** Install OpenCV
```bash
pip install opencv-python
```

### "Backend not available"
**Fix:** Check backend initialization logs
- YOLOv11/YOLOv8: `pip install ultralytics`
- CLIP/ViT: `pip install transformers torch`

## Next Steps

1. ✅ Download test media: `download_media.bat`
2. ✅ Test everything: `test_all.bat`
3. ✅ Compare results to find best backend
4. ✅ Configure your preferred backend in `config.py`

Happy testing! 🦌🦝📹

