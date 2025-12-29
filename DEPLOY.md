# Thandev Fly.io Production Deployment Guide

This guide covers deploying all Thandev services to Fly.io for production.

## Prerequisites

- Fly CLI installed and logged in: `fly auth login`
- Fly.io account and organization
- All apps will be deployed to region `iad` (Washington, D.C.)

## Architecture Overview

```
Vercel Frontend (https://thandev.vercel.app)
    ↓ (public HTTPS)
Fly Backend (https://thandev-backend.fly.dev - PUBLIC)
    ↓ (private .internal DNS)
    ├→ Brain Service (thandev-brain.internal:8001 - PRIVATE)
    │   └→ Qdrant (thandev-qdrant.internal:6333 - PRIVATE)
    │   └→ Redis (Upstash via Fly - PRIVATE)
    ├→ Redis (Upstash via Fly - PRIVATE) → Runner (thandev-runner, worker - PRIVATE)
    └→ PostgreSQL (Neon DB or Fly Postgres - via DATABASE_URL)
```

## Step 1: Create Fly Apps

Create all apps in the same region (`iad`) and organization:

```bash
# Backend (already exists, but verify)
fly apps list | grep thandev-backend || fly apps create thandev-backend --org <your-org>

# Brain service
fly apps create thandev-brain --org <your-org>

# Runner service
fly apps create thandev-runner --org <your-org>

# Qdrant service
fly apps create thandev-qdrant --org <your-org>
```

## Step 2: Provision Redis (Upstash via Fly)

```bash
# Create Upstash Redis instance in region iad
fly redis create --region iad --name thandev-redis

# The command will output the REDIS_URL
# Example output:
# Upstash Redis instance created!
# REDIS_URL=redis://default:...@...upstash.io:6379
# or
# REDIS_URL=rediss://default:...@...upstash.io:6380 (if TLS enabled)

# Copy the REDIS_URL - you'll need it in the next steps
```

**Note**: If the URL uses `rediss://` (TLS), all services support TLS. If certificate verification fails, you can set `REDIS_TLS_INSECURE=true` as a secret (not recommended for production).

## Step 3: Database Setup

Use your existing database (Neon DB or Fly Postgres). The `DATABASE_URL` must be accessible from both backend and runner (they use the same database).

**Important**: Runner must use the same `DATABASE_URL` as backend to avoid "scan job not found" errors.

```bash
# If using Fly Postgres (example):
fly postgres create --name thandev-db --region iad
fly postgres attach thandev-db --app thandev-backend

# Get the connection string
fly postgres connect -a thandev-db
# Or check: fly postgres show -a thandev-db
```

## Step 4: Deploy Qdrant

```bash
cd services/qdrant-fly

# Create volume for persistent storage (name must match fly.toml)
fly volumes create qdrant_data --size 10 --region iad -a thandev-qdrant

# Deploy Qdrant (PRIVATE service, no public access)
fly deploy -a thandev-qdrant --remote-only

# Verify Qdrant is running
fly status -a thandev-qdrant
```

Qdrant will be accessible only via `http://thandev-qdrant.internal:6333` from other Fly services.

## Step 5: Deploy Brain Service

```bash
cd services/thandev-brain

# Set secrets
fly secrets set \
  REDIS_URL="<your-redis-url-from-step-2>" \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  RAG_STORE_TYPE="qdrant" \
  EMBEDDING_PROVIDER="sentence_transformers" \
  OPENAI_API_KEY="<your-openai-key-if-using-openai>" \
  -a thandev-brain

# If using OpenAI embeddings, set:
# EMBEDDING_PROVIDER="openai"
# OPENAI_API_KEY="sk-..."

# Deploy brain service (PRIVATE service)
fly deploy -a thandev-brain

# Verify brain is running
fly status -a thandev-brain
```

Brain service will be accessible only via `http://thandev-brain.internal:8001` from backend.

## Step 6: Deploy Runner Service

```bash
cd services/thandev-runner

# Copy wordlists from repo root into runner directory (required for Docker build)
# This is needed because Docker build context is the runner directory
cp -r ../../wordlists wordlists

# Set secrets (DATABASE_URL must match backend)
fly secrets set \
  DATABASE_URL="<same-database-url-as-backend>" \
  REDIS_URL="<your-redis-url-from-step-2>" \
  WORDLISTS_DIR="/opt/thandev/wordlists" \
  -a thandev-runner

# Deploy runner service (PRIVATE worker)
fly deploy -a thandev-runner

# Clean up copied wordlists after deployment (optional, they're in .gitignore)
rm -rf wordlists

# Verify runner is running
fly status -a thandev-runner
fly logs -a thandev-runner

# Expected log output should include:
# - Tool versions (nuclei, httpx, ffuf, dalfox, nmap, sslscan, sqlmap)
# - Tool paths (which commands)
# - WORDLISTS_DIR verification
# - Wordlist files listed
# - "Starting runner worker..."
```

