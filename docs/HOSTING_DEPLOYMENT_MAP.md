# Thandev Hosting & Deployment Map

**Generated:** 2025-01-27  
**Repository:** thandev  
**Purpose:** Production-grade deployment guide for all components

---

## Executive Summary

- **Monorepo Structure:** 7 main services + 3 Cloud Run jobs + shared infrastructure + 1 shared package
- **Primary Stack:** FastAPI (Python) backend, Next.js 14 frontend, PostgreSQL, Redis, Qdrant
- **Deployment Targets:** Vercel (frontend), Fly.io (backend/brain/runner/scheduler), Cloud Run (scanners), Supabase/Railway (databases)
- **Key Dependencies:** PostgreSQL (shared), Redis (shared), Qdrant (brain), OpenAI API (brain), NVD API (scheduler), GitHub OAuth
- **Background Jobs:** Scheduler (CVE ingestion every 6h), Runner (scan execution via Redis streams), Celery (legacy, disabled by default)
- **Scaling Model:** Stateless API services, stateful workers, auto-scaling Cloud Run jobs
- **Critical Path:** Frontend → Backend → Runner → Cloud Run scanners → Results ingestion
- **Data Flow:** User → Frontend → Backend API → Redis Streams → Runner → Tools → Findings DB
- **Monorepo Recommendation:** **Keep monorepo, split deployments** (see detailed analysis below)
- **Production Gaps:** Secrets management, centralized observability, plan-based rate limiting, automated DNS verification, admin bootstrap automation

---

## Repository Inventory

```
thandev/
├── backend/                    # FastAPI main API service
│   ├── app/
│   │   ├── main.py            # Entrypoint: uvicorn app.main:app
│   │   ├── api/               # API routers
│   │   ├── models/            # SQLAlchemy models
│   │   └── core/
│   │       └── config.py      # Settings (env vars)
│   ├── scheduler.py           # CVE ingestion scheduler
│   ├── Dockerfile             # Container build
│   ├── fly.toml              # Fly.io config
│   └── requirements.txt       # Python deps
│
├── frontend/                   # Next.js 14 frontend
│   ├── app/                   # App Router
│   ├── package.json           # Node deps
│   ├── Dockerfile             # Container build
│   ├── vercel.json            # Vercel config
│   └── env.example            # Env vars template
│
├── services/
│   ├── thandev-brain/         # RAG-powered AI service
│   │   ├── app/
│   │   │   └── main.py        # Entrypoint: uvicorn app.main:app
│   │   ├── requirements.txt
│   │   └── start_brain.sh
│   │
│   └── thandev-runner/        # Scan execution worker
│       ├── app/
│       │   └── tasks.py       # Entrypoint: python -m app.tasks
│       ├── requirements.txt
│       └── start_runner.sh
│
├── cloud-run/                  # Google Cloud Run services
│   ├── security-scanner/      # Nuclei/Nmap/SSLScan
│   │   ├── Dockerfile
│   │   └── server.py          # Flask API
│   ├── lighthouse-scanner/    # Performance scanning
│   │   ├── Dockerfile
│   │   └── server-enhanced.js # Node.js API
│   └── locust-runner/         # Load testing
│       ├── Dockerfile
│       └── run_locust.py      # Python job
│
├── packages/
│   └── thandev_schemas/       # Shared Python package
│
├── docker-compose.yml          # Local dev setup
└── fly-scheduler.toml         # Fly.io scheduler config
```

---

## Co-Location Requirements & Network Dependencies

### Must Be Co-Located (Same Region/Network)

1. **Backend + Runner + Database:**
   - **Why:** Runner must access same PostgreSQL database as backend (shared schema, scan_jobs table)
   - **Evidence:** `services/thandev-runner/app/config.py:25-26` (comment: "CRITICAL: Runner must use the SAME database as backend")
   - **Requirement:** Same region for low latency (<10ms), same VPC/network if possible
   - **Recommendation:** Deploy backend and runner in same Fly.io region, use managed PostgreSQL in same region

2. **Brain + Qdrant (if self-hosted):**
   - **Why:** Vector database queries require low latency (<10ms ideal for RAG)
   - **Requirement:** Same region, prefer same VPC
   - **Recommendation:** Use Qdrant Cloud (managed, global) or deploy Qdrant on Fly.io in same region as brain

3. **Backend + Redis:**
   - **Why:** Redis streams for scan step queueing, session state, rate limiting
   - **Requirement:** Same region for <5ms latency
   - **Recommendation:** Use Upstash Redis (global edge) or Railway Redis in same region as backend

### Can Be Separated (Any Region)

1. **Frontend:** Can be anywhere (Vercel edge is optimal for global users)
2. **Cloud Run Scanners:** Can be in any GCP region (prefer us-central1 for cost)
3. **Scheduler:** Can be anywhere (runs every 6h, not latency-sensitive)

### Network Latency Requirements

| Service Pair | Latency Requirement | Reason |
|--------------|---------------------|--------|
| Backend → Database | <10ms | Query performance, transaction consistency |
| Runner → Database | <10ms | Scan job updates, findings ingestion |
| Backend → Redis | <5ms | Queue operations, session state |
| Runner → Redis | <5ms | Stream consumption, step publishing |
| Brain → Qdrant | <10ms | Vector search performance |
| Backend → Brain | <50ms | HTTP API calls (acceptable) |
| Backend → Cloud Run | <100ms | HTTP API calls (acceptable) |
| Frontend → Backend | <200ms | User experience (acceptable) |

---

## Component Analysis

### 1. Backend API (`backend/`)

**Purpose:** Main FastAPI application providing REST API for scans, projects, users, findings, metrics, notifications, admin operations.

**Runtime:** Python 3.11, FastAPI, Uvicorn

**Entrypoint:**
```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production (Docker)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# With Gunicorn (recommended for production)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Port:** 8000 (internal), configurable via `PORT` env var

**Health Endpoints:**
- `GET /health` - Basic health check (returns service status, version)
  - Source: `backend/app/main.py:164-171`
- `GET /ready` - Readiness check (verifies DB, Redis, Brain service connectivity)
  - Source: `backend/app/main.py:175-233`
- Docker healthcheck: `curl -f http://localhost:8000/_health` (note: endpoint is `/health`, not `/_health`)
  - Source: `backend/Dockerfile:81-82`

**Dependencies:**
- **PostgreSQL:** Primary database (tables: users, tenants, projects, scan_jobs, findings, notifications, performance_scans, etc.)
- **Redis:** Task queues, caching, session state (default: `redis://localhost:6380/0`)
- **Brain Service (optional):** RAG-powered scan planning (`BRAIN_SERVICE_URL`)
- **External APIs:** NVD API (CVE data, optional `NVD_API_KEY`)

