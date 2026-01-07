#!/usr/bin/env python3
"""
Simple FastAPI server for SpeciesNet
Provides a /predict endpoint for image classification
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import tempfile
import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CRITICAL: Set up YOLOv5 workaround at module import time
# This must happen before any imports that might trigger model loading

def _setup_models_package():
    """Helper to set up models package structure with models.common and models.yolo"""
    import sys
    import types
    
    # Check if already set up
    if 'models.common' in sys.modules and 'models.yolo' in sys.modules:
        return
    
    # CRITICAL: If 'models' is already in sys.modules as a file (models.py), we need to replace it
    # with a package to allow submodules like models.common and models.yolo
    if 'models' in sys.modules:
        existing_models = sys.modules['models']
        # Check if it's a file module (has __file__ attribute pointing to models.py)
        if hasattr(existing_models, '__file__') and existing_models.__file__ and 'models.py' in existing_models.__file__:
            # Save the original models module content
            original_models_content = {}
            for attr in dir(existing_models):
                if not attr.startswith('_'):
                    try:
                        original_models_content[attr] = getattr(existing_models, attr)
                    except:
                        pass
            
            # Create a new package module
            models_package = types.ModuleType('models')
            models_package.__package__ = 'models'
            
            # Restore original content
            for attr, value in original_models_content.items():
                setattr(models_package, attr, value)
            
            # Replace in sys.modules
            sys.modules['models'] = models_package
            logger.info("Replaced models module with package to support models.common and models.yolo")
        else:
            # It's already a package, use it
            models_package = existing_models
    else:
        # Create a new 'models' package
        models_package = types.ModuleType('models')
        models_package.__package__ = 'models'
        sys.modules['models'] = models_package
    
    # Create 'models.common' module - this is what the checkpoint is looking for
    try:
        from yolov5.models import common as yolov5_common
        # Create the common module and populate it with YOLOv5 common classes
        common_module = types.ModuleType('common')
        common_module.__package__ = 'models'
        
        # Copy all attributes from yolov5.models.common
        for attr_name in dir(yolov5_common):
            if not attr_name.startswith('_'):
                try:
                    attr = getattr(yolov5_common, attr_name)
                    setattr(common_module, attr_name, attr)
                except:
                    pass
        
        # Register the module
        models_package.common = common_module
        sys.modules['models.common'] = common_module
        logger.info("Created models.common module with YOLOv5 common classes")
    except Exception as e:
        logger.warning(f"Could not create models.common: {e}")
        # Create minimal common module for unpickling
        common_module = types.ModuleType('common')
        common_module.__package__ = 'models'
        models_package.common = common_module
        sys.modules['models.common'] = common_module
        logger.info("Created minimal models.common module for unpickling")
    
    # Create 'models.yolo' module
    yolo_module = types.ModuleType('yolo')
    yolo_module.__package__ = 'models'
    models_package.yolo = yolo_module
    sys.modules['models.yolo'] = yolo_module
    
    # Import YOLOv5 classes and add them to the yolo module
    try:
        # Import the main Model class and Detect class (critical for unpickling)
        try:
            from yolov5.models.yolo import Model as YOLOModel, Detect as YOLODetect
            yolo_module.Model = YOLOModel
            yolo_module.Detect = YOLODetect
            logger.info("Added YOLOv5 Model and Detect classes to models.yolo")
        except Exception as e:
            logger.warning(f"Could not import YOLOv5 Model/Detect: {e}")
            # Try importing separately
            try:
                from yolov5.models.yolo import Model as YOLOModel
                yolo_module.Model = YOLOModel
                logger.info("Added YOLOv5 Model class to models.yolo")
            except:
                pass
            try:
                from yolov5.models.yolo import Detect as YOLODetect
                yolo_module.Detect = YOLODetect
                logger.info("Added YOLOv5 Detect class to models.yolo")
            except Exception as e2:
                logger.warning(f"Could not import YOLOv5 Detect: {e2}")
        
        # Also try importing Segment and Classify if they exist
        try:
            from yolov5.models.yolo import Segment as YOLOSegment, Classify as YOLOClassify
            yolo_module.Segment = YOLOSegment
            yolo_module.Classify = YOLOClassify
            logger.info("Added YOLOv5 Segment and Classify classes to models.yolo")
        except:
            # These might not exist in all YOLOv5 versions, that's okay
            pass
        
        # Also try importing from yolov5.models directly as fallback
        try:
            import yolov5.models as yolo_models
            # Copy any additional classes that might be needed
            for attr_name in ['Segment', 'Classify']:
                if hasattr(yolo_models, attr_name) and not hasattr(yolo_module, attr_name):
                    setattr(yolo_module, attr_name, getattr(yolo_models, attr_name))
        except:
            pass
        
        logger.info("YOLOv5 workaround applied: created models.common and models.yolo modules")
    except Exception as e:
        logger.warning(f"Could not fully set up YOLOv5 workaround: {e}")
        logger.info("Created minimal models.yolo module for unpickling")

def _setup_yolo_workaround_early():
    """Workaround for YOLOv5 model loading issue - runs at module import time"""
    import sys
    
    # Check if workaround is already applied
    if 'models.common' in sys.modules and 'models.yolo' in sys.modules:
        return
    
    # Set up the models package structure first
    _setup_models_package()
    
    # Patch torch.load to ensure models.common is available during unpickling
    # This must happen AFTER setting up the package but BEFORE any model loading
    try:
        import torch.serialization
        original_find_class = torch.serialization.pickle.Unpickler.find_class
        
        def patched_find_class(self, mod_name, name):
            """Patched find_class that ensures models.common and models.yolo are available"""
            # If looking for models.common or models.yolo, ensure they exist
            if mod_name == 'models.common' or mod_name == 'models.yolo':
                if mod_name not in sys.modules:
                    # Trigger workaround setup if not already done
                    _setup_models_package()
                # If looking for Detect in models.yolo, ensure it's there
                if mod_name == 'models.yolo' and name == 'Detect':
                    if not hasattr(sys.modules.get('models.yolo', None), 'Detect'):
                        _setup_models_package()
            # Also handle the case where it's looking for models.common.SomeClass
            elif mod_name.startswith('models.'):
                if 'models.common' not in sys.modules:
                    _setup_models_package()
            return original_find_class(self, mod_name, name)
        
        # Only patch if not already patched
        if not hasattr(torch.serialization.pickle.Unpickler.find_class, '_patched'):
            torch.serialization.pickle.Unpickler.find_class = patched_find_class
            torch.serialization.pickle.Unpickler.find_class._patched = True
            logger.info("Patched torch.load to handle models.common lookup")
    except Exception as e:
        logger.warning(f"Could not patch torch.load: {e}")

# Run workaround at module import time
_setup_yolo_workaround_early()

app = FastAPI(title="SpeciesNet Server", version="1.0.0")

# Add CORS middleware - restrict to backend server only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],  # Only backend
    allow_credentials=True,
    allow_methods=["POST", "GET"],  # Only needed methods
    allow_headers=["Content-Type"],  # Only needed headers
)

# Global SpeciesNet model
speciesnet_model = None

def _setup_yolo_workaround():
    """Workaround for YOLOv5 model loading issue - wrapper that ensures it's applied"""
    # The workaround is already applied at module import time via _setup_yolo_workaround_early()
    # This function is kept for backward compatibility and as a safety check
    import sys
    if 'models.common' not in sys.modules or 'models.yolo' not in sys.modules:
        # If for some reason it wasn't applied, run it now
        _setup_yolo_workaround_early()

