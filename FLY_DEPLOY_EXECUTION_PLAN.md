# Fly.io Deployment Execution Plan

**Goal**: Deploy Qdrant, Brain, and Runner services on Fly.io (region `iad`), wire internal networking, and verify end-to-end scans work.

**Status**: Backend already deployed (`thandev-backend`), Frontend on Vercel, Database on Neon.

---

## Section 1: Preflight Checks (Files)

### ✅ Qdrant Configuration (`services/qdrant-fly/fly.toml`)
**Status**: ✅ CORRECT - No changes needed

- ✅ Pinned image: `qdrant/qdrant:v1.7.4`
- ✅ Private service: `[[services]]` with `internal_port=6333`, `protocol=tcp`
- ✅ No `[http_service]` section (keeps it private)
- ✅ Volume mount: `qdrant-data` → `/qdrant/storage`
- ✅ Region: `iad`

### ✅ Brain Configuration (`services/thandev-brain/fly.toml`)
**Status**: ✅ CORRECT - No changes needed

- ✅ Private service: `[[services]]` with `internal_port=8001`
- ✅ Health checks: `[[services.http_checks]]` with `path=/healthz`
- ✅ No `[http_service]` section (keeps it private)
- ✅ Region: `iad`

### ✅ Runner Configuration (`services/thandev-runner/fly.toml`)
**Status**: ✅ CORRECT - No changes needed

- ✅ Private worker: `[processes]` only, no `[http_service]`
- ✅ Resources: `cpus=2`, `memory_mb=2048`
- ✅ Region: `iad`

### ✅ Additional Verifications

```bash
# Verify healthz endpoint exists
grep -A 3 "def healthz" services/thandev-brain/app/main.py
# ✅ Should show: async def healthz(): return {"status": "ok", ...}

# Verify wordlists directory exists
ls -la services/thandev-runner/wordlists/
# ✅ Should show: common.txt, ffuf-*.txt files

# Verify check_tools.sh exists
test -f services/thandev-runner/check_tools.sh && echo "✅ check_tools.sh exists"
```

**All configurations verified. Ready to deploy.**

---

## Section 2: Copy-Paste Deployment Commands

**Run these commands in order from the project root (`/home/ashwath/thandev`):**

### Step 1: Create Redis (Upstash)

```bash
# Create Redis instance
fly redis create --name thandev-redis --region iad

# ⚠️ IMPORTANT: Copy the REDIS_URL from output
# It will look like:
#   redis://default:XXXXX@XXX.upstash.io:6379
# OR (if TLS enabled):
#   rediss://default:XXXXX@XXX.upstash.io:6379
# 
# Save this URL - you'll need it for all services!
# Export it for easy reference:
# export REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379"
```

### Step 2: Create Fly Apps (if they don't exist)

```bash
# Create Qdrant app
fly apps create thandev-qdrant --org personal --region iad 2>&1 | grep -v "already exists" || true

# Create Brain app
fly apps create thandev-brain --org personal --region iad 2>&1 | grep -v "already exists" || true

# Create Runner app
fly apps create thandev-runner --org personal --region iad 2>&1 | grep -v "already exists" || true
```

### Step 3: Create Qdrant Volume

```bash
# Create 10GB volume for Qdrant persistence
fly volumes create qdrant-data --size 10 --region iad -a thandev-qdrant
```

### Step 4: Deploy Qdrant

```bash
cd services/qdrant-fly
fly deploy -a thandev-qdrant --remote-only
cd ../..
```

### Step 5: Deploy Brain

```bash
cd services/thandev-brain
fly deploy -a thandev-brain --remote-only
cd ../..
```

### Step 6: Deploy Runner

```bash
cd services/thandev-runner
fly deploy -a thandev-runner --remote-only
cd ../..
```

**Note**: Secrets will be set in Section 3. Services will fail until secrets are configured.

---

## Section 3: Secrets Checklist

### Step 1: Get Backend DATABASE_URL (Neon)

```bash
# Get the Neon DATABASE_URL from backend secrets
fly secrets list -a thandev-backend | grep DATABASE_URL

# Or if you need to see the actual value (it will be masked):
# fly ssh console -a thandev-backend -C "echo \$DATABASE_URL"
```

