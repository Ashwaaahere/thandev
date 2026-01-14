# Parallelism and Brain Service Fixes

## Date: January 12, 2026

## Problem Summary
1. **Dalfox** and **Nmap** tools were not executing in Pro scans
2. Tools were showing **"timed out"** despite actual execution time being less than timeout
3. Brain service was crashing with `UnboundLocalError: cannot access local variable 'logger'`

---

## Root Causes Identified

### 1. Insufficient Parallelism (FIXED ✅)
**Issue:** `SCAN_PARALLELISM` for "pro" scans was set to `max_concurrent: 3`, but Pro scans have 6 tools.

**Location:** 
- `backend/app/core/scan_timeouts.py`
- `services/thandev-brain/app/core/scan_timeouts.py` (needed to be added)

**Fix:** Increased parallelism:
```python
SCAN_PARALLELISM: Dict[str, Dict] = {
    "basic": {"max_concurrent": 3},   # Was 2 -> Now 3
    "pro": {"max_concurrent": 6},     # Was 3 -> Now 6 (all 6 Pro tools in parallel)
    "advanced": {"max_concurrent": 7} # Was 4 -> Now 7 (all 7 Advanced tools in parallel)
}
```

### 2. Execution Time Measurement Bug (FIXED ✅)
**Issue:** `run_step()` was measuring wall-clock time (including setup overhead) instead of actual subprocess execution time.

**Location:** `services/thandev-runner/app/services/tools.py`

**Fix:** Modified each tool (`_run_dalfox`, `_run_nmap`, `_run_nuclei`, `_run_sqlmap`) to return their own `execution_time` calculated around the subprocess call only:

```python
# Each tool now returns:
return {
    "tool_name": "dalfox",
    "execution_time": exec_duration,  # Accurate subprocess-only time
    # ... other fields
}
```

And updated `run_step()` to use tool-provided time:
```python
if "execution_time" not in result:
    execution_time = (datetime.utcnow() - start_time).total_seconds()
    result["execution_time"] = execution_time
```

### 3. Brain Service UnboundLocalError (FIXED ✅)
**Issue:** Brain service crashed during plan generation with:
```
UnboundLocalError: cannot access local variable 'logger' where it is not associated with a value
```

**Root Cause:** In `services/thandev-brain/app/planner/plan.py`, the `_validate_plan()` function had:
- Line 705: `logger.info(...)` - **USING logger**
- Lines 722-723: `import logging; logger = logging.getLogger(__name__)` - **DEFINING logger**

Python treats `logger` as a LOCAL variable for the entire function when it sees the assignment, causing the UnboundLocalError when trying to use it before assignment.

**Location:** `services/thandev-brain/app/planner/plan.py` lines 720-727

**Fix:** Removed duplicate logger import/assignment inside the function (logger is already imported at module level):

```python
# BEFORE (BROKEN):
if total_runtime > max_allowed_runtime:
    import logging
    logger = logging.getLogger(__name__)  # ← This caused the error!
    logger.warning(...)

# AFTER (FIXED):
if total_runtime > max_allowed_runtime:
    # Note: logger is already imported at module level
    logger.warning(...)
```

### 4. Brain Service Volume Mount (FIXED ✅)
**Issue:** Brain service code changes weren't persisting across restarts because code was baked into Docker image.

**Location:** `docker-compose.fly-local.yml`

**Fix:** Added volume mount for live development (similar to runner service):
```yaml
thandev-brain:
  build: ./services/thandev-brain
  volumes:
    # Mount app code for live development (allows code changes without rebuild)
    - ./services/thandev-brain/app:/app/app
  # ... rest of config
```

---

## Files Modified

### 1. Backend
- ✅ `backend/app/core/scan_timeouts.py` - Increased parallelism to 6 for Pro, 7 for Advanced

### 2. Runner
- ✅ `services/thandev-runner/app/services/tools.py` - Fixed execution_time measurement in `run_step()`, `_run_dalfox()`, `_run_nmap()`, `_run_nuclei()`, `_run_sqlmap()`