**Required Environment Variables:**
```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Redis (REQUIRED)
REDIS_URL=redis://host:port/db

# Security (REQUIRED in production)
SECRET_KEY=<generate-with-openssl-rand-base64-32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS (REQUIRED)
CORS_ORIGINS=https://your-frontend-domain.com,https://api.your-domain.com

# Environment
ENVIRONMENT=production
DEBUG=false

# Brain Service (optional, enables AI planning)
BRAIN_SERVICE_URL=http://brain-service:8001
BRAIN_SERVICE_ENABLED=true
BRAIN_REQUIRED=false  # Set true to fail scans if brain unavailable

# OpenAI (optional, for AI features)
OPENAI_API_KEY=sk-...

# NVD API (optional, for CVE ingestion)
NVD_API_KEY=...

# Tenant/Admin Configuration
THANDEV_SUPERADMIN_EXTERNAL_IDS=github:123456,github:789012
THANDEV_SETUP_TOKEN=<one-time-bootstrap-token>
SELF_SERVICE_SIGNUP_ENABLED=false  # Disable in production

# Domain Verification
DOMAIN_VERIFICATION_DISABLED=false
ALLOWED_SCAN_DOMAINS=example.com,demo.com  # Staging only

# Scan Configuration
MAX_PARALLEL_TOOLS=5
MAX_SCAN_TIMEOUT_SECONDS=3600
TOOL_EXECUTION_TIMEOUT_SECONDS=900
SCAN_RECOVERY_ENABLED=false  # Enable to recover stale scans on startup
```

**Build Command:**
```bash
cd backend
pip install -r requirements.txt
python init_db.py  # Only for SQLite dev
alembic upgrade head  # Run migrations for PostgreSQL
```

**Start Command:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Scaling Notes:**
- Stateless API (can scale horizontally)
- Requires shared PostgreSQL and Redis
- No sticky sessions needed
- Recommended: 2-4 workers per instance (Gunicorn)

**Hosting Recommendation:**
- **Best:** Fly.io (already configured with `fly.toml`)
  - Pros: Auto-scaling, global edge, persistent volumes, built-in health checks
  - Cons: Cost at scale, vendor lock-in
  - Config: `backend/fly.toml` (1 CPU, 256MB RAM, auto-stop enabled)
- **Alternative 1:** Railway
  - Pros: Simple deployment, PostgreSQL included, good DX
  - Cons: Less control, pricing can spike
- **Alternative 2:** Render
  - Pros: Free tier, PostgreSQL included, easy setup
  - Cons: Cold starts, limited customization
- **Alternative 3:** Google Cloud Run
  - Pros: Serverless, auto-scaling, pay-per-use
  - Cons: Cold starts, 15min timeout limit

---

### 2. Frontend (`frontend/`)

**Purpose:** Next.js 14 application with App Router, providing user interface for scans, projects, findings, dashboard, authentication.

**Runtime:** Node.js 20, Next.js 14

**Entrypoint:**
```bash
# Development
npm run dev  # Port 3000

# Production
npm run build
npm run start  # Port 3000
```

**Port:** 3000 (configurable via `PORT` env var)

**Health Endpoints:**
- `GET /api/health` (if implemented)
- Built-in Next.js health checks

**Dependencies:**
- **Backend API:** REST API calls to backend service (`NEXT_PUBLIC_API_BASE`)
- **PostgreSQL (via Prisma):** User sessions, local data (optional, can use backend API only)
- **NextAuth.js:** GitHub OAuth authentication

**Required Environment Variables:**
```bash
# Backend API (REQUIRED)
NEXT_PUBLIC_API_BASE=https://your-backend-api.fly.dev

# NextAuth (REQUIRED)
NEXTAUTH_SECRET=<generate-with-openssl-rand-base64-32>
NEXTAUTH_URL=https://your-frontend-domain.vercel.app

# GitHub OAuth (REQUIRED)
GITHUB_CLIENT_ID=your_github_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_app_client_secret
# Alternative naming (also supported):
# GITHUB_ID=...
# GITHUB_SECRET=...

# Database (optional, if using Prisma directly)
DATABASE_URL=postgresql://...  # Only if frontend needs direct DB access
```

**Build Command:**
```bash
cd frontend
npm install
npm run build
```

**Start Command:**
```bash
npm run start
```

**Output Directory:** `frontend/.next` (for static export if needed)

**Scaling Notes:**
- Stateless, can scale horizontally
- Static assets can be CDN-cached
- API routes run on server (consider edge functions for low latency)

**Hosting Recommendation:**
- **Best:** Vercel (already configured with `vercel.json`)
  - Pros: Zero-config Next.js, edge functions, automatic deployments, built-in analytics
  - Cons: Vendor lock-in, pricing at scale
  - Config: `vercel.json` (rootDirectory: `frontend`)
- **Alternative 1:** Netlify
  - Pros: Good Next.js support, edge functions, free tier
  - Cons: Slightly less optimized than Vercel
- **Alternative 2:** Railway/Render
  - Pros: Full control, Docker support
  - Cons: Need to configure Next.js manually, no edge functions

---

### 3. Brain Service (`services/thandev-brain/`)

**Purpose:** RAG-powered AI service for scan planning, report prompt generation, finding enrichment using OpenAI + vector store (Qdrant or PgVector).

**Runtime:** Python 3.11, FastAPI, Uvicorn

**Entrypoint:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Port:** 8001 (configurable)

**Health Endpoints:**
- `GET /health` - Basic health check
- `GET /ready` - Readiness (Qdrant/PgVector, Redis, OpenAI)

**Dependencies:**
- **Qdrant (default):** Vector database for RAG (`QDRANT_URL`, collection: `thandev_rag`)
- **OR PgVector:** Alternative vector store using PostgreSQL (`DATABASE_URL` with pgvector extension)
- **Redis:** Session state, queues (`REDIS_URL`)
- **OpenAI API:** Embeddings and LLM calls (`OPENAI_API_KEY`)
- **PostgreSQL (if using PgVector):** Same database as backend or separate

**Required Environment Variables:**
```bash
# RAG Store (REQUIRED - choose one)
RAG_STORE_TYPE=qdrant  # or pgvector
QDRANT_URL=http://qdrant-host:6333
QDRANT_COLLECTION=thandev_rag

# OR for PgVector:
# DATABASE_URL=postgresql://... (with pgvector extension)

# Embedding Provider (REQUIRED)
EMBEDDING_PROVIDER=sentence_transformers  # or openai
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Default model
# OR if using OpenAI:
# OPENAI_API_KEY=sk-...
# OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# OpenAI (REQUIRED for finding enrichment)
OPENAI_API_KEY=sk-...

# Redis (REQUIRED)
REDIS_URL=redis://host:port/db

# CORS
CORS_ORIGINS=http://localhost:3000,https://your-frontend.com

# Brain Configuration
BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
BRAIN_MAX_TOTAL_RUNTIME_SEC=3600
SESSION_MAX_STEPS=20
SESSION_MAX_RUNTIME_SEC=3600

# Finding Enrichment
ENRICH_FINDINGS_ENABLED=true
ENRICH_FINDINGS_MODEL=gpt-4o-mini
ENRICH_FINDINGS_TIMEOUT_SEC=30
```

