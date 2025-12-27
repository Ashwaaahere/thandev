# Environment Setup Guide

This document describes the required environment variables for each service.

## Backend Service

**Location:** `backend/.env`

### Required Variables

```bash
# Environment Mode (development/local/dev/test/production/docker/testing/staging)
ENVIRONMENT=development

# Database (must match runner's DATABASE_URL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
# OR for local SQLite:
# DATABASE_URL=sqlite:///./thandev.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Brain Service
BRAIN_SERVICE_URL=http://localhost:8001
BRAIN_SERVICE_ENABLED=true
BRAIN_REQUIRED=false
```

### Optional Variables

```bash
# Security
SECRET_KEY=change-me-in-production

# OpenAI (for AI features)
OPENAI_API_KEY=

# Plan Enforcement Bypass (ONLY for dev/test/local)
THANDEV_DISABLE_PLAN_ENFORCEMENT=1

# Tenant Auto-creation (enabled by default in dev/test/local)
THANDEV_TENANT_AUTOCREATE=1
```

## Runner Service

**Location:** `services/thandev-runner/.env`

### Required Variables

```bash
# CRITICAL: Must match backend's DATABASE_URL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
# OR for local SQLite:
# DATABASE_URL=sqlite:///../../backend/thandev.db

# Redis (must match backend)
REDIS_URL=redis://localhost:6379/0

# Environment
ENVIRONMENT=development
```

### Optional Variables

```bash
# Consumer Configuration
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=runner-1

# Execution Configuration
MAX_CONCURRENT_STEPS=5
MAX_INFLIGHT_PER_SESSION=2
```

## Brain Service

**Location:** `services/thandev-brain/.env`

### Required Variables

```bash
# Redis (must match backend)
REDIS_URL=redis://localhost:6379/0

# RAG Store
RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
```

### Optional Variables

```bash
# Embedding Provider
EMBEDDING_PROVIDER=sentence_transformers
OPENAI_API_KEY=

# Brain Configuration
BRAIN_MAX_STEPS=20
BRAIN_MAX_PARALLELISM=5
```

## Quick Setup for Local Development

1. **Start dependencies:**
   ```bash
   docker-compose up -d postgres redis qdrant
   ```

2. **Create backend/.env:**
   ```bash
   cd backend
   cat > .env << EOF
   ENVIRONMENT=local
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   REDIS_URL=redis://localhost:6379/0
   BRAIN_SERVICE_ENABLED=true
   BRAIN_SERVICE_URL=http://localhost:8001
   EOF
   ```

3. **Create services/thandev-runner/.env:**
   ```bash
   cd services/thandev-runner
   cat > .env << EOF
   ENVIRONMENT=local
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   REDIS_URL=redis://localhost:6379/0
   EOF
   ```

4. **Create services/thandev-brain/.env:**
   ```bash
   cd services/thandev-brain
   cat > .env << EOF
   ENVIRONMENT=local
   REDIS_URL=redis://localhost:6379/0
   QDRANT_URL=http://localhost:6333
   EOF
   ```

5. **Run migrations:**
   ```bash
   cd backend
   python3 -m alembic upgrade head
   ```

## Production Setup

1. **Set ENVIRONMENT=production** in all services
2. **Use PostgreSQL** (not SQLite) for DATABASE_URL
3. **Set strong SECRET_KEY** in backend
4. **Disable auto-creation** (default in production)
5. **Set BRAIN_REQUIRED=true** if brain is critical

## Verification

After setup, verify connections:

```bash
# Check backend DB connection
cd backend
python3 -c "from app.core.config import settings; print('Backend DB:', settings.DATABASE_URL)"

# Check runner DB connection (should match backend)
cd services/thandev-runner
python3 -c "from app.config import settings; print('Runner DB:', settings.DATABASE_URL)"
```

Both should show the same DATABASE_URL.

## Auth Bootstrap & UUID Headers
- Frontend NextAuth calls `POST {BACKEND_API_BASE_URL}/api/auth/bootstrap` after GitHub login to map the external user to internal UUIDs.  
- Every backend request must include `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` (UUIDs). The frontend refuses to send numeric IDs.  
- If self-service signup is disabled in production, new users will see a clear onboarding error and no backend calls are made with numeric IDs. Existing users continue to bootstrap.  
- Quick curl check (replace tokens):  
  ```bash
  curl -s -H "X-Thandev-User-Id:<uuid>" -H "X-Thandev-Tenant-Id:<uuid>" http://localhost:8000/api/projects
  ```

## Domain Verification & Plan Gating & Admin Bootstrap
- `DOMAIN_VERIFICATION_DISABLED=true` only for local/dev; production must verify domains via DNS TXT.
- `ALLOWED_SCAN_DOMAINS=example.com,demo.test` allowlist for staging demos (registrable domains).
- **Admin bootstrap (immutable IDs):**
  - `THANDEV_SUPERADMIN_EXTERNAL_IDS="github:12345,github:67890"` (preferred; uses provider:id)
  - `THANDEV_SETUP_TOKEN=<random-long-secret>` for one-time seeding via `POST /api/admin/bootstrap-superadmin`
  - Legacy (not recommended): `THANDEV_ADMIN_EMAILS`, `THANDEV_ADMIN_GITHUB_IDS`
- `THANDEV_DISABLE_PLAN_ENFORCEMENT=1` (dev only) skips plan checks; keep unset in prod.
- Admin UI: `/admin` (visible only if `session.user.isAdmin`). Use to approve users and set entitlements/limits.