**Save this DATABASE_URL - Runner must use the SAME Neon database.**

### Step 2: Set Brain Secrets

```bash
# Replace <REDIS_URL> with the URL from Step 1 (Section 2)
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  RAG_STORE_TYPE="qdrant" \
  EMBEDDING_PROVIDER="sentence_transformers" \
  -a thandev-brain

# Example:
# fly secrets set \
#   REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
#   QDRANT_URL="http://thandev-qdrant.internal:6333" \
#   RAG_STORE_TYPE="qdrant" \
#   EMBEDDING_PROVIDER="sentence_transformers" \
#   -a thandev-brain
```

### Step 3: Set Runner Secrets

```bash
# Replace <DATABASE_URL> with SAME Neon URL from backend
# Replace <REDIS_URL> with the URL from Step 1 (Section 2)
fly secrets set \
  DATABASE_URL="<DATABASE_URL>" \
  REDIS_URL="<REDIS_URL>" \
  WORDLISTS_DIR="/opt/thandev/wordlists" \
  -a thandev-runner

# Example:
# fly secrets set \
#   DATABASE_URL="postgresql://user:pass@neon-host.neon.tech/dbname?sslmode=require" \
#   REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
#   WORDLISTS_DIR="/opt/thandev/wordlists" \
#   -a thandev-runner
```

### Step 4: Update Backend Secrets

```bash
# Replace <REDIS_URL> with the URL from Step 1 (Section 2)
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend

# Example:
# fly secrets set \
#   REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
#   BRAIN_URL="http://thandev-brain.internal:8001" \
#   -a thandev-backend
```

### Secrets Summary Table

| Service | Secret | Value | Notes |
|---------|--------|-------|-------|
| **thandev-brain** | REDIS_URL | From `fly redis create` | May be `redis://` or `rediss://` |
| **thandev-brain** | QDRANT_URL | `http://thandev-qdrant.internal:6333` | Internal DNS |
| **thandev-brain** | RAG_STORE_TYPE | `qdrant` | Fixed value |
| **thandev-brain** | EMBEDDING_PROVIDER | `sentence_transformers` | Default (no OpenAI required) |
| **thandev-runner** | DATABASE_URL | **Same as backend** | **CRITICAL: Must be same Neon DB** |
| **thandev-runner** | REDIS_URL | From `fly redis create` | May be `redis://` or `rediss://` |
| **thandev-runner** | WORDLISTS_DIR | `/opt/thandev/wordlists` | Fixed path |
| **thandev-backend** | REDIS_URL | From `fly redis create` | May be `redis://` or `rediss://` |
| **thandev-backend** | BRAIN_URL | `http://thandev-brain.internal:8001` | Internal DNS |
| **thandev-backend** | DATABASE_URL | Neon URL | Already set, verify it's Neon |

---

## Section 4: Verification Commands

### 4.1: Check All Apps Status

```bash
# Check all apps are running
fly status -a thandev-backend
fly status -a thandev-qdrant
fly status -a thandev-brain
fly status -a thandev-runner

# All should show: STATUS = running
```

### 4.2: Verify Backend → Brain Connectivity

```bash
# Test Brain health endpoint from backend VM
fly ssh console -a thandev-backend -C "curl -sS http://thandev-brain.internal:8001/healthz"

# Expected output:
# {"status":"ok","service":"thandev-brain","version":"1.0.0"}
```

### 4.3: Verify Brain → Qdrant Connectivity

```bash
# Test Qdrant from brain VM
fly ssh console -a thandev-brain -C "curl -sS http://thandev-qdrant.internal:6333/collections"

# Expected output:
# {"result":{"collections":[...]},"status":"ok","time":...}
# (Collections may be empty initially - that's OK)
```

### 4.4: Verify Redis Connection (All Services)

