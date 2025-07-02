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

### 1. Clone the repository
```sh
git clone https://github.com/inagib21/WildlifeApp.git
cd wildlife-app
```

### 2. Install Python dependencies
- Use the provided `requirements.txt` (auto-generated from the working environment):
```sh
pip install -r requirements.txt
```

### 3. Start the services (Docker Compose)
- This will start PostgreSQL (with pg_mooncake) and MotionEye:
```sh
docker-compose up -d
```

### 4. Run the backend (FastAPI)
```sh
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Run the frontend (Next.js)
```sh
cd ..
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8001/docs
- MotionEye: http://localhost:8765

## Development
- **Backend code:** `backend/`
- **Frontend code:** `wildlife-app/`
- **Components:** `components/`
- **API types:** `types/`
- **Scripts:** `scripts/`

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

## Wildlife Classification
- **SpeciesNet** (from [google/cameratrapai](https://github.com/google/cameratrapai)) is used for AI-based species classification.
- The backend calls a local SpeciesNet server for predictions.
- For more on SpeciesNet, see the [official repo](https://github.com/google/cameratrapai).

## Requirements
- All Python dependencies are listed in `requirements.txt` (auto-generated from the working environment).
- Node.js dependencies are in `package.json`.

## Credits
- **SpeciesNet** and the core wildlife classification models are from [google/cameratrapai](https://github.com/google/cameratrapai) (Apache-2.0 License).
- This project integrates and extends these models for a full-stack, real-time analytics dashboard.

## License
MIT or as specified. See [google/cameratrapai](https://github.com/google/cameratrapai) for model license details. 