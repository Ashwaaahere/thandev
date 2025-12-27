# Thandev Infrastructure and DevOps

## Infrastructure Overview

Thandev services are designed to run on multiple platforms:

- **Backend**: Fly.io (primary) or Docker
- **Frontend**: Vercel (primary) or Docker
- **Brain Service**: Local or Docker (can be deployed to Fly.io)
- **Runner Service**: Local or Docker (can be deployed to Fly.io)
- **Database**: PostgreSQL (production) or SQLite (development)
- **Redis**: Local or managed Redis service
- **Qdrant**: Docker container or managed service

## Deployment Units

### Backend

**Fly.io Configuration**: `backend/fly.toml`

```toml
app = "thandev-backend"
primary_region = "iad"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

**Dockerfile**: `backend/Dockerfile`

**Build**:
```bash
docker build -t thandev-backend ./backend
```

**Run**:
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  thandev-backend
```

**Deploy to Fly.io**:
```bash
cd backend
fly deploy
```

### Frontend

**Vercel Configuration**: `vercel.json` (if exists)

**Dockerfile**: `frontend/Dockerfile`

**Build**:
```bash
docker build -t thandev-frontend ./frontend
```

**Run**:
```bash
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=https://thandev-backend.fly.dev \
  -e GITHUB_CLIENT_ID=... \
  -e GITHUB_CLIENT_SECRET=... \
  -e NEXTAUTH_SECRET=... \
  thandev-frontend
```

**Deploy to Vercel**:
- Connect GitHub repository
- Set root directory to `frontend`
- Configure environment variables
- Automatic deployments on push

### Brain Service

**Dockerfile**: Not present (can be added)

**Run Locally**:
```bash
cd services/thandev-brain
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Deploy to Fly.io** (if needed):
- Create `fly.toml` in `services/thandev-brain/`
- Deploy: `fly deploy`

### Runner Service

**Dockerfile**: Not present (can be added)

**Run Locally**:
```bash
cd services/thandev-runner
./start_runner.sh
```

**Deploy to Fly.io** (if needed):
- Create `fly.toml` in `services/thandev-runner/`
- Deploy: `fly deploy`

### Docker Compose

**File**: `docker-compose.yml`

**Services**:
- `postgres`: PostgreSQL database
- `redis`: Redis cache/queue
- `qdrant`: Qdrant vector store
- `api`: Backend API
- `scheduler`: Data ingestion scheduler
- `frontend`: Next.js frontend

**Start**:
```bash
docker-compose up -d
```

**Stop**:
```bash
docker-compose down
```

**View Logs**:
```bash
docker-compose logs -f
```

## Development Workflow

### Local Development Setup

**Prerequisites**:
- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ (or SQLite for development)
- Redis (optional)
- Docker (for Qdrant)

**1. Start Infrastructure Services**:
```bash
# Start PostgreSQL, Redis, Qdrant
docker-compose up -d postgres redis qdrant
```

**2. Backend Setup**:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
REDIS_URL=redis://localhost:6379/0
BRAIN_SERVICE_URL=http://localhost:8001
ENVIRONMENT=development
EOF

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000
```

**3. Brain Service Setup**:
```bash
cd services/thandev-brain
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
ENVIRONMENT=development
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-key
EOF

# Start brain service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**4. Runner Service Setup** (optional):
```bash
cd services/thandev-runner
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
CONSUMER_GROUP=runner-workers
EOF

# Start runner
./start_runner.sh
```

**5. Frontend Setup**:
```bash
cd frontend
npm install

# Create .env.local file
cat > .env.local << EOF
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret
NEXTAUTH_SECRET=your-secret
NEXTAUTH_URL=http://localhost:3000
EOF

