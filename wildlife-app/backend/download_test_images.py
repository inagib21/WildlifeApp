#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download sample wildlife images and videos for AI backend testing.

This script downloads free sample images and videos from Unsplash and Pexels
for testing the AI backends without needing to find your own media.

Usage:
    python download_test_images.py
    python download_test_images.py --count 10
    python download_test_images.py --videos 5
    python download_test_images.py --output ./test_images
"""

import os
import sys
import io
import argparse
import requests
import json
from pathlib import Path
from typing import List, Dict
import time

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass  # If already wrapped or fails, continue

# Unsplash API (free, no key required for basic usage)
UNSPLASH_API = "https://api.unsplash.com"
UNSPLASH_PHOTOS_ENDPOINT = "https://api.unsplash.com/photos/random"

# Wildlife-related search terms
WILDLIFE_TERMS = [
    "deer", "raccoon", "squirrel", "bird", "fox", "coyote",
    "rabbit", "opossum", "skunk", "wildlife", "forest animal",
    "wild animal", "nature", "camera trap", "wildlife photography"
]

# Pexels video API
PEXELS_VIDEOS_API = "https://api.pexels.com/videos/search"

# Alternative: Use Pexels API (also free)
PEXELS_API = "https://api.pexels.com/v1/search"
PEXELS_KEY = None  # Optional - works without key for limited requests


def download_image(url: str, filepath: str) -> bool:
    """Download an image from URL"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {e}")
        return False


def download_from_unsplash(count: int, output_dir: str) -> List[str]:
    """Download images from Unsplash"""
    print(f"\n[1] Downloading {count} images from Unsplash...")
    print("-" * 60)
    
    downloaded = []
    
    for i in range(count):
        term = WILDLIFE_TERMS[i % len(WILDLIFE_TERMS)]
        print(f"  [{i+1}/{count}] Downloading: {term}...", end=" ")
        
        try:
            # Use Unsplash Source API (no key required, but rate limited)
            # Format: https://source.unsplash.com/800x600/?deer
            url = f"https://source.unsplash.com/800x600/?{term}"
            
            filename = f"test_{term}_{i+1}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            if download_image(url, filepath):
                # Verify it's actually an image
                if os.path.getsize(filepath) > 1000:  # At least 1KB
                    downloaded.append(filepath)
                    print(f"✓ ({os.path.getsize(filepath)/1024:.1f} KB)")
                else:
                    os.remove(filepath)
                    print("[FAIL] (too small, retrying...)")
                    time.sleep(1)
                    continue
            else:
                print("[FAIL]")
            
            # Rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(1)
    
    return downloaded


def download_from_pexels(count: int, output_dir: str, api_key: str = None) -> List[str]:
    """Download images from Pexels (requires API key for best results)"""
    print(f"\n[2] Downloading {count} images from Pexels...")
    print("-" * 60)
    
    if not api_key:
        print("  [INFO] No Pexels API key provided - using Unsplash instead")
        return []
    
    downloaded = []
    headers = {"Authorization": api_key}
    
    for i in range(count):
        term = WILDLIFE_TERMS[i % len(WILDLIFE_TERMS)]
        print(f"  [{i+1}/{count}] Downloading: {term}...", end=" ")
        
        try:
            # Search for images
            search_url = f"{PEXELS_API}?query={term}&per_page=1"
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("photos"):
                photo = data["photos"][0]
                url = photo["src"]["large"]
                
                filename = f"test_{term}_{i+1}.jpg"
                filepath = os.path.join(output_dir, filename)
                
                if download_image(url, filepath):
                    downloaded.append(filepath)
                    print(f"✓ ({os.path.getsize(filepath)/1024:.1f} KB)")
                else:
                    print("[FAIL]")
            else:
                print("[FAIL] (no results)")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(1)
    
    return downloaded


def download_videos_from_pexels(count: int, output_dir: str, api_key: str = None) -> List[str]:
    """Download videos from Pexels"""
    print(f"\n[3] Downloading {count} videos from Pexels...")
    print("-" * 60)
    
    if not api_key:
        print("  [INFO] No Pexels API key provided - skipping videos")
        print("  [INFO] Get free API key at: https://www.pexels.com/api/")
        return []
    
    downloaded = []
    headers = {"Authorization": api_key}
    
    for i in range(count):
        term = WILDLIFE_TERMS[i % len(WILDLIFE_TERMS)]
        print(f"  [{i+1}/{count}] Downloading video: {term}...", end=" ")
        
        try:
            # Search for videos
            search_url = f"{PEXELS_VIDEOS_API}?query={term}&per_page=1"
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get("videos"):
                video = data["videos"][0]
                # Get the best quality video file
                video_files = video.get("video_files", [])
                if video_files:
                    # Prefer HD quality
                    best_video = None
                    for vf in video_files:
                        if vf.get("quality") == "hd":
                            best_video = vf
                            break
                    if not best_video:
                        best_video = video_files[0]  # Use first available
                    
                    url = best_video.get("link")
                    if url:
                        filename = f"test_{term}_{i+1}.mp4"
                        filepath = os.path.join(output_dir, filename)
                        
                        if download_image(url, filepath):  # Reuse download function
                            downloaded.append(filepath)
                            print(f"✓ ({os.path.getsize(filepath)/1024/1024:.1f} MB)")
                        else:
                            print("[FAIL]")
                    else:
                        print("[FAIL] (no video URL)")
                else:
                    print("[FAIL] (no video files)")
            else:
                print("[FAIL] (no results)")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(1)
    
    return downloaded


