# Fixes Applied - Scan Tool Execution Issues

**Date:** 2026-01-12  
**Issues Fixed:** Dalfox not running for Pro scans + execution_time measurement bug

---

## 🐛 Issues Identified

### Issue 1: Dalfox Not Running for Pro Scans
**Problem:** Dalfox was configured to run for Pro scans but wasn't executing due to concurrency limits.

- **Root Cause:** `max_concurrent = 3` for Pro scans, but 6 tools were scheduled (httpx, nuclei, nmap, sslscan, dalfox, zap)
- **Impact:** Dalfox and potentially other tools would be queued but scan would complete before they ran

### Issue 2: Execution Time Measurement Bug
**Problem:** Tools showed "timed out" even though they ran for less time than the configured timeout.

- **Root Cause:** `run_step()` was overwriting accurate subprocess-only timing with wall-clock time that included 60-160 seconds of setup overhead (parameter harvesting, crawler, etc.)
- **Example:**
  - Dalfox subprocess ran for 839s (wall clock) with 900s timeout
  - But execution_time was calculated from start of `run_step()` (included 68s overhead)
  - Made it appear like timeout triggered early when it actually ran the full duration
- **Impact:** Confusing timeout reporting and inaccurate performance metrics

---

## ✅ Fixes Applied

### Fix 1: Increased Scan Parallelism

**File:** `/home/ashwath/thandev/backend/app/core/scan_timeouts.py`

**Changes:**
```python
SCAN_PARALLELISM: Dict[str, Dict] = {
    "basic": {
        "max_concurrent": 3,  # Was 2 → Now 3
    },
    "pro": {
        "max_concurrent": 6,  # Was 3 → Now 6 (all Pro tools can run in parallel)
    },
    "advanced": {
        "max_concurrent": 7,  # Was 4 → Now 7 (all Advanced tools can run in parallel)
    }
}
```

**Why:** Ensures all scheduled tools can run in parallel instead of being queued and potentially skipped.

---

### Fix 2: Fixed execution_time Measurement

**Files Modified:**
- `/home/ashwath/thandev/services/thandev-runner/app/services/tools.py`

**Changes:**

#### 2a. Modified `run_step()` to not overwrite tool-provided execution_time
```python
# Before: Always overwrote execution_time
execution_time = (datetime.utcnow() - start_time).total_seconds()
result["execution_time"] = execution_time

# After: Only set if tool didn't provide it
if "execution_time" not in result:
    execution_time = (datetime.utcnow() - start_time).total_seconds()
    result["execution_time"] = execution_time
```

#### 2b. Added accurate timing to all tools
Each tool now tracks and returns its actual subprocess execution time:

**Dalfox:**
```python
exec_start_time = time.time()
result = subprocess.run(cmd, ..., timeout=timeout)
exec_duration = time.time() - exec_start_time

return {
    ...
    "execution_time": exec_duration,  # Accurate subprocess-only time
}
```

**Nmap:**
```python
exec_start_time = time.time()
result = subprocess.run(cmd, ..., timeout=timeout_seconds)
exec_duration = time.time() - exec_start_time

return {
    ...
    "execution_time": exec_duration,  # Accurate subprocess-only time
}
```

**Nuclei:**
```python
exec_start_time = time.time()
result = subprocess.run(cmd, ..., timeout=timeout_seconds)
exec_duration = time.time() - exec_start_time

return {
    ...
    "execution_time": exec_duration,  # Accurate subprocess-only time
}
```

**SQLMap:**
```python
exec_start_time = time.time()
result = subprocess.run(cmd, ..., timeout=timeout)
exec_duration = time.time() - exec_start_time

return {
    ...
    "execution_time": exec_duration,  # Accurate subprocess-only time
}
```

**Why:** Provides accurate performance metrics by excluding setup overhead (parameter harvesting, crawler, etc.)

---

## 🎯 Expected Results

### Before Fixes:
- ❌ Dalfox wouldn't run for Pro scans
- ❌ Only 3 tools could run in parallel (others queued)
- ❌ execution_time included setup overhead (60-160s)
- ❌ Tools appeared to timeout early (confusing logs)

### After Fixes:
- ✅ Dalfox will run for all Pro/Advanced scans
- ✅ All tools run in parallel (no queueing)
- ✅ execution_time shows only subprocess execution (accurate)
- ✅ Timeout reporting is clear and correct

---

## 📋 How to Apply Fixes

### 1. Restart Runner Service
```bash
docker compose -f docker-compose.fly-local.yml restart thandev-runner
```

### 2. Restart Backend (for parallelism changes)
```bash
docker compose -f docker-compose.fly-local.yml restart backend
```

### 3. Verify Fixes
Run a Pro scan and verify:
- ✅ Dalfox appears in "Tools Executed"
- ✅ All tools show in the UI
- ✅ execution_time values are accurate
- ✅ No false timeout warnings

---

## 🧪 Testing

**Test Scan:**
1. Start a **Pro-level scan** on https://demo.owasp-juice.shop
2. Monitor Tools Executed section
3. Verify Dalfox shows up with proper status
4. Check execution_time values are reasonable (no 60s+ overhead)
5. Check logs for accurate timeout reporting

**Expected Tools for Pro Scan:**
- httpx
- nuclei
- nmap
- sslscan
- dalfox ← **Should now appear!**
- zap (passive + active)

---

## 📝 Notes

- **No database migration needed** - these are code-only fixes
- **No breaking changes** - backward compatible
- **Performance impact:** Minimal - more tools run in parallel but total scan time should be similar or faster
- **Resource usage:** Slightly higher CPU/memory during parallel execution (acceptable trade-off for completeness)

---

## ✨ Summary

| Fix | File | Lines Changed | Impact |
|-----|------|---------------|--------|
| Increase parallelism | `backend/app/core/scan_timeouts.py` | ~10 | Ensures all tools execute |
| Fix timing in run_step() | `services/thandev-runner/app/services/tools.py` | ~5 | Prevents overwriting accurate time |
| Add timing to dalfox | `services/thandev-runner/app/services/tools.py` | ~10 | Accurate subprocess time |
| Add timing to nmap | `services/thandev-runner/app/services/tools.py` | ~12 | Accurate subprocess time |
| Add timing to nuclei | `services/thandev-runner/app/services/tools.py` | ~8 | Accurate subprocess time |
| Add timing to sqlmap | `services/thandev-runner/app/services/tools.py` | ~15 | Accurate subprocess time |

**Total:** ~60 lines changed across 2 files

All fixes applied successfully! 🎉
