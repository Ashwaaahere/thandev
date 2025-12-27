# Thandev Production Deployment Blueprint

**Generated:** 2025-01-27  
**Repository:** thandev  
**Purpose:** Complete production deployment guide with exact commands, environment variables, and security requirements  
**Audience:** Release engineers, DevOps, Platform engineers

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Service Inventory](#service-inventory)
3. [Hosting Decision Matrix](#hosting-decision-matrix)
4. [Environment Variables](#environment-variables)
5. [Security & Networking](#security--networking)
6. [Deployment Commands](#deployment-commands)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Runbook & Smoke Tests](#runbook--smoke-tests)
9. [Troubleshooting](#troubleshooting)

---

## 1. Executive Summary

Thandev is a security intelligence platform deployed as a monorepo with 8 deployable services:

- **Frontend** (Next.js 14) → Vercel
- **Backend API** (FastAPI) → Fly.io
- **Brain Service** (FastAPI RAG) → Fly.io
- **Runner Worker** (Python async) → Fly.io with persistent volume
- **Scheduler** (Python cron) → Fly.io
- **Security Scanner** (Flask) → Google Cloud Run
- **Lighthouse Scanner** (Node.js) → Google Cloud Run
- **Locust Runner** (Python job) → Google Cloud Run Jobs

**Infrastructure:**
- **PostgreSQL** (managed, e.g., Supabase, Neon, or Fly Postgres)
- **Redis** (managed, e.g., Upstash, Redis Cloud, or Fly Redis)
- **Qdrant** (optional, for RAG) → Fly.io or managed Qdrant Cloud
- **Object Storage** (reports/logs) → Cloudflare R2 or AWS S3

**Critical Data Flow:**
```
Frontend (Vercel) 
  → Backend API (Fly.io) 
  → Redis Streams 
  → Runner Worker (Fly.io) 
  → Cloud Run Scanners (GCP) 
  → PostgreSQL (findings storage)
```

**Deployment Strategy:** Monorepo with path-based CI/CD triggers. Each service deploys independently when its directory changes.

---

## 2. Service Inventory

### 2.1 Frontend (Next.js 14)

**Location:** `frontend/`

**Entrypoint:**
- **Build:** `npm run build` (outputs to `.next/`)
- **Start:** `npm start` (production) or `npm run dev` (development)
- **Port:** 3000

**Dockerfile:** `frontend/Dockerfile` (Node 20, dev mode - update for production)

**Deployment Config:** `vercel.json`

**Health Endpoint:** N/A (static site, Vercel handles health)

**Dependencies:**
- Next.js 14.2.32
- React 18.3.1
- NextAuth 4.24.11 (GitHub OAuth)

---

### 2.2 Backend API (FastAPI)

**Location:** `backend/`

**Entrypoint:**
- **Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Port:** 8000
- **Health:** `GET /health` (returns `{"status": "ok", "service": "thandev-backend", "version": "2.0.0"}`)
- **Readiness:** `GET /ready` (checks DB, Redis, Brain service)

**Dockerfile:** `backend/Dockerfile` (Python 3.11, includes Chrome + Lighthouse)

**Deployment Config:** `backend/fly.toml`

**Database Migrations:**
- **Command:** `alembic upgrade head`
- **Location:** `backend/migrations/`
- **Init:** `python init_db.py` (creates tables if needed)

**Dependencies:**
- FastAPI 0.112.0
- SQLAlchemy 2.0.35
- PostgreSQL (psycopg[binary] 3.2.10)
- Redis 5.0.8
- Alembic 1.13.2 (migrations)

---

### 2.3 Brain Service (FastAPI RAG)

**Location:** `services/thandev-brain/`

**Entrypoint:**
- **Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8001`
- **Port:** 8001
- **Health:** `GET /health` (returns `{"status": "ok", "service": "thandev-brain", "version": "1.0.0"}`)
- **Readiness:** `GET /ready` (checks RAG store: Qdrant or PostgreSQL)

**Dockerfile:** `services/thandev-brain/Dockerfile` (created)

**Deployment Config:** `services/thandev-brain/fly.toml` (created)

**Dependencies:**
- FastAPI 0.104.0
- Qdrant client 1.7.0 (optional, if RAG_STORE_TYPE=qdrant)
- pgvector 0.2.0 (optional, if RAG_STORE_TYPE=pgvector)
- Sentence Transformers 2.2.0 (default embeddings)
- OpenAI 1.0.0 (optional embeddings)

---

### 2.4 Runner Worker (Python Async)

**Location:** `services/thandev-runner/`

**Entrypoint:**
- **Command:** `python -m app.tasks` (runs `asyncio.run(run_worker_loop())`)
- **Port:** N/A (worker, not HTTP service)
- **Health:** Process health (monitored by Fly.io)

**Dockerfile:** `services/thandev-runner/Dockerfile` (created)

**Deployment Config:** `services/thandev-runner/fly.toml` (created)

**Persistent Storage:**
- **Volume:** `/app/data` (for tool execution artifacts)
- **Mount:** Fly.io volume `runner-data`

**Dependencies:**
- Redis 5.0.8 (for stream consumption)
- SQLAlchemy 2.0.35 (for findings ingestion)
- Security tools: Nuclei, FFuF, Dalfox, HTTPX, SQLMap, Nmap, SSLScan

**CRITICAL:** Runner must use the **SAME DATABASE_URL** as Backend to avoid "scan job not found" errors.

---

### 2.5 Scheduler (Python Cron)

**Location:** `backend/scheduler.py`

**Entrypoint:**
- **Command:** `python scheduler.py`
- **Port:** N/A (background process)
- **Schedule:** Every 6 hours (CVE data ingestion)

**Deployment Config:** `fly-scheduler.toml`

**Dependencies:**
- schedule 1.2.0
- Backend dependencies (shares backend codebase)

---

### 2.6 Cloud Run Services

#### 2.6.1 Security Scanner (Flask)

**Location:** `cloud-run/security-scanner/`

**Entrypoint:**
- **Command:** `python server.py` (Flask app)
- **Port:** 8080 (Cloud Run default)
- **Health:** `GET /health` (returns `{"status": "ok", "service": "security-scanner"}`)
- **Run:** `POST /run` (accepts `{"url": "...", "tier": "level1|level2|level3", "jobId": "..."}`)

**Dockerfile:** `cloud-run/security-scanner/Dockerfile`

**Tools:** Nuclei, Nmap, SSLScan

---

#### 2.6.2 Lighthouse Scanner (Node.js)

**Location:** `cloud-run/lighthouse-scanner/`

**Entrypoint:**
- **Command:** `node server-enhanced.js` (Express app)
- **Port:** 8080 (Cloud Run default)
- **Health:** `GET /health` (returns `{"status": "ok", "service": "lighthouse-scanner"}`)
- **Run:** `POST /run` (accepts `{"url": "...", "device": "desktop|mobile"}`)

**Dockerfile:** `cloud-run/lighthouse-scanner/Dockerfile`

**Tools:** Lighthouse (Chrome)

---

#### 2.6.3 Locust Runner (Cloud Run Job)

**Location:** `cloud-run/locust-runner/`

**Entrypoint:**
- **Command:** `python run_locust.py` (one-time job execution)
- **Port:** N/A (job, not service)
- **Output:** Uploads results to GCS bucket

**Dockerfile:** `cloud-run/locust-runner/Dockerfile`

**Tools:** Locust (load testing)

---

### 2.7 Shared Packages

**Location:** `packages/thandev_schemas/`

**Purpose:** Shared Pydantic schemas used by Backend, Brain, and Runner

**Build:** `pip install -e packages/thandev_schemas/` (editable install)

**Dependencies:**
- Pydantic >=2.0

**Impact:** Changes to schemas require rebuild of Backend, Brain, and Runner services.

---

## 3. Hosting Decision Matrix

| Service | Hosting Target | Region | State Needs | Scaling | Rationale |
|---------|----------------|--------|-------------|---------|-----------|
| **Frontend** | Vercel | Global (CDN) | None | Auto (edge) | Next.js optimized, zero-config, global CDN |
| **Backend API** | Fly.io | `iad` (US East) | None | Horizontal (1-10 machines) | FastAPI, needs low latency to DB/Redis, Fly.io private networking |
| **Brain Service** | Fly.io | `iad` (same as Backend) | None | Horizontal (1-3 machines) | RAG service, co-located with Backend for low latency |
| **Runner Worker** | Fly.io | `iad` (same as Backend) | **Persistent volume** (`/app/data`) | Horizontal (2-5 machines) | Tool execution requires local storage, must access same DB as Backend |
| **Scheduler** | Fly.io | `iad` (same as Backend) | None | Single instance | Cron job, runs every 6 hours |
| **Security Scanner** | Google Cloud Run | `us-central1` | Ephemeral | Auto (0-10 instances) | Resource-intensive, auto-scales to zero, pay-per-use |
| **Lighthouse Scanner** | Google Cloud Run | `us-central1` | Ephemeral | Auto (0-5 instances) | Chrome-based, resource-intensive, auto-scales to zero |
| **Locust Runner** | Google Cloud Run Jobs | `us-central1` | Ephemeral | On-demand | One-time job execution, no HTTP service |
| **PostgreSQL** | Managed (Supabase/Neon/Fly Postgres) | `iad` (US East) | Persistent | Vertical + read replicas | Primary database, requires backups, high availability |
| **Redis** | Managed (Upstash/Redis Cloud/Fly Redis) | `iad` (US East) | In-memory | Horizontal (cluster) | Streams, queues, session state, requires persistence |
| **Qdrant** | Fly.io or Qdrant Cloud | `iad` (US East) | Persistent | Single instance (can scale) | Vector DB for RAG (optional, can use pgvector instead) |
| **Object Storage** | Cloudflare R2 or AWS S3 | `iad` (US East) | Persistent | Unlimited | Reports, tool logs, scan artifacts |

### 3.1 Alternative Hosting Options

| Service | Primary | Alternative 1 | Alternative 2 |
|---------|---------|--------------|---------------|
| Frontend | Vercel | Netlify | AWS Amplify |
| Backend | Fly.io | Railway | Render |
| Brain | Fly.io | Railway | Render |
| Runner | Fly.io + Volume | VM (DigitalOcean/Hetzner) | Kubernetes (GKE/EKS) |
| Scheduler | Fly.io | Cloud Run Jobs | AWS Lambda (cron) |
| Scanners | Cloud Run | AWS Fargate | Fly.io (higher cost) |

### 3.2 Co-location Requirements

**MUST be in same region/VPC:**
- Backend + Runner + PostgreSQL (low latency, same DB)
- Backend + Brain (low latency for RAG calls)
- Backend + Redis (low latency for streams/queues)
- Brain + Qdrant (if using Qdrant, low latency for vector queries)

**CAN be in different regions:**
- Frontend (global CDN)
- Cloud Run scanners (can be in `us-central1` for cost optimization)

---

## 4. Environment Variables

### 4.1 Frontend (Vercel)

**Required:**

```bash
# NextAuth.js
NEXTAUTH_SECRET=<32+ char random string>
NEXTAUTH_URL=https://thandev.vercel.app

# GitHub OAuth
GITHUB_CLIENT_ID=<github_oauth_app_client_id>
GITHUB_CLIENT_SECRET=<github_oauth_app_client_secret>

# Backend API
NEXT_PUBLIC_API_BASE_URL=https://thandev-backend.fly.dev

# Cloud Run (optional, for direct scanner calls)
GOOGLE_CLOUD_PROJECT_ID=thandev
GOOGLE_CLOUD_REGION=us-central1
GCS_BUCKET=thandev-reports
```

**Optional:**
- `NODE_ENV=production` (auto-set by Vercel)
- `BACKEND_API_BASE_URL` (fallback if `NEXT_PUBLIC_API_BASE_URL` not set)

**How to set in Vercel:**
```bash
vercel env add NEXTAUTH_SECRET
vercel env add NEXTAUTH_URL
vercel env add GITHUB_CLIENT_ID
vercel env add GITHUB_CLIENT_SECRET
vercel env add NEXT_PUBLIC_API_BASE_URL
```

---

### 4.2 Backend (Fly.io)

**Required:**

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/thandev

# Redis
REDIS_URL=redis://host:6379/0

# Security
SECRET_KEY=<64+ char random string>
ENVIRONMENT=production
DEBUG=false

# CORS
CORS_ORIGINS=https://thandev.vercel.app,https://thandev.com

# Brain Service
BRAIN_SERVICE_URL=https://thandev-brain.fly.dev
BRAIN_SERVICE_ENABLED=true
BRAIN_REQUIRED=false
BRAIN_SERVICE_TIMEOUT=30

# Admin Bootstrap
THANDEV_SUPERADMIN_EXTERNAL_IDS=github:123456,github:789012
THANDEV_SETUP_TOKEN=<one-time token for first admin>

# Domain Verification
DOMAIN_VERIFICATION_DISABLED=false
ALLOWED_SCAN_DOMAINS=demo.example.com,test.example.com

# Tenant Auto-creation (production: disabled)
TENANT_AUTOCREATE_ENABLED=false
THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD=false

# Self-service Signup (production: disabled)
SELF_SERVICE_SIGNUP_ENABLED=false
```

**Optional:**

```bash
# OpenAI (for AI features)
OPENAI_API_KEY=sk-...

# Celery (legacy, not used if USE_CELERY_SCAN_EXECUTION=false)
CELERY_BROKER_URL=redis://host:6379/0
CELERY_RESULT_BACKEND=redis://host:6379/0
USE_CELERY_SCAN_EXECUTION=false

# Scan Configuration
MAX_PARALLEL_TOOLS=5
MAX_SCAN_TIMEOUT_SECONDS=3600
TOOL_EXECUTION_TIMEOUT_SECONDS=900
HTTP_PROBE_TIMEOUT_SECONDS=10
MAX_INDIVIDUAL_FINDINGS_PER_SCAN=300
HIGH_RISK_PORTS=22,3389,5900

# Scan Recovery
SCAN_RECOVERY_ENABLED=false
SCAN_RECOVERY_MODE=requeue
SCAN_RECOVERY_MAX_STALE_AGE_HOURS=24

# Stalled Scan Detection
STALLED_SCAN_THRESHOLD_MINUTES=30
STALLED_SCAN_NO_PROGRESS_POLLS=3

# Logging
USE_JSON_LOGGING=true

# Legacy Admin (deprecated, use THANDEV_SUPERADMIN_EXTERNAL_IDS)
THANDEV_ADMIN_EMAILS=admin@example.com
THANDEV_ADMIN_GITHUB_IDS=123456
```

**How to set in Fly.io:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-backend
fly secrets set REDIS_URL="redis://..." --app thandev-backend
fly secrets set SECRET_KEY="..." --app thandev-backend
# ... (repeat for all secrets)
```

---

### 4.3 Brain Service (Fly.io)

**Required:**

```bash
# Database (for pgvector, if RAG_STORE_TYPE=pgvector)
DATABASE_URL=postgresql://user:pass@host:5432/thandev

# Redis (for session state)
REDIS_URL=redis://host:6379/0

# RAG Store
RAG_STORE_TYPE=qdrant  # or "pgvector"
QDRANT_URL=http://qdrant-host:6333
QDRANT_COLLECTION=thandev_rag

# Embeddings
EMBEDDING_PROVIDER=sentence_transformers  # or "openai"
EMBEDDING_MODEL=all-MiniLM-L6-v2
OPENAI_API_KEY=sk-...  # if EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# CORS
CORS_ORIGINS=https://thandev-backend.fly.dev

# Environment
ENVIRONMENT=production
DEBUG=false
```

**Optional:**

```bash
# Brain Configuration
BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
BRAIN_MAX_TOTAL_RUNTIME_SEC=3600

# Session Configuration
SESSION_MAX_STEPS=20
SESSION_MAX_RUNTIME_SEC=3600
SESSION_MAX_CONSECUTIVE_FAILURES=3
SESSION_NO_NEW_FINDINGS_ITERATIONS=3
REDIS_SESSION_TTL_SEC=86400

# Finding Enrichment
ENRICH_FINDINGS_ENABLED=true
ENRICH_FINDINGS_MODEL=gpt-4o-mini
ENRICH_FINDINGS_TIMEOUT_SEC=30
```

**How to set in Fly.io:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-brain
fly secrets set REDIS_URL="redis://..." --app thandev-brain
fly secrets set QDRANT_URL="http://..." --app thandev-brain
# ... (repeat for all secrets)
```

---

### 4.4 Runner Worker (Fly.io)

**Required:**

```bash
# Database (CRITICAL: must match Backend DATABASE_URL)
DATABASE_URL=postgresql://user:pass@host:5432/thandev

# Redis (for stream consumption)
REDIS_URL=redis://host:6379/0

# Consumer Configuration
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=runner-1  # unique per instance

# Execution
EXECUTION_ADAPTER=local
MAX_CONCURRENT_STEPS=5
MAX_INFLIGHT_PER_SESSION=2

# Tool Paths (defaults computed, can override)
TOOLS_BASE_DIR=/app
DATA_DIR=/app/data
JOBS_DIR=/app/data/jobs
WORDLISTS_DIR=/app/data/wordlists

# Environment
ENVIRONMENT=production
DEBUG=false
```

**How to set in Fly.io:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-runner
fly secrets set REDIS_URL="redis://..." --app thandev-runner
fly secrets set CONSUMER_NAME="runner-1" --app thandev-runner
# ... (repeat for all secrets)
```

---

### 4.5 Scheduler (Fly.io)

**Required:**

```bash
# Database (same as Backend)
DATABASE_URL=postgresql://user:pass@host:5432/thandev

# Environment
ENVIRONMENT=production
```

**How to set in Fly.io:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-scheduler
```

---

### 4.6 Cloud Run Services

#### Security Scanner

**Environment Variables (set in Cloud Run):**
```bash
# None required (scanner is stateless)
```

#### Lighthouse Scanner

**Environment Variables (set in Cloud Run):**
```bash
# None required (scanner is stateless)
```

#### Locust Runner (Job)

**Environment Variables (passed at job execution):**
```bash
DOMAIN=<target_domain>
VUS=50
DURATION=120
SPAWN=10
SCAN_ID=<scan_id>
CALLBACK_URL=https://thandev-backend.fly.dev/api/scans/{scan_id}/callback
GCS_BUCKET=thandev-reports
```

---

### 4.7 Production Environment Template

**Create `.env.production` template:**

```bash
# ============================================
# THANDEV PRODUCTION ENVIRONMENT TEMPLATE
# ============================================
# Copy this file and fill in actual values
# DO NOT commit actual secrets to git

# ============================================
# SHARED SECRETS
# ============================================
DATABASE_URL=postgresql://user:password@host:5432/thandev
REDIS_URL=redis://host:6379/0
SECRET_KEY=<generate_64_char_random_string>
NEXTAUTH_SECRET=<generate_32_char_random_string>

# ============================================
# ADMIN BOOTSTRAP
# ============================================
# Format: "provider:external_id" (e.g., "github:123456")
THANDEV_SUPERADMIN_EXTERNAL_IDS=github:123456,github:789012
THANDEV_SETUP_TOKEN=<generate_random_token>

# ============================================
# DOMAIN VERIFICATION
# ============================================
DOMAIN_VERIFICATION_DISABLED=false
ALLOWED_SCAN_DOMAINS=demo.example.com,test.example.com

# ============================================
# GITHUB OAUTH
# ============================================
GITHUB_CLIENT_ID=<github_oauth_app_client_id>
GITHUB_CLIENT_SECRET=<github_oauth_app_client_secret>

# ============================================
# OPENAI (OPTIONAL)
# ============================================
OPENAI_API_KEY=sk-...

# ============================================
# CLOUD RUN / GCS
# ============================================
GOOGLE_CLOUD_PROJECT_ID=thandev
GOOGLE_CLOUD_REGION=us-central1
GCS_BUCKET=thandev-reports

# ============================================
# SERVICE URLs
# ============================================
NEXT_PUBLIC_API_BASE_URL=https://thandev-backend.fly.dev
NEXTAUTH_URL=https://thandev.vercel.app
BRAIN_SERVICE_URL=https://thandev-brain.fly.dev
```

**Generate secrets:**
```bash
# Generate SECRET_KEY (64 chars)
openssl rand -hex 32

# Generate NEXTAUTH_SECRET (32+ chars)
openssl rand -base64 32

# Generate THANDEV_SETUP_TOKEN
openssl rand -hex 16
```

---

## 5. Security & Networking

### 5.1 Private Networking

**Fly.io Private Networking:**

All Fly.io services (Backend, Brain, Runner, Scheduler) should use Fly.io's private IPv6 network for inter-service communication.

**Configure in `fly.toml`:**
```toml
[[services]]
  internal_only = true  # Only accessible via private network
```

**Service-to-Service URLs:**
- Backend → Brain: `http://thandev-brain.internal:8001`
- Backend → Runner: N/A (Runner consumes from Redis, not HTTP)
- Backend → Scheduler: N/A (Scheduler is independent)

**Public Endpoints:**
- Frontend: `https://thandev.vercel.app` (public)
- Backend: `https://thandev-backend.fly.dev` (public, with CORS restrictions)
- Brain: `https://thandev-brain.fly.dev` (public, but only called by Backend)
- Runner: N/A (no HTTP service)
- Scheduler: N/A (background process)

---

### 5.2 Service-to-Service Authentication

**Option 1: Internal Network (Recommended)**

Use Fly.io private networking. Services communicate via private IPv6 addresses. No authentication needed (network isolation).

**Option 2: Shared Secret (If public endpoints required)**

If services must be public, use a shared secret:

```python
# In Backend → Brain calls
headers = {"X-Internal-Token": os.getenv("INTERNAL_SERVICE_TOKEN")}

# In Brain
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")
# Validate in middleware
```

**Set secret:**
```bash
fly secrets set INTERNAL_SERVICE_TOKEN="..." --app thandev-backend
fly secrets set INTERNAL_SERVICE_TOKEN="..." --app thandev-brain
```

---

### 5.3 Firewall & Public Exposure Rules

**Public Endpoints:**
- ✅ Frontend (Vercel) - Public, authenticated via NextAuth
- ✅ Backend API - Public, CORS-restricted, authenticated via JWT
- ✅ Brain Service - Public, but only called by Backend (can restrict via IP/firewall)
- ❌ Runner - No HTTP service (worker only)
- ❌ Scheduler - No HTTP service (cron only)
- ✅ Cloud Run Scanners - Public, but only called by Runner/Backend (can restrict via IAM)

**CORS Configuration:**

Backend `CORS_ORIGINS` must include:
- Frontend domain: `https://thandev.vercel.app`
- Any custom domains: `https://thandev.com`

**Firewall Rules (if using Cloud Run):**

Restrict Cloud Run scanners to only accept requests from:
- Backend service IPs (Fly.io)
- Runner service IPs (Fly.io)

**Example (GCP IAM):**
```bash
# Allow only Backend service account
gcloud run services update security-scanner \
  --service-account=backend-service@thandev.iam.gserviceaccount.com \
  --region=us-central1
```

---

### 5.4 Domain Verification Flow

**Purpose:** Prevent unauthorized scanning of domains users don't own.

**Flow:**
1. User requests to scan `example.com`
2. Backend checks if `example.com` is in `ALLOWED_SCAN_DOMAINS` (demo/staging)
3. If not, Backend requires DNS TXT record verification:
   - Generate verification token: `thandev-verify=<token>`
   - Store in database: `domain_verifications` table
   - User adds TXT record: `_thandev-verify.example.com TXT "thandev-verify=<token>"`
4. Backend polls DNS (every 5 minutes) until TXT record found
5. Once verified, user can scan any subdomain under `example.com`

**Environment Variables:**
```bash
DOMAIN_VERIFICATION_DISABLED=false  # Enable verification
ALLOWED_SCAN_DOMAINS=demo.example.com,test.example.com  # Bypass verification
```

**Admin-Added Demo Targets:**
Admins can add domains to `ALLOWED_SCAN_DOMAINS` to bypass verification (for demo targets like bWAPP, itsecgames).

**API Endpoints:**
- `POST /api/projects/{project_id}/domains` - Request domain verification
- `GET /api/projects/{project_id}/domains/{domain_id}/verify` - Check verification status
- `GET /api/projects/{project_id}/domains` - List verified domains

---

### 5.5 Admin Bootstrap Strategy

**Method 1: Superadmin External IDs (Recommended)**

Set `THANDEV_SUPERADMIN_EXTERNAL_IDS` with GitHub user IDs:

```bash
THANDEV_SUPERADMIN_EXTERNAL_IDS=github:123456,github:789012
```

**Format:** `provider:external_id` (e.g., `github:123456`)

**How it works:**
1. User signs in with GitHub OAuth
2. Backend checks if `(provider, external_id)` is in superadmin set
3. If yes, user is automatically granted superadmin role

**Method 2: Setup Token (One-time)**

Set `THANDEV_SETUP_TOKEN` for first-time setup:

```bash
THANDEV_SETUP_TOKEN=<random_token>
```

**How it works:**
1. First user to sign in with valid setup token becomes superadmin
2. Token is consumed (can only be used once)
3. Subsequent admins added via `THANDEV_SUPERADMIN_EXTERNAL_IDS`

**API Endpoint:**
- `POST /api/auth/bootstrap` - Bootstrap first admin (requires `THANDEV_SETUP_TOKEN`)

---

## 6. Deployment Commands

### 6.1 Prerequisites

**Install CLI tools:**
```bash
# Fly.io CLI
curl -L https://fly.io/install.sh | sh

# Vercel CLI
npm i -g vercel

# Google Cloud SDK
curl https://sdk.cloud.google.com | bash

# Docker (for local testing)
# Install Docker Desktop or Docker Engine
```

**Authenticate:**
```bash
# Fly.io
fly auth login

# Vercel
vercel login

# Google Cloud
gcloud auth login
gcloud config set project thandev
```

---

### 6.2 Infrastructure Setup

#### 6.2.1 PostgreSQL (Managed)

**Option 1: Fly Postgres**
```bash
fly postgres create --name thandev-db --region iad --vm-size shared-cpu-1x --volume-size 10
fly postgres attach thandev-db --app thandev-backend
```

**Option 2: Supabase**
1. Create project at https://supabase.com
2. Get connection string from Settings → Database
3. Set `DATABASE_URL` in Fly.io secrets

**Option 3: Neon**
1. Create project at https://neon.tech
2. Get connection string from dashboard
3. Set `DATABASE_URL` in Fly.io secrets

---

#### 6.2.2 Redis (Managed)

**Option 1: Fly Redis**
```bash
fly redis create --name thandev-redis --region iad --vm-size shared-cpu-1x
fly redis attach thandev-redis --app thandev-backend
```

**Option 2: Upstash**
1. Create database at https://upstash.com
2. Get connection string from dashboard
3. Set `REDIS_URL` in Fly.io secrets

**Option 3: Redis Cloud**
1. Create database at https://redis.com/cloud
2. Get connection string from dashboard
3. Set `REDIS_URL` in Fly.io secrets

---

#### 6.2.3 Qdrant (Optional)

**Option 1: Fly.io**
```bash
fly launch --name thandev-qdrant --region iad --image qdrant/qdrant:latest
fly volumes create qdrant-data --size 10 --app thandev-qdrant
fly deploy --app thandev-qdrant
```

**Option 2: Qdrant Cloud**
1. Create cluster at https://cloud.qdrant.io
2. Get connection URL from dashboard
3. Set `QDRANT_URL` in Brain service secrets

**Option 3: Use pgvector (no Qdrant needed)**
Set `RAG_STORE_TYPE=pgvector` in Brain service (uses same PostgreSQL as Backend).

---

#### 6.2.4 Object Storage (R2 or S3)

**Option 1: Cloudflare R2**
```bash
# Create bucket via Cloudflare dashboard
# Get credentials: Account ID, Access Key ID, Secret Access Key
```

**Option 2: AWS S3**
```bash
aws s3 mb s3://thandev-reports --region us-east-1
```

---

### 6.3 Service Deployments

#### 6.3.1 Frontend (Vercel)

**Initial Setup:**
```bash
cd frontend
vercel --prod
```

**Connect to Git (automatic deploys):**
```bash
vercel git connect
```

**Set Environment Variables:**
```bash
vercel env add NEXTAUTH_SECRET
vercel env add NEXTAUTH_URL
vercel env add GITHUB_CLIENT_ID
vercel env add GITHUB_CLIENT_SECRET
vercel env add NEXT_PUBLIC_API_BASE_URL
```

**Manual Deploy:**
```bash
vercel --prod
```

---

#### 6.3.2 Backend (Fly.io)

**Initial Setup:**
```bash
cd backend
fly launch --name thandev-backend --region iad
# Answer prompts:
# - Dockerfile: Yes (use existing)
# - App name: thandev-backend
# - Region: iad
```

**Set Secrets:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-backend
fly secrets set REDIS_URL="redis://..." --app thandev-backend
fly secrets set SECRET_KEY="..." --app thandev-backend
fly secrets set ENVIRONMENT="production" --app thandev-backend
fly secrets set CORS_ORIGINS="https://thandev.vercel.app" --app thandev-backend
fly secrets set BRAIN_SERVICE_URL="https://thandev-brain.fly.dev" --app thandev-backend
fly secrets set THANDEV_SUPERADMIN_EXTERNAL_IDS="github:123456" --app thandev-backend
fly secrets set DOMAIN_VERIFICATION_DISABLED="false" --app thandev-backend
fly secrets set SELF_SERVICE_SIGNUP_ENABLED="false" --app thandev-backend
```

**Deploy:**
```bash
fly deploy --app thandev-backend
```

**Run Migrations:**
```bash
fly ssh console --app thandev-backend
# Inside container:
python init_db.py
alembic upgrade head
exit
```

**Or use Fly.io release command:**
```bash
# Add to fly.toml:
[deploy]
  release_command = "python init_db.py && alembic upgrade head"
```

---

#### 6.3.3 Brain Service (Fly.io)

**Initial Setup:**
```bash
cd services/thandev-brain
fly launch --name thandev-brain --region iad
# Use existing Dockerfile and fly.toml
```

**Set Secrets:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-brain
fly secrets set REDIS_URL="redis://..." --app thandev-brain
fly secrets set RAG_STORE_TYPE="qdrant" --app thandev-brain
fly secrets set QDRANT_URL="http://thandev-qdrant.internal:6333" --app thandev-brain
fly secrets set QDRANT_COLLECTION="thandev_rag" --app thandev-brain
fly secrets set EMBEDDING_PROVIDER="sentence_transformers" --app thandev-brain
fly secrets set EMBEDDING_MODEL="all-MiniLM-L6-v2" --app thandev-brain
fly secrets set CORS_ORIGINS="https://thandev-backend.fly.dev" --app thandev-brain
fly secrets set ENVIRONMENT="production" --app thandev-brain
```

**Deploy:**
```bash
fly deploy --app thandev-brain
```

---

#### 6.3.4 Runner Worker (Fly.io)

**Initial Setup:**
```bash
cd services/thandev-runner
fly launch --name thandev-runner --region iad
# Use existing Dockerfile and fly.toml
```

**Create Persistent Volume:**
```bash
fly volumes create runner-data --size 20 --app thandev-runner --region iad
```

**Set Secrets:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-runner
fly secrets set REDIS_URL="redis://..." --app thandev-runner
fly secrets set CONSUMER_GROUP="runner-workers" --app thandev-runner
fly secrets set CONSUMER_NAME="runner-1" --app thandev-runner
fly secrets set EXECUTION_ADAPTER="local" --app thandev-runner
fly secrets set MAX_CONCURRENT_STEPS="5" --app thandev-runner
fly secrets set MAX_INFLIGHT_PER_SESSION="2" --app thandev-runner
fly secrets set ENVIRONMENT="production" --app thandev-runner
```

**Deploy:**
```bash
fly deploy --app thandev-runner
```

**Scale (multiple workers):**
```bash
fly scale count 3 --app thandev-runner
# Update CONSUMER_NAME per instance: runner-1, runner-2, runner-3
```

---

#### 6.3.5 Scheduler (Fly.io)

**Initial Setup:**
```bash
cd backend
fly launch --name thandev-scheduler --region iad --config fly-scheduler.toml
```

**Set Secrets:**
```bash
fly secrets set DATABASE_URL="postgresql://..." --app thandev-scheduler
fly secrets set ENVIRONMENT="production" --app thandev-scheduler
```

**Deploy:**
```bash
fly deploy --app thandev-scheduler --config fly-scheduler.toml
```

---

#### 6.3.6 Cloud Run Services

**Security Scanner:**
```bash
cd cloud-run/security-scanner
gcloud builds submit --tag gcr.io/thandev/security-scanner
gcloud run deploy security-scanner \
  --image gcr.io/thandev/security-scanner \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10 \
  --min-instances 0
```

**Lighthouse Scanner:**
```bash
cd cloud-run/lighthouse-scanner
gcloud builds submit --tag gcr.io/thandev/lighthouse-scanner
gcloud run deploy lighthouse-scanner \
  --image gcr.io/thandev/lighthouse-scanner \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 5 \
  --min-instances 0
```

**Locust Runner (Job):**
```bash
cd cloud-run/locust-runner
gcloud builds submit --tag gcr.io/thandev/locust-runner
gcloud run jobs create locust-runner \
  --image gcr.io/thandev/locust-runner \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-retries 1
```

**Update Backend/Runner with Cloud Run URLs:**
```bash
# Get URLs
SECURITY_SCANNER_URL=$(gcloud run services describe security-scanner --region us-central1 --format 'value(status.url)')
LIGHTHOUSE_SCANNER_URL=$(gcloud run services describe lighthouse-scanner --region us-central1 --format 'value(status.url)')

# Set in Backend secrets (if needed)
fly secrets set SECURITY_SCANNER_URL="$SECURITY_SCANNER_URL" --app thandev-backend
fly secrets set LIGHTHOUSE_SCANNER_URL="$LIGHTHOUSE_SCANNER_URL" --app thandev-backend
```

---

## 7. CI/CD Pipeline

### 7.1 GitHub Actions Workflow

**Create `.github/workflows/deploy.yml`:**

```yaml
name: Deploy Services

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
  VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
  VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
  VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
  GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      frontend: ${{ steps.filter.outputs.frontend }}
      backend: ${{ steps.filter.outputs.backend }}
      brain: ${{ steps.filter.outputs.brain }}
      runner: ${{ steps.filter.outputs.runner }}
      scheduler: ${{ steps.filter.outputs.scheduler }}
      security-scanner: ${{ steps.filter.outputs.security-scanner }}
      lighthouse-scanner: ${{ steps.filter.outputs.lighthouse-scanner }}
      locust-runner: ${{ steps.filter.outputs.locust-runner }}
      schemas: ${{ steps.filter.outputs.schemas }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            frontend:
              - 'frontend/**'
            backend:
              - 'backend/**'
              - 'packages/thandev_schemas/**'
            brain:
              - 'services/thandev-brain/**'
              - 'packages/thandev_schemas/**'
            runner:
              - 'services/thandev-runner/**'
              - 'packages/thandev_schemas/**'
            scheduler:
              - 'backend/scheduler.py'
              - 'fly-scheduler.toml'
            security-scanner:
              - 'cloud-run/security-scanner/**'
            lighthouse-scanner:
              - 'cloud-run/lighthouse-scanner/**'
            locust-runner:
              - 'cloud-run/locust-runner/**'
            schemas:
              - 'packages/thandev_schemas/**'

  deploy-frontend:
    needs: detect-changes
    if: needs.detect-changes.outputs.frontend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ env.VERCEL_TOKEN }}
          vercel-org-id: ${{ env.VERCEL_ORG_ID }}
          vercel-project-id: ${{ env.VERCEL_PROJECT_ID }}
          working-directory: ./frontend

  deploy-backend:
    needs: detect-changes
    if: needs.detect-changes.outputs.backend == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --app thandev-backend --config backend/fly.toml
        working-directory: ./backend

  deploy-brain:
    needs: detect-changes
    if: needs.detect-changes.outputs.brain == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --app thandev-brain --config services/thandev-brain/fly.toml
        working-directory: ./services/thandev-brain

  deploy-runner:
    needs: detect-changes
    if: needs.detect-changes.outputs.runner == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --app thandev-runner --config services/thandev-runner/fly.toml
        working-directory: ./services/thandev-runner

  deploy-scheduler:
    needs: detect-changes
    if: needs.detect-changes.outputs.scheduler == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --app thandev-scheduler --config fly-scheduler.toml
        working-directory: ./backend

  deploy-security-scanner:
    needs: detect-changes
    if: needs.detect-changes.outputs.security-scanner == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ env.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud builds submit --tag gcr.io/${{ env.GCP_PROJECT_ID }}/security-scanner
          gcloud run deploy security-scanner \
            --image gcr.io/${{ env.GCP_PROJECT_ID }}/security-scanner \
            --region us-central1 \
            --platform managed \
            --allow-unauthenticated
        working-directory: ./cloud-run/security-scanner

  deploy-lighthouse-scanner:
    needs: detect-changes
    if: needs.detect-changes.outputs.lighthouse-scanner == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ env.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud builds submit --tag gcr.io/${{ env.GCP_PROJECT_ID }}/lighthouse-scanner
          gcloud run deploy lighthouse-scanner \
            --image gcr.io/${{ env.GCP_PROJECT_ID }}/lighthouse-scanner \
            --region us-central1 \
            --platform managed \
            --allow-unauthenticated
        working-directory: ./cloud-run/lighthouse-scanner

  deploy-locust-runner:
    needs: detect-changes
    if: needs.detect-changes.outputs.locust-runner == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ env.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud builds submit --tag gcr.io/${{ env.GCP_PROJECT_ID }}/locust-runner
          gcloud run jobs update locust-runner \
            --image gcr.io/${{ env.GCP_PROJECT_ID }}/locust-runner \
            --region us-central1
        working-directory: ./cloud-run/locust-runner
```

**Required GitHub Secrets:**
- `FLY_API_TOKEN` - Fly.io API token
- `VERCEL_TOKEN` - Vercel API token
- `VERCEL_ORG_ID` - Vercel organization ID
- `VERCEL_PROJECT_ID` - Vercel project ID
- `GCP_PROJECT_ID` - Google Cloud project ID
- `GCP_SA_KEY` - Google Cloud service account key (JSON)

---

## 8. Runbook & Smoke Tests

### 8.1 Initial Setup

#### 8.1.1 Run Database Migrations

```bash
# SSH into Backend container
fly ssh console --app thandev-backend

# Run migrations
cd /app
python init_db.py
alembic upgrade head

# Verify
alembic current

# Exit
exit
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade -> <revision>, <message>
```

---

#### 8.1.2 Create First Admin

**Method 1: Using Setup Token**

```bash
# Set setup token
fly secrets set THANDEV_SETUP_TOKEN="<random_token>" --app thandev-backend

# Call bootstrap endpoint
curl -X POST https://thandev-backend.fly.dev/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "setup_token": "<random_token>",
    "github_external_id": "123456"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Admin user created",
  "user_id": "..."
}
```

**Method 2: Using Superadmin External IDs**

```bash
# Set superadmin IDs
fly secrets set THANDEV_SUPERADMIN_EXTERNAL_IDS="github:123456" --app thandev-backend

# User signs in with GitHub OAuth
# Backend automatically grants superadmin role
```

---

#### 8.1.3 Approve a User

```bash
# As admin, approve user
curl -X POST https://thandev-backend.fly.dev/api/admin/users/{user_id}/approve \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "User approved",
  "user": {
    "id": "...",
    "status": "approved"
  }
}
```

---

#### 8.1.4 Verify a Domain

```bash
# Request domain verification
curl -X POST https://thandev-backend.fly.dev/api/projects/{project_id}/domains \
  -H "Authorization: Bearer <user_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "root_domain": "example.com"
  }'
```

**Expected Response:**
```json
{
  "id": "...",
  "root_domain": "example.com",
  "verification_token": "thandev-verify=abc123...",
  "status": "pending",
  "instructions": "Add TXT record: _thandev-verify.example.com TXT \"thandev-verify=abc123...\""
}
```

**Add DNS TXT Record:**
```
_thandev-verify.example.com TXT "thandev-verify=abc123..."
```

**Check Verification Status:**
```bash
curl https://thandev-backend.fly.dev/api/projects/{project_id}/domains/{domain_id}/verify \
  -H "Authorization: Bearer <user_jwt_token>"
```

**Expected Response (verified):**
```json
{
  "id": "...",
  "root_domain": "example.com",
  "status": "verified",
  "verified_at": "2025-01-27T12:00:00Z"
}
```

---

### 8.2 Smoke Tests

#### 8.2.1 Health Checks

```bash
# Frontend (Vercel)
curl https://thandev.vercel.app
# Expected: 200 OK, HTML page

# Backend Health
curl https://thandev-backend.fly.dev/health
# Expected: {"status": "ok", "service": "thandev-backend", "version": "2.0.0"}

# Backend Readiness
curl https://thandev-backend.fly.dev/ready
# Expected: {"status": "ready", "checks": {"database": "ready", "redis": "ready", "brain_service": "ready"}, "version": "2.0.0"}

# Brain Health
curl https://thandev-brain.fly.dev/health
# Expected: {"status": "ok", "service": "thandev-brain", "version": "1.0.0"}

# Brain Readiness
curl https://thandev-brain.fly.dev/ready
# Expected: {"status": "ready", "checks": {"rag_store": "ready"}, "version": "1.0.0"}

# Security Scanner
curl https://security-scanner-xxx.run.app/health
# Expected: {"status": "ok", "service": "security-scanner"}

# Lighthouse Scanner
curl https://lighthouse-scanner-xxx.run.app/health
# Expected: {"status": "ok", "service": "lighthouse-scanner"}
```

---

#### 8.2.2 End-to-End Scan Test

**1. Create Project:**
```bash
curl -X POST https://thandev-backend.fly.dev/api/projects \
  -H "Authorization: Bearer <user_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "target_url": "https://example.com",
    "description": "Test scan"
  }'
```

**Expected Response:**
```json
{
  "id": "...",
  "name": "Test Project",
  "target_url": "https://example.com",
  "status": "active"
}
```

**2. Start Scan:**
```bash
curl -X POST https://thandev-backend.fly.dev/api/projects/{project_id}/scans \
  -H "Authorization: Bearer <user_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_level": "basic"
  }'
