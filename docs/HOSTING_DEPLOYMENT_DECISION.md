# Thandev Hosting & Deployment Decision

**Generated:** 2025-01-27  
**Repository:** thandev  
**Purpose:** Production-grade hosting and deployment architecture decision document  
**Auditor:** DevOps/Platform Engineering Team

---

## 1. Executive Summary

Thandev is a security intelligence platform providing real-time CVE data, security scanning, performance analysis, and exploit feeds. The system consists of 8 deployable services (Frontend, Backend API, Brain RAG service, Runner worker, Scheduler, 3 Cloud Run scanners) plus shared infrastructure (PostgreSQL, Redis, Qdrant). The architecture follows a microservices pattern with a monorepo structure, where services communicate via HTTP APIs and Redis streams. The critical data flow path is: **Frontend (Vercel) → Backend API (Fly.io) → Redis Streams → Runner Worker (Fly.io) → Cloud Run Scanners (GCP) → Findings Database (PostgreSQL)**. The system is designed for horizontal scaling of stateless API services, with stateful workers consuming from Redis streams, and auto-scaling Cloud Run jobs for resource-intensive scanning operations.

### Monorepo Recommendation: **KEEP MONOREPO, SPLIT DEPLOYMENTS**

**Rationale:**

1. **Critical Code Coupling:** Runner service must share the exact same database schema as Backend (evidenced by `services/thandev-runner/app/config.py:25-26` comment: "CRITICAL: Runner must use the SAME database as backend"). Splitting would require complex schema synchronization or duplication.

2. **Shared Package Dependency:** `packages/thandev_schemas` is used by multiple services. Monorepo allows direct imports without external package publishing overhead.

3. **Coordinated Schema Changes:** Database migrations (Alembic) affect both Backend and Runner. Monorepo enables atomic schema updates across dependent services.

4. **Small Team Size:** Current structure suggests small team (<10 developers). Monorepo simplifies cross-service development and reduces CI/CD complexity.

5. **Deployment Independence:** Each service has independent deployment configs (fly.toml, vercel.json, Dockerfiles). Path-based CI/CD can deploy only changed services, maintaining deployment independence while keeping code together.

**When to Reconsider Splitting:**
- Team size exceeds 10 developers with independent release cycles
- Service count exceeds 15 deployable units
- Services require independent versioning and release cadences
- Security/compliance requires separate repository access controls

---

## 2. Repository Inventory

### Top-Level Structure

```
thandev/
├── backend/                          # [DEPLOYABLE] FastAPI main API service
│   ├── app/
│   │   ├── main.py                  # Entrypoint: uvicorn app.main:app
│   │   ├── api/                     # API routers (scans, projects, users, etc.)
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (50+ env vars)
│   │   │   ├── database.py          # SQLAlchemy engine/session
│   │   │   └── logging_config.py    # Structured logging (referenced)
│   │   └── services/                # Business logic (scan orchestrator, etc.)
│   ├── migrations/                  # Alembic database migrations
│   ├── scheduler.py                 # [DEPLOYABLE] CVE ingestion cron job
│   ├── Dockerfile                    # Container build (Python 3.11, Chrome, Lighthouse)
│   ├── fly.toml                     # Fly.io deployment config
│   ├── requirements.txt             # Python dependencies
│   ├── alembic.ini                  # Alembic migration config
│   └── init_db.py                    # Database initialization script
│
├── frontend/                         # [DEPLOYABLE] Next.js 14 frontend
│   ├── app/                          # Next.js App Router
│   ├── components/                  # React components
│   ├── lib/                         # Utility libraries
│   ├── prisma/                      # Prisma schema (optional, for local DB)
│   ├── package.json                 # Node.js dependencies
│   ├── Dockerfile                    # Container build (Node 20)
│   ├── vercel.json                  # Vercel deployment config
│   └── env.example                  # Environment variables template
│
├── services/
│   ├── thandev-brain/               # [DEPLOYABLE] RAG-powered AI service
│   │   ├── app/
│   │   │   ├── main.py              # Entrypoint: uvicorn app.main:app
│   │   │   ├── api/v1.py            # FastAPI routers
│   │   │   ├── core/config.py       # Settings (RAG, Qdrant, OpenAI)
│   │   │   ├── rag/                 # RAG store implementations
│   │   │   └── controller/         # Session controller
│   │   ├── requirements.txt         # Python dependencies
│   │   └── start_brain.sh           # Startup script
│   │
│   └── thandev-runner/              # [DEPLOYABLE] Scan execution worker
│       ├── app/
│       │   ├── tasks.py             # Entrypoint: python -m app.tasks
│       │   ├── config.py            # Settings (Redis, Database, Consumer)
│       │   ├── executor.py          # Tool execution adapter
│       │   ├── queue.py             # Redis streams consumer
│       │   └── ingestion.py        # Findings ingestion to DB
│       ├── requirements.txt         # Python dependencies
│       └── start_runner.sh          # Startup script
│
├── cloud-run/                        # [DEPLOYABLE] Google Cloud Run services
│   ├── security-scanner/            # Nuclei/Nmap/SSLScan scanner
│   │   ├── Dockerfile               # Ubuntu 22.04, Go, Nuclei, Nmap
│   │   ├── server.py                # Flask API (Flask, CORS)
│   │   ├── scanner.py               # SecurityScanner class
│   │   └── result_processor.py      # Result processing
│   │
│   ├── lighthouse-scanner/           # Performance scanner
│   │   ├── Dockerfile               # Node 18 Alpine, Chromium
│   │   ├── server-enhanced.js      # Express API
│   │   └── package.json            # Node dependencies
│   │
│   └── locust-runner/               # Load testing job
│       ├── Dockerfile               # Python 3.11 slim
│       ├── run_locust.py            # Entrypoint script
│       └── locustfile.py            # Locust test definition
│
├── packages/
│   └── thandev_schemas/             # [LIBRARY] Shared Pydantic schemas
│       ├── pyproject.toml           # Package config
│       └── thandev_schemas/         # Python package
│
├── scripts/                         # [INFRA] Development/deployment scripts
│   ├── bootstrap_dev.sh            # Dev environment bootstrap
│   ├── venv_backend.sh             # Backend venv wrapper
│   ├── venv_runner.sh              # Runner venv wrapper
│   ├── venv_brain.sh               # Brain venv wrapper
│   └── doctor.py                   # System health check
│
├── wordlists/                       # [DATA] Security scanning wordlists
│
├── docker-compose.yml               # [INFRA] Local development orchestration
├── fly-scheduler.toml               # [INFRA] Fly.io scheduler config
├── vercel.json                      # [INFRA] Vercel root config
├── Makefile                         # [INFRA] Development commands
└── deploy.sh                        # [INFRA] Quick deployment script
```

### Deployable Units Summary

