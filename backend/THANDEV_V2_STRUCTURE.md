# Thandev v2 Backend Structure

## Overview

Thandev v2 is a complete rewrite with a clean, modular architecture using:
- **FastAPI** for the REST API
- **PostgreSQL** via SQLAlchemy ORM
- **Celery + Redis** for background job processing
- **Alembic** for database migrations

## Directory Structure

```
backend/app/
├── main.py                 # FastAPI application entry point
├── core/                   # Core application components
│   ├── config.py          # Settings and configuration
│   └── database.py        # SQLAlchemy setup and session management
├── models/                # SQLAlchemy ORM models
│   ├── user.py           # User model
│   ├── tenant.py         # Tenant model (multi-tenancy)
│   ├── project.py        # Project model
│   ├── scan.py           # ScanJob model
│   └── finding.py        # Finding and ToolResult models
├── schemas/               # Pydantic schemas for API
│   ├── project.py        # Project request/response schemas
│   └── scan.py           # Scan request/response schemas
├── api/                   # API routers
│   ├── projects.py       # Project management endpoints
│   └── scans.py          # Scan management endpoints
├── services/             # Business logic and orchestration
│   ├── scan_orchestrator.py  # Scan job orchestration
│   ├── tools.py          # Security tool execution
│   └── ai/               # AI services (placeholder)
└── tasks/                 # Celery tasks
    └── celery_app.py     # Celery configuration and tasks
```

## Core Models

### User
- Authentication and authorization
- Belongs to a Tenant
- Owns Projects

### Tenant
- Multi-tenancy support
- Subscription plan management (FREE, BASIC, PRO, ENTERPRISE)
- Plan limits (max projects, scans per month, concurrent scans)

### Project
- Represents a target to scan
- Has target_url and optional repo_url
- Belongs to a User and Tenant
- Has many ScanJobs

### ScanJob
- Represents a security scan execution
- Has scan_level (basic, pro, advanced)
- Tracks status (pending, queued, running, completed, failed, cancelled)
- Linked to Celery task via celery_task_id
- Has many Findings and ToolResults

### Finding
- Security vulnerability or issue
- Has severity (critical, high, medium, low, info)
- Can have CVE/CWE information
- Linked to a ScanJob

### ToolResult
- Raw output from security scanning tools
- Stores tool name, output, exit code, execution time
- Linked to a ScanJob

## API Endpoints

### Projects
- `POST /api/projects` - Create a new project
- `GET /api/projects` - List all projects (paginated)
- `GET /api/projects/{project_id}` - Get a specific project

### Scans
- `POST /api/scans` - Create a new scan job
- `GET /api/scans/{scan_id}` - Get scan status, findings, and summary

## Configuration

Settings are loaded from environment variables via `app/core/config.py`:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `CELERY_BROKER_URL` - Celery broker URL (defaults to REDIS_URL)
- `CELERY_RESULT_BACKEND` - Celery result backend (defaults to REDIS_URL)
- `SECRET_KEY` - Secret key for JWT tokens
- `CORS_ORIGINS` - Allowed CORS origins (comma-separated)
- `ENVIRONMENT` - Environment (development, production)
- `DEBUG` - Debug mode (true/false)

## Database Migrations

Alembic is configured for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Celery Tasks

Background tasks are defined in `app/tasks/celery_app.py`:

- `run_scan_task` - Executes a security scan
- `ingest_nvd` - Ingest NVD data (TODO)
- `ingest_kev` - Ingest KEV data (TODO)
- `enrich_pending` - Enrich pending findings (TODO)

## Running the Application

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/thandev"
export REDIS_URL="redis://localhost:6379/0"

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (in separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

### Production

Use gunicorn with uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## TODO / Future Enhancements

- [ ] Add authentication and authorization (JWT tokens)
- [ ] Implement rate limiting per tenant
- [ ] Add proper tool output parsing
- [ ] Implement AI-powered finding analysis
- [ ] Add webhook support for scan completion
- [ ] Add scan scheduling
- [ ] Implement finding deduplication
- [ ] Add export functionality (PDF, JSON, CSV)
- [ ] Add scan templates/presets
- [ ] Implement scan comparison
- [ ] Add notification system



