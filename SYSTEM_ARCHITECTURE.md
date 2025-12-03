# Wildlife Detection System - Architecture Overview

## System Architecture Diagram

The system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Next.js     │  │   React      │  │   API Client         │  │
│  │  Frontend    │─►│  Components  │─►│   (api.ts)           │  │
│  │  (Port 3000) │  │              │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                                                       │
│         └───────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/REST API
                              │ Server-Sent Events
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND API LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  FastAPI     │  │   Rate       │  │   CORS &              │  │
│  │  Server      │─►│   Limiting   │─►│   Authentication     │  │
│  │  (Port 8001) │  │              │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                                                       │
│         └───────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Service Calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ MotionEye    │  │ SpeciesNet   │  │   Backup             │  │
│  │ Service      │  │ Service      │  │   Service            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Notification │  │  Scheduler   │  │   Webhook             │  │
│  │ Service      │  │  Service     │  │   Service             │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ Auth         │  │  Audit       │                            │
│  │ Service      │  │  Service     │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQL Queries
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         PostgreSQL Database (with pg_mooncake)           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │  │ Detections   │  │  Cameras     │  │  Audit Logs  │   │  │
│  │  │ Table        │  │  Table       │  │  Table       │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │  │
│  │  ┌──────────────┐  ┌──────────────┐                      │  │
│  │  │ Users        │  │  Webhooks    │                      │  │
│  │  │ Table        │  │  Table       │                      │  │
│  │  └──────────────┘  └──────────────┘                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICES                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ MotionEye   │  │ SpeciesNet   │  │   ESP32 Cameras       │  │
│  │ (Docker)    │  │ (Port 8000)  │  │   (Network)          │  │
│  │ Port 8765   │  │              │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interactions

### 1. Image Detection Flow
```
Camera → MotionEye → Webhook → Backend → SpeciesNet → Database → Frontend
```

### 2. Real-time Updates
```
Frontend ←── SSE Stream ──← Backend ←── Database (polling)
```

### 3. Scheduled Tasks
```
Scheduler → Backup Service → Database
Scheduler → Audit Service → Database
Scheduler → MotionEye Service → MotionEye
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 15, React, TypeScript | User interface |
| Backend | FastAPI, Python 3.11+ | API server |
| Database | PostgreSQL 17, pg_mooncake | Data storage & analytics |
| Camera Integration | MotionEye (Docker) | Camera management |
| AI Classification | SpeciesNet (TensorFlow) | Species detection |
| Scheduling | APScheduler | Background tasks |

## API Endpoints Overview

### Detection Endpoints
- `GET /api/detections` - List detections (paginated, searchable)
- `POST /api/detections` - Create detection
- `DELETE /api/detections/{id}` - Delete detection
- `POST /api/detections/bulk-delete` - Bulk delete

### Camera Endpoints
- `GET /api/cameras` - List cameras
- `POST /api/cameras` - Create camera
- `PUT /api/cameras/{id}` - Update camera
- `POST /api/cameras/sync` - Sync from MotionEye

### Analytics Endpoints
- `GET /api/analytics/species` - Species statistics
- `GET /api/analytics/timeline` - Timeline data
- `GET /api/analytics/cameras` - Camera performance

### System Endpoints
- `GET /api/system` - System health
- `GET /api/realtime` - Server-Sent Events stream
- `POST /api/backup/create` - Manual backup
- `GET /api/backup/list` - List backups

### Webhook Endpoints
- `POST /webhook/motioneye` - MotionEye webhook receiver
- `POST /webhook/custom` - Custom webhook receiver

## Scheduled Tasks Schedule

| Task | Frequency | Time | Purpose |
|------|-----------|------|---------|
| Monthly Backup | Monthly | 1st at 2:00 AM | Database backup |
| Audit Cleanup | Monthly | 1st at 3:30 AM | Remove old logs (90+ days) |
| Backup Cleanup | Daily | Every 24 hours | Remove old backups |
| Camera Sync | Every 6 hours | Continuous | Sync with MotionEye |
| Health Checks | Hourly | Every hour | Monitor services |
| Reports | Weekly | Monday 8:00 AM | Generate reports |

## Security Features

- **Rate Limiting**: Prevents API abuse
- **CORS**: Restricts cross-origin requests
- **API Keys**: Optional authentication
- **Audit Logging**: Tracks all actions
- **Input Validation**: Prevents invalid data crashes

## Performance Features

- **Caching**: API response caching
- **Pagination**: Large dataset handling
- **Chunked Queries**: Efficient data retrieval
- **Columnstore Analytics**: Fast aggregations (pg_mooncake)
- **Server-Sent Events**: Real-time updates without polling