| Unit | Type | Runtime | Entrypoint | Port | State |
|------|------|---------|------------|------|-------|
| **Backend API** | Web Service | Python 3.11, FastAPI | `uvicorn app.main:app` | 8000 | Stateless |
| **Frontend** | Web App | Node.js 20, Next.js 14 | `npm run start` | 3000 | Stateless |
| **Brain Service** | Web Service | Python 3.11, FastAPI | `uvicorn app.main:app` | 8001 | Stateless |
| **Runner Service** | Background Worker | Python 3.11 | `python -m app.tasks` | N/A | Stateful |
| **Scheduler** | Cron Job | Python 3.11 | `python scheduler.py` | N/A | Stateless |
| **Security Scanner** | Cloud Run Service | Python 3.11, Flask | `python3 server.py` | 8080 | Stateless |
| **Lighthouse Scanner** | Cloud Run Service | Node.js 18, Express | `node server-enhanced.js` | 8080 | Stateless |
| **Locust Runner** | Cloud Run Job | Python 3.11 | `python run_locust.py` | N/A | Stateless |

### Shared Infrastructure

| Component | Type | Purpose | Hosting Recommendation |
|-----------|------|---------|----------------------|
| **PostgreSQL** | Database | Primary data store (users, scans, findings) | Supabase or Railway (managed) |
| **Redis** | Cache/Queue | Redis streams (scan steps), session state, rate limiting | Upstash (serverless) or Railway |
| **Qdrant** | Vector DB | RAG embeddings for Brain service | Qdrant Cloud (managed) or Fly.io (self-hosted) |

---

## 3. Service-by-Service Breakdown

### 3.1 Backend API (`backend/`)

**Name:** Thandev Backend API  
**Path:** `backend/`  
**Role:** Main REST API service providing endpoints for scans, projects, users, findings, metrics, notifications, admin operations, authentication.

**Entrypoint:**
```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production (Docker)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Production with Gunicorn (recommended)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Ports:**
- Internal: 8000 (configurable via `PORT` env var)
- External: 8000 (Fly.io maps to public URL)

**Dockerfile:**
- Location: `backend/Dockerfile`
- Base: `python:3.11-slim`
- Build Context: `./backend`
- Includes: Chrome, Lighthouse, Node.js 18 (for Lighthouse)
- Healthcheck: `curl -f http://localhost:8000/_health` (NOTE: endpoint is `/health`, not `/_health` - **ISSUE FOUND**)
- CMD: `python init_db.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`

**Deploy Config:**
- Fly.io: `backend/fly.toml` (app: `thandev-backend`, region: `iad`, 1 CPU, 256MB RAM, auto-stop enabled)

**Runtime:**
- Language: Python 3.11
- Framework: FastAPI 0.112.0, Uvicorn 0.30.6
- WSGI Server: Gunicorn 21.2.0 (optional, for production)

**Dependencies:**
- **PostgreSQL:** Primary database (shared with Runner)
  - Tables: `users`, `tenants`, `projects`, `scan_jobs`, `findings`, `notifications`, `performance_scans`, `domain_verifications`, `audit_logs`, `entitlements`, `allowed_domains`
  - Connection: `DATABASE_URL` env var
- **Redis:** Task queues (Redis streams), caching, session state
  - Connection: `REDIS_URL` env var
  - Default: `redis://localhost:6380/0`
- **Brain Service (optional):** RAG-powered scan planning
  - Connection: `BRAIN_SERVICE_URL` (default: `http://localhost:8001`)
  - HTTP API calls
- **External APIs:**
  - NVD API: CVE data ingestion (optional `NVD_API_KEY`)
  - GitHub OAuth: User authentication (via Frontend)

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

# Brain Service (optional)
BRAIN_SERVICE_URL=http://brain-service:8001
BRAIN_SERVICE_ENABLED=true
BRAIN_REQUIRED=false
BRAIN_SERVICE_TIMEOUT=30

# OpenAI (optional)
OPENAI_API_KEY=sk-...

# NVD API (optional)
NVD_API_KEY=...

# Tenant/Admin
THANDEV_SUPERADMIN_EXTERNAL_IDS=github:123456,github:789012
THANDEV_SETUP_TOKEN=<one-time-bootstrap-token>
SELF_SERVICE_SIGNUP_ENABLED=false

# Domain Verification
DOMAIN_VERIFICATION_DISABLED=false
ALLOWED_SCAN_DOMAINS=example.com,demo.com

# Scan Configuration
MAX_PARALLEL_TOOLS=5
MAX_SCAN_TIMEOUT_SECONDS=3600
TOOL_EXECUTION_TIMEOUT_SECONDS=900
SCAN_RECOVERY_ENABLED=false
```

**Data Storage:**
- **Ephemeral:** Application code, logs
- **Persistent:** None (stateless API)
- **External:** PostgreSQL (data), Redis (cache/queues)

**Latency Sensitivity:**
- Database: <10ms (critical for query performance)
- Redis: <5ms (critical for queue operations)
- Brain Service: <50ms (acceptable for HTTP API)
- Cloud Run Scanners: <100ms (acceptable for HTTP API)

**Scaling Model:**
- **Type:** Stateless (horizontal scaling)
- **Constraints:** Requires shared PostgreSQL and Redis
- **Recommended:** 2-4 Gunicorn workers per instance, multiple instances
- **Failure Modes:**
  - Database connection loss: Returns 500 on `/ready` endpoint
  - Redis connection loss: Scan step publishing fails, returns 500 on `/ready`
  - Brain service unavailable: Falls back to legacy orchestrator if `BRAIN_REQUIRED=false`

**Recommended Hosting Target:**
- **Best:** Fly.io
  - **Why:** Already configured (`fly.toml`), auto-scaling, global edge, persistent volumes available, built-in health checks
  - **Config:** 1 CPU, 256MB RAM (can scale up), auto-stop enabled (cost optimization)
  - **Alternative 1:** Railway
    - Pros: Simple deployment, PostgreSQL included, good DX
    - Cons: Less control, pricing can spike, no auto-stop
  - **Alternative 2:** Google Cloud Run
    - Pros: Serverless, auto-scaling, pay-per-use
    - Cons: Cold starts (2-5s), 15min timeout limit, no persistent volumes

---

### 3.2 Frontend (`frontend/`)

**Name:** Thandev Frontend  
**Path:** `frontend/`  
**Role:** Next.js 14 application with App Router providing user interface for scans, projects, findings, dashboard, authentication, security news, exploit feeds.

**Entrypoint:**
```bash
# Development
npm run dev  # Port 3000