## Step 7: Deploy Backend Service

```bash
cd backend

# Set secrets
fly secrets set \
  DATABASE_URL="<your-database-url>" \
  REDIS_URL="<your-redis-url-from-step-2>" \
  BRAIN_SERVICE_URL="http://thandev-brain.internal:8001" \
  OPENAI_API_KEY="<your-openai-key>" \
  -a thandev-backend

# Note: BRAIN_SERVICE_URL defaults to http://thandev-brain.internal:8001 in config
# You can also set BRAIN_URL to override BRAIN_SERVICE_URL if needed

# Optional: Set other secrets as needed
# fly secrets set ENVIRONMENT="production" -a thandev-backend

# Deploy backend (PUBLIC service)
fly deploy -a thandev-backend

# Verify backend is running
fly status -a thandev-backend
```

Backend will be accessible at `https://thandev-backend.fly.dev` (public).

## Step 8: Update Frontend (Vercel)

In Vercel dashboard, update environment variables:

```
NEXT_PUBLIC_API_BASE=https://thandev-backend.fly.dev
```

The frontend is already deployed and doesn't need changes except this env var update.

## Step 9: Verification

### 9.1 Backend Health Check (Public)

```bash
curl https://thandev-backend.fly.dev/health
```

Expected response: JSON with status checks for database, redis, brain_service.

### 9.2 Internal Connectivity Checks

Use Fly SSH console to test internal service-to-service connectivity:

```bash
# SSH into backend machine
fly ssh console -a thandev-backend

# Test brain service connectivity
curl http://thandev-brain.internal:8001/healthz

# Expected: {"status":"ok","service":"thandev-brain","version":"1.0.0"}

# Test qdrant connectivity (from backend, via brain's perspective)
# You can also test directly:
curl http://thandev-qdrant.internal:6333/health

# Expected: Qdrant health check JSON

# Exit SSH console
exit
```

### 9.3 Runner Verification

```bash
# Check runner logs for tool verification output
fly logs -a thandev-runner | grep -A 50 "Tool Verification"

# Expected output includes:
# - Tool versions for all tools (nuclei, httpx, ffuf, dalfox, nmap, sslscan, sqlmap)
# - Tool paths (which commands)
# - WORDLISTS_DIR exists: /opt/thandev/wordlists
# - Wordlist files listed (ffuf-small.txt, ffuf-pro.txt, etc.)

# Check runner is consuming from Redis streams
fly logs -a thandev-runner | grep "Received messages from Redis"

# Expected: Log entries showing stream consumption
```

### 9.4 Smoke Test (End-to-End)

1. **Create a project**:
```bash
curl -X POST https://thandev-backend.fly.dev/api/projects \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <test-user-id>" \
  -H "X-Thandev-Tenant-Id: <test-tenant-id>" \
  -d '{
    "name": "Test Project",
    "target_url": "https://example.com"
  }'
```

2. **Start domain verification** (if required):
```bash
# Check project verification status
curl https://thandev-backend.fly.dev/api/projects/<project-id>/domain-verifications \
  -H "X-Thandev-User-Id: <test-user-id>" \
  -H "X-Thandev-Tenant-Id: <test-tenant-id>"
```

3. **Create a scan job**:
```bash
curl -X POST https://thandev-backend.fly.dev/api/scans \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: <test-user-id>" \
  -H "X-Thandev-Tenant-Id: <test-tenant-id>" \
  -d '{
    "project_id": "<project-id>",
    "scan_level": "basic"
  }'
```

4. **Verify runner consumes and processes scan**:
```bash
# Check runner logs for step execution
fly logs -a thandev-runner | grep "Executing step"

# Check backend for tool_results
curl https://thandev-backend.fly.dev/api/scans/<scan-id>/tool-results \
  -H "X-Thandev-User-Id: <test-user-id>" \
  -H "X-Thandev-Tenant-Id: <test-tenant-id>"

# Check findings were created
curl https://thandev-backend.fly.dev/api/scans/<scan-id>/findings \
  -H "X-Thandev-User-Id: <test-user-id>" \
  -H "X-Thandev-Tenant-Id: <test-tenant-id>"
```

## Step 10: Scaling

### Backend Scaling

```bash
# Scale backend instances
fly scale count 2 -a thandev-backend

# Scale backend VM size (if needed)
fly scale vm shared-cpu-2x -a thandev-backend
fly scale memory 512 -a thandev-backend
```

