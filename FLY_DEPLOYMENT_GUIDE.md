# Fly.io Production Deployment Guide

**Goal**: Deploy Redis, Qdrant, Brain, and Runner services on Fly.io to match local setup.

**Status**: Backend is already deployed on Fly, Frontend on Vercel, Database on Neon.

---

## Prerequisites Check

✅ **Fly CLI**: Installed (v0.4.0)
✅ **Fly Auth**: Logged in as `aswathama0604@gmail.com`
✅ **Fly Org**: `personal`
✅ **Region**: `iad` (all apps must use this region)
✅ **Existing Apps**: `thandev-backend` (suspended, will be updated)

---

## DEPLOYMENT EXECUTION

Run these commands **in order** from the project root (`/home/ashwath/thandev`):

### Step 1: Provision Redis (Fly Upstash)

```bash
# Create Upstash Redis instance
fly redis create --region iad --name thandev-redis

# IMPORTANT: Capture the REDIS_URL from the output
# It will look like: redis://default:XXXXX@XXX.upstash.io:6379
# OR: rediss://default:XXXXX@XXX.upstash.io:6379 (if TLS enabled)
# Save this URL - you'll need it for all services!
```

**Note**: If the output shows `rediss://` (with double 's'), it means TLS is enabled. All services already support TLS.

---

### Step 2: Deploy Qdrant (Private Service)

```bash
cd services/qdrant-fly

# Create app if it doesn't exist
fly apps create thandev-qdrant --org personal --region iad 2>&1 | grep -v "already exists" || true

# Create volume for persistent storage (10GB)
fly volumes create qdrant-data --size 10 --region iad -a thandev-qdrant

# Deploy Qdrant (uses pinned image v1.7.4 from fly.toml)
fly deploy -a thandev-qdrant --remote-only

cd ../..
```

**Verify Qdrant is running:**
```bash
fly status -a thandev-qdrant
# Should show: STATUS = running
```

---

### Step 3: Deploy Brain Service (Private FastAPI)

```bash
cd services/thandev-brain

# Create app if it doesn't exist
fly apps create thandev-brain --org personal --region iad 2>&1 | grep -v "already exists" || true

# Set secrets (REPLACE <REDIS_URL> with the URL from Step 1)
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  RAG_STORE_TYPE="qdrant" \
  EMBEDDING_PROVIDER="sentence_transformers" \
  -a thandev-brain

# If you want to use OpenAI embeddings instead:
# fly secrets set EMBEDDING_PROVIDER="openai" OPENAI_API_KEY="sk-..." -a thandev-brain

# Deploy Brain service
fly deploy -a thandev-brain --remote-only

cd ../..
```

**Verify Brain is running:**
```bash
fly status -a thandev-brain
# Should show: STATUS = running
```

---

### Step 4: Deploy Runner Service (Private Worker)

```bash
cd services/thandev-runner

# Create app if it doesn't exist
fly apps create thandev-runner --org personal --region iad 2>&1 | grep -v "already exists" || true

# Get the DATABASE_URL from backend secrets (same Neon database)
BACKEND_DB_URL=$(fly secrets list -a thandev-backend | grep DATABASE_URL | awk '{print $1}')
# Or manually set it if the command above doesn't work:
# BACKEND_DB_URL="postgresql://user:pass@neon-host.neon.tech/dbname?sslmode=require"

# Set secrets (REPLACE <REDIS_URL> with URL from Step 1, <DATABASE_URL> with Neon URL)
fly secrets set \
  DATABASE_URL="<DATABASE_URL>" \
  REDIS_URL="<REDIS_URL>" \
  WORDLISTS_DIR="/opt/thandev/wordlists" \
  -a thandev-runner

# Deploy Runner service
fly deploy -a thandev-runner --remote-only

cd ../..
```

**Verify Runner is running:**
```bash
fly status -a thandev-runner
# Should show: STATUS = running
fly logs -a thandev-runner
# Should show tool verification output and worker starting
```

---

### Step 5: Update Backend Secrets

