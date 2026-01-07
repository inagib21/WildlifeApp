# Quick Download Guide - Test Images & Videos

## 🚀 Fastest Way to Get Test Media

### Option 1: Use the Batch Script (Easiest)

**Windows:**
```bash
cd wildlife-app/backend
download_media.bat
```

This downloads 15 images and 5 videos automatically!

**Custom amounts:**
```bash
download_media.bat 20 10
# Downloads 20 images and 10 videos
```

### Option 2: Use Python Script Directly

```bash
cd wildlife-app/backend

# Download images and videos
python download_test_images.py --count 15 --videos 5 --pexels-key PZIghIm0CCKcLD0JMRdvMCyVflYiLqcBkRuPEzLorAp5WjWeofQEPekk

# Just images
python download_test_images.py --count 20 --pexels-key PZIghIm0CCKcLD0JMRdvMCyVflYiLqcBkRuPEzLorAp5WjWeofQEPekk

# Just videos
python download_test_images.py --videos 10 --pexels-key PZIghIm0CCKcLD0JMRdvMCyVflYiLqcBkRuPEzLorAp5WjWeofQEPekk
```

## Your Pexels API Key

Your API key is already configured in `download_media.bat`. 

**Key:** `PZIghIm0CCKcLD0JMRdvMCyVflYiLqcBkRuPEzLorAp5WjWeofQEPekk`

## What Gets Downloaded

### Images
- Deer, raccoons, squirrels, birds, foxes, etc.
- High quality wildlife photos
- Saved to: `test_images/`

### Videos
- Wildlife movement videos
- HD quality when available
- Saved to: `test_images/` (as .mp4 files)

## Testing After Download

### Test Images
```bash
python test_ai_backends.py test_images/test_deer_1.jpg
```

### Test Videos
```bash
python test_video_backends.py test_images/test_deer_1.mp4
```

## Quick Commands

```bash
# Download everything (15 images + 5 videos)
download_media.bat

# Download more
download_media.bat 30 10

# Test images
python test_ai_backends.py test_images/test_deer_1.jpg

# Test videos
python test_video_backends.py test_images/test_deer_1.mp4
```

## Troubleshooting

### "API key invalid"
- Check the key is correct
- Verify Pexels account is active
- Try again (rate limits may apply)

### "No videos downloaded"
- Videos require Pexels API key
- Make sure `--pexels-key` is provided
- Check internet connection

### "Download failed"
- Check internet connection
- Wait a few minutes (rate limiting)
- Try downloading fewer files at once

## Next Steps

1. ✅ Run `download_media.bat` to get test media
2. ✅ Test with `test_ai_backends.py` for images
3. ✅ Test with `test_video_backends.py` for videos
4. ✅ Compare all backends to find the best one

Happy testing! 🦌🦝📹