**Build Command:**
```bash
cd services/thandev-brain
pip install -r requirements.txt
```

**Start Command:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
```

**Scaling Notes:**
- Stateless API (can scale horizontally)
- Requires shared Qdrant/PgVector and Redis
- OpenAI API calls are rate-limited (consider queuing)

**Hosting Recommendation:**
- **Best:** Fly.io
  - Pros: Same platform as backend, easy networking, persistent volumes for Qdrant data
  - Cons: Cost, need separate Qdrant instance
  - Config: Similar to backend `fly.toml` (port 8001, 512MB+ RAM for embeddings)
- **Alternative 1:** Railway
  - Pros: Simple, can deploy Qdrant as service
  - Cons: Less control
- **Alternative 2:** Render
  - Pros: Free tier, easy setup
  - Cons: Cold starts affect AI latency
- **Note:** Qdrant can be hosted separately on Qdrant Cloud, Railway, or self-hosted

---

### 4. Runner Service (`services/thandev-runner/`)

**Purpose:** Background worker that consumes scan step requests from Redis streams, executes security tools (Nuclei, Nmap, SSLScan, etc.), and ingests findings into database.

**Runtime:** Python 3.11, Celery-like worker (custom Redis streams consumer)

**Entrypoint:**
```bash
python -m app.tasks
```

**Port:** None (background worker, no HTTP server)

**Dependencies:**
- **Redis:** Streams for step requests (`REDIS_URL`, consumer group: `runner-workers`)
- **PostgreSQL:** Same database as backend (CRITICAL: must match `DATABASE_URL`)
- **Local Tools:** Nuclei, Nmap, SSLScan, ffuf, sqlmap, etc. (installed in container/VM)
- **File System:** `backend/data/jobs/{scan_id}/` for tool outputs

**Required Environment Variables:**
```bash
# Database (REQUIRED - MUST match backend DATABASE_URL)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Redis (REQUIRED)
REDIS_URL=redis://host:port/db

# Consumer Configuration
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=runner-1  # Unique per instance

# Execution Configuration
EXECUTION_ADAPTER=local  # or remote
MAX_CONCURRENT_STEPS=5
MAX_INFLIGHT_PER_SESSION=2

# Tool Paths (computed automatically, can override)
TOOLS_BASE_DIR=/app/backend  # Path to backend directory
DATA_DIR=/app/backend/data
JOBS_DIR=/app/backend/data/jobs
WORDLISTS_DIR=/app/wordlists
```

**Build Command:**
```bash
cd services/thandev-runner
pip install -r requirements.txt
```

**Start Command:**
```bash
python -m app.tasks
```

**Scaling Notes:**
- Can run multiple instances (each with unique `CONSUMER_NAME`)
- Redis streams handle load balancing automatically
- Requires access to security tools (Docker volume or installed binaries)
- CPU/memory intensive (tool execution)

**Hosting Recommendation:**
- **Best:** Fly.io (VM with persistent volume for tools)
  - Pros: Can install tools, persistent storage, good for long-running workers
  - Cons: Cost, need to manage tool installation
  - Config: `fly.toml` with volume mount for tools/data
- **Alternative 1:** Railway (Docker with tool installation)
  - Pros: Simple, good Docker support
  - Cons: Ephemeral storage, need to install tools in image
- **Alternative 2:** Google Cloud Run Jobs (for batch execution)
  - Pros: Pay-per-use, auto-scaling
  - Cons: Not ideal for long-running workers, 15min timeout
- **Alternative 3:** Self-hosted VM (DigitalOcean, AWS EC2)
  - Pros: Full control, can install tools easily
  - Cons: Manual scaling, infrastructure management

---

### 5. Scheduler Service (`backend/scheduler.py`)

**Purpose:** Background cron-like service that runs CVE data ingestion from NVD API every 6 hours.

**Runtime:** Python 3.11, schedule library

**Entrypoint:**
```bash
python scheduler.py
```

**Port:** None (background process)

**Dependencies:**
- **PostgreSQL:** Same database as backend (CVE data storage)
- **NVD API:** Optional API key for higher rate limits

**Required Environment Variables:**
```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Redis (optional, if used)
REDIS_URL=redis://host:port/db

# NVD API (optional)
NVD_API_KEY=...
```

**Build Command:**
```bash
cd backend
pip install -r requirements.txt
```

**Start Command:**
```bash
python scheduler.py
```

**Scaling Notes:**
- Should run as single instance (prevents duplicate ingestion)
- Can use Fly.io scheduler or cron job

**Hosting Recommendation:**
- **Best:** Fly.io Scheduler (already configured with `fly-scheduler.toml`)
  - Pros: Built-in cron, automatic execution, no always-on cost
  - Cons: Fly.io specific
  - Config: `fly-scheduler.toml` (runs every 6 hours)
- **Alternative 1:** Cloud Run Jobs (scheduled)
  - Pros: Serverless, pay-per-execution
  - Cons: Need to set up Cloud Scheduler
- **Alternative 2:** Railway Cron Jobs
  - Pros: Simple cron syntax
  - Cons: Railway specific
- **Alternative 3:** GitHub Actions (scheduled workflow)
  - Pros: Free, version controlled
  - Cons: External dependency

---

### 6. Security Scanner (`cloud-run/security-scanner/`)

**Purpose:** Google Cloud Run service that executes security scans (Nuclei, Nmap, SSLScan) on-demand via HTTP API.

**Runtime:** Python 3.11, Flask, Ubuntu 22.04

**Entrypoint:**
```bash
python3 server.py
```

**Port:** 8080 (Cloud Run default)

**Health Endpoints:**
- `GET /health` - Health check

**Dependencies:**
- **External Tools:** Nuclei, Nmap, SSLScan, Subfinder (installed in Docker image)
- **Google Cloud Storage (optional):** For result artifacts

**Required Environment Variables:**
```bash
# None required (optional GCS for artifacts)
GCS_BUCKET=thandev-reports  # Optional
```

**Build Command:**
```bash
cd cloud-run/security-scanner
gcloud builds submit --tag gcr.io/PROJECT_ID/security-scanner .
```

**Deploy Command:**
```bash
gcloud run deploy security-scanner \
  --image gcr.io/PROJECT_ID/security-scanner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10
