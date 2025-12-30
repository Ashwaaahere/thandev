# Fly.io Deployment Changes Summary

This document summarizes the changes made to prepare Thandev for production deployment on Fly.io.

## Changes Made

### 1. Backend Service (`backend/`)

#### `backend/fly.toml`
- ✅ Increased memory from 256MB to 512MB (better performance for FastAPI + migrations)
- ✅ Health check endpoint already configured at `/health`

#### `backend/app/services/tools.py`
- ✅ Added `-sT` (TCP connect scan) flag to all nmap scan levels
  - Prevents requirement for root privileges
  - Safe for containerized environments
  - Applied to: `basic`, `pro`, and `advanced` scan levels

#### `backend/app/core/config.py`
- ✅ Already configured with `BRAIN_SERVICE_URL` default: `http://thandev-brain.internal:8001`

### 2. Brain Service (`services/thandev-brain/`)

#### `services/thandev-brain/app/api/v1.py`
- ✅ Added `/healthz` endpoint (Kubernetes-style naming for Fly.io health checks)
- ✅ Existing `/health` endpoint remains for backward compatibility

#### `services/thandev-brain/app/core/config.py`
- ✅ Already configured with `QDRANT_URL` default: `http://thandev-qdrant.internal:6333`

#### `services/thandev-brain/fly.toml`
- ✅ Already configured with `/healthz` health check endpoint
- ✅ Memory set to 2048MB (appropriate for sentence-transformers)

### 3. Runner Service (`services/thandev-runner/`)

#### `services/thandev-runner/fly.toml`
- ✅ Added `WORDLISTS_DIR="/opt/thandev/wordlists"` environment variable
- ✅ Memory set to 2048MB (sufficient for tool execution)

#### `services/thandev-runner/app/config.py`
- ✅ Already configured with `WORDLISTS_DIR` default: `/opt/thandev/wordlists`

#### `services/thandev-runner/Dockerfile`
- ✅ Already configured to copy wordlists from `wordlists/` directory
- ✅ Already includes `check_tools.sh` verification script
- ✅ Tools use pinned versions (for reproducibility)

### 4. Qdrant Service (`services/qdrant-fly/`)

#### `services/qdrant-fly/fly.toml`
- ✅ Already properly configured
- ✅ Uses volume `qdrant_data` for persistent storage
- ✅ Private service (accessible via `.internal` DNS only)

### 5. Documentation (`DEPLOY.md`)

#### Updated `DEPLOY.md`
- ✅ Fixed volume name reference: `qdrant-data` → `qdrant_data` (to match fly.toml)
- ✅ Updated BRAIN_URL references to BRAIN_SERVICE_URL for clarity
- ✅ Added note about nmap `-sT` flag (TCP connect scan, no root required)
- ✅ Clarified environment variable defaults and overrides

## Key Features

### Private Networking
All services use Fly.io private networking (`.internal` DNS) for service-to-service communication:
- Backend → Brain: `http://thandev-brain.internal:8001`
- Brain → Qdrant: `http://thandev-qdrant.internal:6333`
- Backend → Redis: Via Upstash Redis (private connection)

### Security
- ✅ Nmap runs in safe mode (`-sT`) - no raw sockets required
- ✅ All services run as non-root users
- ✅ Only backend is publicly accessible (HTTPS)
- ✅ Brain, Qdrant, and Runner are private (no public endpoints)

### Resilience
- ✅ Health checks configured for all HTTP services
- ✅ Automatic migrations via `release_command` in backend
- ✅ Graceful degradation (Brain falls back if Qdrant unavailable)
- ✅ Tool verification in runner startup

### Configuration
- ✅ Sensible defaults for all services
- ✅ Environment variables can override defaults
- ✅ Secrets managed via Fly.io secrets (not in code)

## Deployment Checklist

Before deploying, ensure:

1. ✅ All Fly apps created (`thandev-backend`, `thandev-brain`, `thandev-runner`, `thandev-qdrant`)
2. ✅ Redis provisioned (Upstash via Fly)
3. ✅ PostgreSQL database available (DATABASE_URL)
4. ✅ Qdrant volume created (`qdrant_data`)
5. ✅ Secrets set for all services (see DEPLOY.md)
6. ✅ Wordlists copied to runner directory before build (if needed)

## Testing Locally

To verify changes work locally before deploying:

```bash
# Test backend health
curl http://localhost:8000/health

# Test brain health
curl http://localhost:8001/health
curl http://localhost:8001/healthz

# Test nmap safe mode (should work without sudo)
nmap -sT --top-ports 100 -sV example.com
```

## Next Steps

1. Review this summary
2. Follow `DEPLOY.md` for step-by-step deployment instructions
3. Monitor logs after deployment: `fly logs -a <app-name>`
4. Run smoke tests (see DEPLOY.md Step 9.4)

## Notes

- All changes maintain backward compatibility
- No breaking changes to existing functionality
- Configuration defaults work out-of-the-box
- Production-ready with proper error handling and logging