# Start frontend
npm run dev
```

### Database Migrations

**Tool**: Alembic

**Location**: `backend/migrations/`

**Create Migration**:
```bash
cd backend
alembic revision --autogenerate -m "description"
```

**Apply Migrations**:
```bash
alembic upgrade head
```

**Rollback Migration**:
```bash
alembic downgrade -1
```

**Note**: In development with SQLite, tables may be auto-created. Always use Alembic in production.

### Testing

**Backend Tests** (if available):
```bash
cd backend
pytest
```

**Frontend Tests** (if available):
```bash
cd frontend
npm test
```

## Observability

### Logging

**Backend**:
- **Development**: Human-readable format
- **Production**: JSON logging (if `USE_JSON_LOGGING=true`)
- **Location**: Console/stdout
- **Levels**: DEBUG, INFO, WARNING, ERROR

**Brain Service**:
- Human-readable format
- Console/stdout
- Levels: DEBUG, INFO, WARNING, ERROR

**Runner Service**:
- Human-readable format
- Console/stdout
- Levels: INFO, WARNING, ERROR

**Frontend**:
- Browser console
- Next.js server logs
- Error boundaries for React errors

### Metrics

**Current Status**: No explicit metrics collection system

**Future Considerations**:
- Prometheus metrics endpoint
- Application Performance Monitoring (APM)
- Custom metrics for scan execution times, finding counts, etc.

### Health Checks

**Backend**:
- `GET /health`: Health check with database status
- Returns: `{"status": "ok", "database": "connected"}`

**Brain Service**:
- `GET /health`: Health check
- Returns: `{"status": "ok", "service": "thandev-brain"}`

**Frontend**:
- Next.js built-in health checks
- Error boundaries for graceful degradation

### Tracing

**Current Status**: No distributed tracing

**Future Considerations**:
- OpenTelemetry integration
- Request ID propagation
- Trace correlation across services

## Production Deployment

### Backend (Fly.io)

**1. Install Fly CLI**:
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

**2. Create PostgreSQL Database**:
```bash
fly postgres create --name thandev-db --region iad
```

**3. Deploy Backend**:
```bash
cd backend
fly launch
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set REDIS_URL="redis://..."
fly secrets set BRAIN_SERVICE_URL="http://brain-service:8001"
fly secrets set OPENAI_API_KEY="your-key"
fly deploy
```

**4. Deploy Scheduler** (if separate):
```bash
fly deploy --config ../fly-scheduler.toml
```

### Frontend (Vercel)

**1. Connect Repository**:
- Go to Vercel Dashboard
- Import GitHub repository
- Set root directory to `frontend`

**2. Configure Build**:
- Framework: Next.js
- Build Command: `npm run build`
- Output Directory: `.next`

**3. Set Environment Variables**:
- `NEXT_PUBLIC_API_BASE_URL`: Backend URL
- `GITHUB_CLIENT_ID`: GitHub OAuth client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth client secret
- `NEXTAUTH_SECRET`: JWT secret
- `NEXTAUTH_URL`: Frontend URL

**4. Deploy**:
- Push to main branch for automatic deployment
- Or manually trigger deployment

### Brain Service (Optional Fly.io Deployment)

**1. Create Fly App**:
```bash
cd services/thandev-brain
fly launch
```

**2. Set Secrets**:
```bash
fly secrets set QDRANT_URL="http://qdrant:6333"
fly secrets set OPENAI_API_KEY="your-key"
fly secrets set DATABASE_URL="postgresql://..."  # if using PgVector
```

**3. Deploy**:
```bash
fly deploy
```

### Cloud Run Services (Alternative)

**Security Scanner**:
- Location: `cloud-run/security-scanner/`
- Deploy: `./deploy-security-scanner.sh`

**Lighthouse Scanner**:
- Location: `cloud-run/lighthouse-scanner/`
- Deploy: `./deploy.sh`

## Environment Variables Reference

### Backend

**Required**:
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string

**Optional**:
- `BRAIN_SERVICE_URL`: Brain service URL (default: `http://localhost:8001`)
- `BRAIN_SERVICE_ENABLED`: Enable brain service (default: `true`)
- `OPENAI_API_KEY`: OpenAI API key
- `ENVIRONMENT`: `development`, `production`, `docker`, `testing`
- `CORS_ORIGINS`: Comma-separated allowed origins
- `SECRET_KEY`: JWT secret key (change in production!)

### Frontend

**Required**:
- `NEXT_PUBLIC_API_BASE_URL`: Backend API URL
- `GITHUB_CLIENT_ID`: GitHub OAuth client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth client secret
- `NEXTAUTH_SECRET`: NextAuth secret
- `NEXTAUTH_URL`: Frontend URL

### Brain Service

**Required**:
- `RAG_STORE_TYPE`: `qdrant` or `pgvector`
- `QDRANT_URL`: Qdrant server URL (if using Qdrant)
- `EMBEDDING_PROVIDER`: `openai` or `sentence_transformers`
- `OPENAI_API_KEY`: OpenAI API key (if using OpenAI)

**Optional**:
- `DATABASE_URL`: PostgreSQL connection (if using PgVector)
- `ENVIRONMENT`: `development` or `production`

### Runner Service

**Required**:
- `REDIS_URL`: Redis connection string
- `DATABASE_URL`: Database connection string

**Optional**:
- `CONSUMER_GROUP`: Consumer group name (default: `runner-workers`)
- `CONSUMER_NAME`: Unique consumer name (default: hostname)
- `MAX_CONCURRENT_STEPS`: Max parallel steps (default: 5)
- `MAX_INFLIGHT_PER_SESSION`: Max steps per session (default: 2)

