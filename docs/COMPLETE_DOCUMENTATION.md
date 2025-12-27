# Thandev Complete Documentation

This document consolidates all documentation for the Thandev security testing platform.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [API Documentation](#api-documentation)
6. [Services](#services)
7. [Development](#development)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (optional, SQLite for local dev)
- Redis
- Docker (optional)

### Setup
1. Clone the repository
2. Install dependencies: `./install_all_tools.sh`
3. Configure environment: Copy `.env.example` to `.env` and set values
4. Run migrations: `cd backend && alembic upgrade head`
5. Start services: `./start_services.sh`
6. Start frontend: `cd frontend && npm run dev`

## Architecture

### Services
- **Backend API** (FastAPI): Core API, scan orchestration, findings management
- **Brain Service**: RAG-powered scan planning and report generation
- **Runner Service**: Tool execution worker
- **Frontend** (Next.js): User interface

### Data Flow
1. User creates scan via frontend
2. Frontend calls backend API
3. Backend requests plan from brain service
4. Brain service returns tool execution plan
5. Backend queues steps to Redis Streams
6. Runner service executes tools
7. Findings are ingested into database
8. Frontend displays results

## Configuration

### Environment Variables

#### Backend
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `BRAIN_SERVICE_URL`: Brain service URL
- `BRAIN_SERVICE_ENABLED`: Enable/disable brain service
- `BRAIN_REQUIRED`: Fail scans if brain is unavailable
- `OPENAI_API_KEY`: OpenAI API key for reports
- `MAX_PARALLEL_TOOLS`: Max concurrent tool executions
- `USE_JSON_LOGGING`: Use structured JSON logging

#### Runner Service
- `DATABASE_URL`: Database connection (shared with backend)
- `REDIS_URL`: Redis connection
- `JOBS_DIR`: Directory for scan job outputs
- `WORDLISTS_DIR`: Directory for wordlists

## API Documentation

See `/api/docs` for interactive API documentation when backend is running.

### Key Endpoints
- `POST /api/scans`: Create a new scan
- `GET /api/scans/{id}`: Get scan status
- `GET /api/scans/{id}/findings`: Get scan findings
- `GET /api/tenants/current`: Get current tenant plan info

## Services

### Backend Service
- Location: `backend/`
- Port: 8000 (default)
- Start: `cd backend && uvicorn app.main:app --reload`

### Brain Service
- Location: `services/thandev-brain/`
- Port: 8001 (default)
- Start: `cd services/thandev-brain && python -m uvicorn app.main:app --reload`

### Runner Service
- Location: `services/thandev-runner/`
- Start: `cd services/thandev-runner && ./start_runner.sh`

## Development

### Code Structure
- `backend/app/api/`: API endpoints
- `backend/app/services/`: Business logic
- `backend/app/models/`: Database models
- `backend/app/core/`: Core configuration and utilities
- `frontend/app/`: Next.js pages
- `frontend/components/`: React components

### Adding a New Tool
1. Add tool definition to `services/thandev-brain/catalog/catalog.json`
2. Implement tool runner in `backend/app/services/tools.py`
3. Add parser in `backend/app/services/findings_ingestor.py`
4. Add ingestion logic in `backend/app/services/scan_orchestrator.py`

## Testing

### Unit Tests
```bash
cd backend
pytest tests/unit/
```

### Integration Tests
```bash
cd backend
pytest tests/integration/
```

## Deployment

See `DEPLOYMENT.md` for detailed deployment instructions.

### Docker
```bash
docker-compose up -d
```

### Manual Deployment
1. Set environment variables
2. Run migrations: `alembic upgrade head`
3. Start services
4. Configure reverse proxy (nginx)

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Check `DATABASE_URL` is correct
   - Ensure database is running
   - Verify network connectivity

2. **Brain service unavailable**
   - Check `BRAIN_SERVICE_URL` is correct
   - Verify brain service is running
   - Set `BRAIN_REQUIRED=false` for fallback mode

3. **No findings in scans**
   - Check tool execution logs
   - Verify tools are installed
   - Check scan level includes desired tools

4. **Migration errors**
   - Check database permissions
   - Verify migration order
   - Try `alembic downgrade -1` then `alembic upgrade head`

For more details, see individual service READMEs in their respective directories.