# Production
npm run build
npm run start  # Port 3000
```

**Ports:**
- Internal: 3000 (configurable via `PORT` env var)
- External: 3000 (Vercel maps to public URL)

**Dockerfile:**
- Location: `frontend/Dockerfile`
- Base: `node:20`
- Build Context: `./frontend`
- CMD: `npm run dev` (development mode - **ISSUE FOUND**: should be `npm run start` for production)

**Deploy Config:**
- Vercel: `vercel.json` (rootDirectory: `frontend`, framework: `nextjs`)

**Runtime:**
- Language: TypeScript/JavaScript
- Framework: Next.js 14.2.32
- Node.js: 20

**Dependencies:**
- **Backend API:** REST API calls
  - Connection: `NEXT_PUBLIC_API_BASE` env var
- **PostgreSQL (optional):** Via Prisma for local data (if used)
  - Connection: `DATABASE_URL` env var (optional)
- **NextAuth.js:** GitHub OAuth authentication
  - Requires: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

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

**Data Storage:**
- **Ephemeral:** Build artifacts (`.next` directory), node_modules
- **Persistent:** None (stateless)
- **External:** Backend API (all data)

**Latency Sensitivity:**
- Backend API: <200ms (acceptable for user experience)
- Static assets: CDN-cached (Vercel edge)

**Scaling Model:**
- **Type:** Stateless (horizontal scaling)
- **Constraints:** None (fully stateless)
- **Recommended:** Vercel edge functions for API routes, CDN for static assets
- **Failure Modes:**
  - Backend API unavailable: User sees error messages, graceful degradation
  - GitHub OAuth failure: Authentication fails, user cannot login

**Recommended Hosting Target:**
- **Best:** Vercel
  - **Why:** Zero-config Next.js, edge functions, automatic deployments, built-in analytics, CDN
  - **Config:** `vercel.json` specifies `rootDirectory: "frontend"`
  - **Alternative 1:** Netlify
    - Pros: Good Next.js support, edge functions, free tier
    - Cons: Slightly less optimized than Vercel for Next.js
  - **Alternative 2:** Railway/Render
    - Pros: Full control, Docker support
    - Cons: Need to configure Next.js manually, no edge functions, higher cost

---

### 3.3 Brain Service (`services/thandev-brain/`)

**Name:** Thandev Brain Service  
**Path:** `services/thandev-brain/`  
**Role:** RAG-powered AI service for scan planning, report prompt generation, finding enrichment using OpenAI + vector store (Qdrant or PgVector).

**Entrypoint:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Ports:**
- Internal: 8001 (configurable via `PORT` env var)
- External: 8001 (Fly.io maps to public URL)

**Dockerfile:**
- Location: Not found (needs to be created - **ISSUE FOUND**)
- Should be: Similar to backend (Python 3.11, FastAPI)

**Deploy Config:**
- Fly.io: Not found (needs to be created - **ISSUE FOUND**)

**Runtime:**
- Language: Python 3.11
- Framework: FastAPI 0.104.0+, Uvicorn

**Dependencies:**
- **Qdrant (default):** Vector database for RAG
  - Connection: `QDRANT_URL` (default: `http://localhost:6333`)
  - Collection: `QDRANT_COLLECTION` (default: `thandev_rag`)
- **OR PgVector:** Alternative vector store using PostgreSQL
  - Connection: `DATABASE_URL` (with pgvector extension)
- **Redis:** Session state, queues
  - Connection: `REDIS_URL`
- **OpenAI API:** Embeddings and LLM calls
  - Connection: `OPENAI_API_KEY` (required for finding enrichment)
  - Models: `gpt-4o-mini` (enrichment), `text-embedding-3-small` (embeddings)

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
EMBEDDING_MODEL=all-MiniLM-L6-v2
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
SESSION_MAX_CONSECUTIVE_FAILURES=3

# Finding Enrichment
ENRICH_FINDINGS_ENABLED=true
ENRICH_FINDINGS_MODEL=gpt-4o-mini
ENRICH_FINDINGS_TIMEOUT_SEC=30
```

**Data Storage:**
- **Ephemeral:** Application code, logs
- **Persistent:** None (stateless API, Qdrant stores vectors externally)
- **External:** Qdrant (vector embeddings), Redis (session state)

**Latency Sensitivity:**
- Qdrant: <10ms (critical for RAG query performance)
- Redis: <5ms (critical for session state)
- OpenAI API: <500ms (acceptable, external API)

**Scaling Model:**
- **Type:** Stateless (horizontal scaling)
- **Constraints:** Requires shared Qdrant/PgVector and Redis
- **Recommended:** Multiple instances, OpenAI API rate limiting may require queuing
- **Failure Modes:**
  - Qdrant unavailable: RAG queries fail, service returns 500 on `/ready`
  - OpenAI API failure: Finding enrichment fails, falls back to generic responses if `ENRICH_FINDINGS_ENABLED=false`
  - Redis unavailable: Session state lost, returns 500 on `/ready`

**Recommended Hosting Target:**
- **Best:** Fly.io
  - **Why:** Same platform as backend, easy networking, can deploy Qdrant on Fly.io in same region
  - **Config:** Similar to backend (1 CPU, 512MB+ RAM for embeddings), port 8001
  - **Alternative 1:** Railway
    - Pros: Simple, can deploy Qdrant as service
    - Cons: Less control, pricing can spike
  - **Alternative 2:** Render
    - Pros: Free tier, easy setup
    - Cons: Cold starts affect AI latency, no persistent volumes

---

### 3.4 Runner Service (`services/thandev-runner/`)

**Name:** Thandev Runner Service  
**Path:** `services/thandev-runner/`  
**Role:** Background worker that consumes scan step requests from Redis streams, executes security tools (Nuclei, Nmap, SSLScan, ffuf, sqlmap, etc.), and ingests findings into database.

**Entrypoint:**
```bash
python -m app.tasks
```

**Ports:**
- None (background worker, no HTTP server)

**Dockerfile:**
- Location: Not found (needs to be created - **ISSUE FOUND**)
- Should be: Python 3.11, includes security tools (Nuclei, Nmap, SSLScan, etc.)

**Deploy Config:**
- Fly.io: Not found (needs to be created - **ISSUE FOUND**)

**Runtime:**
- Language: Python 3.11
- Framework: Custom Redis streams consumer (not Celery)

**Dependencies:**
- **Redis:** Streams for step requests
  - Connection: `REDIS_URL`
  - Consumer Group: `CONSUMER_GROUP` (default: `runner-workers`)
  - Consumer Name: `CONSUMER_NAME` (default: `runner-1`, must be unique per instance)
- **PostgreSQL:** Same database as backend (CRITICAL)
  - Connection: `DATABASE_URL` (MUST match backend `DATABASE_URL`)
  - Evidence: `services/thandev-runner/app/config.py:25-26` comment
- **Local Tools:** Nuclei, Nmap, SSLScan, ffuf, sqlmap, etc.
  - Path: `TOOLS_BASE_DIR` (default: repo root `backend/` directory)
  - Data Dir: `DATA_DIR` (default: `backend/data`)
  - Jobs Dir: `JOBS_DIR` (default: `backend/data/jobs`)
  - Wordlists: `WORDLISTS_DIR` (default: `wordlists/`)

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
TOOLS_BASE_DIR=/app/backend
DATA_DIR=/app/backend/data
JOBS_DIR=/app/backend/data/jobs
WORDLISTS_DIR=/app/wordlists
```

**Data Storage:**
- **Ephemeral:** Application code, logs
- **Persistent:** REQUIRED for tool outputs
  - Volume: `backend/data/jobs/{scan_id}/` (tool output files)
  - Volume: `wordlists/` (scanning wordlists)
  - **ISSUE FOUND:** No persistent volume config in deployment files