```

**Expected Response:**
```json
{
  "id": "...",
  "project_id": "...",
  "target_url": "https://example.com",
  "scan_level": "basic",
  "status": "queued",
  "created_at": "2025-01-27T12:00:00Z"
}
```

**3. Monitor Scan Progress:**
```bash
# Poll scan status
curl https://thandev-backend.fly.dev/api/scans/{scan_id} \
  -H "Authorization: Bearer <user_jwt_token>"
```

**Expected Response (running):**
```json
{
  "id": "...",
  "status": "running",
  "progress": {
    "current_step": 3,
    "total_steps": 5,
    "completed_tools": ["httpx", "nuclei"],
    "running_tools": ["ffuf"]
  }
}
```

**Expected Response (completed):**
```json
{
  "id": "...",
  "status": "completed",
  "progress": {
    "current_step": 5,
    "total_steps": 5,
    "completed_tools": ["httpx", "nuclei", "ffuf", "nmap", "sslscan"]
  },
  "findings_count": 42,
  "completed_at": "2025-01-27T12:15:00Z"
}
```

**4. Get Findings:**
```bash
curl https://thandev-backend.fly.dev/api/scans/{scan_id}/findings \
  -H "Authorization: Bearer <user_jwt_token>"
```

**Expected Response:**
```json
{
  "findings": [
    {
      "id": "...",
      "severity": "high",
      "title": "SQL Injection Vulnerability",
      "description": "...",
      "tool": "nuclei",
      "url": "https://example.com/vulnerable-endpoint"
    }
  ],
  "total": 42,
  "by_severity": {
    "critical": 2,
    "high": 8,
    "medium": 15,
    "low": 12,
    "info": 5
  }
}
```

---

### 8.3 Troubleshooting

#### 8.3.1 Backend Not Ready

**Check logs:**
```bash
fly logs --app thandev-backend
```

**Common issues:**
- Database connection failed → Check `DATABASE_URL`
- Redis connection failed → Check `REDIS_URL`
- Brain service unreachable → Check `BRAIN_SERVICE_URL` and Brain service health

**Fix:**
```bash
# Verify secrets
fly secrets list --app thandev-backend