```bash
# Test Redis from backend
fly ssh console -a thandev-backend -C "python3 -c \"
from app.core.config import settings
import redis
from urllib.parse import urlparse
parsed = urlparse(settings.REDIS_URL)
use_tls = parsed.scheme == 'rediss'
kwargs = {'decode_responses': True}
if use_tls:
    kwargs['ssl'] = True
client = redis.from_url(settings.REDIS_URL, **kwargs)
client.ping()
print('✅ Backend Redis connected')
\""

# Test Redis from brain
fly ssh console -a thandev-brain -C "python3 -c \"
import os
import redis
from urllib.parse import urlparse
redis_url = os.environ.get('REDIS_URL')
parsed = urlparse(redis_url)
use_tls = parsed.scheme == 'rediss'
kwargs = {'decode_responses': True}
if use_tls:
    kwargs['ssl'] = True
client = redis.from_url(redis_url, **kwargs)
client.ping()
print('✅ Brain Redis connected')
\""

# Test Redis from runner
fly ssh console -a thandev-runner -C "python3 -c \"
import os
import redis
from urllib.parse import urlparse
redis_url = os.environ.get('REDIS_URL')
parsed = urlparse(redis_url)
use_tls = parsed.scheme == 'rediss'
kwargs = {'decode_responses': True}
if use_tls:
    kwargs['ssl'] = True
client = redis.from_url(redis_url, **kwargs)
client.ping()
print('✅ Runner Redis connected')
\""
```

### 4.5: Verify Runner Tool Verification

```bash
# Check runner logs for tool verification output
fly logs -a thandev-runner | grep -A 50 "Tool Verification"

# Expected output should show:
# - Tool versions (nuclei, httpx, ffuf, dalfox, nmap, sslscan, sqlmap)
# - Wordlists directory verification
# - "Tool Verification Complete"
```

### 4.6: Verify Runner Database Connection

```bash
# Test database connection from runner VM
fly ssh console -a thandev-runner -C "python3 -c \"
import os
from sqlalchemy import create_engine, text
db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✅ Runner database connected')
\""
```

### 4.7: Verify Backend Health Endpoint

```bash
# Check backend health (should show Redis and Brain status)
curl -sS https://thandev-backend.fly.dev/health | python3 -m json.tool

# Expected output should show:
# {
#   "status": "ok",
#   "checks": {
#     "database": "ready",
#     "redis": "ready",
#     "brain": "ready" (if brain is accessible)
#   }
# }
```

### 4.8: End-to-End Scan Test (Allowlisted Domain)

```bash
# Watch logs in parallel (run in separate terminals)

# Terminal 1: Backend logs
fly logs -a thandev-backend

# Terminal 2: Runner logs
fly logs -a thandev-runner

# Terminal 3: Brain logs (if brain is used)
fly logs -a thandev-brain

# Then trigger a scan from UI or API:
# Use allowlisted domain (e.g., bwapp.itsecgames.com or itsecgames.com)
# Expected flow:
# 1. Backend: Scan created, steps published to Redis
# 2. Runner: Tool verification, consuming from Redis stream, executing tools
# 3. Brain: (if enabled) Planning requests, RAG queries
```

---

## Section 5: If Something Fails - Fast Troubleshooting

### Issue 1: `.internal` DNS Not Resolving

**Symptoms**:
- `Connection refused` when accessing `*.internal` addresses
- Brain/Qdrant not reachable from backend

**Causes**:
- Apps in different regions (must all be `iad`)
- Apps in different orgs (must all be `personal`)

**Fix**:
```bash
# Verify all apps are in same region
fly status -a thandev-backend | grep REGION
fly status -a thandev-brain | grep REGION
fly status -a thandev-qdrant | grep REGION
# All should show: REGION = iad

# Verify all apps are in same org
fly apps list | grep thandev
# All should show: OWNER = personal

# If any are wrong, recreate the app:
# fly apps destroy <wrong-app> -a <app-name>
# fly apps create <app-name> --org personal --region iad
```

---

### Issue 2: Redis Connection Failed (TLS Mismatch)

**Symptoms**:
- `SSL` errors or `Connection refused` when connecting to Redis
- Upstash gave `rediss://` but service can't connect

**Fix**:
```bash
# Verify REDIS_URL scheme
fly secrets list -a thandev-backend | grep REDIS_URL

# If it's rediss:// (double 's'), TLS is enabled - code already supports this
# If connection still fails, check logs:
fly logs -a thandev-backend | grep -i redis
fly logs -a thandev-brain | grep -i redis
fly logs -a thandev-runner | grep -i redis

# All services already support rediss:// with SSL=True
# No code changes needed - verify secrets are set correctly
```