### Runner Scaling

```bash
# Scale runner instances (multiple workers)
fly scale count 3 -a thandev-runner

# Runner uses performance-1x recommended for tool execution
fly scale vm performance-1x -a thandev-runner
fly scale memory 2048 -a thandev-runner
```

### Brain Scaling

```bash
# Scale brain VM size (adjust memory for sentence-transformers if needed)
fly scale vm shared-cpu-2x -a thandev-brain
fly scale memory 1024 -a thandev-brain  # Increase if using sentence-transformers
```

### Qdrant Scaling

```bash
# Scale Qdrant VM size (if needed)
fly scale vm shared-cpu-2x -a thandev-qdrant
fly scale memory 1024 -a thandev-qdrant
```

## Troubleshooting

### Backend can't reach brain service

- Verify brain service is running: `fly status -a thandev-brain`
- Check brain logs: `fly logs -a thandev-brain`
- Verify `BRAIN_SERVICE_URL` secret is set correctly (or uses default): `fly secrets list -a thandev-backend`
- Test internal connectivity: `fly ssh console -a thandev-backend` then `curl http://thandev-brain.internal:8001/healthz`

### Runner not consuming from Redis

- Verify Redis is accessible: Check `REDIS_URL` secret
- Check runner logs: `fly logs -a thandev-runner`
- Verify runner is running: `fly status -a thandev-runner`
- Check Redis stream exists (SSH into backend and use redis-cli)

### Qdrant not accessible

- Verify Qdrant is running: `fly status -a thandev-qdrant`
- Check Qdrant logs: `fly logs -a thandev-qdrant`
- Verify volume is attached: `fly volumes list -a thandev-qdrant`
- Test internal connectivity: `fly ssh console -a thandev-brain` then `curl http://thandev-qdrant.internal:6333/health`

### Tools not found in runner

- Check runner startup logs for tool verification output
- Verify Dockerfile pinned tool versions are correct
- Check tool paths in logs (should show /home/app/go/bin or /usr/local/bin)
- Verify wordlists directory exists: Check logs for "WORDLISTS_DIR exists: /opt/thandev/wordlists"

## Environment Variables Summary

### Backend (`thandev-backend`)
- `DATABASE_URL` (required) - PostgreSQL connection string
- `REDIS_URL` (required) - Redis connection string (redis:// or rediss://)
- `BRAIN_SERVICE_URL` (optional) - Defaults to `http://thandev-brain.internal:8001`
- `BRAIN_URL` (optional) - Overrides BRAIN_SERVICE_URL if set
- `OPENAI_API_KEY` (optional) - For report generation

### Brain (`thandev-brain`)
- `REDIS_URL` (required) - Redis connection string
- `QDRANT_URL` (optional) - Defaults to `http://thandev-qdrant.internal:6333`
- `RAG_STORE_TYPE` (optional) - Defaults to `qdrant`
- `EMBEDDING_PROVIDER` (optional) - `sentence_transformers` or `openai`
- `OPENAI_API_KEY` (required if using OpenAI embeddings)

### Runner (`thandev-runner`)
- `DATABASE_URL` (required) - **Must match backend's DATABASE_URL**
- `REDIS_URL` (required) - Redis connection string
- `WORDLISTS_DIR` (optional) - Defaults to `/opt/thandev/wordlists`

### All Services
- `REDIS_TLS_INSECURE` (optional) - Set to `true` if Redis TLS certificate verification fails (not recommended for production)

## Deployment Order Summary

1. **Redis** → Provision Upstash Redis, capture REDIS_URL
2. **Qdrant** → Create volume, deploy qdrant service
3. **Brain** → Set secrets, deploy brain service
4. **Runner** → Set secrets (same DATABASE_URL as backend), deploy runner service
5. **Backend** → Set secrets, deploy backend service (migrations run via release_command)
6. **Frontend** → Update Vercel env var to point to backend public URL

## Notes

- All services use Fly private networking (`.internal` DNS) for service-to-service communication
- Backend is the only public service (accessible from internet via `https://thandev-backend.fly.dev`)
- Brain, Qdrant, and Runner are PRIVATE (no public HTTP endpoints)
- Migrations run automatically via Fly `release_command` before backend containers start
- Runner tools are self-contained (no backend dependencies)
- Wordlists are baked into runner image at `/opt/thandev/wordlists`
- All Go tools use pinned versions (no `@latest`)
- Nmap runs in safe mode (`-sT`) - TCP connect scan, no raw sockets required
- All nmap scans use `-sT` flag to avoid requiring root privileges