# Update secret if needed
fly secrets set DATABASE_URL="postgresql://..." --app thandev-backend
```

---

#### 8.3.2 Runner Not Processing Scans

**Check logs:**
```bash
fly logs --app thandev-runner
```

**Common issues:**
- Database connection failed → Check `DATABASE_URL` (must match Backend)
- Redis connection failed → Check `REDIS_URL`
- Consumer group not found → Check `CONSUMER_GROUP`

**Fix:**
```bash
# Verify secrets match Backend
fly secrets list --app thandev-runner
fly secrets list --app thandev-backend

# Ensure DATABASE_URL is identical
```

---

#### 8.3.3 Brain Service Not Responding

**Check logs:**
```bash
fly logs --app thandev-brain
```

**Common issues:**
- Qdrant connection failed → Check `QDRANT_URL`
- RAG store not initialized → Check Brain startup logs

**Fix:**
```bash
# Verify Qdrant is running
curl http://thandev-qdrant.internal:6333/health

# Or switch to pgvector
fly secrets set RAG_STORE_TYPE="pgvector" --app thandev-brain
```

---

#### 8.3.4 Cloud Run Scanner Timeout

**Check logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=security-scanner" --limit 50
```

**Common issues:**
- Memory limit too low → Increase `--memory`
- Timeout too short → Increase `--timeout`
- Tool execution failed → Check scanner logs