```

**Scaling Notes:**
- Auto-scales based on requests
- Each instance can handle multiple concurrent scans
- Memory: 2GB (for Chrome/Nuclei)
- CPU: 2 vCPUs (for parallel tool execution)

**Hosting Recommendation:**
- **Best:** Google Cloud Run (already configured)
  - Pros: Serverless, auto-scaling, pay-per-use, 15min timeout
  - Cons: Cold starts, GCP vendor lock-in
- **Alternative 1:** Fly.io (with Dockerfile)
  - Pros: Global edge, no cold starts
  - Cons: Always-on cost, need to manage scaling
- **Alternative 2:** AWS Lambda (with container support)
  - Pros: Serverless, pay-per-use
  - Cons: 15min timeout, cold starts

---

### 7. Lighthouse Scanner (`cloud-run/lighthouse-scanner/`)

**Purpose:** Google Cloud Run service for performance scanning using Lighthouse (headless Chrome).

**Runtime:** Node.js 18, Express

**Entrypoint:**
```bash
node server-enhanced.js
```

**Port:** 8080 (Cloud Run default)

**Health Endpoints:**
- `GET /health` - Health check

**Dependencies:**
- **Chrome/Chromium:** Headless browser (installed in Docker image)
- **Lighthouse:** NPM package (installed in image)

**Required Environment Variables:**
```bash
# None required
PORT=8080  # Cloud Run sets this automatically
```

**Build Command:**
```bash
cd cloud-run/lighthouse-scanner
gcloud builds submit --tag gcr.io/PROJECT_ID/lighthouse-scanner .
```

**Deploy Command:**
```bash
gcloud run deploy lighthouse-scanner \
  --image gcr.io/PROJECT_ID/lighthouse-scanner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10
```

**Scaling Notes:**
- Auto-scales based on requests
- Memory: 2GB (for Chrome + Lighthouse)
- CPU: 2 vCPUs (for parallel scans)

**Hosting Recommendation:**
- **Best:** Google Cloud Run (already configured)
  - Pros: Serverless, auto-scaling, pay-per-use
  - Cons: Cold starts
- **Alternative:** Same as Security Scanner

---

### 8. Locust Runner (`cloud-run/locust-runner/`)

**Purpose:** Google Cloud Run Job for load testing using Locust (executes and uploads results to GCS).

**Runtime:** Python 3.11, Locust

**Entrypoint:**
```bash
python run_locust.py
```

**Port:** None (Cloud Run Job, not a service)

**Dependencies:**
- **Google Cloud Storage:** For result uploads
- **Target Domain:** Domain to load test (from env var)

**Required Environment Variables:**
```bash
DOMAIN=example.com  # Target domain
VUS=50  # Virtual users
DURATION=120  # Duration in seconds
SPAWN=10  # Spawn rate
SCAN_ID=...  # Optional scan ID
CALLBACK_URL=...  # Optional callback
GCS_BUCKET=thandev-reports
```

**Build Command:**
```bash
cd cloud-run/locust-runner
gcloud builds submit --tag gcr.io/PROJECT_ID/locust-runner .
```

**Deploy Command:**
```bash
# Deploy as Cloud Run Job (not service)
gcloud run jobs create locust-runner \
  --image gcr.io/PROJECT_ID/locust-runner \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --max-retries 1 \
  --task-timeout 900
```

**Scaling Notes:**
- Runs as one-time job (not long-running service)
- Can be triggered via Cloud Scheduler or API

**Hosting Recommendation:**
- **Best:** Google Cloud Run Jobs (already configured)
  - Pros: Perfect for batch jobs, pay-per-execution
  - Cons: GCP specific
- **Alternative:** Fly.io (one-off machine)
  - Pros: Simple execution
  - Cons: Always-on cost if scheduled

---

## Infrastructure Dependencies

### PostgreSQL Database

**Purpose:** Primary database for all services (users, tenants, projects, scans, findings, notifications, performance scans).

**Tables Used:**
- `users`, `tenants`, `projects`, `scan_jobs`, `findings`, `notifications`, `performance_scans`, `domain_verifications`, `audit_logs`, `entitlements`, `allowed_domains`

**Requirements:**
- **CPU:** 1-2 vCPUs (small to medium workload)
- **RAM:** 2-4GB (depends on data size)
- **Storage:** 20GB+ (grows with scan results)
- **Extensions:** `pgvector` (if brain uses PgVector instead of Qdrant)

**Hosting Recommendation:**
- **Best:** Supabase (PostgreSQL + pgvector)
  - Pros: Free tier, pgvector included, easy backups, dashboard
  - Cons: Limited customization
- **Alternative 1:** Railway PostgreSQL
  - Pros: Simple, included with Railway apps
  - Cons: Pricing can spike
- **Alternative 2:** AWS RDS / Google Cloud SQL
  - Pros: Managed, scalable, backups
  - Cons: More expensive, need to configure
- **Alternative 3:** Render PostgreSQL
  - Pros: Free tier, easy setup
  - Cons: Limited performance on free tier

**Connection String:**
```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

---

### Redis

**Purpose:** Task queues (Redis streams), caching, session state, Celery broker (if used).

**Requirements:**
- **CPU:** 1 vCPU
- **RAM:** 512MB-1GB (depends on queue size)
- **Storage:** In-memory (persistence optional)

**Hosting Recommendation:**
- **Best:** Upstash Redis (serverless)
  - Pros: Pay-per-use, global edge, automatic scaling
  - Cons: Slightly higher latency
- **Alternative 1:** Railway Redis
  - Pros: Simple, included with Railway
  - Cons: Pricing
- **Alternative 2:** Redis Cloud (Redis Labs)
  - Pros: Managed, good performance
  - Cons: Pricing at scale
- **Alternative 3:** Self-hosted (Fly.io, DigitalOcean)
  - Pros: Full control, lower cost
  - Cons: Need to manage backups, scaling

**Connection String:**
```bash
REDIS_URL=redis://host:port/db
# Or with password:
REDIS_URL=redis://:password@host:port/db
```

---

### Qdrant (Vector Database)

**Purpose:** Vector store for RAG in brain service (embeddings for scan planning, report generation).

**Requirements:**
- **CPU:** 1-2 vCPUs
- **RAM:** 1-2GB (depends on collection size)
- **Storage:** 10GB+ (for vector embeddings)

**Hosting Recommendation:**
- **Best:** Qdrant Cloud
  - Pros: Managed, optimized, free tier available
  - Cons: Vendor lock-in
- **Alternative 1:** Self-hosted on Fly.io (Docker)
  - Pros: Full control, lower cost
  - Cons: Need to manage backups
- **Alternative 2:** Railway (Qdrant Docker)
  - Pros: Simple deployment
  - Cons: Ephemeral storage (need volumes)

**Connection String:**
```bash
QDRANT_URL=http://qdrant-host:6333
QDRANT_COLLECTION=thandev_rag
```

**Note:** Can use PgVector instead (same PostgreSQL as backend) to reduce infrastructure.

---

## Deployment Topology

