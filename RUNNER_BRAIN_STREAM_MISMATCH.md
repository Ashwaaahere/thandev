# Runner ↔ Brain Stream Mismatch Issue

## Date: January 12, 2026, 8:10 PM

## Problem Summary

**Brain Tool Matrix Fix WORKED** ✅ - All 7 tools are now scheduled for Pro scans!

But **tools are not executing** ❌ because:
- **Brain writes to:** `brain:steps:{session_id}` (e.g., `brain:steps:0b03186a-ce3c-409f-b458-74a16964be95`)
- **Runner polls from:** `scan_step_requests` (global stream)

**Result:** Runner never sees the tasks Brain enqueues!

---

## Evidence

### 1. Brain Successfully Enqueued All 7 Tools

```
2026-01-13 01:05:50,269 - app.planner.plan - INFO - Building plan for pro scan with 7 required tools
2026-01-13 01:05:50,272 - app.planner.plan - INFO - Generated 7 steps for pro scan
2026-01-13 01:05:50,320 - app.planner.plan - INFO - Max parallelism for pro scan: 6 (parallel_steps: 5)
2026-01-13 01:05:50,322 - app.controller.session_controller - INFO - Enqueued step 06044fa3-090b-4917-96b1-4864a62d439d (httpx/medium) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,322 - app.controller.session_controller - INFO - Enqueued step 8127ae2b-ce89-43a4-a834-7e58666558d3 (nuclei/pro_web) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,323 - app.controller.session_controller - INFO - Enqueued step 2b4d63b2-525a-4677-93e6-cc6d5bb06cc0 (nmap/top_ports) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,323 - app.controller.session_controller - INFO - Enqueued step d2e7c166-d66a-421b-8069-62ad35f2b085 (sslscan/standard) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,324 - app.controller.session_controller - INFO - Enqueued step bad8db2f-a80e-49b2-974b-51e89c8945a9 (dalfox/standard) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,324 - app.controller.session_controller - INFO - Enqueued step 437b6e77-0549-476e-a263-349058dbe377 (zap/passive_spider) for session 0b03186a-ce3c-409f-b458-74a16964be95
2026-01-13 01:05:50,325 - app.controller.session_controller - INFO - Enqueued step b782698a-fbde-41b7-9a94-59131e505532 (zap/active_scan) for session 0b03186a-ce3c-409f-b458-74a16964be95
```

### 2. Brain Wrote to Session-Specific Stream

```
2026-01-13 01:05:50,322 - app.queue.streams - INFO - Published step request 8127ae2b-ce89-43a4-a834-7e58666558d3 for session 0b03186a-ce3c-409f-b458-74a16964be95 (message_id: 1768266350322-0)
2026-01-13 01:05:50,322 - app.queue.streams - INFO - Published step request 2b4d63b2-525a-4677-93e6-cc6d5bb06cc0 for session 0b03186a-ce3c-409f-b458-74a16964be95 (message_id: 1768266350322-1)
... (5 more published steps)
```

### 3. Redis Stream Status

```bash
$ redis-cli XLEN brain:steps:0b03186a-ce3c-409f-b458-74a16964be95
0

$ redis-cli XINFO STREAM brain:steps:0b03186a-ce3c-409f-b458-74a16964be95
ERR no such key
```

**Stream was created, consumed, and deleted** - but no tool execution happened!

### 4. Runner Configuration

File: `services/thandev-runner/app/queue/streams.py:75`

```python
# Reuse stream names from brain service
STREAM_STEP_REQUESTS = "scan_step_requests"  # ← WRONG!
STREAM_STEP_RESULTS = "scan_step_results"
```

Runner polls from `"scan_step_requests"` but Brain writes to `"brain:steps:{session_id}"`.

---

## Root Cause

The system has **two different architectures** that aren't properly integrated:

### OLD Architecture (Pre-Brain):
- Backend writes scan tasks → `scan_step_requests` (global stream)
- Runner polls from → `scan_step_requests`
- Runner writes results → `scan_step_results`

### NEW Architecture (with Brain):
- Brain writes scan steps → `brain:steps:{session_id}` (session-specific streams)
- Brain reads results from → `brain:results:{session_id}`
- Runner polls from → ??? (MISMATCH!)

The Runner was never updated to support Brain's session-specific streams!

---

## Solution Options

### Option 1: Make Brain Write to Global Stream (WRONG)
- Change Brain to write to `scan_step_requests` instead of `brain:steps:{session_id}`
- ❌ Breaks session isolation
- ❌ Multiple scans would interfere with each other
- ❌ Can't track which steps belong to which session

