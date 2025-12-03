# Wildlife Detection System - Architecture & Workflow Diagrams

## System Architecture Diagram

```mermaid
graph TB
    subgraph "Frontend Layer"
        Frontend[Next.js Frontend<br/>Port 3000]
        Components[React Components]
        APIClient[API Client]
        RealtimeHooks[Real-time Hooks]
    end

    subgraph "Backend API Layer"
        Backend[FastAPI Server<br/>Port 8001]
        Endpoints[API Endpoints]
        RateLimit[Rate Limiting]
        CORS[CORS Middleware]
        Auth[Authentication]
    end

    subgraph "Business Logic Layer"
        MotionEyeService[MotionEye Service]
        SpeciesNetService[SpeciesNet Service]
        BackupService[Backup Service]
        NotificationService[Notification Service]
        SchedulerService[Scheduler Service]
        WebhookService[Webhook Service]
        AuthService[Auth Service]
        AuditService[Audit Service]
    end

    subgraph "Data Layer"
        Database[(PostgreSQL Database<br/>with pg_mooncake)]
        DetectionsDB[Detections Table]
        CamerasDB[Cameras Table]
        AuditDB[Audit Logs Table]
        UsersDB[Users Table]
        WebhooksDB[Webhooks Table]
    end

    subgraph "External Services"
        MotionEye[MotionEye<br/>Docker<br/>Port 8765]
        SpeciesNet[SpeciesNet Server<br/>Port 8000]
        Cameras[ESP32 Cameras]
        Notifications[Email/SMS]
    end

    subgraph "Scheduled Tasks"
        MonthlyBackup[Monthly Backup<br/>1st at 2 AM]
        AuditCleanup[Audit Cleanup<br/>1st at 3:30 AM]
        BackupCleanup[Backup Cleanup<br/>Every 24h]
        CameraSync[Camera Sync<br/>Every 6h]
        HealthChecks[Health Checks<br/>Every hour]
        Reports[Report Generation<br/>Monday 8 AM]
    end

    Frontend --> Components
    Frontend --> APIClient
    Frontend --> RealtimeHooks
    APIClient --> Backend
    RealtimeHooks --> Backend

    Backend --> Endpoints
    Backend --> RateLimit
    Backend --> CORS
    Backend --> Auth
    Endpoints --> MotionEyeService
    Endpoints --> SpeciesNetService
    Endpoints --> BackupService
    Endpoints --> NotificationService
    Endpoints --> WebhookService
    Endpoints --> AuthService
    Endpoints --> AuditService
    Endpoints --> Database

    MotionEyeService --> MotionEye
    SpeciesNetService --> SpeciesNet
    BackupService --> Database
    NotificationService --> Notifications
    WebhookService --> Notifications
    AuthService --> Database
    AuditService --> Database

    DetectionsDB --> Database
    CamerasDB --> Database
    AuditDB --> Database
    UsersDB --> Database
    WebhooksDB --> Database

    SchedulerService --> MonthlyBackup
    SchedulerService --> AuditCleanup
    SchedulerService --> BackupCleanup
    SchedulerService --> CameraSync
    SchedulerService --> HealthChecks
    SchedulerService --> Reports
    MonthlyBackup --> BackupService
    AuditCleanup --> Database
    BackupCleanup --> BackupService
    CameraSync --> MotionEyeService
    HealthChecks --> MotionEye
    HealthChecks --> SpeciesNet
    Reports --> Database

    MotionEye --> Cameras
    MotionEye -.Webhooks.-> Backend
    SpeciesNet -.API Calls.-> Backend

    style Frontend fill:#e1f5ff
    style Backend fill:#fff4e1
    style Database fill:#e8f5e9
    style MotionEye fill:#f3e5f5
    style SpeciesNet fill:#f3e5f5
    style SchedulerService fill:#fff9c4
```

## Image Detection Workflow

```mermaid
sequenceDiagram
    participant Camera as ESP32 Camera
    participant MotionEye as MotionEye
    participant Backend as FastAPI Backend
    participant SpeciesNet as SpeciesNet AI
    participant Database as PostgreSQL
    participant Frontend as Next.js Frontend
    participant User as User

    Camera->>MotionEye: Capture Image
    MotionEye->>MotionEye: Detect Motion
    MotionEye->>Backend: POST /webhook/motioneye
    activate Backend
    
    Backend->>MotionEye: GET Image File
    MotionEye-->>Backend: Image Data
    
    Backend->>SpeciesNet: POST /process-image
    activate SpeciesNet
    SpeciesNet->>SpeciesNet: AI Classification
    SpeciesNet-->>Backend: Species + Confidence
    deactivate SpeciesNet
    
    Backend->>Database: INSERT Detection
    Database-->>Backend: Confirmation
    
    Backend->>Backend: Log Audit Event
    Backend-->>MotionEye: 200 OK
    deactivate Backend
    
    Frontend->>Backend: SSE Connection
    Backend->>Database: Query Latest
    Database-->>Backend: New Detections
    Backend-->>Frontend: Push Update
    Frontend-->>User: Display Detection
```

