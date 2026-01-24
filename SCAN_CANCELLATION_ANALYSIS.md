# Scan Cancellation Flow Analysis

## Current State

### ✅ What Works

1. **UI → Backend**
   - Frontend sends `PATCH /api/scans/{scan_id}/cancel`
   - Backend updates DB status to `CANCELLED`
   - Backend tries to stop brain session (if exists)
   - Backend commits the status change

2. **Backend → DB**
   - Scan status is updated to `CANCELLED` in database
   - `error_message` is set to "Cancelled by user"
   - Completion time is recorded

3. **Runner → Backend (Status Check)**
   - Runner checks scan status before executing each NEW step
   - If status is `cancelled`, runner skips the step
   - Code location: `services/thandev-runner/app/tasks.py:195-214`

### ❌ What's Broken

1. **Long-Running Tools Don't Check Cancellation**
   - **ZAP scans** can run for 5-40+ minutes
   - **Spider polling loop** (lines 2689-2720) - NO cancellation check
   - **Active scan polling loop** (lines 3121-3165) - NO cancellation check
   - **Other tool loops** (Nuclei, SQLMap, Nmap) - NO cancellation check

2. **ZAP Process Not Stopped**
   - When scan is cancelled, ZAP continues:
     - Spider keeps crawling
     - Active scan keeps testing
     - Proxy keeps recording traffic
   - No API call to stop ZAP scans
   - ZAP container keeps running until tool timeout

3. **Brain Session Stop May Fail**
   - Backend calls `brain_client.stop_session()` but doesn't verify success
   - If brain session is controlling the runner steps, they may continue

## Impact

- **Wasted Resources**: Cancelled scans continue consuming CPU/memory/network
- **False Sense of Control**: User thinks scan stopped, but it's still running
- **Cost**: In cloud deployments, cancelled scans still incur compute costs
- **UX**: User has to wait for timeout instead of immediate cancellation

## Proposed Fixes

### 1. Add Cancellation Checks in Tool Polling Loops

**Location**: `services/thandev-runner/app/services/tools.py`

**For ZAP Spider (line ~2689)**:
```python
while True:
    # CHECK FOR CANCELLATION
    if scan_job_id:
        status_payload = await get_scan_status(scan_job_id)
        if status_payload and status_payload.get("status") in {"cancelled", "failed"}:
            logger.info(f"Scan {scan_job_id} was cancelled, stopping ZAP spider {spider_id}")
            try:
                # Stop the spider
                await asyncio.to_thread(
                    http_session.get,
                    f"{zap_api_url}/JSON/spider/action/stop/?scanId={spider_id}&apikey=",
                    timeout=10
                )
            except Exception as e:
                logger.warning(f"Failed to stop ZAP spider: {e}")
            raise InterruptedError(f"Scan {scan_job_id} was cancelled")
    
    # Existing status check code...
```

**For ZAP Active Scan (line ~3121)**:
```python
while True:
    poll_count += 1
    
    # CHECK FOR CANCELLATION
    if scan_job_id:
        status_payload = await get_scan_status(scan_job_id)
        if status_payload and status_payload.get("status") in {"cancelled", "failed"}:
            logger.info(f"Scan {scan_job_id} was cancelled, stopping ZAP active scan {active_scan_id}")
            try:
                # Stop the active scan
                await asyncio.to_thread(
                    http_session.get,
                    f"{zap_api_url}/JSON/ascan/action/stop/?scanId={active_scan_id}&apikey=",
                    timeout=10
                )
            except Exception as e:
                logger.warning(f"Failed to stop ZAP active scan: {e}")
            raise InterruptedError(f"Scan {scan_job_id} was cancelled")
    
    # Existing status check code...
```

**For Nuclei, SQLMap, Nmap, etc.**:
- Add similar checks in any polling/waiting loops
- If using `subprocess.run()`, use `subprocess.Popen()` instead and periodically check status
- Kill subprocess if scan is cancelled

### 2. Add ZAP Scan Stop API Calls

**ZAP API endpoints to use**:
- **Stop spider**: `GET /JSON/spider/action/stop/?scanId={scanId}&apikey=`
- **Stop active scan**: `GET /JSON/ascan/action/stop/?scanId={scanId}&apikey=`
- **Stop AJAX spider**: `GET /JSON/ajaxSpider/action/stop/&apikey=`

### 3. Optimize Status Check Frequency

**Current**: Status is checked only BEFORE each step starts
**Proposed**: Check status periodically during long-running operations

**Implementation**:
- Create a helper function: `async def check_if_cancelled(scan_job_id: str) -> bool`
- Call this in polling loops every 10-30 seconds
- Use a cache with short TTL (10s) to avoid excessive API calls

### 4. Handle Brain Session Cancellation

**In backend**: `backend/app/api/scans.py:2396-2457`
- Already calls `brain_client.stop_session()`
- Add verification and logging
- Consider retrying if first stop attempt fails

### 5. Update Frontend UX

**Current**: Shows "Scan cancelled successfully" immediately
**Proposed**: 
- Show "Cancelling scan..." spinner
- Poll scan status until it's actually stopped
- Show "Scan cancelled" only after confirmation
- Add timeout (30s) and fallback message

## Testing Plan

1. **Basic Cancellation**
   - Start a ZAP scan
   - Cancel after 10 seconds
   - Verify: DB status = CANCELLED, ZAP scan stopped, alerts not generated

2. **Mid-Spider Cancellation**
   - Start a scan with deep spidering (depth=10)
   - Cancel while spider is at 50%
   - Verify: Spider stops immediately, no new URLs discovered

3. **Mid-Active-Scan Cancellation**
   - Start an active scan (long timeout)
   - Cancel while active scan is running
   - Verify: Active scan stops, no new alerts generated

4. **Multi-Tool Cancellation**
   - Start a PRO scan (Nuclei + ZAP + Nmap)
   - Cancel while first tool is running
   - Verify: Current tool stops, subsequent tools never start

5. **Already-Completed Cancellation**
   - Try to cancel a completed scan
   - Verify: Backend returns 400 error with clear message

## Priority

**P0 (Critical)**: 
- Add cancellation checks in ZAP spider loop
- Add cancellation checks in ZAP active scan loop
- Call ZAP stop APIs

**P1 (High)**:
- Add cancellation checks in other tools (Nuclei, SQLMap)
- Optimize status check caching
- Update frontend UX

**P2 (Medium)**:
- Handle subprocess cancellation for tools using `subprocess`
- Add monitoring/metrics for cancellation success rate

## Estimated Effort

- **Backend fixes**: 2-3 hours (add checks, ZAP stop APIs)
- **Runner fixes**: 3-4 hours (update all tool loops)
- **Frontend fixes**: 1 hour (improve UX)
- **Testing**: 2-3 hours (manual + automated tests)
- **Total**: ~8-11 hours

## Acceptance Criteria

✅ When user clicks "Cancel Scan":
1. Backend updates DB status to CANCELLED within 1 second
2. Runner detects cancellation within 30 seconds
3. ZAP spider/active scan stops within 30 seconds
4. No new findings are generated after cancellation
5. Resources (CPU/memory) are released within 1 minute
6. UI shows accurate cancellation status

---

**Status**: ANALYSIS COMPLETE
**Next Steps**: Implement P0 fixes