**Fix:**
```bash
# Increase resources
gcloud run services update security-scanner \
  --memory 4Gi \
  --cpu 4 \
  --timeout 1800 \
  --region us-central1
```

---

## 9. Troubleshooting

### 9.1 Common Issues

**Issue: "scan job not found" error**

**Cause:** Runner and Backend using different databases.

**Fix:**
```bash
# Ensure DATABASE_URL is identical in both services
fly secrets get DATABASE_URL --app thandev-backend
fly secrets get DATABASE_URL --app thandev-runner
# If different, update Runner:
fly secrets set DATABASE_URL="<backend_database_url>" --app thandev-runner
```

---

**Issue: Frontend can't connect to Backend**

**Cause:** CORS misconfiguration or wrong API URL.

**Fix:**
```bash
# Check CORS_ORIGINS includes frontend domain
fly secrets get CORS_ORIGINS --app thandev-backend
# Should include: https://thandev.vercel.app

# Update if needed
fly secrets set CORS_ORIGINS="https://thandev.vercel.app,https://thandev.com" --app thandev-backend

# Verify frontend API URL
vercel env get NEXT_PUBLIC_API_BASE_URL
# Should be: https://thandev-backend.fly.dev
```

---

**Issue: Domain verification not working**

**Cause:** DNS propagation delay or wrong TXT record.