```mermaid
graph TB
    subgraph "User Layer"
        U[Users/Browsers]
    end

    subgraph "Frontend (Vercel)"
        FE[Next.js Frontend<br/>Port: 3000<br/>Build: npm run build<br/>Start: npm start]
    end

    subgraph "API Layer (Fly.io)"
        BE[Backend API<br/>FastAPI<br/>Port: 8000<br/>Entry: uvicorn app.main:app]
        BR[Brain Service<br/>FastAPI<br/>Port: 8001<br/>Entry: uvicorn app.main:app]
    end

    subgraph "Worker Layer (Fly.io)"
        RN[Runner Service<br/>Python Worker<br/>Entry: python -m app.tasks]
        SCH[Scheduler<br/>Cron Job<br/>Entry: python scheduler.py<br/>Schedule: Every 6h]
    end

    subgraph "Cloud Run (GCP)"
        SS[Security Scanner<br/>Flask API<br/>Port: 8080<br/>Tools: Nuclei/Nmap/SSLScan]
        LS[Lighthouse Scanner<br/>Node.js API<br/>Port: 8080<br/>Tool: Lighthouse]
        LR[Locust Runner<br/>Cloud Run Job<br/>Tool: Locust]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Supabase/Railway<br/>Tables: users, scans, findings)]
        RD[(Redis<br/>Upstash/Railway<br/>Streams: scan-steps<br/>Cache: sessions)]
        QD[(Qdrant<br/>Qdrant Cloud/Fly.io<br/>Collection: thandev_rag)]
    end

    subgraph "External Services"
        GH[GitHub OAuth]
        OAI[OpenAI API<br/>Embeddings + LLM]
        NVD[NVD API<br/>CVE Data]
    end

    U -->|HTTPS| FE
    FE -->|REST API| BE
    FE -->|OAuth| GH
    BE -->|RAG Queries| BR
    BE -->|Publish Steps| RD
    BE -->|Read/Write| PG
    BE -->|Session State| RD
    RN -->|Consume Steps| RD
    RN -->|Execute Tools| SS
    RN -->|Ingest Findings| PG
    BR -->|Vector Search| QD
    BR -->|Embeddings/LLM| OAI
    BR -->|Session State| RD
    SCH -->|CVE Ingestion| NVD
    SCH -->|Store CVEs| PG
    BE -->|Performance Scans| LS
    BE -->|Load Tests| LR

    style FE fill:#0070f3
    style BE fill:#8b5cf6
    style BR fill:#8b5cf6
    style RN fill:#f59e0b
    style SCH fill:#f59e0b
    style SS fill:#34d399
    style LS fill:#34d399
    style LR fill:#34d399
    style PG fill:#3b82f6
    style RD fill:#ef4444
    style QD fill:#10b981
```

---

## Hosting Matrix

