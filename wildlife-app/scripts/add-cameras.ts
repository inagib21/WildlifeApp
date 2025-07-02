import axios from 'axios';

const cameras = [
  {
    camera_name: "Camera 1",
    netcam_url: "rtsp://192.168.88.22:8554/unicast",
    width: 640,
    height: 480,
    framerate: 30,
    stream_quality: 75,
    stream_maxrate: 1000,
    stream_localhost: false,
    stream_auth_method: "none",
    detection_enabled: true,
    detection_threshold: 50,
    detection_smart_mask_speed: 5
  },
  {
    camera_name: "Camera 2",
    netcam_url: "rtsp://192.168.88.58:554",
    width: 640,
    height: 480,
    framerate: 30,
    stream_quality: 75,
    stream_maxrate: 1000,
    stream_localhost: false,
    stream_auth_method: "none",
    detection_enabled: true,
    detection_threshold: 50,
    detection_smart_mask_speed: 5
  }
];

async function addCameras() {
  for (const camera of cameras) {
    try {
      await axios.post('http://localhost:8000/cameras', camera);
      console.log(`Added camera: ${camera.camera_name}`);
    } catch (error: any) {
      console.error(`Failed to add camera ${camera.camera_name}:`, error.response?.data?.detail || error.message);
    }
  }
}

addCameras(); 