**Latency Sensitivity:**
- Database: <10ms (critical for scan job updates, findings ingestion)
- Redis: <5ms (critical for stream consumption)
- Tool execution: Variable (Nuclei: 1-10min, Nmap: 30s-5min, etc.)

**Scaling Model:**
- **Type:** Stateful worker (multiple instances with unique consumer names)
- **Constraints:**
  - Requires access to security tools (installed binaries or Docker volume)
  - Requires persistent volume for tool outputs
  - Each instance must have unique `CONSUMER_NAME`
  - Redis streams handle load balancing automatically
- **Recommended:** 2-5 instances for redundancy, scale based on queue depth
- **Failure Modes:**
  - Database connection loss: Findings ingestion fails, scan jobs stuck in RUNNING
  - Redis connection loss: Cannot consume steps, worker loop exits
  - Tool execution failure: Step marked as failed, continues to next step
  - Tool not found: Execution fails, error logged

**Recommended Hosting Target:**
- **Best:** Fly.io (VM with persistent volume)
  - **Why:** Can install tools, persistent storage for outputs, good for long-running workers, same region as backend
  - **Config:** 2 CPU, 2GB RAM (for tool execution), persistent volume for `backend/data/` and `wordlists/`
  - **Alternative 1:** Railway (Docker with tool installation)
    - Pros: Simple, good Docker support
    - Cons: Ephemeral storage (need volumes), less control
  - **Alternative 2:** Self-hosted VM (DigitalOcean, AWS EC2)
    - Pros: Full control, can install tools easily, persistent storage
    - Cons: Manual scaling, infrastructure management, higher operational overhead

---

### 3.5 Scheduler (`backend/scheduler.py`)

**Name:** CVE Data Ingestion Scheduler  
**Path:** `backend/scheduler.py`  
**Role:** Background cron-like service that runs CVE data ingestion from NVD API every 6 hours.

**Entrypoint:**
```bash
python scheduler.py
```

**Ports:**
- None (background process)

**Dockerfile:**
- Uses: `backend/Dockerfile` (same as Backend API)

**Deploy Config:**
- Fly.io: `fly-scheduler.toml` (app: `thandev-scheduler`, region: `iad`, 1 CPU, 256MB RAM)
- Process: `python scheduler.py` (not HTTP service)

**Runtime:**
- Language: Python 3.11
- Framework: `schedule` library (1.2.0)

**Dependencies:**
- **PostgreSQL:** Same database as backend (CVE data storage)
  - Connection: `DATABASE_URL`
- **NVD API:** Optional API key for higher rate limits
  - Connection: `NVD_API_KEY` (optional)
  - Rate limit: 50 requests per 30 seconds without key, higher with key

**Required Environment Variables:**
```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Redis (optional, if used)
REDIS_URL=redis://host:port/db

# NVD API (optional)
NVD_API_KEY=...
```

**Data Storage:**
- **Ephemeral:** Application code, logs
- **Persistent:** None (writes to PostgreSQL)
- **External:** PostgreSQL (CVE data)

**Latency Sensitivity:**
- Database: <50ms (acceptable, not time-critical)
- NVD API: Variable (external API, rate-limited)

**Scaling Model:**
- **Type:** Single instance (prevents duplicate ingestion)
- **Constraints:** Should run as single instance to avoid duplicate CVE ingestion
- **Recommended:** Fly.io Scheduler (cron) or Cloud Run Jobs (scheduled)
- **Failure Modes:**
  - Database connection loss: Ingestion fails, logs error, retries on next schedule
  - NVD API failure: Ingestion fails, logs error, retries on next schedule

**Recommended Hosting Target:**
- **Best:** Fly.io Scheduler
  - **Why:** Already configured (`fly-scheduler.toml`), built-in cron, automatic execution, no always-on cost
  - **Config:** Runs every 6 hours (configured in `scheduler.py:34`)
  - **Alternative 1:** Cloud Run Jobs (scheduled)
    - Pros: Serverless, pay-per-execution
    - Cons: Need to set up Cloud Scheduler, GCP-specific
  - **Alternative 2:** GitHub Actions (scheduled workflow)
    - Pros: Free, version controlled
    - Cons: External dependency, not ideal for production

---

### 3.6 Security Scanner (`cloud-run/security-scanner/`)

**Name:** Security Scanner Cloud Run Service  
**Path:** `cloud-run/security-scanner/`  
**Role:** Google Cloud Run service that executes security scans (Nuclei, Nmap, SSLScan) on-demand via HTTP API.

**Entrypoint:**
```bash
python3 server.py
```

**Ports:**
- Internal: 8080 (Cloud Run default, configurable via `PORT` env var)
- External: Cloud Run provides HTTPS URL

**Dockerfile:**
- Location: `cloud-run/security-scanner/Dockerfile`
- Base: `ubuntu:22.04`
- Includes: Go 1.21, Nuclei, Nmap, SSLScan, Subfinder, Python 3, Flask
- CMD: `python3 server.py`

**Deploy Config:**
- Cloud Run: Deploy via `gcloud run deploy` (see Deployment Commands)

**Runtime:**
- Language: Python 3.11, Flask
- Tools: Nuclei (Go), Nmap, SSLScan (system packages)

**Dependencies:**
- **External Tools:** Nuclei, Nmap, SSLScan, Subfinder (installed in Docker image)
- **Google Cloud Storage (optional):** For result artifacts
  - Connection: `GCS_BUCKET` env var (optional)

**Required Environment Variables:**
```bash
# None required (optional GCS for artifacts)
GCS_BUCKET=thandev-reports  # Optional
PORT=8080  # Cloud Run sets this automatically
```

**Data Storage:**
- **Ephemeral:** Tool outputs (in-memory job storage)
- **Persistent:** None (stateless, results returned via API)
- **External:** Google Cloud Storage (optional, for artifacts)

**Latency Sensitivity:**
- Tool execution: Variable (Nuclei: 1-10min, Nmap: 30s-5min, SSLScan: 10s-2min)
- API response: <100ms for job creation, results via polling

**Scaling Model:**
- **Type:** Stateless (auto-scaling Cloud Run service)
- **Constraints:** 
  - Memory: 2GB (for Chrome/Nuclei)
  - CPU: 2 vCPUs (for parallel tool execution)
  - Timeout: 900 seconds (15 minutes) per request
- **Recommended:** Auto-scales based on requests, max 10 instances
- **Failure Modes:**
  - Tool execution timeout: Returns error, job marked as failed
  - Memory exhaustion: Container killed, job fails
  - Tool not found: Returns 500 error

**Recommended Hosting Target:**
- **Best:** Google Cloud Run
  - **Why:** Serverless, auto-scaling, pay-per-use, 15min timeout, 2GB memory support
  - **Config:** 2GB RAM, 2 CPU, timeout 900s, max instances 10
  - **Alternative 1:** Fly.io (with Dockerfile)
    - Pros: Global edge, no cold starts
    - Cons: Always-on cost, need to manage scaling, 256MB RAM limit (too small)
  - **Alternative 2:** AWS Lambda (with container support)
    - Pros: Serverless, pay-per-use
    - Cons: 15min timeout, cold starts, memory limits

