# Wildlife Detection System - UML Diagrams

This document contains UML diagrams describing the Wildlife Detection System architecture and workflows.

## Diagram Files

1. **SYSTEM_ARCHITECTURE.puml** - Component architecture diagram showing all system components and their relationships
2. **SYSTEM_WORKFLOW.puml** - Sequence/workflow diagrams showing data flow and interactions

## How to View the Diagrams

### Option 1: Online Viewers (Recommended)
1. Go to [PlantUML Online Server](http://www.plantuml.com/plantuml/uml/)
2. Copy the contents of either `.puml` file
3. Paste into the editor
4. View the rendered diagram

### Option 2: VS Code Extension
1. Install the "PlantUML" extension in VS Code
2. Open the `.puml` file
3. Press `Alt+D` (or `Cmd+D` on Mac) to preview

### Option 3: Command Line
```bash
# Install PlantUML (requires Java)
# Windows: choco install plantuml
# Mac: brew install plantuml
# Linux: apt-get install plantuml

# Generate PNG
plantuml SYSTEM_ARCHITECTURE.puml
plantuml SYSTEM_WORKFLOW.puml

# Generate SVG
plantuml -tsvg SYSTEM_ARCHITECTURE.puml
plantuml -tsvg SYSTEM_WORKFLOW.puml
```

### Option 4: Mermaid Alternative
If you prefer Mermaid format, you can use online tools like:
- [Mermaid Live Editor](https://mermaid.live/)
- [GitHub](https://github.com) (Mermaid is natively supported in markdown)

## Diagram Descriptions

### SYSTEM_ARCHITECTURE.puml
Shows the complete system architecture including:
- **Frontend Layer**: Next.js, React components, API client
- **Backend API Layer**: FastAPI server, endpoints, middleware
- **Business Logic Layer**: All service modules
- **Data Layer**: PostgreSQL database with tables
- **External Services**: MotionEye, SpeciesNet, cameras
- **Scheduled Tasks**: All automated background jobs

### SYSTEM_WORKFLOW.puml
Shows detailed workflow sequences for:
- **Image Capture & Detection**: How images flow from cameras to detections
- **Motion Detection & Processing**: Webhook → SpeciesNet → Database flow
- **Real-time Updates**: Server-Sent Events (SSE) flow
- **Scheduled Tasks**: Backup, cleanup, sync, health checks
- **User Operations**: Search, delete, analytics
- **Backup & Restore**: Manual backup operations
- **Webhook Integration**: External webhook processing

## System Overview

```
┌─────────────────┐
│   ESP32 Cameras │
└────────┬────────┘
         │ Images
         ▼
┌─────────────────┐
│   MotionEye     │───Webhooks───►┌──────────────┐
│   (Docker)      │               │ FastAPI      │
└─────────────────┘               │ Backend      │
                                  └──────┬───────┘
                                         │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │ SpeciesNet   │   │ PostgreSQL   │   │ Next.js     │
            │ (Port 8000)  │   │ Database     │   │ Frontend    │
            └──────────────┘   └──────────────┘   └──────────────┘
```

## Key Components

### Frontend (Next.js)
- **Port**: 3000
- **Technology**: React, TypeScript, Tailwind CSS
- **Features**: Real-time dashboard, analytics charts, detection management

### Backend (FastAPI)
- **Port**: 8001
- **Technology**: Python, FastAPI, SQLAlchemy
- **Features**: REST API, webhooks, scheduled tasks, authentication

### MotionEye
- **Port**: 8765
- **Technology**: Docker container
- **Features**: Camera management, live streaming, motion detection

### SpeciesNet
- **Port**: 8000
- **Technology**: Python, TensorFlow
- **Features**: AI-powered wildlife classification

### PostgreSQL
- **Port**: 5432
- **Technology**: PostgreSQL 17 with pg_mooncake
- **Features**: Data storage, analytics, columnstore tables

## Data Flow Summary

1. **Camera** → Captures image
2. **MotionEye** → Detects motion, sends webhook
3. **Backend** → Receives webhook, fetches image
4. **SpeciesNet** → Classifies species
5. **Backend** → Stores detection in database
6. **Frontend** → Displays via real-time updates

## Scheduled Tasks

- **Monthly Backup**: 1st of month at 2:00 AM
- **Audit Log Cleanup**: 1st of month at 3:30 AM (90-day retention)
- **Backup Cleanup**: Every 24 hours
- **Camera Sync**: Every 6 hours
- **Health Checks**: Every hour
- **Report Generation**: Monday at 8:00 AM

