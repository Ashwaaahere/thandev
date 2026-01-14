# 🔴 Scan Pending - Root Cause Analysis

## **Problem Summary**

All scans are stuck in `PENDING` status with tools showing "0/6 checks completed • 6 queued" after deployment to Fly.io.

---

## **Root Cause: Internal DNS Not Working in Fly.io**

### **Why It Worked Locally But Not in Deployment:**

**Local Environment:**
- ✅ All services run in Docker Compose on the same network
- ✅ Services can communicate via service names (e.g., `http://backend:8000`)
- ✅ No DNS resolution needed - Docker handles networking

**Fly.io Deployment:**
- ❌ Services run on separate machines/VMs
- ❌ Services need `.internal` DNS to communicate
- ❌ Internal DNS requires proper Fly.io configuration
- ❌ Connection timeouts suggest DNS isn't resolving

---

## **Issues Identified**

### **1. Backend Not Calling Brain Service** ❌

**Evidence:**
- No logs showing "Starting brain session for scan_job..."
- No logs showing "Failed to start brain session..."
- Scans created but `brain_session_id` is NULL

**Root Cause:**
- Backend tries to call brain at `http://thandev-brain.internal:8001`
- Connection fails silently (exception caught but not logged properly)
- Fallback to runner publishing also fails silently

### **2. Runner Cannot Connect to Backend** ❌

**Evidence:**
```
Network error during tool result POST (attempt 1/5): All connection attempts failed
Network error during tool result POST after 5 attempts: All connection attempts failed
```

**Root Cause:**
- Runner tries to POST results to `http://thandev-backend.internal:8000`
- DNS resolution fails or connection refused
- Tools complete but results never reach backend

### **3. No Step Requests Published** ❌

**Evidence:**
- No brain session = no step requests published to Redis
- Runner has nothing to consume
- Tools stay in PENDING state

---

## **Fixes Applied**

### **1. Added Internal Service Configuration to Backend**

**File:** `backend/fly.toml`

Added `[[services]]` section to enable `.internal` DNS access:

```toml
# Internal service for .internal DNS access
[[services]]
  protocol = "tcp"
  internal_port = 8000
  processes = ["app"]
  
  [[services.ports]]
    handlers = ["http"]
    port = 8000
```

**Why:** Backend needs to be accessible via `.internal` DNS for runner to connect.

---

### **2. Increased Connection Timeouts**

**Files:**
- `services/thandev-runner/app/backend_client.py`
- `backend/app/services/brain_client.py`

**Changes:**
- Added explicit `connect_timeout=10.0` seconds
- Increased total timeout handling
- Better error logging with endpoint URLs

**Why:** Internal DNS resolution can take longer, and connection attempts were timing out too quickly.

---

### **3. Enhanced Error Logging**

**File:** `backend/app/api/scans.py`

**Changes:**
- Added `[BRAIN-SESSION-FAILED]` prefix to error logs
- Log full connection details (URLs, error types)
- Log when fallback path is used

**Why:** Need visibility into why brain calls are failing.

---

## **Why It Worked Locally**

### **Local Docker Compose:**

```yaml
services:
  backend:
    networks: [thandev-network]
  brain:
    networks: [thandev-network]
  runner:
    networks: [thandev-network]
```

**Result:**
- All services on same Docker network
- Can use service names directly: `http://backend:8000`
- No DNS resolution needed
- Instant connectivity

### **Fly.io Deployment:**

```
Backend:  Machine A (public IP + private IPv6)
Brain:    Machine B (private IPv6 only)
Runner:   Machine C (private IPv6 only)
```

**Problem:**
- Services on different machines
- Need `.internal` DNS to resolve to private IPv6 addresses
- DNS resolution failing or timing out
- Connection attempts fail

---

## **Deployment Fixes**

### **1. Redeploy Backend with Internal Service**

```bash
cd backend
fly deploy --remote-only --app thandev-backend
```

This adds the `[[services]]` section for internal access.

### **2. Verify Secrets**

```bash
# Backend
fly secrets list -a thandev-backend | grep BRAIN

# Runner  
fly secrets list -a thandev-runner | grep BACKEND
```

Should show:
- `BRAIN_URL=http://thandev-brain.internal:8001`
- `BACKEND_URL=http://thandev-backend.internal:8000`

### **3. Test Internal Connectivity**

After redeploy, test from within machines:

```bash
# From backend machine
fly ssh console -a thandev-backend
curl http://thandev-brain.internal:8001/healthz

# From runner machine
fly ssh console -a thandev-runner  
curl http://thandev-backend.internal:8000/healthz
```

---

## **Alternative: Use Public URLs (Temporary Workaround)**

If `.internal` DNS still doesn't work, use public URLs temporarily:

```bash
# Backend → Brain (use public URL)
fly secrets set BRAIN_URL="https://thandev-brain.fly.dev" -a thandev-backend

# Runner → Backend (use public URL)
fly secrets set BACKEND_URL="https://thandev-backend.fly.dev" -a thandev-runner
```

**Note:** This is less secure but will work for testing.

---

## **Expected Behavior After Fix**

1. **Backend creates scan** → Logs "Starting brain session..."
2. **Brain creates session** → Logs "Created session {id}..."
3. **Brain publishes steps** → Logs "Published step request..."
4. **Runner consumes steps** → Logs "Processing step..."
5. **Runner POSTs results** → Logs "Posted tool result..." (SUCCESS)
6. **Scan progresses** → Tools transition PENDING → RUNNING → COMPLETED

---

## **Next Steps**

1. **Commit and push fixes:**
   ```bash
   git add backend/fly.toml services/thandev-runner/app/backend_client.py backend/app/services/brain_client.py backend/app/api/scans.py
   git commit -m "fix: Add internal service config and increase connection timeouts for Fly.io deployment"
   git push origin main
   ```

2. **Redeploy services:**
   ```bash
   cd backend && fly deploy --remote-only --app thandev-backend
   cd ../services/thandev-runner && fly deploy --remote-only --app thandev-runner
   ```

3. **Monitor logs:**
   ```bash
   fly logs -a thandev-backend | grep -i "brain\|session"
   fly logs -a thandev-runner | grep -i "POST\|connection"
   ```

4. **Test new scan** and verify tools start executing.

---

**Status:** 🔴 **FIXES APPLIED - READY TO DEPLOY**

**Root Cause:** Internal DNS (`.internal`) not working in Fly.io deployment

**Solution:** Added internal service config + increased timeouts + better logging