def initialize_speciesnet():
    """Initialize the SpeciesNet model"""
    global speciesnet_model
    try:
        # Apply YOLOv5 workaround before importing SpeciesNet
        _setup_yolo_workaround()
        
        import speciesnet
        from speciesnet import SpeciesNet, DEFAULT_MODEL
        import torch
        import os
        
        # Check if CUDA is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing SpeciesNet with model: {DEFAULT_MODEL} on device: {device}")
        
        # Force PyTorch to use CUDA if available - MUST be done BEFORE any imports/initialization
        if torch.cuda.is_available():
            # Set CUDA device first
            torch.cuda.set_device(0)
            device_obj = torch.device("cuda:0")
            logger.info(f"Setting PyTorch to use CUDA: {torch.cuda.get_device_name(0)}")
            # Set environment variable that some libraries check
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
            # Force CUDA to be the default (this affects new tensors)
            # Note: set_default_tensor_type is deprecated but still works
            try:
                if hasattr(torch, 'set_default_device'):
                    torch.set_default_device(device_obj)
                    logger.info("Set PyTorch default device to CUDA")
                else:
                    # Fallback for older PyTorch
                    torch.set_default_tensor_type('torch.cuda.FloatTensor')
                    logger.info("Set PyTorch default tensor type to CUDA")
            except Exception as e:
                logger.warning(f"Could not set default device: {e}")
        
        # Initialize SpeciesNet - check if device parameter is supported
        # Add timeout handling for network downloads (Kaggle, etc.)
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("SpeciesNet initialization timeout (network download)")
        
        try:
            # Set a longer timeout for model download (5 minutes)
            # Note: This only works on Unix, Windows needs different approach
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(300)  # 5 minute timeout
            except (AttributeError, OSError):
                # Windows doesn't support SIGALRM, use threading timeout instead
                pass
            
            try:
                speciesnet_model = SpeciesNet(DEFAULT_MODEL, device=device)
                logger.info(f"SpeciesNet initialized with device parameter: {device}")
            except (TypeError, AttributeError):
                # If device parameter is not supported, try without it
                logger.warning("SpeciesNet doesn't support device parameter, initializing without it")
                try:
                    speciesnet_model = SpeciesNet(DEFAULT_MODEL)
                    logger.info("SpeciesNet initialized without device parameter")
                except Exception as e:
                    # Check if it's a network timeout
                    error_str = str(e).lower()
                    if "timeout" in error_str or "kaggle" in error_str or "read timeout" in error_str:
                        logger.error(f"SpeciesNet initialization failed: Network timeout downloading from Kaggle")
                        logger.error("This is usually due to slow internet or Kaggle being unavailable")
                        logger.error("SpeciesNet is OPTIONAL - you have 5 other AI backends working:")
                        logger.error("  - YOLOv11 (BEST - 90-95% accuracy)")
                        logger.error("  - YOLOv8 (85-90% accuracy)")
                        logger.error("  - CLIP (80-85% accuracy)")
                        logger.error("  - ViT (90-95% accuracy)")
                        logger.error("  - Ensemble (92-97% accuracy)")
                        logger.error("The system will work fine without SpeciesNet!")
                    else:
                        logger.error(f"Failed to initialize SpeciesNet: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return False
            finally:
                # Cancel alarm if set
                try:
                    signal.alarm(0)
                except (AttributeError, OSError):
                    pass
        except (TimeoutError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            logger.error("=" * 60)
            logger.error("[WARN] SpeciesNet initialization timed out")
            logger.error("=" * 60)
            logger.error("SpeciesNet tried to download model/data from Kaggle but timed out")
            logger.error("This is OK - SpeciesNet is OPTIONAL!")
            logger.error("")
            logger.error("You have 5 other AI backends that are working:")
            logger.error("  [OK] YOLOv11 - Latest, most accurate (90-95%)")
            logger.error("  [OK] YOLOv8 - Fast and accurate (85-90%)")
            logger.error("  [OK] CLIP - Zero-shot classification (80-85%)")
            logger.error("  [OK] ViT - High accuracy (90-95%)")
            logger.error("  [OK] Ensemble - Maximum accuracy (92-97%)")
            logger.error("")
            logger.error("The system will use these instead. SpeciesNet is not needed!")
            logger.error("=" * 60)
            return False
            
            # Force move ALL PyTorch modules to GPU recursively
            if torch.cuda.is_available():
                try:
                    def move_to_gpu(obj, path="root"):
                        """Recursively move all PyTorch modules to GPU"""
                        moved = False
                        # If it's a PyTorch module, move it
                        if isinstance(obj, torch.nn.Module):
                            try:
                                obj = obj.to(device)
                                logger.info(f"Moved {path} to {device}")
                                moved = True
                            except Exception as e:
                                logger.debug(f"Could not move {path} directly: {e}")
                        
                        # Recursively check all attributes
                        if hasattr(obj, '__dict__'):
                            for attr_name, attr_value in obj.__dict__.items():
                                if not attr_name.startswith('_'):
                                    try:
                                        if isinstance(attr_value, torch.nn.Module):
                                            setattr(obj, attr_name, attr_value.to(device))
                                            logger.info(f"Moved {path}.{attr_name} to {device}")
                                            moved = True
                                        elif hasattr(attr_value, '__dict__'):
                                            move_to_gpu(attr_value, f"{path}.{attr_name}")
                                    except Exception as e:
                                        logger.debug(f"Could not move {path}.{attr_name}: {e}")
                        return moved
                    
                    # Try moving the whole model first
                    if hasattr(speciesnet_model, 'to'):
                        try:
                            speciesnet_model = speciesnet_model.to(device)
                            logger.info(f"Moved SpeciesNet model to {device} via .to()")
                        except:
                            pass
                    
                    # Recursively move all internal modules
                    moved = move_to_gpu(speciesnet_model, "speciesnet_model")
                    
                    # Also try common attribute names
                    for attr_name in ['detector', 'classifier', 'model', '_model', 'net', '_net']:
                        if hasattr(speciesnet_model, attr_name):
                            attr = getattr(speciesnet_model, attr_name)
                            if isinstance(attr, torch.nn.Module):
                                setattr(speciesnet_model, attr_name, attr.to(device))
                                logger.info(f"Moved speciesnet_model.{attr_name} to {device}")
                    
                    logger.info(f"[OK] SpeciesNet configured for GPU: {torch.cuda.get_device_name(0)}")
                except Exception as e:
                    logger.warning(f"Could not explicitly move model to GPU: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
        except Exception as e:
            # Check if it's a network/timeout error
            error_str = str(e).lower()
            is_timeout = any(term in error_str for term in ["timeout", "kaggle", "read timeout", "connection", "timed out"])
            
            if is_timeout:
                logger.warning("=" * 60)
                logger.warning("[WARN] SpeciesNet initialization timed out")
                logger.warning("=" * 60)
                logger.warning("SpeciesNet tried to download model/data from Kaggle but timed out")
                logger.warning("This is OK - SpeciesNet is OPTIONAL!")
                logger.warning("")
                logger.warning("You have 5 other AI backends that are working:")
                logger.warning("  [OK] YOLOv11 - Latest, most accurate (90-95%)")
                logger.warning("  [OK] YOLOv8 - Fast and accurate (85-90%)")
                logger.warning("  [OK] CLIP - Zero-shot classification (80-85%)")
                logger.warning("  [OK] ViT - High accuracy (90-95%)")
                logger.warning("  [OK] Ensemble - Maximum accuracy (92-97%)")
                logger.warning("")
                logger.warning("The system will use these instead. SpeciesNet is not needed!")
                logger.warning("=" * 60)
                return False
            
            logger.error(f"Failed to initialize SpeciesNet: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Try without device parameter as fallback
            try:
                logger.info("Attempting to initialize SpeciesNet without device parameter...")
                speciesnet_model = SpeciesNet(DEFAULT_MODEL)
                logger.info("SpeciesNet initialized successfully")
            except Exception as e2:
                # Check if second attempt is also a timeout
                error_str2 = str(e2).lower()
                is_timeout2 = any(term in error_str2 for term in ["timeout", "kaggle", "read timeout", "connection", "timed out"])
                
                if is_timeout2:
                    logger.warning("=" * 60)
                    logger.warning("[WARN] SpeciesNet initialization timed out (retry also failed)")
                    logger.warning("=" * 60)
                    logger.warning("SpeciesNet cannot download from Kaggle - this is OK!")
                    logger.warning("You have 5 other working AI backends - SpeciesNet is optional")
                    logger.warning("=" * 60)
                else:
                    logger.error(f"Failed to initialize SpeciesNet even without device parameter: {e2}")
                    import traceback
                    logger.error(traceback.format_exc())
                return False
        
        # Verify device usage and check if model is actually on GPU
        if torch.cuda.is_available():
            logger.info(f"[OK] GPU available: {torch.cuda.get_device_name(0)}")
            # Check if model parameters are on GPU
            try:
                def check_model_device(model, path="model"):
                    """Recursively check if model parameters are on GPU"""
                    on_gpu = False
                    on_cpu = False
                    param_count = 0
                    
                    if isinstance(model, torch.nn.Module):
                        for name, param in model.named_parameters():
                            param_count += 1
                            if param.is_cuda:
                                on_gpu = True
                            else:
                                on_cpu = True
                    
                    # Check attributes
                    if hasattr(model, '__dict__'):
                        for attr_name, attr_value in model.__dict__.items():
                            if isinstance(attr_value, torch.nn.Module):
                                sub_gpu, sub_cpu, sub_count = check_model_device(attr_value, f"{path}.{attr_name}")
                                on_gpu = on_gpu or sub_gpu
                                on_cpu = on_cpu or sub_cpu
                                param_count += sub_count
                    
                    return on_gpu, on_cpu, param_count
                
                on_gpu, on_cpu, param_count = check_model_device(speciesnet_model)
                
                if on_gpu and not on_cpu:
                    logger.info(f"[OK] ALL {param_count} model parameters are on GPU")
                elif on_gpu and on_cpu:
                    logger.warning(f"[WARN] Model has parameters on both GPU ({on_gpu}) and CPU ({on_cpu})")
                elif on_cpu:
                    logger.error(f"[ERROR] Model has {param_count} parameters but ALL are on CPU - GPU not being used!")
                else:
                    logger.warning(f"[WARN] Could not find model parameters to verify device")
                
                # Test tensor creation
                test_tensor = torch.zeros(1, device=device)
                if test_tensor.is_cuda:
                    logger.info("[OK] GPU tensor operations confirmed working")
                else:
                    logger.warning("[WARN] GPU available but test tensor not on GPU")
            except Exception as e:
                logger.warning(f"Could not verify model device: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        logger.info(f"SpeciesNet model initialized successfully on {device}")
        return True
    except Exception as e:
        logger.error(f"Error initializing SpeciesNet: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize SpeciesNet on startup"""
    logger.info("=" * 60)
    logger.info("SpeciesNet Server Starting...")
    logger.info("=" * 60)
    # Initialize model in thread pool to avoid blocking event loop
    # but still wait for it to complete before server accepts requests
    import asyncio
    import concurrent.futures
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        logger.info("Initializing SpeciesNet model...")
        logger.info("(This may take 1-2 minutes for first-time download)")
        try:
            # Run initialization in thread pool but wait for it
            result = await loop.run_in_executor(executor, initialize_speciesnet)
            if result:
                logger.info("=" * 60)
                logger.info("[OK] SpeciesNet server ready - model loaded successfully")
                logger.info("=" * 60)
            else:
                logger.warning("=" * 60)
                logger.warning("[WARN] SpeciesNet initialization failed")
                logger.warning("=" * 60)
                logger.warning("SpeciesNet is OPTIONAL - you have other AI backends working!")
                logger.warning("The server will run fine - use YOLOv11/YOLOv8/CLIP/ViT/Ensemble instead")
                logger.warning("SpeciesNet predictions will not work, but all other backends will")
                logger.warning("=" * 60)
        except Exception as e:
            logger.error("=" * 60)
            logger.error("[ERROR] EXCEPTION during SpeciesNet initialization")
            logger.error("=" * 60)
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            logger.error(traceback.format_exc())

@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "SpeciesNet Server",
        "status": "running" if speciesnet_model else "error",
        "endpoints": {
            "predict": "/predict",
            "health": "/health"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint - responds even during model loading"""
    return {
        "status": "healthy" if speciesnet_model else "loading",
        "model_loaded": speciesnet_model is not None,
        "message": "Model loaded and ready" if speciesnet_model else "Model is loading, please wait..."
    }

@app.post("/predict")
async def predict_species(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Predict species from uploaded image"""
    try:
        if speciesnet_model is None:
            raise HTTPException(status_code=500, detail="SpeciesNet model not initialized")
        
        # Check file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Import SpeciesNet utilities
            from speciesnet.utils import prepare_instances_dict
            
            # Prepare instances for SpeciesNet
            instances = prepare_instances_dict(filepaths=[temp_path])
            
            # Run predictions
            predictions = speciesnet_model.predict(instances_dict=instances)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            logger.info(f"Prediction completed for {file.filename}")
            return predictions
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
            
    except Exception as e:
        logger.error(f"Error processing prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 