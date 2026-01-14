# Fly.io Secrets Verification Report

## ✅ **Secrets Status Check**

Based on your terminal output, here's the analysis of your Fly.io secrets:

---

## 📋 **Backend Secrets (thandev-backend)**

### ✅ **Present Secrets:**
- `DATABASE_URL` ✅ (Neon PostgreSQL)
- `REDIS_URL` ✅ (Upstash Redis)
- `BRAIN_URL` ✅
- `BRAIN_SERVICE_URL` ✅
- `RUNNER_API_TOKEN` ✅
- `BACKEND_URL` ✅
- `CORS_ORIGINS` ✅
- `CORS_ALLOW_ORIGINS` ✅
- `CALLBACK_SECRET` ✅
- `THANDEV_SUPERADMIN_EXTERNAL_IDS` ✅
- `THANDEV_SETUP_TOKEN` ✅
- `SELF_SERVICE_SIGNUP_ENABLED` ✅
- `INTERNAL_ENDPOINT_REQUIRE_PRIVATE_NETWORK` ✅

### ⚠️ **Critical Values to Verify:**

**BRAIN_URL & BRAIN_SERVICE_URL:**
- **Should be:** `http://thandev-brain.internal:8001`
- **NOT:** `http://thandev-brain.flycast:8001` (old format)
- **NOT:** `https://thandev-brain.fly.dev` (public URL - won't work for internal networking)

**Why:** Fly.io uses `.internal` DNS for private networking between services.

---

## 📋 **Brain Secrets (thandev-brain)**

### ✅ **Present Secrets:**
- `REDIS_URL` ✅ (Upstash Redis - same as backend)
- `QDRANT_URL` ✅
- `CORE_BACKEND_URL` ✅
- `EMBEDDING_PROVIDER` ✅
- `QDRANT_COLLECTION` ✅

### ⚠️ **Critical Values to Verify:**

**QDRANT_URL:**
- **Should be:** `http://thandev-qdrant.internal:6333`
- **NOT:** `http://thandev-qdrant.flycast:6333` (old format)
- **NOT:** `https://thandev-qdrant.fly.dev` (public URL)

**CORE_BACKEND_URL:**
- **Should be:** `http://thandev-backend.internal:8000` OR `https://thandev-backend.fly.dev`
- **Note:** Brain needs to call backend APIs, so this can be either internal or public URL
- **Recommended:** Use `.internal` for better performance and security

**EMBEDDING_PROVIDER:**
- **Should be:** `sentence_transformers` (default, no API key needed)
- **OR:** `openai` (requires `OPENAI_API_KEY` secret)

---

## 📋 **Runner Secrets (thandev-runner)**

### ✅ **Present Secrets:**
- `DATABASE_URL` ✅ (Must match backend's DATABASE_URL exactly!)
- `REDIS_URL` ✅ (Must match backend's REDIS_URL exactly!)
- `BACKEND_URL` ✅
- `RUNNER_API_TOKEN` ✅ (Must match backend's RUNNER_API_TOKEN exactly!)
- `WORDLISTS_DIR` ✅

### ⚠️ **Critical Values to Verify:**

**DATABASE_URL:**
- **CRITICAL:** Must be **identical** to backend's `DATABASE_URL`
- Both services share the same database
- **Check:** Both should have digest `6e8a522983800e6c` ✅ (matches!)

**REDIS_URL:**
- **CRITICAL:** Must be **identical** to backend's `REDIS_URL`
- Both services share the same Redis instance
- **Check:** Both should have digest `9c91b271ea26b68c` ✅ (matches!)

**RUNNER_API_TOKEN:**
- **CRITICAL:** Must be **identical** to backend's `RUNNER_API_TOKEN`
- Used for authentication between backend and runner
- **Check:** Both should have digest `a4e7d78896c0ad9d` ✅ (matches!)

**BACKEND_URL:**
- **Should be:** `http://thandev-backend.internal:8000` OR `https://thandev-backend.fly.dev`
- **Recommended:** Use `.internal` for better performance

---

## 🔍 **Verification Commands**

### **1. Check Actual Secret Values:**

```bash
# Backend - Check BRAIN_URL value
fly ssh console -a thandev-backend -C "echo \$BRAIN_URL"

# Brain - Check QDRANT_URL value
fly ssh console -a thandev-brain -C "echo \$QDRANT_URL"

# Brain - Check CORE_BACKEND_URL value
fly ssh console -a thandev-brain -C "echo \$CORE_BACKEND_URL"

# Runner - Check BACKEND_URL value
fly ssh console -a thandev-runner -C "echo \$BACKEND_URL"
```

### **2. Verify Internal DNS Connectivity:**

```bash
# Test Backend → Brain
fly ssh console -a thandev-backend -C "curl -sS http://thandev-brain.internal:8001/healthz"

# Test Brain → Qdrant
fly ssh console -a thandev-brain -C "curl -sS http://thandev-qdrant.internal:6333/collections"

# Test Runner → Backend
fly ssh console -a thandev-runner -C "curl -sS http://thandev-backend.internal:8000/healthz"
```

---

## ⚠️ **Potential Issues**

### **Issue 1: Using `.flycast` Instead of `.internal`**

**Symptom:** Services can't communicate internally

**Fix:**
```bash
# Update backend
fly secrets set \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  BRAIN_SERVICE_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend

# Update brain
fly secrets set \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  CORE_BACKEND_URL="http://thandev-backend.internal:8000" \
  -a thandev-brain

# Update runner
fly secrets set \
  BACKEND_URL="http://thandev-backend.internal:8000" \
  -a thandev-runner
```

---

### **Issue 2: Missing RAG_STORE_TYPE in Brain**

**Check if needed:**
```bash
fly secrets list -a thandev-brain | grep RAG_STORE_TYPE
```

**If missing, add:**
```bash
fly secrets set RAG_STORE_TYPE="qdrant" -a thandev-brain
```

**Note:** Code defaults to `qdrant`, but explicit is better.

---

### **Issue 3: DATABASE_URL Mismatch**

**Critical:** Backend and Runner must use the **exact same** DATABASE_URL.

**Verify:**
```bash
# Get backend DATABASE_URL digest
fly secrets list -a thandev-backend | grep DATABASE_URL

# Get runner DATABASE_URL digest
fly secrets list -a thandev-runner | grep DATABASE_URL

# They should match! ✅ (Your digests match: 6e8a522983800e6c)
```

---

## ✅ **Summary**

### **What Looks Good:**
1. ✅ All required secrets are present
2. ✅ DATABASE_URL matches between backend and runner
3. ✅ REDIS_URL matches between backend, brain, and runner
4. ✅ RUNNER_API_TOKEN matches between backend and runner

### **What to Verify:**
1. ⚠️ **BRAIN_URL** should use `.internal` DNS (not `.flycast`)
2. ⚠️ **QDRANT_URL** should use `.internal` DNS (not `.flycast`)
3. ⚠️ **CORE_BACKEND_URL** should use `.internal` DNS (recommended)
4. ⚠️ **BACKEND_URL** (runner) should use `.internal` DNS (recommended)
5. ⚠️ **RAG_STORE_TYPE** should be explicitly set in brain (optional but recommended)

---

## 🚀 **Next Steps**

1. **Run verification commands** above to check actual values
2. **Test internal connectivity** using curl commands
3. **Update secrets if needed** using `fly secrets set` commands
4. **Redeploy services** after updating secrets (secrets take effect immediately, but restarting ensures clean state)

---

## 📝 **Quick Fix Script**

If you need to update all internal URLs to use `.internal` DNS:

```bash
#!/bin/bash

# Backend
fly secrets set \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  BRAIN_SERVICE_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend

# Brain
fly secrets set \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  CORE_BACKEND_URL="http://thandev-backend.internal:8000" \
  RAG_STORE_TYPE="qdrant" \
  -a thandev-brain

# Runner
fly secrets set \
  BACKEND_URL="http://thandev-backend.internal:8000" \
  -a thandev-runner

echo "✅ Secrets updated! Services will pick up changes on next request/restart."
```

---

**Your secrets configuration looks mostly correct!** Just verify the internal DNS URLs are using `.internal` instead of `.flycast`.