**Fix:**
```bash
# Check DNS record
dig TXT _thandev-verify.example.com

# Verify token matches
# Token should be: thandev-verify=<token_from_api_response>

# Wait 5-15 minutes for propagation
# Backend polls every 5 minutes
```

---

**Issue: Admin bootstrap not working**

**Cause:** Wrong external ID format or setup token already used.

**Fix:**
```bash
# Check format: must be "provider:external_id"
fly secrets get THANDEV_SUPERADMIN_EXTERNAL_IDS --app thandev-backend
# Should be: github:123456

# For setup token, generate new one if already used
fly secrets set THANDEV_SETUP_TOKEN="<new_token>" --app thandev-backend
```

---

### 9.2 Monitoring & Alerts

**Recommended Monitoring:**
- **Fly.io:** Use Fly.io dashboard for service health
- **Vercel:** Use Vercel dashboard for frontend metrics
- **Cloud Run:** Use GCP Cloud Monitoring for scanner metrics
- **PostgreSQL:** Use managed provider's monitoring (Supabase/Neon)
- **Redis:** Use managed provider's monitoring (Upstash/Redis Cloud)

**Health Check Endpoints:**
- Backend: `GET /health`, `GET /ready`
- Brain: `GET /health`, `GET /ready`
- Scanners: `GET /health`