```bash
cd backend

# Get current DATABASE_URL (should already be set to Neon)
fly secrets list -a thandev-backend

# Set secrets (REPLACE <REDIS_URL> with URL from Step 1)
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend

# DATABASE_URL should already be set - verify it's Neon
# If not, set it: fly secrets set DATABASE_URL="postgresql://..." -a thandev-backend

# Only deploy if fly.toml or code changed, otherwise secrets are already active
# fly deploy -a thandev-backend --remote-only

cd ..
```

---

## SECRETS CHECKLIST

Use this checklist to verify all secrets are set correctly:

### thandev-backend
- [ ] `DATABASE_URL` = Neon PostgreSQL URL (already set)
- [ ] `REDIS_URL` = Upstash Redis URL from Step 1
- [ ] `BRAIN_URL` = `http://thandev-brain.internal:8001`

### thandev-brain
- [ ] `REDIS_URL` = Upstash Redis URL from Step 1
- [ ] `QDRANT_URL` = `http://thandev-qdrant.internal:6333`
- [ ] `RAG_STORE_TYPE` = `qdrant`
- [ ] `EMBEDDING_PROVIDER` = `sentence_transformers` (or `openai` if using OpenAI)
- [ ] `OPENAI_API_KEY` = (only if `EMBEDDING_PROVIDER=openai`)

### thandev-runner
- [ ] `DATABASE_URL` = **Same Neon URL as backend** (CRITICAL!)
- [ ] `REDIS_URL` = Upstash Redis URL from Step 1
- [ ] `WORDLISTS_DIR` = `/opt/thandev/wordlists`

### thandev-qdrant
- No secrets needed (uses volume for storage)

---

## VERIFY DEPLOYMENT

### 1. Check All Apps Status

```bash
fly status -a thandev-backend
fly status -a thandev-qdrant
fly status -a thandev-brain
fly status -a thandev-runner
```

All should show `STATUS = running`.

---

### 2. Verify Internal Connectivity

#### From Backend → Brain

```bash
fly ssh console -a thandev-backend

# Inside the VM, test Brain connectivity:
python3 -c "
import httpx
try:
    resp = httpx.get('http://thandev-brain.internal:8001/healthz', timeout=5)
    print(f'✅ Brain health: {resp.status_code} - {resp.json()}')
except Exception as e:
    print(f'❌ Brain connection failed: {e}')
"

exit
```

**Expected**: `{'status': 'ok', 'service': 'thandev-brain', 'version': '1.0.0'}`

---

#### From Brain → Qdrant

```bash
fly ssh console -a thandev-brain

# Inside the VM, test Qdrant connectivity:
python3 -c "
import httpx
try:
    resp = httpx.get('http://thandev-qdrant.internal:6333/collections', timeout=5)
    print(f'✅ Qdrant connection: {resp.status_code}')
    print(f'Collections: {resp.json()}')
except Exception as e:
    print(f'❌ Qdrant connection failed: {e}')
"

exit
```

**Expected**: HTTP 200 with collections list (may be empty initially).

---

### 3. Verify Redis Connection (All Services)

```bash
# Test from backend
fly ssh console -a thandev-backend
python3 -c "
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
print('✅ Redis connected')
"
exit

# Test from brain (should be similar)
fly ssh console -a thandev-brain
python3 -c "
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
print('✅ Redis connected')
"
exit

# Test from runner (should be similar)
fly ssh console -a thandev-runner
python3 -c "
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
print('✅ Redis connected')
"
exit
```

**Expected**: All should print `✅ Redis connected`.

---

### 4. Verify Runner Tool Verification

```bash
fly logs -a thandev-runner | grep -A 50 "Tool Verification"
```

**Expected**: Should show:
- Tool versions (nuclei, httpx, ffuf, dalfox, nmap, sslscan, sqlmap)
- Wordlists directory verification
- "Tool Verification Complete"

---

### 5. Verify Runner Database Connection

```bash
fly ssh console -a thandev-runner
python3 -c "
import os
from sqlalchemy import create_engine, text
db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✅ Database connected')
"
exit
```

**Expected**: `✅ Database connected`

---

### 6. End-to-End Scan Test

