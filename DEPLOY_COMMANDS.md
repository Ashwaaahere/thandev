# Quick Deployment Commands

**Copy-paste these commands in order.** Replace `<REDIS_URL>` and `<DATABASE_URL>` with actual values.

---

## 1. Create Redis (Upstash)

```bash
fly redis create --region iad --name thandev-redis
# ⚠️ COPY THE REDIS_URL FROM OUTPUT - you'll need it below!
# It will look like: redis://default:XXXXX@XXX.upstash.io:6379
# OR: rediss://default:XXXXX@XXX.upstash.io:6379 (TLS enabled)
```

**Save this URL as `REDIS_URL` for all services below.**

---

## 2. Deploy Qdrant

```bash
cd services/qdrant-fly
fly apps create thandev-qdrant --org personal --region iad 2>&1 | grep -v "already exists" || true
fly volumes create qdrant-data --size 10 --region iad -a thandev-qdrant
fly deploy -a thandev-qdrant --remote-only
cd ../..
```

---

## 3. Deploy Brain

```bash
cd services/thandev-brain
fly apps create thandev-brain --org personal --region iad 2>&1 | grep -v "already exists" || true
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  RAG_STORE_TYPE="qdrant" \
  EMBEDDING_PROVIDER="sentence_transformers" \
  -a thandev-brain
fly deploy -a thandev-brain --remote-only
cd ../..
```

---

## 4. Deploy Runner

First, get the DATABASE_URL from backend:
```bash
fly secrets list -a thandev-backend | grep DATABASE_URL
```

Then deploy runner:
```bash
cd services/thandev-runner
fly apps create thandev-runner --org personal --region iad 2>&1 | grep -v "already exists" || true
fly secrets set \
  DATABASE_URL="<DATABASE_URL_FROM_BACKEND>" \
  REDIS_URL="<REDIS_URL>" \
  WORDLISTS_DIR="/opt/thandev/wordlists" \
  -a thandev-runner
fly deploy -a thandev-runner --remote-only
cd ../..
```

---

## 5. Update Backend Secrets

```bash
cd backend
fly secrets set \
  REDIS_URL="<REDIS_URL>" \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend
cd ..
```

---

## 6. Verify (Quick Check)

```bash
# Check all apps are running
fly status -a thandev-backend
fly status -a thandev-qdrant
fly status -a thandev-brain
fly status -a thandev-runner

# Check backend → brain connectivity
fly ssh console -a thandev-backend -C "python3 -c \"import httpx; r = httpx.get('http://thandev-brain.internal:8001/healthz', timeout=5); print(r.json())\""

# Check runner logs (should show tool verification)
fly logs -a thandev-runner | head -100
```

---

## Secrets Summary

| Service | Secret | Value |
|---------|--------|-------|
| thandev-backend | DATABASE_URL | Neon URL (already set) |
| thandev-backend | REDIS_URL | From Step 1 |
| thandev-backend | BRAIN_URL | `http://thandev-brain.internal:8001` |
| thandev-brain | REDIS_URL | From Step 1 |
| thandev-brain | QDRANT_URL | `http://thandev-qdrant.internal:6333` |
| thandev-brain | RAG_STORE_TYPE | `qdrant` |
| thandev-brain | EMBEDDING_PROVIDER | `sentence_transformers` |
| thandev-runner | DATABASE_URL | **Same as backend** (CRITICAL!) |
| thandev-runner | REDIS_URL | From Step 1 |
| thandev-runner | WORDLISTS_DIR | `/opt/thandev/wordlists` |

---

For detailed troubleshooting and verification steps, see `FLY_DEPLOYMENT_GUIDE.md`.