**Set up alerts:**
- Backend `/ready` returns 500 → Alert
- Brain `/ready` returns 500 → Alert
- Runner process crashes → Alert (Fly.io handles this)
- Database connection failures → Alert (managed provider)

---

## 10. Appendix

### 10.1 File Locations

**Deployment Configs:**
- `backend/fly.toml` - Backend Fly.io config
- `backend/Dockerfile` - Backend container
- `services/thandev-brain/fly.toml` - Brain Fly.io config (created)
- `services/thandev-brain/Dockerfile` - Brain container (created)
- `services/thandev-runner/fly.toml` - Runner Fly.io config (created)
- `services/thandev-runner/Dockerfile` - Runner container (created)
- `fly-scheduler.toml` - Scheduler Fly.io config
- `frontend/vercel.json` - Frontend Vercel config
- `frontend/Dockerfile` - Frontend container (dev mode, update for prod)

**Health Endpoints:**
- Backend: `backend/app/main.py:164` (`/health`), `backend/app/main.py:175` (`/ready`)
- Brain: `services/thandev-brain/app/main.py:121` (`/health`), `services/thandev-brain/app/main.py:132` (`/ready`)
- Security Scanner: `cloud-run/security-scanner/server.py:36` (`/health`)
- Lighthouse Scanner: `cloud-run/lighthouse-scanner/server-enhanced.js:353` (`/health`)