### Option 2: Update Runner to Poll from Brain Streams (CORRECT) ✅
- Runner needs to discover active Brain sessions
- Poll from all active `brain:steps:{session_id}` streams
- Write results back to `brain:results:{session_id}` streams
- ✅ Maintains session isolation
- ✅ Proper closed-loop architecture
- ✅ Scalable to multiple concurrent sessions

### Option 3: Create a Bridge Service (COMPLEX)
- New service that reads from Brain streams and writes to Runner streams
- ❌ Adds unnecessary complexity
- ❌ Extra point of failure

---

## Implementation Plan (Option 2)

### 1. Update Runner Stream Configuration

**File:** `services/thandev-runner/app/queue/streams.py`

```python
# Add support for Brain session-specific streams
def get_brain_session_stream(session_id: str) -> str:
    """Get the Brain step request stream name for a session"""
    return f"brain:steps:{session_id}"

def get_brain_result_stream(session_id: str) -> str:
    """Get the Brain step result stream name for a session"""
    return f"brain:results:{session_id}"
```

### 2. Create Multi-Stream Polling Function

**New function in:** `services/thandev-runner/app/queue/streams.py`

```python
async def consume_brain_session_steps(
    sessions: List[str],
    consumer_group: str,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Consume steps from multiple Brain session streams.
    
    Args:
        sessions: List of session IDs to poll
        consumer_group: Consumer group name
        consumer_name: Consumer name (unique per worker)
        count: Max messages per stream
        block_ms: Block time if no messages
        
    Returns:
        List of messages with session_id added to each
    """
    # Poll from all session streams
    # Use XREAD with multiple streams
    # Return messages with session_id metadata
```

### 3. Update Runner Main Loop

**File:** `services/thandev-runner/app/main.py` or wherever the polling loop is

- Get list of active sessions from Backend API (new endpoint needed)
- Poll from all active Brain session streams
- Execute steps and write results back to session-specific result streams

### 4. Add Backend Endpoint for Active Sessions

**File:** `backend/app/api/runner.py` (new)

```python
@router.get("/api/runner/active-sessions")
async def get_active_sessions():
    """Return list of active Brain session IDs for Runner to poll"""
    active_scans = db.query(ScanJob).filter(
        ScanJob.status == "running",
        ScanJob.brain_session_id.isnot(None)
    ).all()
    return {
        "sessions": [
            {"session_id": scan.brain_session_id, "scan_id": scan.id}
            for scan in active_scans
        ]
    }
```

---

## Quick Workaround (Testing Only)

For immediate testing, we can:

1. **Disable Brain for one scan** to test tool matrix changes work
2. **Force Runner to poll from specific Brain stream** (hardcoded session ID)

### Quick Fix Code:

**File:** `services/thandev-runner/app/queue/streams.py:75`

```python
# TEMPORARY: Support both old global stream and new Brain streams
STREAM_STEP_REQUESTS = "scan_step_requests"
STREAM_STEP_RESULTS = "scan_step_results"

# NEW: Brain stream support
BRAIN_STREAM_PREFIX = "brain:steps:"
BRAIN_RESULT_PREFIX = "brain:results:"

# For testing: poll from known active session
ACTIVE_BRAIN_SESSION = os.getenv("ACTIVE_BRAIN_SESSION", "")
if ACTIVE_BRAIN_SESSION:
    STREAM_STEP_REQUESTS = f"brain:steps:{ACTIVE_BRAIN_SESSION}"
    STREAM_STEP_RESULTS = f"brain:results:{ACTIVE_BRAIN_SESSION}"
    logger.info(f"Runner configured to poll Brain session: {ACTIVE_BRAIN_SESSION}")
```

Then restart Runner with:
```bash
docker compose -f docker-compose.fly-local.yml stop thandev-runner
docker compose -f docker-compose.fly-local.yml run -e ACTIVE_BRAIN_SESSION=0b03186a-ce3c-409f-b458-74a16964be95 thandev-runner
```

---

## Next Steps

1. **Implement Option 2** properly with multi-stream polling
2. **Test** with multiple concurrent scans
3. **Update documentation** on Brain ↔ Runner integration
4. **Add monitoring** for stream lag/backlog

---

## Related Files

- Brain stream writes: `services/thandev-brain/app/queue/streams.py`
- Brain session controller: `services/thandev-brain/app/controller/session_controller.py`
- Runner stream reads: `services/thandev-runner/app/queue/streams.py`
- Runner tasks: `services/thandev-runner/app/tasks.py`
- Backend scan API: `backend/app/api/scans.py`

---

## Status

- ✅ Brain tool matrix fix complete - All 7 tools scheduled
- ❌ Runner not consuming from Brain streams - **BLOCKING ISSUE**
- 🔧 Need to implement multi-stream polling in Runner
