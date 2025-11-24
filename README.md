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
- Advanced analytics: detections per hour/day, top species, unique species count

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

1. **Navigate to the `scripts/` folder** and **double-click `wildlife-app-control.bat`** - This opens a menu-driven control center
2. Select option **`[1] Start All Services`** - This will:
   - Check and start Docker (if needed)
   - Start Docker services (PostgreSQL & MotionEye)
   - Launch Backend server (port 8001)
   - Launch Frontend server (port 3000)
3. When done, select option **`[2] Stop All Services`** to cleanly shut everything down

**Additional script:**
- `scripts/stop-wildlife-app.bat` - Quick one-click shutdown (if you need to stop without opening control center)

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

### 7. Run the frontend & backend together (Next.js) & (FastAPI)
```sh
cd wildlife-app
npm run dev:all
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/docs
- MotionEye: http://localhost:8765

### 8. OPTIONAL: Run services separately

**Backend only:**
```sh
cd wildlife-app/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Frontend only:**
```sh
cd wildlife-app
npm run dev
```

## Development
- **Backend code:** `wildlife-app/backend/`
- **Frontend code:** `wildlife-app/`
- **Components:** `wildlife-app/components/`
- **API types:** `wildlife-app/types/`
- **Startup Scripts:** `scripts/` (Windows batch scripts for easy service management)

## Startup Scripts (Windows)

All startup and shutdown scripts are organized in the `scripts/` folder:

- **`scripts/wildlife-app-control.bat`** ⭐ **MAIN SCRIPT** - Interactive control center with menu (Start/Stop/Status)
- **`scripts/stop-wildlife-app.bat`** - Quick one-click shutdown (optional)

The control center automatically:
- Checks for Docker and starts it if needed
- Starts Docker services (PostgreSQL & MotionEye)
- Launches Backend and Frontend in separate windows
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
- **Manual Camera Setup:** If you need to configure ESP32-CAM modules manually or set up custom camera hardware, refer to the [ESP32SETUP repository](https://github.com/inagib21/ESP32SETUP) for detailed PlatformIO setup instructions, hardware connections, and firmware configuration.

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

See `wildlife-app/backend/AUDIT_LOGS_GUIDE.md` for detailed documentation.

## Future Improvements

See `FUTURE_IMPROVEMENTS.md` for a comprehensive list of recommended enhancements including:
- Email/SMS notifications for detections
- Automated database backups
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