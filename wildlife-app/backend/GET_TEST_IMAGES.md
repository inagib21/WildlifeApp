# Getting Test Images and Videos for AI Backend Testing

## Quick Start

**Download sample wildlife images and videos automatically:**

```bash
cd wildlife-app/backend
python download_test_images.py
```

This downloads 10 free wildlife images from Unsplash for testing.

**Download images AND videos:**

```bash
# Get free Pexels API key first: https://www.pexels.com/api/
python download_test_images.py --count 10 --videos 5 --pexels-key YOUR_KEY
```

## Options

### Download More Images

```bash
# Download 20 images
python download_test_images.py --count 20

# Download to specific folder
python download_test_images.py --output ./my_test_images

# Download 30 images to custom folder
python download_test_images.py --count 30 --output ./test_data
```

### Using Pexels (Better Quality + Videos)

Pexels requires a free API key but provides better quality images AND videos:

1. Get free API key: https://www.pexels.com/api/
2. Use it for images:
   ```bash
   python download_test_images.py --pexels-key YOUR_API_KEY --count 20
   ```
3. Use it for videos:
   ```bash
   python download_test_images.py --pexels-key YOUR_API_KEY --videos 10
   ```
4. Or both:
   ```bash
   python download_test_images.py --pexels-key YOUR_API_KEY --count 15 --videos 5
   ```

## Manual Download

### Option 1: Unsplash (Free, No Key Required)

1. Go to: https://unsplash.com/s/photos/wildlife
2. Search for: "deer", "raccoon", "squirrel", "bird", "fox", etc.
3. Download images
4. Save to: `wildlife-app/backend/test_images/`

### Option 2: Pexels (Free, Better Quality)

1. Go to: https://www.pexels.com/search/wildlife/
2. Download free images
3. Save to: `wildlife-app/backend/test_images/`

### Option 3: Use Your Own Images

1. Copy your camera trap images
2. Place in: `wildlife-app/backend/test_images/`
3. Test with: `python test_ai_backends.py test_images/your_image.jpg`

## Recommended Test Images

For comprehensive testing, include:

### Common Wildlife
- ✅ Deer (white-tailed deer, mule deer)
- ✅ Raccoons
- ✅ Squirrels
- ✅ Birds (various species)
- ✅ Rabbits

### Predators
- ✅ Foxes
- ✅ Coyotes
- ✅ Owls

### Edge Cases
- ✅ Empty scenes (to test false positive filtering)
- ✅ Blurry images (to test quality assessment)
- ✅ Night images (to test low-light handling)
- ✅ Multiple animals (to test multi-detection)

## Testing with Downloaded Media

### Testing Images

Once you have images:

```bash
# Test all backends on one image
python test_ai_backends.py test_images/test_deer_1.jpg

# Test specific backend
python -c "from services.ai_backends import ai_backend_manager; result = ai_backend_manager.predict('test_images/test_deer_1.jpg', 'yolov11'); print(result)"

# Compare all models
curl -X POST http://localhost:8001/api/ai/compare -F "file=@test_images/test_deer_1.jpg"
```

### Testing Videos

Once you have videos:

```bash
# Test all backends on video (extracts 10 frames)
python test_video_backends.py test_images/test_deer_1.mp4

# Extract and test more frames
python test_video_backends.py test_images/test_deer_1.mp4 --frames 20

# Test specific backend on video
python test_video_backends.py test_images/test_deer_1.mp4 --backend yolov11

# Extract frame every 30 frames
python test_video_backends.py test_images/test_deer_1.mp4 --interval 30
```

## Media Requirements

### Images
- **Format**: JPG, PNG, BMP
- **Size**: Any (will be processed automatically)
- **Content**: Wildlife, animals, or empty scenes
- **Quality**: Any (system tests quality automatically)

### Videos
- **Format**: MP4, AVI, MOV, MKV
- **Size**: Any (frames extracted automatically)
- **Content**: Wildlife videos, animal movement
- **Duration**: Any (system extracts frames evenly)
- **Quality**: HD preferred for best results

## Troubleshooting

### Download Script Fails

**Issue**: "Failed to download" errors

**Solutions**:
1. Check internet connection
2. Unsplash may be rate-limited - wait a few minutes and try again
3. Use `--pexels-key` for better reliability
4. Download manually from websites above

### No Images Found

**Issue**: Test script says "No test image found"

**Solutions**:
1. Run download script: `python download_test_images.py`
2. Or manually add images to `test_images/` folder
3. Or specify image path: `python test_ai_backends.py path/to/image.jpg`

### Images Too Small

**Issue**: Downloaded images are very small

**Solutions**:
1. Use Pexels API (better quality): `--pexels-key YOUR_KEY`
2. Download manually from Unsplash/Pexels websites
3. Use your own camera trap images

## Example Workflow

```bash
# 1. Download test images
cd wildlife-app/backend
python download_test_images.py --count 15

# 2. Test all backends
python test_ai_backends.py test_images/test_deer_1.jpg

# 3. Check which backend works best
# Look at the "Performance Comparison" section in output

# 4. Use best backend in production
# Edit config.py: AI_BACKEND = "yolov11"
```

## Free Image Sources

1. **Unsplash**: https://unsplash.com/s/photos/wildlife
   - Free, no attribution required
   - High quality
   - Rate limited for API

2. **Pexels**: https://www.pexels.com/search/wildlife/
   - Free, no attribution required
   - Very high quality
   - API key available (free)

3. **Your Own Images**
   - Best for testing your specific setup
   - Real camera trap images
   - Most relevant results

## Next Steps

1. ✅ Download test images: `python download_test_images.py`
2. ✅ Test backends: `python test_ai_backends.py test_images/test_deer_1.jpg`
3. ✅ Compare models: Use `/api/ai/compare` endpoint
4. ✅ Choose best backend: Based on your needs (speed vs accuracy)

Happy testing! 🦌🦝🐦

