# Test Images and Videos for AI Backend Testing

This folder contains sample wildlife images and videos for testing the AI backends.

## Usage

### Test with Images

Test all backends with these images:
```bash
cd wildlife-app/backend
python test_ai_backends.py test_images/test_deer_1.jpg
```

Or test a specific backend:
```bash
python -c "from services.ai_backends import ai_backend_manager; result = ai_backend_manager.predict('test_images/test_deer_1.jpg', 'yolov11'); print(result)"
```

### Test with Videos

Extract frames from videos and test:
```bash
python test_video_backends.py test_images/test_deer_1.mp4
```

Or process video frames:
```python
from services.ai_backends import ai_backend_manager
import cv2

cap = cv2.VideoCapture('test_images/test_deer_1.mp4')
ret, frame = cap.read()
if ret:
    cv2.imwrite('frame.jpg', frame)
    result = ai_backend_manager.predict('frame.jpg')
    print(result)
```

## Media Sources

These files were downloaded from:
- Unsplash (free stock photos)
- Pexels (free stock photos and videos)
- Public wildlife datasets

## Adding More Media

1. Download images/videos from:
   - Unsplash: https://unsplash.com/s/photos/wildlife
   - Pexels: https://www.pexels.com/search/wildlife/
   - Pexels Videos: https://www.pexels.com/videos/search/wildlife/
   - Your own camera trap images/videos

2. Place them in this folder

3. Run the test script:
   ```bash
   python test_ai_backends.py path/to/image.jpg
   python test_video_backends.py path/to/video.mp4
   ```

## Recommended Test Media

For best testing, include:

### Images
- Deer (common wildlife)
- Raccoons (nocturnal animals)
- Birds (various species)
- Squirrels (small animals)
- Foxes/Coyotes (predators)
- Empty scenes (to test false positive filtering)

### Videos
- Wildlife movement videos
- Multiple animals in frame
- Day and night scenes
- Different lighting conditions
- Various durations (short clips work best)