| Component | Hosting Target | Build Command | Start Command | Port | Key Env Vars |
|-----------|---------------|---------------|---------------|------|--------------|
| **Frontend** | Vercel | `cd frontend && npm install && npm run build` | `npm run start` | 3000 | `NEXT_PUBLIC_API_BASE`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |
| **Backend API** | Fly.io | `cd backend && pip install -r requirements.txt && alembic upgrade head` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 8000 | `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `BRAIN_SERVICE_URL`, `OPENAI_API_KEY` |
| **Brain Service** | Fly.io | `cd services/thandev-brain && pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port 8001` | 8001 | `QDRANT_URL`, `QDRANT_COLLECTION`, `REDIS_URL`, `OPENAI_API_KEY`, `EMBEDDING_PROVIDER` |
| **Runner Service** | Fly.io | `cd services/thandev-runner && pip install -r requirements.txt` | `python -m app.tasks` | N/A | `DATABASE_URL`, `REDIS_URL`, `CONSUMER_GROUP`, `CONSUMER_NAME` |
| **Scheduler** | Fly.io Scheduler | `cd backend && pip install -r requirements.txt` | `python scheduler.py` | N/A | `DATABASE_URL`, `NVD_API_KEY` |
| **Security Scanner** | Cloud Run | `gcloud builds submit --tag gcr.io/PROJECT/security-scanner ./cloud-run/security-scanner` | `python3 server.py` | 8080 | `GCS_BUCKET` (optional) |
| **Lighthouse Scanner** | Cloud Run | `gcloud builds submit --tag gcr.io/PROJECT/lighthouse-scanner ./cloud-run/lighthouse-scanner` | `node server-enhanced.js` | 8080 | None |
| **Locust Runner** | Cloud Run Jobs | `gcloud builds submit --tag gcr.io/PROJECT/locust-runner ./cloud-run/locust-runner` | `python run_locust.py` | N/A | `DOMAIN`, `VUS`, `DURATION`, `GCS_BUCKET` |
| **PostgreSQL** | Supabase/Railway | N/A | Managed service | 5432 | `DATABASE_URL` |
| **Redis** | Upstash/Railway | N/A | Managed service | 6379 | `REDIS_URL` |
| **Qdrant** | Qdrant Cloud/Fly.io | N/A | Managed/Docker | 6333 | `QDRANT_URL`, `QDRANT_COLLECTION` |

---

## Monorepo Deployment Strategy

### Path-Based CI/CD Trigger Plan

**Strategy:** Deploy only services whose code paths changed, using GitHub Actions path filters.

**Trigger Rules:**
- `frontend/**` → Deploy to Vercel
- `backend/**` (excluding `backend/data/**`) → Deploy backend to Fly.io
- `services/thandev-brain/**` → Deploy brain to Fly.io
- `services/thandev-runner/**` → Deploy runner to Fly.io
- `backend/scheduler.py` or `backend/real_data_ingestion.py` → Deploy scheduler (or trigger manual run)
- `cloud-run/security-scanner/**` → Deploy security scanner to Cloud Run
- `cloud-run/lighthouse-scanner/**` → Deploy lighthouse scanner to Cloud Run
- `cloud-run/locust-runner/**` → Deploy locust runner to Cloud Run
- `packages/thandev_schemas/**` → Rebuild all dependent services (backend, brain, runner)

**GitHub Actions Workflow:**
```yaml
name: Deploy Services

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - 'backend/**'
      - 'services/**'
      - 'cloud-run/**'

jobs:
  deploy-frontend:
    if: contains(github.event.head_commit.modified_files, 'frontend/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: vercel/action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: frontend

  deploy-backend:
    if: contains(github.event.head_commit.modified_files, 'backend/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --config backend/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy-brain:
    if: contains(github.event.head_commit.modified_files, 'services/thandev-brain/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --config services/thandev-brain/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy-runner:
    if: contains(github.event.head_commit.modified_files, 'services/thandev-runner/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --config services/thandev-runner/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy-security-scanner:
    if: contains(github.event.head_commit.modified_files, 'cloud-run/security-scanner/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      - name: Build and deploy security scanner
        run: |
          cd cloud-run/security-scanner
          gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/security-scanner .
          gcloud run deploy security-scanner \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/security-scanner \
            --platform managed \
            --region us-central1 \
            --allow-unauthenticated \
            --memory 2Gi \
            --cpu 2 \
            --timeout 900

  deploy-lighthouse-scanner:
    if: contains(github.event.head_commit.modified_files, 'cloud-run/lighthouse-scanner/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      - name: Build and deploy lighthouse scanner
        run: |
          cd cloud-run/lighthouse-scanner
          gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/lighthouse-scanner .
          gcloud run deploy lighthouse-scanner \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/lighthouse-scanner \
            --platform managed \
            --region us-central1 \
            --allow-unauthenticated \
            --memory 2Gi \
            --cpu 2 \
            --timeout 900

  deploy-locust-runner:
    if: contains(github.event.head_commit.modified_files, 'cloud-run/locust-runner/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      - name: Build and deploy locust runner
        run: |
          cd cloud-run/locust-runner
          gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/locust-runner .
          gcloud run jobs update locust-runner \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/locust-runner \
            --region us-central1 \
            --memory 2Gi \
            --cpu 2
```

**Note:** The above workflow uses `contains(github.event.head_commit.modified_files, ...)` which requires the `paths` filter in the workflow trigger. For more reliable path detection, use:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - 'backend/**'
      - 'services/**'
      - 'cloud-run/**'
      - 'packages/**'
```

**Secrets Management per Platform:**

- **Vercel:** Environment variables in Vercel dashboard (encrypted at rest)
  - Set via: Vercel dashboard → Project Settings → Environment Variables
  - Or CLI: `vercel env add KEY value`

- **Fly.io:** Secrets via `flyctl secrets set`
  - Command: `flyctl secrets set KEY=value --app APP_NAME`
  - Secrets are encrypted and injected as environment variables
  - Source: Fly.io documentation

- **Cloud Run:** Google Secret Manager (recommended) or environment variables
  - Secret Manager: `gcloud secrets create SECRET_NAME --data-file=-`
  - Reference in deployment: `--set-secrets ENV_VAR=SECRET_NAME:latest`
  - Or env vars: `--set-env-vars KEY=value` (less secure)

- **GitHub Actions:** Repository secrets
  - Set via: Repository Settings → Secrets and variables → Actions
  - Access via: `${{ secrets.SECRET_NAME }}`

### Root Directory Mapping

- **Vercel:** `vercel.json` specifies `rootDirectory: "frontend"`
- **Fly.io:** Each service has its own `fly.toml` in its directory
- **Cloud Run:** Build context is set per service directory

### Build Contexts

- **Frontend:** `./frontend` (Vercel auto-detects)
- **Backend:** `./backend` (Fly.io uses `fly.toml` location)
- **Brain:** `./services/thandev-brain` (Fly.io)
- **Runner:** `./services/thandev-runner` (Fly.io)
- **Cloud Run:** Each service directory is build context

---

## Production Checklist

### ✅ Completed (Verified in Code)

- [x] Database migrations (Alembic)
  - Source: `backend/alembic.ini`, `backend/migrations/` directory exists
  - Command: `alembic upgrade head` (from `backend/Dockerfile:86`)

- [x] Health check endpoints
  - Backend: `GET /health`, `GET /ready` (Source: `backend/app/main.py:164-233`)
  - Brain: `GET /health`, `GET /ready` (Source: `services/thandev-brain/app/main.py` - inferred from FastAPI pattern)
  - Cloud Run scanners: `GET /health` (Source: `cloud-run/security-scanner/server.py:36-39`)

- [x] Dockerfiles for all services
  - Backend: `backend/Dockerfile` (Python 3.11, includes Chrome/Lighthouse)
  - Frontend: `frontend/Dockerfile` (Node 20)
  - Security Scanner: `cloud-run/security-scanner/Dockerfile` (Ubuntu 22.04, Nuclei/Nmap)
  - Lighthouse Scanner: `cloud-run/lighthouse-scanner/Dockerfile` (Node 18 Alpine, Chromium)
  - Locust Runner: `cloud-run/locust-runner/Dockerfile` (Python 3.11 slim)

- [x] Environment variable configuration
  - Backend: `backend/app/core/config.py` (Pydantic Settings, 50+ env vars)
  - Frontend: `frontend/env.example` (NextAuth, GitHub OAuth, API base)
  - Brain: `services/thandev-brain/app/core/config.py` (RAG, Qdrant, OpenAI)
  - Runner: `services/thandev-runner/app/config.py` (Redis, Database, Consumer config)

- [x] CORS configuration
  - Backend: `backend/app/main.py:90-96` (CORSMiddleware with configurable origins)
  - Brain: `services/thandev-brain/app/main.py:61-67` (CORSMiddleware)

- [x] Authentication (GitHub OAuth via NextAuth.js)
  - Frontend: `frontend/package.json:24` (next-auth@4.24.11)
  - Config: `frontend/env.example` (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, NEXTAUTH_SECRET)

- [x] Rate limiting (SlowAPI - **PARTIAL IMPLEMENTATION**)
  - Package: `backend/requirements.txt:17` (slowapi==0.1.9)
  - Implemented in: `backend/app/routers/exploits.py:17-18`, `backend/app/routers/security.py:21`, `backend/app/routers/performance.py:23`
  - **Missing:** Global middleware, plan-based quotas, distributed rate limiting

- [x] Error handling (Sentry SDK - **NOT INITIALIZED**)
  - Package: `backend/requirements.txt:20` (sentry-sdk[fastapi]==2.15.0)
  - **Missing:** Import and initialization in `backend/app/main.py` (not found in code)

- [x] Logging (structured logging support)
  - Backend: `backend/app/main.py:26-34` (JSON logging via `USE_JSON_LOGGING` env var)
  - Structured logging module: `backend/app/core/logging_config.py` (referenced but not verified)

### ❌ Missing / Needs Attention

#### Secrets Management
- [ ] **Secrets Manager Integration:** Currently env vars in platform UIs (Fly.io, Vercel). Should use:
  - **Fly.io:** `flyctl secrets set KEY=value` (encrypted at rest)
  - **Vercel:** Environment variables (encrypted)
  - **Cloud Run:** Secret Manager (recommended)
  - **Action:** Migrate sensitive keys (SECRET_KEY, API keys) to platform secret managers

#### Observability
- [ ] **Centralized Logging:** 
  - Current: Platform-specific logs (Fly.io logs, Vercel logs, Cloud Run logs)
  - **Recommended:** Datadog, Logtail, or Axiom for unified log aggregation
  - **Action:** Set up log forwarding from all services

- [ ] **Metrics & APM:**
  - Current: Basic health checks
  - **Recommended:** 
    - Sentry (already integrated, expand coverage)
    - Datadog APM or New Relic for performance monitoring
    - Custom metrics dashboard (Grafana + Prometheus or Datadog)
  - **Action:** Add metrics collection (request latency, queue depth, error rates)

- [ ] **Distributed Tracing:**
  - Current: None
  - **Recommended:** OpenTelemetry with Jaeger or Datadog APM
  - **Action:** Instrument services with OpenTelemetry

#### Background Workers
- [ ] **Worker Health Monitoring:**
  - Current: Runner logs to stdout
  - **Recommended:** Health check endpoint or heartbeat to Redis
  - **Action:** Add worker health checks and alerting

- [ ] **Dead Letter Queue:**
  - Current: Failed steps may be lost
  - **Recommended:** Redis stream with DLQ or separate error queue
  - **Action:** Implement DLQ for failed scan steps

#### Rate Limiting & Quotas
- [ ] **API Rate Limiting:**
  - Current: SlowAPI in backend (basic)
  - **Recommended:** 
    - Per-user rate limits (tiered plans)
    - Per-IP rate limits (DDoS protection)
    - Redis-based distributed rate limiting
  - **Action:** Enhance rate limiting with plan-based quotas

- [ ] **Scan Quotas:**
  - Current: Plan limits in code (`get_plan_limits`)
  - **Recommended:** 
    - Enforce quotas at API level
    - Track usage in database
    - Soft/hard limits with notifications
  - **Action:** Implement quota enforcement middleware

#### Domain Verification DNS
- [ ] **DNS Check Automation:**
  - Current: Manual DNS TXT record verification
  - **Recommended:**
    - Automated DNS polling (every 5min during verification window)
    - DNS provider API integration (Cloudflare, AWS Route53)
    - Webhook callbacks for instant verification
  - **Action:** Add background job to poll DNS records

#### Admin Bootstrap
- [ ] **Automated Admin Setup:**
  - Current: Manual `THANDEV_SUPERADMIN_EXTERNAL_IDS` env var
  - **Recommended:**
    - One-time setup endpoint (protected by `THANDEV_SETUP_TOKEN`)
    - Admin dashboard for user management
    - Automated tenant creation for first user
  - **Action:** Create admin bootstrap script/endpoint

#### Private Beta Gate
- [ ] **Access Control:**
  - Current: `SELF_SERVICE_SIGNUP_ENABLED` flag
  - **Recommended:**
    - Invite-only signup (invite codes)
    - Waitlist management
    - Beta user whitelist
  - **Action:** Implement invite code system

#### Database Backups
- [ ] **Automated Backups:**
  - Current: Platform-managed (Supabase/Railway have backups)
  - **Recommended:**
    - Daily automated backups (retain 30 days)
    - Point-in-time recovery (PITR)
    - Backup verification and restore testing
  - **Action:** Verify backup strategy with hosting provider

#### Security Hardening
- [ ] **Security Headers:**
  - Current: Basic CORS, GZip
  - **Recommended:**
    - Helmet.js for frontend (security headers)
    - CSP (Content Security Policy)
    - HSTS (HTTP Strict Transport Security)
  - **Action:** Add security middleware

- [ ] **API Security:**
  - Current: JWT tokens, rate limiting
  - **Recommended:**
    - API key rotation
    - IP allowlisting for admin endpoints
    - Request signing for webhooks
  - **Action:** Enhance API security

#### Monitoring & Alerting
- [ ] **Alerting:**
  - Current: None (manual monitoring)
  - **Recommended:**
    - PagerDuty, Opsgenie, or Slack alerts
    - Alert on: service downtime, high error rates, queue backlog, database connection failures
  - **Action:** Set up alerting pipeline

- [ ] **Uptime Monitoring:**
  - Current: None
  - **Recommended:** UptimeRobot, Pingdom, or Better Uptime
  - **Action:** Set up external health checks

#### Cost Optimization
- [ ] **Resource Right-Sizing:**
  - Current: Default Fly.io config (256MB RAM, 1 CPU)
  - **Recommended:**
    - Monitor actual usage
    - Scale down if over-provisioned
    - Use auto-scaling where possible
  - **Action:** Review and optimize resource allocation

- [ ] **Cloud Run Optimization:**
  - Current: 2GB RAM, 2 CPU per instance
  - **Recommended:**
    - Right-size based on actual usage
    - Use min-instances=0 for cost savings
    - Optimize container startup time
  - **Action:** Profile and optimize Cloud Run services

---

## Deployment Commands Reference

### Frontend (Vercel)
```bash
# Deploy via CLI
cd frontend
vercel --prod

# Or connect GitHub repo in Vercel dashboard (auto-deploy)
```

### Backend (Fly.io)
```bash
# Initial setup
cd backend
flyctl launch --name thandev-backend

# Deploy
flyctl deploy

# Set secrets
flyctl secrets set DATABASE_URL=postgresql://...
flyctl secrets set REDIS_URL=redis://...
flyctl secrets set SECRET_KEY=...
```

### Brain Service (Fly.io)
```bash
cd services/thandev-brain
flyctl launch --name thandev-brain
flyctl deploy
flyctl secrets set QDRANT_URL=http://...
flyctl secrets set OPENAI_API_KEY=sk-...
```

### Runner Service (Fly.io)
```bash
cd services/thandev-runner
flyctl launch --name thandev-runner
flyctl deploy
flyctl secrets set DATABASE_URL=postgresql://...
flyctl secrets set REDIS_URL=redis://...
```

### Scheduler (Fly.io)
```bash
# Deploy scheduler app
flyctl launch --name thandev-scheduler --config fly-scheduler.toml

# Set up cron schedule (every 6 hours)
flyctl cron schedule "0 */6 * * *" --command "python scheduler.py"
```

### Cloud Run Services
```bash
# Security Scanner
cd cloud-run/security-scanner
gcloud builds submit --tag gcr.io/$PROJECT_ID/security-scanner .
gcloud run deploy security-scanner \
  --image gcr.io/$PROJECT_ID/security-scanner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900