def download_sample_images_local() -> List[str]:
    """Create a script to download from a public dataset or provide local samples"""
    print("\n[4] Setting up local sample images...")
    print("-" * 60)
    
    # We'll create a script that uses a public wildlife dataset
    # For now, return empty - user can add their own images
    print("  [INFO] Place your own test images in the test_images/ folder")
    print("  [INFO] Or use the download functions above")
    
    return []


def create_sample_images_info(output_dir: str):
    """Create an info file about the test images and videos"""
    info_file = os.path.join(output_dir, "README.md")
    
    content = """# Test Images and Videos for AI Backend Testing

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
"""
    
    with open(info_file, 'w') as f:
        f.write(content)
    
    print(f"  [OK] Created info file: {info_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Download sample wildlife images for AI backend testing"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of images to download (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./test_images",
        help="Output directory (default: ./test_images)"
    )
    parser.add_argument(
        "--pexels-key",
        type=str,
        default=None,
        help="Pexels API key (optional, for better results). Can also set PEXELS_API_KEY env var."
    )
    parser.add_argument(
        "--skip-unsplash",
        action="store_true",
        help="Skip Unsplash downloads"
    )
    parser.add_argument(
        "--videos",
        type=int,
        default=0,
        help="Number of videos to download (default: 0, requires --pexels-key)"
    )
    
    args = parser.parse_args()
    
    # Check for API key in environment variable if not provided
    if not args.pexels_key:
        args.pexels_key = os.getenv("PEXELS_API_KEY")
    
    print("=" * 60)
    print("Wildlife Test Media Downloader")
    print("=" * 60)
    print(f"\nOutput directory: {args.output}")
    print(f"Number of images: {args.count}")
    print(f"Number of videos: {args.videos}")
    if args.videos > 0 and not args.pexels_key:
        print("  [WARN] Videos require --pexels-key (get free key at https://www.pexels.com/api/)")
        print("  [INFO] Or set PEXELS_API_KEY environment variable")
    elif args.pexels_key:
        print(f"  [OK] Pexels API key configured (videos enabled)")
    print()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Output directory: {output_dir.absolute()}")
    
    all_downloaded = []
    
    # Download from Unsplash
    if not args.skip_unsplash:
        downloaded = download_from_unsplash(args.count, str(output_dir))
        all_downloaded.extend(downloaded)
    
    # Download from Pexels (if key provided)
    if args.pexels_key:
        downloaded = download_from_pexels(args.count, str(output_dir), args.pexels_key)
        all_downloaded.extend(downloaded)
    
    # Download videos (if requested and key provided)
    all_videos = []
    if args.videos > 0:
        videos = download_videos_from_pexels(args.videos, str(output_dir), args.pexels_key)
        all_videos.extend(videos)
    
    # Create info file
    create_sample_images_info(str(output_dir))
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Summary")
    print("=" * 60)
    print(f"Total images downloaded: {len(all_downloaded)}")
    print(f"Total videos downloaded: {len(all_videos)}")
    print(f"Location: {output_dir.absolute()}")
    
    if all_downloaded:
        print("\nDownloaded images:")
        for img in all_downloaded[:10]:  # Show first 10
            print(f"  - {os.path.basename(img)}")
        if len(all_downloaded) > 10:
            print(f"  ... and {len(all_downloaded) - 10} more")
    
    if all_videos:
        print("\nDownloaded videos:")
        for vid in all_videos:
            size_mb = os.path.getsize(vid) / (1024 * 1024)
            print(f"  - {os.path.basename(vid)} ({size_mb:.1f} MB)")
    
    if all_downloaded or all_videos:
        print("\n" + "=" * 60)
        print("Next Steps")
        print("=" * 60)
        if all_downloaded:
            print("\nTest the AI backends with images:")
            print(f"  cd wildlife-app/backend")
            print(f"  python test_ai_backends.py {all_downloaded[0]}")
        if all_videos:
            print("\nTest the AI backends with videos:")
            print(f"  cd wildlife-app/backend")
            print(f"  python test_video_backends.py {all_videos[0]}")
    else:
        print("\n[WARN] No media was downloaded")
        print("  - Check your internet connection")
        print("  - Try again (Unsplash may be rate-limited)")
        print("  - For videos, use --pexels-key (free at https://www.pexels.com/api/)")
        print("  - Or add your own images/videos to the test_images/ folder")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

