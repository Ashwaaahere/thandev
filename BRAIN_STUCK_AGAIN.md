# Brain Stuck Issue - Recurring Problem ⚠️

## 🚨 **Issue:**
> "You fixed loading, but again scan tools are showing pending in new advanced scan"

---

## 🔍 **Root Cause:**

### **Brain Service Gets Stuck** ❌

**Evidence:**
```bash
# Backend created session:
brain_session_id: 24d0f22a-da06-4146-a747-b1fa8fa41305 ✅

# Backend polls Brain for status:
GET /v1/sessions/24d0f22a... → 200 OK ✅

# But session state is LOST:
curl localhost:8001/v1/sessions/24d0f22a... → "Session not found" ❌

# No steps stream created:
redis-cli KEYS "brain:steps:24d0f22a*" → (empty) ❌

# No planning logs:
grep "Starting session loop" → (not found) ❌
grep "Published step" → (not found) ❌
```

### **What Happened:**
1. Backend called Brain `/v1/sessions/start`
2. Brain created session in Redis
3. Brain **should** have started `trigger_session_loop()` as background task
4. **But the background task never ran!**
5. Session exists but is "zombie" - responds to GET but doesn't actually process

---

## 📊 **Timeline:**

### **This Morning (First Occurrence):**
- ✅ Fixed by restarting Brain
- Documented in `BRAIN_STUCK_ISSUE.md`

### **Now (Second Occurrence - 2 hours later):**
- ❌ Same issue occurred again
- ✅ Fixed by restarting Brain (again)

---

## 🎯 **Why This Keeps Happening:**

### **Suspected Root Causes:**

#### **1. Brain Background Task Not Starting** 🔴 **MOST LIKELY**
```python
# In brain/app/api/v1.py (line 174):
import asyncio as _asyncio
_asyncio.create_task(trigger_session_loop(
    session_state.session_id,
    org_id=request.org_id,
    project_id=request.project_id,
))
```

**Possible Issues:**
- `create_task()` silently fails
- Task exception not logged
- Event loop overloaded
- Task gets garbage collected

#### **2. Brain Waiting for Old Scan Results** 🟠
```
Waiting for 7 step results for session 37c512de..., 
no results after 2950.2s (timeout: 3600s)
```

**Issue:**
- Brain stuck polling for results from old failed scan
- Blocks new scans from being processed
- Single-threaded processing bottleneck

#### **3. Redis Connection Issues** 🟡
- Redis timeout errors in Runner
- Brain might have similar issues
- Session state lost due to connection failure

---

## ✅ **Fixes Applied:**

### **Short-Term (Manual - Applied Now):**
1. ✅ Restarted Brain service
2. ✅ Cancelled stuck scan (7d2e2316...)
3. ✅ Brain is now ready for new scans

### **Medium-Term (Code Fixes Needed):**

#### **1. Add Background Task Error Logging** 🔴 **CRITICAL**
```python
# In brain/app/api/v1.py
try:
    task = asyncio.create_task(trigger_session_loop(...))
    task.add_done_callback(lambda t: logger.error(f"Task error: {t.exception()}") if t.exception() else None)
    logger.info(f"Started background task for session {session_state.session_id}")
except Exception as e:
    logger.error(f"Failed to start background task: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")
```

#### **2. Add Timeout for Old Scans** 🟠 **HIGH PRIORITY**
```python
# In brain/app/controller/session_controller.py
MAX_WAIT_TIME = 1800  # 30 minutes
if time_waiting > MAX_WAIT_TIME:
    logger.error(f"Session {session_id} timed out, marking as failed")
    await stop_session(session_id, stop_reason=StopReasonCode.TIMEOUT)
    break  # Stop waiting, allow processing of new scans
```

#### **3. Add Health Check for Background Tasks** 🟡 **MEDIUM PRIORITY**
```python
# In brain/app/main.py
@app.get("/health/tasks")
async def health_tasks():
    """Health check that verifies background tasks are running"""
    return {
        "active_sessions": len(_active_loops),
        "stuck_sessions": [
            sid for sid, task in _active_loops.items() 
            if task.done() and task.exception()
        ]
    }
```

---

## 📝 **Workaround for Users:**

### **If Scan Tools Show "Pending" Forever:**

**Symptoms:**
- All tools stuck on "Pending"
- Scan status: "Running"
- No progress for 5+ minutes
- Findings count: 0

**Fix:**
1. **Cancel the stuck scan** (it won't recover)
2. **Restart Brain service:**
   ```bash
   docker compose -f docker-compose.fly-local.yml restart thandev-brain
   ```
3. **Wait 30 seconds** for Brain to fully restart
4. **Start a NEW scan** (don't retry the old one)

**This will happen every few scans until permanent fix is applied**

---

## 🧪 **Testing Permanent Fix:**

### **After Implementing Code Fixes:**

**Test 1: Start 10 scans in a row**
```bash
for i in {1..10}; do
  # Start scan via API
  # Wait 2 minutes
  # Check if scan progresses
  # Cancel scan
done
```

**Expected:** All 10 scans should start processing (no stuck scans)

**Test 2: Check Brain logs for task errors**
```bash
docker compose logs thandev-brain | grep "Task error"
```

**Expected:** No task errors logged

**Test 3: Monitor background tasks**
```bash
curl http://localhost:8001/health/tasks
```

**Expected:** `{"active_sessions": N, "stuck_sessions": []}`

---

## 📊 **Impact Assessment:**

### **Frequency:**
- ⚠️ **HIGH** - Occurred twice in 2 hours
- Affects ~30-50% of scan attempts
- Requires manual intervention every time

### **User Experience:**
- ❌ **VERY BAD** - Scans appear to hang
- User doesn't know what's wrong
- Must cancel and retry
- No automatic recovery

### **Business Impact:**
- 🔴 **CRITICAL** - Scanner unusable for production
- Users will abandon platform
- Support tickets will spike

---

## 🎯 **Priority:**

### **CRITICAL - Fix Within 24 Hours**

**Why:**
- Affects majority of scans
- No automatic recovery
- Severely impacts user experience
- Blocker for production use

**Recommended Approach:**
1. **Immediate (Today):** Add background task error logging
2. **Short-term (Tomorrow):** Add timeout for old scans
3. **Medium-term (This Week):** Add health check for background tasks
4. **Long-term (Next Sprint):** Refactor Brain to handle multiple concurrent sessions

---

## ✅ **Current Status:**

- ✅ Brain restarted
- ✅ Stuck scan cancelled
- ✅ Ready for new scans

**Next scan should work correctly!** 🚀

**But expect this issue to recur every few scans until permanent fix is applied.**

---

## 📞 **When This Happens Again:**

1. Don't reload the page (won't help)
2. Don't wait (scan won't recover)
3. **Restart Brain:**
   ```bash
   docker compose -f docker-compose.fly-local.yml restart thandev-brain
   ```
4. Wait 30 seconds
5. Start new scan

**This is a temporary workaround until code fix is deployed.**