### 3. Brain
- ✅ `services/thandev-brain/app/core/scan_timeouts.py` - Added SCAN_PARALLELISM configuration
- ✅ `services/thandev-brain/app/planner/plan.py` - Fixed UnboundLocalError by:
  - Added `get_max_parallelism` to imports (line 14)
  - Removed duplicate logger definition inside `_validate_plan()` function (lines 722-723)
  - Function now uses module-level logger throughout

### 4. Docker Configuration
- ✅ `docker-compose.fly-local.yml` - Added volume mount for brain service

---

## Testing Results

### Test Scan (d77cb0dc) - Jan 12, 2026 7:54 PM
**Outcome:** PARTIAL SUCCESS ✅⚠️

**What Worked:**
- ✅ Brain service did NOT crash (major improvement!)
- ✅ Parallelism configuration loaded correctly: "Max parallelism for pro scan: 6 (parallel_steps: 3)"
- ✅ Tools executed and reported accurate execution times
- ✅ Httpx: 7.7s
- ✅ Sslscan: 29.7s  
- ✅ Zap (passive): 67.2s with 30 findings

**What's Still Broken:**
- ❌ Only 5 tools scheduled instead of 6 (missing nmap & dalfox)
- ❌ Nuclei stuck in "RUNNING" status (hasn't completed after 6+ minutes)
- ❌ Zap (active) stuck in "RUNNING" status (still at 12% progress)
- ❌ Scan marked "completed" while tools still running

---

## Remaining Issues

### Issue #1: Brain AI Planner Not Scheduling All Tools
The Brain's AI-based planning logic decided to schedule only 5 tools instead of 6 for a Pro scan. It created only "3 parallel steps" according to logs.

**Possible Causes:**
- Brain planner may have dependency logic that groups tools
- Brain may be conditionally excluding certain tools (nmap/dalfox) based on target analysis
- Brain may not be consulting the tool matrix properly

**Next Steps:**
- Investigate Brain planner logic to understand why it creates fewer steps than expected tools
- Check if there are conditional rules that exclude nmap/dalfox from Pro scans
- Consider whether Brain should fallback to backend's tool_matrix for tool selection

### Issue #2: Tools Not Completing / Scan Premature Completion
Tools (Nuclei, Zap) started but never completed, yet scan was marked "completed".

**Possible Causes:**
- Runner may have timeout logic that marks scan complete after first N tools finish
- Backend may be completing scan when Brain session ends, regardless of tool status
- Tool result ingestion may not be properly updating "RUNNING" → "COMPLETED" status

**Next Steps:**
- Check scan completion logic in backend
- Verify runner is properly posting completion status for all tools
- Check if Brain session is ending prematurely

---

## Verification Steps for Next Scan

To confirm all fixes are working:

1. ✅ Start new Pro scan against `https://demo.owasp-juice.shop/`
2. ✅ Check Brain logs for "Max parallelism for pro scan: 6" 
3. ⚠️ Verify 6 tools scheduled (httpx, nuclei, nmap, sslscan, dalfox, zap)
4. ⚠️ Verify all tools complete (not stuck in RUNNING)
5. ✅ Check execution_time values are accurate (subprocess-only time)
6. ⚠️ Verify scan doesn't mark "completed" until all tools finish

---

## Commands to Restart Services After Code Changes

```bash
# Backend
docker compose -f docker-compose.fly-local.yml restart backend

# Brain (with cache clear)
docker compose -f docker-compose.fly-local.yml exec thandev-brain rm -rf /app/app/__pycache__ /app/app/*/__pycache__ /app/app/*/*/__pycache__
docker compose -f docker-compose.fly-local.yml restart thandev-brain

# Runner
docker compose -f docker-compose.fly-local.yml restart thandev-runner

# Verify all healthy
docker compose -f docker-compose.fly-local.yml ps
```

---

## Notes

- The Brain service now uses volume mounts, so code changes take effect after clearing Python cache and restarting
- Backend parallelism is respected by the scan orchestrator when not using Brain
- Brain parallelism is used by Brain's AI planner for Brain-orchestrated scans
- The execution_time fix ensures accurate timing regardless of setup overhead
- All Python cache (`.pyc` files) must be cleared after code changes to ensure new code is loaded