---

### 3.7 Lighthouse Scanner (`cloud-run/lighthouse-scanner/`)

**Name:** Lighthouse Performance Scanner  
**Path:** `cloud-run/lighthouse-scanner/`  
**Role:** Google Cloud Run service for performance scanning using Lighthouse (headless Chrome).

**Entrypoint:**
```bash
node server-enhanced.js
```

**Ports:**
- Internal: 8080 (Cloud Run default, configurable via `PORT` env var)
- External: Cloud Run provides HTTPS URL

**Dockerfile:**
- Location: `cloud-run/lighthouse-scanner/Dockerfile`
- Base: `node:18-alpine`
- Includes: Chromium, Lighthouse (NPM package)
- CMD: `node server-enhanced.js`

**Deploy Config:**
- Cloud Run: Deploy via `gcloud run deploy` (see Deployment Commands)

**Runtime:**
- Language: Node.js 18, Express
- Tool: Lighthouse (NPM package), Chromium (headless browser)

**Dependencies:**
- **Chrome/Chromium:** Headless browser (installed in Docker image)
- **Lighthouse:** NPM package (installed in image)

**Required Environment Variables:**
```bash
# None required
PORT=8080  # Cloud Run sets this automatically
```

**Data Storage:**
- **Ephemeral:** Scan results (in-memory job storage)
- **Persistent:** None (stateless, results returned via API)

**Latency Sensitivity:**
- Lighthouse scan: 30-60 seconds (typical)
- API response: <100ms for job creation, results via polling

**Scaling Model:**
- **Type:** Stateless (auto-scaling Cloud Run service)
- **Constraints:**
  - Memory: 2GB (for Chrome + Lighthouse)
  - CPU: 2 vCPUs (for parallel scans)
  - Timeout: 900 seconds (15 minutes) per request
- **Recommended:** Auto-scales based on requests, max 10 instances
- **Failure Modes:**
  - Chrome crash: Returns error, job marked as failed
  - Memory exhaustion: Container killed, job fails
  - Timeout: Returns error after 15 minutes

**Recommended Hosting Target:**
- **Best:** Google Cloud Run
  - **Why:** Serverless, auto-scaling, pay-per-use, 2GB memory support
  - **Config:** 2GB RAM, 2 CPU, timeout 900s, max instances 10
  - **Alternative:** Same as Security Scanner

---

### 3.8 Locust Runner (`cloud-run/locust-runner/`)

**Name:** Locust Load Testing Runner  
**Path:** `cloud-run/locust-runner/`  
**Role:** Google Cloud Run Job for load testing using Locust (executes and uploads results to GCS).

**Entrypoint:**
```bash
python run_locust.py
```

**Ports:**
- None (Cloud Run Job, not a service)

**Dockerfile:**
- Location: `cloud-run/locust-runner/Dockerfile`
- Base: `python:3.11-slim`
- Includes: Locust 2.17.0, Google Cloud Storage client
- ENTRYPOINT: `python run_locust.py`

**Deploy Config:**
- Cloud Run Jobs: Deploy via `gcloud run jobs create` (see Deployment Commands)

**Runtime:**
- Language: Python 3.11
- Framework: Locust 2.17.0

**Dependencies:**
- **Google Cloud Storage:** For result uploads
  - Connection: `GCS_BUCKET` env var
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

**Data Storage:**
- **Ephemeral:** Test results (temporary files)
- **Persistent:** None (results uploaded to GCS)
- **External:** Google Cloud Storage (result artifacts)

**Latency Sensitivity:**
- Load test execution: Variable (depends on `DURATION` env var)
- GCS upload: <10s (acceptable)

**Scaling Model:**
- **Type:** One-time job (not long-running service)
- **Constraints:**
  - Memory: 2GB
  - CPU: 2 vCPUs
  - Timeout: 900 seconds (15 minutes) per job
- **Recommended:** Triggered on-demand or via Cloud Scheduler
- **Failure Modes:**
  - GCS upload failure: Results lost, job marked as failed
  - Timeout: Job killed after 15 minutes

**Recommended Hosting Target:**
- **Best:** Google Cloud Run Jobs
  - **Why:** Perfect for batch jobs, pay-per-execution, auto-scaling
  - **Config:** 2GB RAM, 2 CPU, max-retries 1, task-timeout 900s
  - **Alternative:** Fly.io (one-off machine)
    - Pros: Simple execution
    - Cons: Always-on cost if scheduled, less suitable for batch jobs

---

## 4. Co-Location & Network Requirements

### Co-Location Matrix

| Service A | Service B | Latency Requirement | Reason | Must Co-Locate? |
|-----------|-----------|---------------------|--------|-----------------|
| **Backend** | **PostgreSQL** | <10ms | Query performance, transaction consistency | ✅ YES (same region) |
| **Runner** | **PostgreSQL** | <10ms | Scan job updates, findings ingestion, shared schema | ✅ YES (same region, same DB) |
| **Backend** | **Redis** | <5ms | Queue operations, session state, rate limiting | ✅ YES (same region) |
| **Runner** | **Redis** | <5ms | Stream consumption, step publishing | ✅ YES (same region) |
| **Brain** | **Qdrant** | <10ms | Vector search performance for RAG | ✅ YES (same region, if self-hosted) |
| **Brain** | **Redis** | <5ms | Session state | ✅ YES (same region) |
| **Backend** | **Brain** | <50ms | HTTP API calls for RAG queries | ❌ NO (acceptable latency) |
| **Backend** | **Cloud Run Scanners** | <100ms | HTTP API calls for scan execution | ❌ NO (acceptable latency) |
| **Frontend** | **Backend** | <200ms | User experience | ❌ NO (acceptable latency, CDN helps) |
| **Scheduler** | **PostgreSQL** | <50ms | CVE data ingestion (not time-critical) | ❌ NO (acceptable latency) |

### Network Requirements Summary

**Must Be in Same Region:**
1. Backend + Runner + PostgreSQL (critical: shared database, <10ms)
2. Backend + Redis (critical: queue operations, <5ms)
3. Runner + Redis (critical: stream consumption, <5ms)
4. Brain + Qdrant (if self-hosted) (critical: vector search, <10ms)
5. Brain + Redis (critical: session state, <5ms)

**Can Be in Different Regions:**
1. Frontend (Vercel edge - global)
2. Cloud Run Scanners (any GCP region, prefer us-central1 for cost)
3. Scheduler (any region, runs every 6h)

**VPC/Network Requirements:**
- Backend and Runner should be in same VPC/private network if possible (for database access)
- Cloud Run services can use public internet (HTTP APIs)
- Qdrant (if self-hosted) should be in private network with Brain service

---

## 5. Hosting Matrix Table