1. **Trigger a scan from UI** (or use API):
   ```bash
   # Use an allowlisted domain or verified project
   curl -X POST https://thandev-backend.fly.dev/api/scans \
     -H "Content-Type: application/json" \
     -H "X-Thandev-User-Id: <your-user-id>" \
     -H "X-Thandev-Tenant-Id: <your-tenant-id>" \
     -d '{"project_id":"<project-id>","scan_level":"basic"}'
   ```

2. **Watch logs in parallel:**
   ```bash
   # Terminal 1: Backend logs
   fly logs -a thandev-backend
   
   # Terminal 2: Runner logs
   fly logs -a thandev-runner
   
   # Terminal 3: Brain logs (if brain is used)
   fly logs -a thandev-brain
   ```

3. **Expected flow:**
   - Backend logs: Scan created, steps published to Redis
   - Runner logs: Tool version checks, consuming from Redis stream, executing tools
   - Brain logs: (if enabled) Planning requests, RAG queries

---

## TROUBLESHOOTING

### Redis TLS Issues

**Symptom**: Connection refused or SSL errors

**Solution**: If Upstash gives `rediss://`, all services already support TLS. Verify:
- `REDIS_URL` starts with `rediss://` (double 's')
- Services are using the latest code (TLS support is already implemented)

---

### .internal DNS Not Resolving

**Symptom**: Connection refused when accessing `*.internal` addresses

**Causes**:
- Apps are in different regions (must all be `iad`)
- Apps are in different orgs (must all be `personal`)

**Solution**:
```bash
# Verify all apps are in same region
fly status -a thandev-backend | grep REGION
fly status -a thandev-brain | grep REGION
fly status -a thandev-qdrant | grep REGION

# All should show: REGION = iad

# Verify all apps are in same org
fly apps list | grep thandev
# All should show: OWNER = personal
```

---

### Runner Missing Tools/Wordlists

**Symptom**: Runner fails on startup with "tool not found" or "wordlists directory not found"

**Solution**:
1. Check Dockerfile copied wordlists: `COPY wordlists /opt/thandev/wordlists`
2. Verify wordlists directory exists in `services/thandev-runner/wordlists`
3. Check runner logs: `fly logs -a thandev-runner`
4. Rebuild if needed: `fly deploy -a thandev-runner --remote-only`

---

### Database Connection Errors (Runner)

**Symptom**: "scan job not found" errors in runner

**Cause**: Runner using different database than backend

**Solution**:
```bash
# Get backend DATABASE_URL
fly secrets list -a thandev-backend | grep DATABASE_URL

# Set same URL for runner
fly secrets set DATABASE_URL="<SAME_NEON_URL>" -a thandev-runner

# Restart runner
fly machine restart -a thandev-runner
```

---

### Brain /healthz Returns 500

**Symptom**: Brain health check fails

**Check**:
```bash
fly logs -a thandev-brain | tail -50
```

**Common causes**:
- Qdrant not accessible (check QDRANT_URL secret)
- Redis not accessible (check REDIS_URL secret)
- Missing dependencies

---

### Qdrant Volume Issues

**Symptom**: Qdrant fails to start or loses data

**Check volume**:
```bash
fly volumes list -a thandev-qdrant
```

**Recreate volume if needed**:
```bash
fly volumes destroy <volume-id> -a thandev-qdrant
fly volumes create qdrant-data --size 10 --region iad -a thandev-qdrant
fly deploy -a thandev-qdrant --remote-only
```

---

## Quick Reference

### App Names
- `thandev-backend` - Public API service
- `thandev-qdrant` - Private vector database
- `thandev-brain` - Private AI planning service
- `thandev-runner` - Private worker service

### Internal URLs
- Brain: `http://thandev-brain.internal:8001`
- Qdrant: `http://thandev-qdrant.internal:6333`

### External URLs
- Backend: `https://thandev-backend.fly.dev`
- Frontend: (on Vercel, check Vercel dashboard)

### Region & Org
- Region: `iad`
- Org: `personal`

---

## Next Steps

After successful deployment:

1. ✅ All services running
2. ✅ Internal connectivity verified
3. ✅ Redis connections working
4. ✅ Runner consuming from Redis streams
5. ✅ End-to-end scan test successful

**System is ready for production use!**

