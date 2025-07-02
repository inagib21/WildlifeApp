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

app = FastAPI(title="SpeciesNet Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global SpeciesNet model
speciesnet_model = None

def initialize_speciesnet():
    """Initialize the SpeciesNet model"""
    global speciesnet_model
    try:
        import speciesnet
        from speciesnet import SpeciesNet, DEFAULT_MODEL
        
        logger.info(f"Initializing SpeciesNet with model: {DEFAULT_MODEL}")
        speciesnet_model = SpeciesNet(DEFAULT_MODEL)
        logger.info("SpeciesNet model initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing SpeciesNet: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize SpeciesNet on startup"""
    logger.info("Starting SpeciesNet server...")
    if initialize_speciesnet():
        logger.info("SpeciesNet server ready")
    else:
        logger.error("Failed to initialize SpeciesNet")

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
    """Health check endpoint"""
    return {
        "status": "healthy" if speciesnet_model else "error",
        "model_loaded": speciesnet_model is not None
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