---

### Issue 3: Runner "scan job not found" Errors

**Symptoms**:
- Runner logs show: `scan job not found` or `relation "scan_jobs" does not exist`
- Runner can't find scans created by backend

**Cause**:
- Runner using different database than backend

**Fix**:
```bash
# Get backend DATABASE_URL
fly secrets list -a thandev-backend | grep DATABASE_URL

# Get runner DATABASE_URL
fly secrets list -a thandev-runner | grep DATABASE_URL

# They MUST be identical! If different, fix runner:
fly secrets set DATABASE_URL="<SAME_NEON_URL_AS_BACKEND>" -a thandev-runner

# Restart runner
fly machine restart -a thandev-runner
```

---

### Issue 4: Runner Missing Tools or Wordlists

**Symptoms**:
- Runner fails on startup with: `tool not found` or `wordlists directory not found`
- Logs show: `ERROR: nuclei not found in PATH` or similar

**Fix**:
```bash
# Check runner logs
fly logs -a thandev-runner

# Verify Dockerfile copies wordlists (should already be correct)
grep "COPY wordlists" services/thandev-runner/Dockerfile
# Should show: COPY wordlists /opt/thandev/wordlists

# Rebuild and redeploy runner
cd services/thandev-runner
fly deploy -a thandev-runner --remote-only
cd ../..
```

---

### Issue 5: Brain /healthz Returns 500

**Symptoms**:
- Brain health check fails
- Backend can't connect to brain

**Fix**:
```bash
# Check brain logs
fly logs -a thandev-brain | tail -50

# Common causes:
# 1. Qdrant not accessible - verify QDRANT_URL secret
fly secrets list -a thandev-brain | grep QDRANT_URL
# Should be: http://thandev-qdrant.internal:6333

# 2. Redis not accessible - verify REDIS_URL secret
fly secrets list -a thandev-brain | grep REDIS_URL

# 3. Missing dependencies - check logs for import errors
fly logs -a thandev-brain | grep -i "error\|exception\|import"
```

---

### Issue 6: Qdrant Volume Issues

**Symptoms**:
- Qdrant fails to start or loses data
- Volume mount errors

**Fix**:
```bash
# Check volume status
fly volumes list -a thandev-qdrant

# Verify volume is attached (should show "attached" status)
# If volume missing or detached:
fly volumes create qdrant-data --size 10 --region iad -a thandev-qdrant

# Redeploy Qdrant
cd services/qdrant-fly
fly deploy -a thandev-qdrant --remote-only
cd ../..
```

---

## Quick Reference

### App Names
- `thandev-backend` - Public API (already deployed)
- `thandev-qdrant` - Private vector database
- `thandev-brain` - Private AI planning service
- `thandev-runner` - Private worker service

### Internal URLs
- Brain: `http://thandev-brain.internal:8001`
- Qdrant: `http://thandev-qdrant.internal:6333`

### Region & Org
- Region: `iad` (all apps)
- Org: `personal` (all apps)

### External URLs
- Backend: `https://thandev-backend.fly.dev`
- Frontend: (on Vercel - check Vercel dashboard)

---

## Deployment Checklist

Use this checklist to track progress:

- [ ] Redis created (`fly redis create`)
- [ ] REDIS_URL saved and exported
- [ ] Qdrant app created
- [ ] Qdrant volume created
- [ ] Qdrant deployed
- [ ] Brain app created
- [ ] Brain secrets set
- [ ] Brain deployed
- [ ] Runner app created
- [ ] Runner secrets set (DATABASE_URL = same as backend)
- [ ] Runner deployed
- [ ] Backend secrets updated (REDIS_URL, BRAIN_URL)
- [ ] All apps status = running
- [ ] Backend → Brain connectivity verified
- [ ] Brain → Qdrant connectivity verified
- [ ] Redis connectivity verified (all services)
- [ ] Runner tool verification passed
- [ ] Runner database connection verified
- [ ] End-to-end scan test successful

**Once all items are checked, deployment is complete! 🎉**

