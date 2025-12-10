# Wildlife Detection App

> **Note:** This setup and all instructions are for **Windows** users. Paths, venv, and commands are Windows-specific. For Linux/Mac, adapt accordingly.

A full-stack platform for automated wildlife monitoring and analytics from camera trap images. This project demonstrates expertise in designing and integrating modern cloud-native systems—combining Python (FastAPI), React (Next.js), Docker, and real-time analytics with PostgreSQL. It features seamless camera integration, live dashboards, and AI-powered species recognition, all engineered with a focus on reliability, scalability, and user experience. The codebase highlights strengths in problem-solving, cross-stack development, and delivering robust, real-world solutions.

A full-stack wildlife detection and analytics platform for camera trap images, using:
- **FastAPI** (Python backend)
- **Next.js** (React frontend)
- **PostgreSQL** (with [pg_mooncake](https://github.com/mooncakelabs/pg_mooncake) for analytics)
- **MotionEye** for camera integration
- **SpeciesNet** (from [google/cameratrapai](https://github.com/google/cameratrapai)) for wildlife classification

## Features
- Real-time wildlife detection and classification from camera trap images
- FastAPI backend with REST and analytics endpoints
- Next.js frontend dashboard (React, TypeScript, Tailwind)
- PostgreSQL with columnstore analytics (pg_mooncake)
- MotionEye camera integration for live streams and image capture
- Real-time system health and live updates
- Chunked and paginated detection queries for large datasets
- Advanced analytics dashboard with interactive charts (species, timeline, camera performance)
- Automated database backups with scheduled tasks
- Email notifications for high-confidence detections
- Disk space monitoring and alerts
- Data export (CSV/JSON) with filtering
- Full-text search across detections
- Bulk operations (delete multiple detections)
- Image compression and thumbnail generation
- Comprehensive audit logging system
- Interactive API documentation (Swagger/ReDoc)
- Robust API validation with error handling (prevents crashes from invalid data)
- Webhook support for external integrations
- **Enhanced Error Detection:** Automatic error categorization, detailed logging, and troubleshooting suggestions
- **Diagnostic Tools:** Built-in diagnostic scripts for system health and error analysis
- **ESP32 Webcam Support:** Easy integration scripts for ESP32-based cameras
- **Advanced keyboard shortcuts** with double-key sequences for safe, intentional navigation (see [`wildlife-app/KEYBOARD_SHORTCUTS.md`](wildlife-app/KEYBOARD_SHORTCUTS.md))
- **Automated database backups** with scheduled monthly backups and retention policies (see [`wildlife-app/STORAGE_MANAGEMENT.md`](wildlife-app/STORAGE_MANAGEMENT.md))
- **Disk space monitoring** with alerts when storage exceeds 90% capacity
  - Double-key navigation: `DD` (Detections), `CC` (Cameras), `AA` (Analytics), `GG` (Dashboard)
  - Search: `Ctrl+K` to focus search anywhere
  - General: `Ctrl+R` (Refresh), `B` (Back), `F` (Forward)
  - Help: `Shift+?` for quick help, `Ctrl+Shift+?` for full documentation

## Stack & Tools
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, asyncpg, psutil, dotenv
- **Frontend:** Next.js 15+, React, TypeScript, Tailwind CSS
- **Database:** PostgreSQL 17 (with pg_mooncake for columnstore analytics)
- **Camera Integration:** MotionEye (Docker)
- **Wildlife Classification:** [SpeciesNet](https://github.com/google/cameratrapai) (Google AI ensemble for camera trap images)
- **Docker Compose:** For database and MotionEye orchestration

## Quick Start

### 🚀 Easiest Method: Use the Control Center (Recommended)

**For Windows users**, we've created convenient startup scripts in the `scripts/` folder:

1. **Navigate to the `scripts/` folder** and **double-click `control.bat`** - This opens a menu-driven control center
2. Select option **`[1] Start All Services`** - This will:
   - Check and start Docker (if needed)
   - Start Docker services (PostgreSQL & MotionEye)
   - Launch SpeciesNet server (port 8000)
   - Launch Backend server (port 8001)
   - Launch Frontend server (port 3000)
3. When done, select option **`[2] Stop All Services`** to cleanly shut everything down

**Additional scripts:**
- `scripts/start-backend-only.bat` - Quick script to start only the backend server (useful for debugging)
- `scripts/QUICK_START.md` - Quick reference guide for starting services

See `scripts/README.md` for detailed information about all available scripts.

### Manual Setup (Alternative)

### 1. Clone the repository
```sh
git clone https://github.com/inagib21/WildlifeApp.git
cd Wildlife
```

### 2. Install Python dependencies
- Use the provided `requirements.txt` (auto-generated from the working environment):
```sh
pip install -r wildlife-app/backend/requirements.txt
```

### 3. Install Node.js dependencies
```sh
cd wildlife-app
npm install
```

### 4. Start the services (Docker Compose)
- This will start PostgreSQL (with pg_mooncake) and MotionEye:
```sh
docker-compose up -d
```

### 5. Initialize and configure each camera on their local addresses
- Refer to microtik for addresses: http://192.168.88.1/
- Example: https://192.168.88.22/

### 6. Configure the cameras on MotionEye
- MotionEye: http://localhost:8765

### 7. Run the services

**Option A: Run all services together (Recommended)**
```sh
cd wildlife-app
npm run dev:all
```
This starts:
- SpeciesNet server (port 8000)
- Backend server (port 8001)
- Frontend server (port 3000)

**Option B: Run services separately**

**SpeciesNet server:**
```sh
cd wildlife-app/backend
python -m uvicorn speciesnet_server:app --host 0.0.0.0 --port 8000 --workers 4
```

**Backend server:**
```sh
cd wildlife-app/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Frontend server:**
```sh
cd wildlife-app
npm run dev
```

**Service URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/docs
- SpeciesNet: http://localhost:8000
- MotionEye: http://localhost:8765

## Development
- **Backend code:** `wildlife-app/backend/`
- **Frontend code:** `wildlife-app/`
- **Components:** `wildlife-app/components/`
- **API types:** `wildlife-app/types/`
- **Startup Scripts:** `scripts/` (Windows batch scripts for easy service management)
- **Diagnostic Tools:** `wildlife-app/backend/diagnose_detections.py`, `wildlife-app/backend/check_webhook_connectivity.py`

## Troubleshooting

### No Detections Appearing
1. **Check Backend Logs:** Look for `"MotionEye webhook received"` messages
2. **Run Diagnostic:** `python wildlife-app/backend/diagnose_detections.py`
3. **Check Error Statistics:** `GET /api/debug/error-statistics`
4. **Verify MotionEye:** Ensure MotionEye is running and webhooks are configured
5. **Check Webhook URL:** Should be `http://host.docker.internal:8001/api/motioneye/webhook` (not `localhost`)

### Common Issues
- **Webhook Errors:** Check error statistics endpoint for categorized errors
- **File Not Found:** Verify `motioneye_media` directory exists and is accessible
- **SpeciesNet Errors:** Check SpeciesNet server status and connectivity
- **Database Errors:** Verify PostgreSQL is running and accessible

See `wildlife-app/CAMERA_DETECTION_TROUBLESHOOTING.md` for detailed troubleshooting guide.

## Recent Improvements

### Error Detection & Diagnostics (Latest)
- **Enhanced Error Detection System:** Comprehensive error categorization and tracking
  - Automatic error categorization (file_path_error, database_error, speciesnet_error, etc.)
  - Detailed error logging with full context and troubleshooting suggestions
  - Error statistics endpoint: `GET /api/debug/error-statistics`
  - All errors tracked in audit logs with actionable suggestions
  - See [`wildlife-app/backend/ERROR_DETECTION_IMPROVEMENTS.md`](wildlife-app/backend/ERROR_DETECTION_IMPROVEMENTS.md) for details

- **Webhook Bug Fixes:**
  - Fixed critical bug where `file_path` was accessed before extraction
  - Improved webhook payload parsing with better error handling
  - Enhanced missing data detection with payload analysis

- **Diagnostic Tools:**
  - `diagnose_detections.py` - Comprehensive detection system diagnostic
  - `check_webhook_connectivity.py` - Webhook connectivity testing
  - Error statistics API endpoint for monitoring

### Code Quality & Architecture
- **Enhanced API Validation:** Improved validation for `/detections` and `/cameras` endpoints to handle edge cases gracefully
- **Better Error Handling:** Invalid data is now skipped with detailed logging instead of crashing the endpoint
- **Improved Scripts:** Updated control scripts with better health checks and status reporting
- **Modular Architecture:** Refactored backend into organized router modules (13 routers, 70+ endpoints)
- **Settings Tab Fix:** Fixed duplicate/non-functional settings tab, now properly shows read-only configuration

### Camera Integration
- **ESP32 Webcam Support:** Added scripts and guides for connecting ESP32 webcams
  - `scripts/find-esp32-stream-url.ps1` - Discover ESP32 stream URLs
  - `scripts/add-esp32-camera.ps1` - Automate camera addition
  - See [`wildlife-app/ESP32_WEBCAM_SETUP.md`](wildlife-app/ESP32_WEBCAM_SETUP.md) for setup guide

- **MotionEye Webhook Fix:** Updated all camera configs to use `host.docker.internal` for Docker connectivity

## Startup Scripts (Windows)

All startup and shutdown scripts are organized in the `scripts/` folder:

- **`scripts/control.bat`** ⭐ **MAIN SCRIPT** - Interactive control center with menu (Start/Stop/Status/Restart)
- **`scripts/start-backend-only.bat`** - Quick script to start only the backend server (useful for debugging)

The control center automatically:
- Checks for Docker and starts it if needed
- Starts Docker services (PostgreSQL & MotionEye)
- Launches SpeciesNet server (port 8000)
- Launches Backend server (port 8001)
- Launches Frontend server (port 3000)
- Runs health checks to verify services are running
- Provides clear status messages

See `scripts/README.md` for detailed documentation.

## Environment Variables
- See `.env` or set:
  - `NEXT_PUBLIC_API_URL` (frontend, default: http://localhost:8001)
  - `MOTIONEYE_URL` (backend, default: http://localhost:8765)
  - `SPECIESNET_URL` (backend, default: http://localhost:8000)

## Database & Analytics
- Uses PostgreSQL 17 with [pg_mooncake](https://github.com/mooncakelabs/pg_mooncake) for real-time analytics and columnstore tables.
- Schema is auto-created by the backend on startup.
- Analytics endpoints use columnstore mirrors for fast aggregation (detections per hour/day, top species, unique species count).

## Camera Integration
- **MotionEye** is used for camera management, live streaming, and image capture.
- Camera configuration files are in `motioneye_config/`.
- **ESP32 Webcam Support:** Scripts available for easy ESP32 camera integration:
  - `scripts/find-esp32-stream-url.ps1` - Discover ESP32 stream URLs automatically
  - `scripts/add-esp32-camera.ps1` - Add ESP32 cameras via API
  - See [`wildlife-app/ESP32_WEBCAM_SETUP.md`](wildlife-app/ESP32_WEBCAM_SETUP.md) for complete setup guide
- **Manual Camera Setup:** If you need to configure ESP32-CAM modules manually or set up custom camera hardware, refer to the [ESP32SETUP repository](https://github.com/inagib21/ESP32SETUP) for detailed PlatformIO setup instructions, hardware connections, and firmware configuration.
- **Webhook Configuration:** MotionEye webhooks are configured to use `host.docker.internal:8001` for Docker compatibility

## Wildlife Classification
- **SpeciesNet** (from [google/cameratrapai](https://github.com/google/cameratrapai)) is used for AI-based species classification.
- The backend calls a local SpeciesNet server for predictions.
- For more on SpeciesNet, see the [official repo](https://github.com/google/cameratrapai).

## Audit Logging

The system includes comprehensive audit logging to track all system changes and activities. Every action is logged with:
- **Who**: IP address and user agent
- **What**: Action type and resource details
- **When**: Precise timestamp
- **Success/Failure**: Status and error messages

**Access Audit Logs:**
- **Frontend UI**: Navigate to "Audit Logs" in the sidebar or visit `http://localhost:3000/audit-logs`
- **API**: `GET http://localhost:8001/api/audit-logs` with optional filters

**Automatic Cleanup**: Audit logs are automatically cleaned up monthly (1st of each month at 3:30 AM) with a 90-day retention policy.

See `wildlife-app/backend/AUDIT_LOGS_GUIDE.md` for detailed documentation.

## Error Detection & Diagnostics

The system includes advanced error detection and diagnostic capabilities:

**Error Categories:**
- `file_path_error` - File path processing issues
- `database_error` - Database operation failures
- `speciesnet_error` - SpeciesNet processing failures
- `permission_error` - File access permission issues
- `not_found_error` - Resource not found errors

**Diagnostic Tools:**
- `python wildlife-app/backend/diagnose_detections.py` - Comprehensive detection system check
- `GET /api/debug/error-statistics?hours=24` - Error statistics and analysis
- `GET /api/debug/status` - System status and health check

**Error Tracking:**
- All errors are automatically logged to audit logs
- Each error includes troubleshooting suggestions
- Error statistics available via API endpoint

See `wildlife-app/backend/ERROR_DETECTION_IMPROVEMENTS.md` for detailed documentation.

## Future Improvements

See `FUTURE_IMPROVEMENTS.md` for a comprehensive list of recommended enhancements including:
- Email/SMS notifications for detections
- Disk space management
- Data export and reporting
- And many more...

## Requirements
- All Python dependencies are listed in `requirements.txt` (auto-generated from the working environment).
- Node.js dependencies are in `package.json`.

## Credits
- **SpeciesNet** and the core wildlife classification models are from [google/cameratrapai](https://github.com/google/cameratrapai) (Apache-2.0 License).
- This project integrates and extends these models for a full-stack, real-time analytics dashboard.

## License
MIT or as specified. See [google/cameratrapai](https://github.com/google/cameratrapai) for model license details.