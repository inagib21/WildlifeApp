"""Image compression and thumbnail utilities"""
import os
import logging
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import io
import hashlib

logger = logging.getLogger(__name__)

# Thumbnail cache directory
THUMBNAIL_CACHE_DIR = Path(__file__).parent.parent.parent / "thumbnails"
THUMBNAIL_CACHE_DIR.mkdir(exist_ok=True)


def compress_image(
    input_path: str,
    output_path: Optional[str] = None,
    quality: int = 85,
    max_width: Optional[int] = 1920,
    max_height: Optional[int] = 1080,
    format: str = "JPEG"
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Compress an image file
    
    Args:
        input_path: Path to input image
        output_path: Path to save compressed image (if None, overwrites input)
        quality: JPEG quality (1-100, default 85)
        max_width: Maximum width (None = no resize)
        max_height: Maximum height (None = no resize)
        format: Output format (JPEG, PNG, WEBP)
    
    Returns:
        Tuple of (success, output_path, original_size_bytes)
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"Input image not found: {input_path}")
            return False, None, None
        
        original_size = os.path.getsize(input_path)
        
        # Open image
        with Image.open(input_path) as img:
            # Convert RGBA to RGB for JPEG
            if format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            
            # Resize if needed
            if max_width or max_height:
                img.thumbnail((max_width or 9999, max_height or 9999), Image.Resampling.LANCZOS)
            
            # Determine output path
            if output_path is None:
                output_path = input_path
            
            # Save compressed image
            save_kwargs = {}
            if format == "JPEG":
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True
            elif format == "PNG":
                save_kwargs["optimize"] = True
            elif format == "WEBP":
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6  # Best compression
            
            img.save(output_path, format=format, **save_kwargs)
            
            new_size = os.path.getsize(output_path)
            compression_ratio = (1 - new_size / original_size) * 100 if original_size > 0 else 0
            
            logger.info(
                f"Compressed image: {input_path} -> {output_path} "
                f"({original_size} -> {new_size} bytes, {compression_ratio:.1f}% reduction)"
            )
            
            return True, output_path, original_size
            
    except Exception as e:
        logger.error(f"Failed to compress image {input_path}: {e}", exc_info=True)
        return False, None, None


def compress_image_in_memory(
    image_data: bytes,
    quality: int = 85,
    max_width: Optional[int] = 1920,
    max_height: Optional[int] = 1080,
    format: str = "JPEG"
) -> Optional[bytes]:
    """
    Compress an image from memory
    
    Args:
        image_data: Image data as bytes
        quality: JPEG quality (1-100)
        max_width: Maximum width
        max_height: Maximum height
        format: Output format
    
    Returns:
        Compressed image data as bytes, or None if failed
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_data))
        
        # Convert RGBA to RGB for JPEG
        if format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        
        # Resize if needed
        if max_width or max_height:
            img.thumbnail((max_width or 9999, max_height or 9999), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        save_kwargs = {}
        if format == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif format == "PNG":
            save_kwargs["optimize"] = True
        elif format == "WEBP":
            save_kwargs["quality"] = quality
            save_kwargs["method"] = 6
        
        img.save(output, format=format, **save_kwargs)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Failed to compress image in memory: {e}", exc_info=True)
        return None


def generate_thumbnail(
    input_path: str,
    size: Tuple[int, int] = (200, 200),
    quality: int = 85
) -> Optional[str]:
    """
    Generate a thumbnail for an image
    
    Args:
        input_path: Path to input image
        size: Thumbnail size (width, height)
        quality: JPEG quality (1-100)
    
    Returns:
        Path to thumbnail file, or None if failed
    """
    try:
        if not os.path.exists(input_path):
            logger.error(f"Input image not found: {input_path}")
            return None
        
        # Generate cache key from file path and size
        cache_key = hashlib.md5(f"{input_path}_{size[0]}_{size[1]}".encode()).hexdigest()
        thumbnail_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.jpg"
        
        # Return cached thumbnail if exists
        if thumbnail_path.exists():
            return str(thumbnail_path)
        
        # Generate thumbnail
        with Image.open(input_path) as img:
            # Convert RGBA to RGB for JPEG
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            
            # Create thumbnail (maintains aspect ratio)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save thumbnail
            img.save(thumbnail_path, format="JPEG", quality=quality, optimize=True)
            
            logger.debug(f"Generated thumbnail: {thumbnail_path}")
            return str(thumbnail_path)
            
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for {input_path}: {e}", exc_info=True)
        return None


def get_thumbnail_url(image_path: str, size: Tuple[int, int] = (200, 200)) -> str:
    """
    Get thumbnail URL for an image (generates if needed)
    
    Args:
        image_path: Path to original image
        size: Thumbnail size
    
    Returns:
        URL path to thumbnail
    """
    thumbnail_path = generate_thumbnail(image_path, size)
    if thumbnail_path:
        # Return relative path from project root
        rel_path = os.path.relpath(thumbnail_path, THUMBNAIL_CACHE_DIR.parent)
        return f"/{rel_path.replace(os.sep, '/')}"
    return None