## Scheduled Tasks Workflow

```mermaid
sequenceDiagram
    participant Scheduler as APScheduler
    participant BackupService as Backup Service
    participant AuditService as Audit Service
    participant MotionEyeService as MotionEye Service
    participant Database as PostgreSQL
    participant MotionEye as MotionEye

    Note over Scheduler: Monthly Tasks (1st of month)
    
    Scheduler->>BackupService: Monthly Backup (2:00 AM)
    activate BackupService
    BackupService->>Database: pg_dump
    Database-->>BackupService: Backup File
    BackupService->>BackupService: Save to backups/
    BackupService->>BackupService: Cleanup old backups
    deactivate BackupService
    
    Scheduler->>AuditService: Audit Cleanup (3:30 AM)
    activate AuditService
    AuditService->>Database: DELETE logs > 90 days
    Database-->>AuditService: Cleanup Complete
    deactivate AuditService
    
    Note over Scheduler: Periodic Tasks
    
    Scheduler->>MotionEyeService: Camera Sync (Every 6h)
    activate MotionEyeService
    MotionEyeService->>MotionEye: GET /config/list
    MotionEye-->>MotionEyeService: Camera List
    MotionEyeService->>Database: UPDATE cameras
    Database-->>MotionEyeService: Sync Complete
    deactivate MotionEyeService
    
    Scheduler->>BackupService: Backup Cleanup (Every 24h)
    activate BackupService
    BackupService->>BackupService: Remove old backups
    deactivate BackupService
```

## Real-time Updates Flow

```mermaid
sequenceDiagram
    participant User as User
    participant Frontend as Next.js Frontend
    participant Backend as FastAPI Backend
    participant Database as PostgreSQL

    User->>Frontend: Open Dashboard
    Frontend->>Backend: GET /api/realtime (SSE)
    activate Backend
    
    loop Every 5 seconds
        Backend->>Database: Query Latest Detections
        Database-->>Backend: New Data
        Backend-->>Frontend: Push Update (SSE)
        Frontend-->>User: Update UI
    end
    
    User->>Frontend: Close Dashboard
    Frontend->>Backend: Close SSE Connection
    deactivate Backend
```

## System Components Overview

```mermaid
graph LR
    subgraph "Client Layer"
        A[User Browser]
    end
    
    subgraph "Application Layer"
        B[Next.js Frontend<br/>React + TypeScript]
        C[FastAPI Backend<br/>Python]
    end
    
    subgraph "Service Layer"
        D[MotionEye<br/>Camera Manager]
        E[SpeciesNet<br/>AI Classifier]
    end
    
    subgraph "Data Layer"
        F[(PostgreSQL<br/>Database)]
    end
    
    subgraph "Infrastructure"
        G[Docker<br/>Containers]
        H[Scheduler<br/>Background Tasks]
    end
    
    A -->|HTTP| B
    B -->|REST API| C
    B -->|SSE| C
    C -->|Webhooks| D
    C -->|API Calls| E
    C -->|SQL| F
    D -->|Images| C
    E -->|Predictions| C
    H -->|Scheduled Jobs| C
    D -.->|Docker| G
    F -.->|Docker| G
    
    style A fill:#e3f2fd
    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#f3e5f5
    style E fill:#f3e5f5
    style F fill:#e8f5e9
    style G fill:#fff9c4
    style H fill:#fff9c4
```

## Data Flow Summary

1. **Image Capture**: ESP32 Camera → MotionEye
2. **Motion Detection**: MotionEye detects motion, triggers webhook
3. **Webhook Processing**: Backend receives webhook, fetches image
4. **AI Classification**: Backend sends image to SpeciesNet
5. **Data Storage**: Backend stores detection in PostgreSQL
6. **Real-time Updates**: Frontend receives updates via Server-Sent Events
7. **User Display**: Frontend displays detections in dashboard

## Key Technologies

- **Frontend**: Next.js 15, React, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.11+, SQLAlchemy
- **Database**: PostgreSQL 17, pg_mooncake (columnstore analytics)
- **Camera Integration**: MotionEye (Docker)
- **AI Classification**: SpeciesNet (TensorFlow)
- **Scheduling**: APScheduler
- **Real-time**: Server-Sent Events (SSE)

## Port Configuration

| Service | Port | Protocol |
|---------|------|----------|
| Next.js Frontend | 3000 | HTTP |
| FastAPI Backend | 8001 | HTTP |
| SpeciesNet Server | 8000 | HTTP |
| MotionEye | 8765 | HTTP |
| PostgreSQL | 5432 | TCP |

