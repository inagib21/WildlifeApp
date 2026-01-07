#!/usr/bin/env python3
"""
Quick diagnostic script to check if CLIP and ViT backends are working.

Usage:
    python check_clip_vit.py
"""

import sys
import os
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("CLIP and ViT Backend Diagnostic")
print("=" * 60)

# Check 1: Dependencies
print("\n[1] Checking Dependencies...")
print("-" * 60)

# Check torch
try:
    import torch
    print(f"  [OK] torch installed: version {torch.__version__}")
    print(f"    CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"    CUDA device: {torch.cuda.get_device_name(0)}")
    else:
        print(f"    Using CPU (will be slower)")
except ImportError:
    print("  [FAIL] torch NOT installed")
    print("    Install with: pip install torch")
    sys.exit(1)

# Check transformers
try:
    import transformers
    print(f"  [OK] transformers installed: version {transformers.__version__}")
except ImportError:
    print("  [FAIL] transformers NOT installed")
    print("    Install with: pip install transformers")
    sys.exit(1)

# Check PIL
try:
    from PIL import Image
    print(f"  [OK] PIL/Pillow installed")
except ImportError:
    print("  [FAIL] PIL/Pillow NOT installed")
    print("    Install with: pip install pillow")
    sys.exit(1)

# Check 2: CLIP Backend
print("\n[2] Testing CLIP Backend...")
print("-" * 60)

try:
    from services.ai_backends import CLIPBackend
    
    clip = CLIPBackend()
    if clip.is_available():
        print("  [OK] CLIP backend is available")
        print(f"    Model: {clip.get_name()}")
        print(f"    Device: {clip.device if hasattr(clip, 'device') else 'unknown'}")
    else:
        print("  [FAIL] CLIP backend is NOT available")
        print("    Check logs above for loading errors")
        
        # Try to load manually to see error
        print("\n    Attempting manual load to see error...")
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = "openai/clip-vit-base-patch32"
            print(f"    Loading {model_name} on {device}...")
            
            model = CLIPModel.from_pretrained(model_name).to(device)
            processor = CLIPProcessor.from_pretrained(model_name)
            print("    [OK] CLIP model loaded successfully!")
            print("    The backend should work - check initialization logs")
        except Exception as e:
            print(f"    [FAIL] Error loading CLIP: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"  [FAIL] Error testing CLIP: {e}")
    import traceback
    traceback.print_exc()

# Check 3: ViT Backend
print("\n[3] Testing ViT Backend...")
print("-" * 60)

try:
    from services.ai_backends import ViTBackend
    
    vit = ViTBackend()
    if vit.is_available():
        print("  [OK] ViT backend is available")
        print(f"    Model: {vit.get_name()}")
        print(f"    Device: {vit.device if hasattr(vit, 'device') else 'unknown'}")
    else:
        print("  [FAIL] ViT backend is NOT available")
        print("    Check logs above for loading errors")
        
        # Try to load manually to see error
        print("\n    Attempting manual load to see error...")
        try:
            import torch
            from transformers import ViTImageProcessor, ViTForImageClassification
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = os.getenv("VIT_MODEL_NAME", "google/vit-base-patch16-224")
            print(f"    Loading {model_name} on {device}...")
            
            processor = ViTImageProcessor.from_pretrained(model_name)
            model = ViTForImageClassification.from_pretrained(model_name).to(device)
            print("    [OK] ViT model loaded successfully!")
            print("    The backend should work - check initialization logs")
        except Exception as e:
            print(f"    [FAIL] Error loading ViT: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"  [FAIL] Error testing ViT: {e}")
    import traceback
    traceback.print_exc()

# Check 4: Test with AI Backend Manager
print("\n[4] Testing with AI Backend Manager...")
print("-" * 60)

try:
    from services.ai_backends import ai_backend_manager
    
    backends = ai_backend_manager.list_backends()
    
    clip_available = any(b["name"] == "clip" and b["available"] for b in backends)
    vit_available = any(b["name"] == "vit" and b["available"] for b in backends)
    
    if clip_available:
        print("  [OK] CLIP registered in backend manager")
    else:
        print("  [FAIL] CLIP NOT registered in backend manager")
    
    if vit_available:
        print("  [OK] ViT registered in backend manager")
    else:
        print("  [FAIL] ViT NOT registered in backend manager")
    
    print("\n  All registered backends:")
    for backend in backends:
        status = "[OK]" if backend["available"] else "[FAIL]"
        print(f"    {status} {backend['name']}: {backend['display_name']}")
        
except Exception as e:
    print(f"  [FAIL] Error checking backend manager: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 60)
print("Summary")
print("=" * 60)

try:
    from services.ai_backends import ai_backend_manager
    backends = ai_backend_manager.list_backends()
    
    clip_available = any(b["name"] == "clip" and b["available"] for b in backends)
    vit_available = any(b["name"] == "vit" and b["available"] for b in backends)
    
    if clip_available and vit_available:
        print("  [OK] Both CLIP and ViT are working!")
    elif clip_available:
        print("  [WARN] CLIP is working, but ViT is not")
    elif vit_available:
        print("  [WARN] ViT is working, but CLIP is not")
    else:
        print("  [FAIL] Neither CLIP nor ViT are working")
        print("\n  Common fixes:")
        print("    1. Install dependencies: pip install transformers torch")
        print("    2. Check internet connection (models download from HuggingFace)")
        print("    3. Check available disk space (models are ~500MB each)")
        print("    4. Check GPU memory if using CUDA")
        print("    5. Restart the backend server after installing dependencies")
        
except Exception as e:
    print(f"  [FAIL] Could not check status: {e}")

print("=" * 60)