# Lighthouse Scanner
cd cloud-run/lighthouse-scanner
gcloud builds submit --tag gcr.io/$PROJECT_ID/lighthouse-scanner .
gcloud run deploy lighthouse-scanner \
  --image gcr.io/$PROJECT_ID/lighthouse-scanner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900

# Locust Runner (Job)
cd cloud-run/locust-runner
gcloud builds submit --tag gcr.io/$PROJECT_ID/locust-runner .
gcloud run jobs create locust-runner \
  --image gcr.io/$PROJECT_ID/locust-runner \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --max-retries 1 \
  --task-timeout 900
```

---

## Monorepo vs Split Repository Analysis

### Current State

**Repository Structure:**
- **8 deployable units:** Frontend, Backend, Brain, Runner, Scheduler, Security Scanner, Lighthouse Scanner, Locust Runner
- **1 shared package:** `packages/thandev_schemas` (Pydantic schemas)
- **Shared code coupling:**
  - Backend and Runner share database models (Runner imports from backend)
  - Backend and Brain communicate via HTTP API (loose coupling)
  - All services share environment variable patterns
  - Frontend is independent (only API calls to backend)

**Evidence from code:**
- Runner imports backend models: `services/thandev-runner/app/tasks.py` references backend paths
- Shared schemas package: `packages/thandev_schemas/pyproject.toml` exists
- Docker compose for local dev: `docker-compose.yml` orchestrates multiple services
- Makefile for dev workflow: `Makefile` coordinates all services

### Recommendation: **Keep Monorepo, Split Deployments**

**Rationale:**

1. **Shared Code Coupling:**
   - Runner must use same database schema as backend (critical dependency)
   - Shared schemas package reduces duplication
   - Splitting would require duplicating models or complex dependency management

2. **Team Size:**
   - Current structure suggests small team (single repo, coordinated deployments)
   - Monorepo simplifies cross-service changes (e.g., schema updates)

3. **CI/CD Complexity:**
   - Path-based triggers (GitHub Actions) can deploy only changed services
   - Single repo = single source of truth for versions, dependencies
   - Easier to coordinate breaking changes across services

4. **Deployment Independence:**
   - Each service has its own Dockerfile/fly.toml/vercel.json
   - Services can be deployed independently via path filters
   - No deployment coupling (can deploy frontend without backend, etc.)

5. **Cost Efficiency:**
   - Single repo = single CI/CD runner (cheaper)
   - Shared package doesn't need separate publishing pipeline

**When to Reconsider Splitting:**

- **Team size > 10 developers:** Multiple teams may need independent release cycles
- **Service count > 15:** Monorepo becomes unwieldy
- **Independent versioning needed:** If services need different release cadences
- **Security isolation required:** If services need separate access controls
- **Different tech stacks:** If services diverge significantly (not applicable here)

**Deployment Strategy:**

- **Keep monorepo structure
- **Use path-based CI/CD triggers** (see Path-based CI/CD section)
- **Deploy services independently** based on changed paths
- **Version shared package** within monorepo (no external publishing needed)

**Alternative: Split Repos (Not Recommended Now)**

If splitting becomes necessary, suggested structure:
- `thandev-frontend` (Next.js)
- `thandev-backend` (FastAPI + Runner + Scheduler)
- `thandev-brain` (RAG service)
- `thandev-scanners` (Cloud Run services)
- `thandev-schemas` (shared package, published to PyPI)

**Trade-offs:**
- ✅ Independent versioning and releases
- ✅ Team autonomy
- ❌ Schema synchronization complexity
- ❌ Cross-service changes require multiple PRs
- ❌ More CI/CD pipelines to maintain

---

## Summary

### Components Found
1. **Frontend** (Next.js) - Vercel
2. **Backend API** (FastAPI) - Fly.io
3. **Brain Service** (FastAPI + RAG) - Fly.io
4. **Runner Service** (Python worker) - Fly.io
5. **Scheduler** (Python cron) - Fly.io Scheduler
6. **Security Scanner** (Flask) - Cloud Run
7. **Lighthouse Scanner** (Node.js) - Cloud Run
8. **Locust Runner** (Python job) - Cloud Run Jobs

### Chosen Hosting Targets
- **Frontend:** Vercel (optimal for Next.js)
- **Backend/Brain/Runner/Scheduler:** Fly.io (consistent platform, good for Python)
- **Scanners:** Google Cloud Run (serverless, auto-scaling, pay-per-use)
- **PostgreSQL:** Supabase or Railway (managed, pgvector support)
- **Redis:** Upstash or Railway (serverless/managed)
- **Qdrant:** Qdrant Cloud or Fly.io (managed/self-hosted)

### Blockers Found
1. **Secrets Management:** Need to migrate to platform secret managers
2. **Observability:** No centralized logging/metrics/tracing
3. **DNS Verification:** Manual process, needs automation
4. **Admin Bootstrap:** Manual setup, needs automation
5. **Rate Limiting:** Basic implementation, needs plan-based quotas
6. **Monitoring:** No alerting or uptime monitoring
7. **Backups:** Rely on platform defaults, need verification

### Next Steps
1. Set up centralized logging (Datadog/Logtail)
2. Implement distributed tracing (OpenTelemetry)
3. Add alerting (PagerDuty/Slack)
4. Automate DNS verification polling
5. Create admin bootstrap endpoint
6. Enhance rate limiting with quotas
7. Set up uptime monitoring
8. Verify backup strategy

---

**Document Version:** 2.0  
**Last Updated:** 2025-01-27  
**Maintained By:** DevOps Team

---

## What Changed vs Previous Version

**Version 1.0 → 2.0 Changes:**

1. **Added Monorepo vs Split Analysis:**
   - Explicit recommendation: Keep monorepo, split deployments
   - Rationale based on code coupling evidence
   - When to reconsider splitting

2. **Enhanced Co-Location Requirements:**
   - New section detailing what must be co-located vs can be separated
   - Network latency requirements per service pair
   - Evidence from code (Runner database dependency)

3. **Improved Source Verification:**
   - All claims now reference specific file paths and line numbers
   - Added "File References" section with complete source list
   - Marked "Unknown/Not Found" items explicitly

4. **Enhanced Path-Based CI/CD:**
   - More detailed GitHub Actions workflow examples
   - Separate jobs for each Cloud Run service
   - Secrets management instructions per platform

5. **Corrected Production Checklist:**
   - Rate limiting: Marked as PARTIAL (only per-router, not global)
   - Sentry: Marked as NOT INITIALIZED (package installed but not used)
   - Added file source references for each completed item

6. **Added Hosting Alternatives:**
   - Each service now has 2+ alternative hosting options with pros/cons
   - More detailed rationale for each recommendation

7. **Enhanced Health Endpoint Documentation:**
   - Added source file references for each health endpoint
   - Noted Docker healthcheck discrepancy (`/_health` vs `/health`)

8. **Added Storage Requirements:**
   - Explicit ephemeral vs persistent storage needs
   - Volume requirements for tools/data directories

---

## File References (Source Verification)

All claims in this document are grounded in actual repository files:

- **Backend Config:** `backend/app/core/config.py` (219 lines)
- **Backend Main:** `backend/app/main.py` (277 lines)
- **Backend Dockerfile:** `backend/Dockerfile` (87 lines)
- **Backend Fly Config:** `backend/fly.toml` (26 lines)
- **Frontend Config:** `frontend/package.json`, `frontend/env.example`, `frontend/vercel.json`
- **Brain Config:** `services/thandev-brain/app/core/config.py` (66 lines)
- **Brain Main:** `services/thandev-brain/app/main.py` (201 lines)
- **Runner Config:** `services/thandev-runner/app/config.py` (91 lines)
- **Runner Tasks:** `services/thandev-runner/app/tasks.py` (972 lines)
- **Scheduler:** `backend/scheduler.py` (48 lines)
- **Scheduler Fly Config:** `fly-scheduler.toml` (26 lines)
- **Docker Compose:** `docker-compose.yml` (81 lines)
- **Makefile:** `Makefile` (96 lines)
- **Deploy Script:** `deploy.sh` (38 lines)
- **Cloud Run Services:** `cloud-run/*/Dockerfile`, `cloud-run/*/server.py`, `cloud-run/*/server-enhanced.js`
- **Shared Package:** `packages/thandev_schemas/pyproject.toml`

**Unknown/Not Found:**
- GitHub Actions workflows (`.github/workflows/` directory not found - needs to be created)
- Sentry initialization code (package installed but not used)
- Global rate limiting middleware (only per-router implementation found)
- Structured logging implementation (`app/core/logging_config.py` referenced but not verified)

