# Fixes Completed

## Issue 1: Indentation Error in Runner ✅ FIXED

**Problem:** Runner was crashing due to indentation error in `tasks.py` line 397.

**Fix:** Fixed indentation for `tool_run_id = str(uuid.uuid4())` to be properly indented inside the `if not tool_run_id:` block.

**Status:** ✅ Fixed and deployed successfully

---

## Issue 2: Endpoint Path Changed ✅ DEPLOYED

**Problem:** Fly.io proxy was blocking `/api/internal/*` endpoints before requests reached FastAPI.

**Solution:** Moved runner endpoint from `/api/internal/` to `/api/runner/`.

**Changes:**
- Backend: Router prefix changed to `/api/runner`
- Runner: Endpoint URL updated to use `/api/runner/scans/.../tool-results`

**Status:** 
- ✅ Backend deployed
- ✅ Runner deployed (with indentation fix)
- ⏳ Testing pending

---

## Next Steps

1. Test the new endpoint from runner to backend
2. Verify backend receives POST requests
3. Confirm tool results are being ingested correctly

## Test Command

Once runner is running, start a scan and monitor logs:
- `fly logs -a thandev-runner` - Check runner logs
- `fly logs -a thandev-backend` - Check for incoming POST requests to `/api/runner/...`

Expected: Backend should now receive and log POST requests successfully.

