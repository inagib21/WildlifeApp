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
                    timeout=(10, 30)  # 10s connect, 30s read (SpeciesNet needs more time)
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
            response = self.session.get(f"{self.server_url}/health", timeout=(5, 5))
            if response.status_code == 200:
                return "running"
            else:
                return "error"
        except requests.exceptions.Timeout:
            return "timeout"
        except Exception:
            return "not_available"


# Global SpeciesNet processor instance
speciesnet_processor = SpeciesNetProcessor()