| Component | Hosting Target | Build Command | Start Command | Port | Key Env Vars | Secrets Strategy |
|-----------|---------------|---------------|---------------|------|--------------|------------------|
| **Frontend** | Vercel | `cd frontend && npm install && npm run build` | `npm run start` | 3000 | `NEXT_PUBLIC_API_BASE`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Vercel dashboard → Environment Variables (encrypted) |
| **Backend API** | Fly.io | `cd backend && pip install -r requirements.txt && alembic upgrade head` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 8000 | `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `BRAIN_SERVICE_URL`, `OPENAI_API_KEY`, `NVD_API_KEY` | `flyctl secrets set KEY=value --app thandev-backend` |
| **Brain Service** | Fly.io | `cd services/thandev-brain && pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port 8001` | 8001 | `QDRANT_URL`, `QDRANT_COLLECTION`, `REDIS_URL`, `OPENAI_API_KEY`, `EMBEDDING_PROVIDER`, `RAG_STORE_TYPE` | `flyctl secrets set KEY=value --app thandev-brain` |
| **Runner Service** | Fly.io | `cd services/thandev-runner && pip install -r requirements.txt` | `python -m app.tasks` | N/A | `DATABASE_URL`, `REDIS_URL`, `CONSUMER_GROUP`, `CONSUMER_NAME` | `flyctl secrets set KEY=value --app thandev-runner` |
| **Scheduler** | Fly.io Scheduler | `cd backend && pip install -r requirements.txt` | `python scheduler.py` | N/A | `DATABASE_URL`, `NVD_API_KEY` | `flyctl secrets set KEY=value --app thandev-scheduler` |
| **Security Scanner** | Cloud Run | `gcloud builds submit --tag gcr.io/PROJECT/security-scanner ./cloud-run/security-scanner` | `python3 server.py` | 8080 | `GCS_BUCKET` (optional) | Google Secret Manager or `--set-env-vars` |
| **Lighthouse Scanner** | Cloud Run | `gcloud builds submit --tag gcr.io/PROJECT/lighthouse-scanner ./cloud-run/lighthouse-scanner` | `node server-enhanced.js` | 8080 | None | Google Secret Manager (if needed) |
| **Locust Runner** | Cloud Run Jobs | `gcloud builds submit --tag gcr.io/PROJECT/locust-runner ./cloud-run/locust-runner` | `python run_locust.py` | N/A | `DOMAIN`, `VUS`, `DURATION`, `GCS_BUCKET` | Google Secret Manager or `--set-env-vars` |
| **PostgreSQL** | Supabase/Railway | N/A (managed) | Managed service | 5432 | `DATABASE_URL` | Platform-managed (connection string in secrets) |
| **Redis** | Upstash/Railway | N/A (managed) | Managed service | 6379 | `REDIS_URL` | Platform-managed (connection string in secrets) |
| **Qdrant** | Qdrant Cloud/Fly.io | N/A (managed/Docker) | Managed/Docker | 6333 | `QDRANT_URL`, `QDRANT_COLLECTION` | Platform-managed (connection string in secrets) |

---

## 6. CI/CD Plan for Monorepo

### Path-Filter Deployment Strategy

**GitHub Actions Workflow:** `.github/workflows/deploy.yml` (needs to be created - **ISSUE FOUND**)

**Trigger Rules:**
- `frontend/**` → Deploy to Vercel
- `backend/**` (excluding `backend/data/**`, `backend/venv/**`) → Deploy backend to Fly.io
- `services/thandev-brain/**` → Deploy brain to Fly.io
- `services/thandev-runner/**` → Deploy runner to Fly.io
- `backend/scheduler.py` or `backend/real_data_ingestion.py` → Deploy scheduler or trigger manual run
- `cloud-run/security-scanner/**` → Deploy security scanner to Cloud Run
- `cloud-run/lighthouse-scanner/**` → Deploy lighthouse scanner to Cloud Run
- `cloud-run/locust-runner/**` → Deploy locust runner to Cloud Run
- `packages/thandev_schemas/**` → Rebuild all dependent services (backend, brain, runner)

### GitHub Actions Workflow Example

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
      - 'packages/**'

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
        working-directory: backend

  deploy-brain:
    if: contains(github.event.head_commit.modified_files, 'services/thandev-brain/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --config services/thandev-brain/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        working-directory: services/thandev-brain

  deploy-runner:
    if: contains(github.event.head_commit.modified_files, 'services/thandev-runner/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --config services/thandev-runner/fly.toml
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
        working-directory: services/thandev-runner

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
            --cpu 2 \
            --max-retries 1 \
            --task-timeout 900
```

### Required Secrets per Platform

**Vercel:**
- `VERCEL_TOKEN` (GitHub Actions)
- `VERCEL_ORG_ID` (GitHub Actions)
- `VERCEL_PROJECT_ID` (GitHub Actions)
- Environment variables set in Vercel dashboard (encrypted)

**Fly.io:**
- `FLY_API_TOKEN` (GitHub Actions)
- Secrets set via `flyctl secrets set` (encrypted at rest)

**Google Cloud Run:**
- `GCP_SA_KEY` (Service Account JSON key for GitHub Actions)
- `GCP_PROJECT_ID` (GCP Project ID)
- Secrets in Google Secret Manager (recommended) or env vars

**GitHub Actions:**
- Repository secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `FLY_API_TOKEN`, `GCP_SA_KEY`, `GCP_PROJECT_ID`

---

## 7. Production Gaps Checklist

### ✅ Implemented

- [x] **Database Migrations:** Alembic configured (`backend/alembic.ini`, `backend/migrations/`)
- [x] **Health Check Endpoints:** Backend (`/health`, `/ready`), Brain (`/health`, `/ready`), Cloud Run scanners (`/health`)
- [x] **Dockerfiles:** Backend, Frontend, Cloud Run services
- [x] **Environment Variable Configuration:** Pydantic Settings in all services
- [x] **CORS Configuration:** Backend and Brain services
- [x] **Authentication:** GitHub OAuth via NextAuth.js
- [x] **Rate Limiting (Partial):** SlowAPI in backend (`app/routers/exploits.py`, `app/routers/security.py`, `app/routers/performance.py`)
- [x] **Error Handling:** Global exception handler in backend (`app/main.py:149-160`)
- [x] **Logging:** Structured logging support (`USE_JSON_LOGGING` env var)

### ❌ Missing / Needs Attention

#### Secrets Management
- [ ] **Centralized Secrets Manager:** Currently using platform env vars (Fly.io, Vercel). Should migrate to:
  - **Fly.io:** `flyctl secrets set` (already supported, needs migration)
  - **Vercel:** Environment variables (encrypted, but should document rotation)
  - **Cloud Run:** Google Secret Manager (recommended, not implemented)
  - **Action:** Create secrets migration guide, set up Secret Manager for Cloud Run

#### Observability
- [ ] **Centralized Logging:**
  - Current: Platform-specific logs (Fly.io logs, Vercel logs, Cloud Run logs)
  - **Recommended:** Datadog, Logtail, or Axiom for unified log aggregation
  - **Action:** Set up log forwarding from all services

- [ ] **Metrics & APM:**
  - Current: Basic health checks
  - **Recommended:**
    - Sentry (package installed but not initialized - **ISSUE FOUND**)
    - Datadog APM or New Relic for performance monitoring
    - Custom metrics dashboard (Grafana + Prometheus or Datadog)
  - **Action:** Initialize Sentry in `backend/app/main.py`, add metrics collection

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
  - Current: SlowAPI in backend (per-router only, not global)
  - **Recommended:**
    - Global rate limiting middleware
    - Per-user rate limits (tiered plans)
    - Per-IP rate limits (DDoS protection)
    - Redis-based distributed rate limiting
  - **Action:** Enhance rate limiting with global middleware and plan-based quotas

- [ ] **Scan Quotas:**
  - Current: Plan limits in code (`get_plan_limits`), not enforced at API level
  - **Recommended:**
    - Enforce quotas at API level (middleware)
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

#### Backups
- [ ] **Automated Backups:**
  - Current: Platform-managed (Supabase/Railway have backups, but need verification)
  - **Recommended:**
    - Daily automated backups (retain 30 days)
    - Point-in-time recovery (PITR)
    - Backup verification and restore testing
  - **Action:** Verify backup strategy with hosting provider, set up restore testing

#### Disaster Recovery
- [ ] **Disaster Recovery Plan:**
  - Current: None documented
  - **Recommended:**
    - RTO (Recovery Time Objective): <4 hours
    - RPO (Recovery Point Objective): <1 hour
    - Runbook for database restore, service recovery
  - **Action:** Create disaster recovery runbook

---

## 8. Diagrams

### 8.1 High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "User Layer"
        U[Users/Browsers]
    end

    subgraph "Frontend Layer - Vercel"
        FE[Next.js Frontend<br/>Port: 3000<br/>Stateless<br/>CDN Edge]
    end

    subgraph "API Layer - Fly.io (iad region)"
        BE[Backend API<br/>FastAPI<br/>Port: 8000<br/>Stateless<br/>1 CPU, 256MB]
        BR[Brain Service<br/>FastAPI<br/>Port: 8001<br/>Stateless<br/>1 CPU, 512MB]
    end

    subgraph "Worker Layer - Fly.io (iad region)"
        RN[Runner Service<br/>Python Worker<br/>Stateful<br/>2 CPU, 2GB<br/>Persistent Volume]
        SCH[Scheduler<br/>Cron Job<br/>Every 6h<br/>1 CPU, 256MB]
    end

    subgraph "Cloud Run - GCP (us-central1)"
        SS[Security Scanner<br/>Flask API<br/>Port: 8080<br/>2GB RAM, 2 CPU<br/>Auto-scaling]
        LS[Lighthouse Scanner<br/>Node.js API<br/>Port: 8080<br/>2GB RAM, 2 CPU<br/>Auto-scaling]
        LR[Locust Runner<br/>Cloud Run Job<br/>2GB RAM, 2 CPU<br/>On-demand]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Supabase/Railway<br/>Shared DB<br/>Same Region)]
        RD[(Redis<br/>Upstash/Railway<br/>Streams + Cache<br/>Same Region)]
        QD[(Qdrant<br/>Qdrant Cloud/Fly.io<br/>Vector Store<br/>Same Region)]
    end

    subgraph "External Services"
        GH[GitHub OAuth]
        OAI[OpenAI API<br/>Embeddings + LLM]
        NVD[NVD API<br/>CVE Data]
        GCS[Google Cloud Storage<br/>Artifacts]
    end

    U -->|HTTPS| FE
    FE -->|REST API<br/><200ms| BE
    FE -->|OAuth| GH
    BE -->|RAG Queries<br/><50ms| BR
    BE -->|Publish Steps<br/><5ms| RD
    BE -->|Read/Write<br/><10ms| PG
    BE -->|Session State<br/><5ms| RD
    RN -->|Consume Steps<br/><5ms| RD
    RN -->|Execute Tools| SS
    RN -->|Ingest Findings<br/><10ms| PG
    BR -->|Vector Search<br/><10ms| QD
    BR -->|Embeddings/LLM<br/><500ms| OAI
    BR -->|Session State<br/><5ms| RD
    SCH -->|CVE Ingestion<br/><50ms| NVD
    SCH -->|Store CVEs<br/><50ms| PG
    BE -->|Performance Scans| LS
    BE -->|Load Tests| LR
    SS -->|Artifacts| GCS
    LR -->|Results| GCS

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

### 8.2 Scan Request Lifecycle Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend (Vercel)
    participant BE as Backend API (Fly.io)
    participant RD as Redis Streams
    participant RN as Runner (Fly.io)
    participant SS as Security Scanner (Cloud Run)
    participant PG as PostgreSQL
    participant BR as Brain Service (Fly.io)
    participant QD as Qdrant

    U->>FE: Create Scan Request
    FE->>BE: POST /api/scans
    BE->>PG: Create ScanJob (status: PENDING)
    PG-->>BE: ScanJob ID
    
    alt Brain Service Enabled
        BE->>BR: POST /api/v1/sessions (start session)
        BR->>QD: Vector search (RAG query)
        QD-->>BR: Relevant context
        BR->>BR: Generate scan plan
        BR-->>BE: Session ID + Plan
        BE->>PG: Update ScanJob (brain_session_id, status: RUNNING)
    else Brain Disabled
        BE->>RD: Publish scan steps to Redis stream
        RD-->>BE: Acknowledged
        BE->>PG: Update ScanJob (status: RUNNING)
    end
    
    BE-->>FE: 201 Created (ScanJob)
    FE-->>U: Scan Started
    
    loop Scan Execution
        RN->>RD: Consume step request (XREADGROUP)
        RD-->>RN: Step data
        
        RN->>SS: POST /run (tool execution)
        SS-->>RN: Job ID
        SS->>SS: Execute tool (Nuclei/Nmap/etc.)
        SS-->>RN: Results (polling)
        
        RN->>PG: Ingest findings (bulk insert)
        RN->>RD: Publish step result
        RN->>PG: Update ScanJob progress
    end
    
    RN->>PG: Update ScanJob (status: COMPLETED)
    
    U->>FE: Poll scan status
    FE->>BE: GET /api/scans/{id}
    BE->>PG: Query ScanJob + Findings
    PG-->>BE: ScanJob data
    BE-->>FE: Scan results
    FE-->>U: Display results
```

---

## 9. Issues Found + Proposed Fixes

### Critical Issues

1. **Backend Dockerfile Healthcheck Mismatch**
   - **Issue:** Healthcheck uses `/_health` but endpoint is `/health`
   - **Location:** `backend/Dockerfile:82`
   - **Fix:** Change `CMD curl -f http://localhost:8000/_health` to `CMD curl -f http://localhost:8000/health`
   - **Impact:** Health checks will fail in Docker/Kubernetes

2. **Frontend Dockerfile Production Mode**
   - **Issue:** Dockerfile CMD uses `npm run dev` (development mode)
   - **Location:** `frontend/Dockerfile:8`
   - **Fix:** Change to `CMD ["npm", "run", "start"]` for production
   - **Impact:** Development server in production (performance, security)

3. **Missing Dockerfiles for Services**
   - **Issue:** Brain and Runner services lack Dockerfiles
   - **Locations:** `services/thandev-brain/`, `services/thandev-runner/`
   - **Fix:** Create Dockerfiles similar to backend (Python 3.11, FastAPI for Brain; Python 3.11, tool installation for Runner)
   - **Impact:** Cannot containerize and deploy these services

4. **Missing Fly.io Configs for Services**
   - **Issue:** Brain and Runner services lack `fly.toml` files
   - **Locations:** `services/thandev-brain/`, `services/thandev-runner/`
   - **Fix:** Create `fly.toml` files with appropriate resource allocations
   - **Impact:** Cannot deploy to Fly.io

5. **Runner Persistent Volume Not Configured**
   - **Issue:** Runner needs persistent volume for tool outputs (`backend/data/jobs/`), but no volume config in deployment files
   - **Location:** `services/thandev-runner/` deployment config
   - **Fix:** Add Fly.io volume mount in `fly.toml` for `backend/data/` and `wordlists/`
   - **Impact:** Tool outputs lost on container restart

### High Priority Issues

6. **Sentry Not Initialized**
   - **Issue:** Sentry SDK installed but not imported/initialized in `backend/app/main.py`
   - **Location:** `backend/app/main.py`
   - **Fix:** Add Sentry initialization at startup:
     ```python
     import sentry_sdk
     from sentry_sdk.integrations.fastapi import FastApiIntegration
     sentry_sdk.init(
         dsn=os.getenv("SENTRY_DSN"),
         integrations=[FastApiIntegration()],
         traces_sample_rate=0.1,
     )
     ```
   - **Impact:** No error tracking in production

7. **Rate Limiting Not Global**
   - **Issue:** Rate limiting only implemented in specific routers, not as global middleware
   - **Location:** `backend/app/routers/exploits.py`, `backend/app/routers/security.py`, `backend/app/routers/performance.py`
   - **Fix:** Add global rate limiting middleware in `backend/app/main.py`
   - **Impact:** Inconsistent rate limiting across endpoints

8. **GitHub Actions Workflow Missing**
   - **Issue:** No CI/CD workflow for automated deployments
   - **Location:** `.github/workflows/` (directory doesn't exist)
   - **Fix:** Create `.github/workflows/deploy.yml` with path-based triggers (see CI/CD Plan section)
   - **Impact:** Manual deployments, no automation

### Medium Priority Issues

9. **Structured Logging Not Verified**
   - **Issue:** `app/core/logging_config.py` referenced but not verified to exist
   - **Location:** `backend/app/core/logging_config.py`
   - **Fix:** Verify file exists or create it
   - **Impact:** JSON logging may not work

10. **Health Check Endpoint Inconsistency**
    - **Issue:** Backend has `/health` and `/ready`, but Dockerfile checks `/_health`
    - **Location:** `backend/Dockerfile:82`, `backend/app/main.py:164,175`
    - **Fix:** Standardize on `/health` for basic health, `/ready` for readiness
    - **Impact:** Confusion in health check configuration

---

## 10. Diff vs Existing Map (HOSTING_DEPLOYMENT_MAP.md)

### What Changed

1. **More Detailed Service Breakdown:**
   - Added explicit "Entrypoint", "Ports", "Dockerfile", "Deploy Config", "Runtime", "Dependencies", "Data Storage", "Latency Sensitivity", "Scaling Model", "Failure Modes" for each service
   - Previous doc had these but less structured

2. **Added Co-Location Matrix:**
   - New table showing Service A ↔ Service B latency requirements
   - Previous doc had co-location section but not in matrix format

3. **Enhanced Hosting Matrix:**
   - Added "Secrets Strategy" column
   - More detailed build/start commands

4. **Added Sequence Diagram:**
   - New Mermaid sequence diagram for scan request lifecycle
   - Previous doc only had architecture diagram

5. **Added Issues Found Section:**
   - New section documenting code/config issues found during audit
   - Previous doc did not have this

6. **More Detailed CI/CD Plan:**
   - Complete GitHub Actions workflow example
   - Previous doc had partial workflow

7. **Enhanced Production Gaps:**
   - More detailed checklist with specific actions
   - Previous doc had gaps but less actionable

### What Was Missing in Previous Doc

1. **Failure Modes:** Not documented per service
2. **Scaling Constraints:** Not explicitly listed
3. **Data Storage Details:** Not broken down (ephemeral vs persistent)
4. **Latency Sensitivity:** Not quantified per service pair
5. **Issues Found:** Not documented
6. **Sequence Diagram:** Only architecture diagram existed

### What's Outdated

1. **Healthcheck Path:** Previous doc noted the issue but didn't call it out as clearly
2. **Sentry Status:** Previous doc marked as "integrated" but should be "not initialized"
3. **Rate Limiting:** Previous doc said "implemented" but should be "partial (per-router only)"

---

## Recommended Hosting Topology

### Production Deployment

- **Frontend:** Vercel (edge network, automatic CDN, zero-config Next.js)
- **Backend API:** Fly.io region `iad` (1 CPU, 256MB RAM, auto-stop enabled)
- **Brain Service:** Fly.io region `iad` (1 CPU, 512MB RAM, same region as backend)
- **Runner Service:** Fly.io region `iad` (2 CPU, 2GB RAM, persistent volume for `backend/data/` and `wordlists/`)
- **Scheduler:** Fly.io Scheduler (cron every 6 hours, region `iad`)
- **Security Scanner:** Google Cloud Run region `us-central1` (2GB RAM, 2 CPU, auto-scaling)
- **Lighthouse Scanner:** Google Cloud Run region `us-central1` (2GB RAM, 2 CPU, auto-scaling)
- **Locust Runner:** Google Cloud Run Jobs region `us-central1` (2GB RAM, 2 CPU, on-demand)

### Infrastructure

- **PostgreSQL:** Supabase or Railway (managed, same region as backend/runner - `iad` or `us-east`)
- **Redis:** Upstash (serverless, global edge) or Railway (managed, same region as backend - `iad`)
- **Qdrant:** Qdrant Cloud (managed, global) or Fly.io (self-hosted, same region as brain - `iad`)

### Key Decisions

1. **Keep monorepo** - Code coupling (Runner shares DB schema with Backend) and small team size justify monorepo
2. **Co-locate Backend + Runner + DB** - Critical for <10ms latency and shared schema
3. **Use Fly.io for Python services** - Consistent platform, good for Python, persistent volumes available
4. **Use Cloud Run for scanners** - Serverless, auto-scaling, pay-per-use, 15min timeout sufficient
5. **Use Vercel for frontend** - Optimal for Next.js, edge functions, zero-config

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-27  
**Next Review:** 2025-04-27 (quarterly)