**Fixed Issues:**
- ✅ Backend Dockerfile healthcheck: Changed `/_health` to `/health`
- ✅ Created Brain Dockerfile and fly.toml
- ✅ Created Runner Dockerfile and fly.toml

---

### 10.2 Quick Reference

**Deploy All Services:**
```bash
# Frontend
cd frontend && vercel --prod

# Backend
cd backend && fly deploy --app thandev-backend

# Brain
cd services/thandev-brain && fly deploy --app thandev-brain

# Runner
cd services/thandev-runner && fly deploy --app thandev-runner

# Scheduler
cd backend && fly deploy --app thandev-scheduler --config fly-scheduler.toml

# Cloud Run (if changed)
cd cloud-run/security-scanner && gcloud builds submit --tag gcr.io/thandev/security-scanner && gcloud run deploy security-scanner --image gcr.io/thandev/security-scanner --region us-central1
```

**Check Service Status:**
```bash
fly status --app thandev-backend
fly status --app thandev-brain
fly status --app thandev-runner
fly status --app thandev-scheduler
```

**View Logs:**
```bash
fly logs --app thandev-backend
fly logs --app thandev-brain
fly logs --app thandev-runner
fly logs --app thandev-scheduler
```

---

**Last Updated:** 2025-01-27  
**Version:** 1.0.0  
**Maintainer:** Release Engineering Team

