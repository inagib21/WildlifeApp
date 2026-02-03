"""MotionEye integration service"""
import logging
import requests
from typing import List, Optional, Dict, Any

try:
    from ..config import MOTIONEYE_URL
except ImportError:
    from config import MOTIONEYE_URL


class MotionEyeClient:
    """Client for interacting with MotionEye API"""
    
    def __init__(self, base_url: str = MOTIONEYE_URL, username: str = None, password: str = None):
        self.base_url = base_url
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # No retries, fail fast
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Try to authenticate if credentials provided
        if username and password:
            self._authenticate(username, password)
    
    def _authenticate(self, username: str, password: str) -> bool:
        """Authenticate with MotionEye to get session cookie"""
        try:
            # MotionEye uses /login endpoint with form data
            # First, get the main page to establish session
            self.session.get(f"{self.base_url}/", timeout=(10, 15))
            
            # Then login with form data
            response = self.session.post(
                f"{self.base_url}/login",
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=(10, 15),
                allow_redirects=True
            )
            
            # Check if we got a successful response or redirect
            if response.status_code in [200, 302]:
                # Verify by trying to access a protected endpoint
                test_response = self.session.get(f"{self.base_url}/config/list", timeout=(10, 15))
                if test_response.status_code == 200:
                    logging.info("MotionEye authentication successful")
                    return True
                else:
                    logging.warning(f"MotionEye auth verification failed: {test_response.status_code}")
            else:
                logging.warning(f"MotionEye authentication failed: {response.status_code} - {response.text[:200]}")
            return False
        except Exception as e:
            logging.warning(f"MotionEye authentication error: {e}")
            return False
    
    def get_cameras(self) -> List[Dict[str, Any]]:
        """Get list of cameras from MotionEye"""
        try:
            # Increased timeout to handle slow responses (10s connect, 15s read)
            response = self.session.get(f"{self.base_url}/config/list", timeout=(10, 15))
            if response.status_code == 200:
                data = response.json()
                return data.get("cameras", [])
            return []
        except requests.exceptions.Timeout:
            # MotionEye not responding - log at warning level
            logging.warning(f"MotionEye timeout (may be slow or not responding): {self.base_url}")
            return []
        except requests.exceptions.ConnectionError:
            # MotionEye not accessible - log at warning level
            logging.warning(f"MotionEye connection error (may not be running): {self.base_url}")
            return []
        except Exception as e:
            # Only log actual errors at error level
            logging.warning(f"Error getting cameras from MotionEye: {e}")
            return []
    
    def add_camera(self, camera_config: Dict[str, Any]) -> bool:
        """Add a camera to MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/add", json=camera_config)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error adding camera to MotionEye: {e}")
            return False
    
    def update_camera(self, camera_id: int, camera_config: Dict[str, Any]) -> bool:
        """Update a camera in MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/{camera_id}/set", json=camera_config)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error updating camera in MotionEye: {e}")
            return False
    
    def delete_camera(self, camera_id: int) -> bool:
        """Delete a camera from MotionEye"""
        try:
            response = self.session.post(f"{self.base_url}/config/{camera_id}/remove")
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error deleting camera from MotionEye: {e}")
            return False
    
    def get_camera_stream_url(self, camera_id: int) -> str:
        """Get the stream URL for a camera"""
        return f"http://localhost:8765/picture/{camera_id}/current/"
    
    def get_camera_mjpeg_url(self, camera_id: int) -> str:
        """Get the MJPEG stream URL for a camera"""
        return f"http://localhost:8765/picture/{camera_id}/current/"
    
    def get_camera_config(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get full camera configuration from MotionEye"""
        try:
            # Increased timeout for config retrieval (10s connect, 15s read)
            response = self.session.get(f"{self.base_url}/config/{camera_id}/get", timeout=(10, 15))
            if response.status_code == 200:
                return response.json()
            else:
                logging.warning(f"MotionEye API returned status {response.status_code} for camera {camera_id}: {response.text[:200]}")
            return None
        except Exception as e:
            logging.error(f"Error getting camera config from MotionEye: {e}", exc_info=True)
            return None
    
    def set_motion_settings(self, camera_id: int, motion_settings: Dict[str, Any]) -> bool:
        """Update motion detection settings for a camera"""
        try:
            # Get current config first
            current_config = self.get_camera_config(camera_id)
            if not current_config:
                return False
            
            # Update with motion settings
            current_config.update(motion_settings)
            
            # Send updated config with increased timeout (10s connect, 15s read)
            response = self.session.post(f"{self.base_url}/config/{camera_id}/set", json=current_config, timeout=(10, 15))
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error setting motion settings in MotionEye: {e}")
            return False
    
    def get_status(self) -> str:
        """Get MotionEye server status"""
        try:
            # Increased timeout for status check (10s connect, 15s read)
            response = self.session.get(f"{self.base_url}/config/list", timeout=(10, 15))
            if response.status_code == 200:
                return "running"
            else:
                return "error"
        except requests.exceptions.Timeout:
            return "timeout"
        except requests.exceptions.ConnectionError:
            return "not_available"
        except Exception:
            return "error"


# Global MotionEye client instance
motioneye_client = MotionEyeClient()

