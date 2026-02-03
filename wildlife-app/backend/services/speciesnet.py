"""SpeciesNet integration service"""
import os
import logging
import requests
from typing import Dict, Any

try:
    from ..config import SPECIESNET_URL
except ImportError:
    from config import SPECIESNET_URL


class SpeciesNetProcessor:
    """Processor for SpeciesNet wildlife classification"""
    
    def __init__(self):
        self.confidence_threshold = 0.5
        self.server_url = SPECIESNET_URL
        self.session = requests.Session()
        # Import smart detection processor
        try:
            from .smart_detection import SmartDetectionProcessor
            self.smart_processor = SmartDetectionProcessor()
        except ImportError:
            from smart_detection import SmartDetectionProcessor
            self.smart_processor = SmartDetectionProcessor()
        # Configure connection pooling with NO retries
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # No retries, fail fast
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process an image through SpeciesNet"""
        try:
            if not os.path.exists(image_path):
                raise ValueError(f"Could not read image: {image_path}")
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
                response = self.session.post(
                    f"{self.server_url}/predict",
                    files=files,
                    timeout=(15, 120)  # 15s connect, 120s read (increased for slow processing)
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logging.error(f"SpeciesNet server error: {response.status_code} - {response.text}")
                    return {"error": f"Server error: {response.status_code}"}
        except requests.exceptions.Timeout:
            logging.error(f"SpeciesNet timeout for {image_path}")
            return {"error": "Request timeout"}
        except Exception as e:
            logging.error(f"Error processing image {image_path}: {str(e)}")
            return {"error": str(e)}
    
    def get_status(self) -> str:
        """Get SpeciesNet server status"""
        try:
            # Increased timeout for SpeciesNet health check (model loading can take time)
            # 30s connect, 60s read to handle slow startup and model initialization
            response = self.session.get(f"{self.server_url}/health", timeout=(30, 60))
            if response.status_code == 200:
                return "running"
            else:
                return "error"
        except requests.exceptions.Timeout:
            # Timeout is expected if SpeciesNet is starting up - don't treat as error
            return "starting"  # Changed from "timeout" to "starting" to be more user-friendly
        except requests.exceptions.ConnectionError:
            return "not_available"
        except Exception:
            return "error"


# Global SpeciesNet processor instance
speciesnet_processor = SpeciesNetProcessor()

