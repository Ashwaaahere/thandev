# Testing Scan Pipeline Improvements

This guide explains how to test the scan pipeline improvements:
- Timeout enforcement
- Parallelism limits
- Tool status tracking
- Failure handling

## Quick Verification

Run the verification script to check configuration and database state:

```bash
cd backend
source venv/bin/activate
python verify_scan_improvements.py [scan_id]
```

This will verify:
- ✅ Timeout configuration (basic < pro < advanced)
- ✅ Parallelism configuration (basic ≤ pro ≤ advanced)
- ✅ Tool status tracking (status field exists and has valid values)
- ✅ Scan completion logic (scan status matches tool results)

## Manual Testing Steps

### 1. Test Basic Scan - Timeout Enforcement

**Goal:** Verify that Basic scans have shorter timeouts than Pro/Advanced.

**Steps:**
1. Create a Basic scan via API or UI:
   ```bash
   curl -X POST http://localhost:8000/api/scans \
     -H "Content-Type: application/json" \
     -H "X-Thandev-User-Id: <user_id>" \
     -H "X-Thandev-Tenant-Id: <tenant_id>" \
     -d '{"project_id": "<project_id>", "scan_level": "basic"}'
   ```

2. Monitor the scan:
   ```bash
   # Get scan status
   curl http://localhost:8000/api/scans/<scan_id> \
     -H "X-Thandev-User-Id: <user_id>" \
     -H "X-Thandev-Tenant-Id: <tenant_id>"
   ```

3. Check tool execution times:
   - Basic scan: nuclei should timeout at ~120s (2 minutes)
   - Verify in `tool_results` table: `execution_time` should be ≤ 120s
   - If tool times out, `status` should be `timed_out` and `error_code` should be `"timeout"`

**Expected Results:**
- ✅ Tools complete within timeout limits
- ✅ If timeout occurs, status is `timed_out` with error_code `"timeout"`
- ✅ Scan completes even if some tools timeout

### 2. Test Pro Scan - Parallelism Limits

**Goal:** Verify that Pro scans run max 3 tools concurrently.

**Steps:**
1. Create a Pro scan (has 5+ tools: httpx, nuclei, nmap, ffuf, dalfox)

2. Monitor tool execution in real-time:
   ```bash
   # Watch scan status (poll every 2 seconds)
   watch -n 2 'curl -s http://localhost:8000/api/scans/<scan_id> \
     -H "X-Thandev-User-Id: <user_id>" | jq ".tool_statuses[] | {tool_name, status}"'
   ```

3. Check database for concurrent execution:
   ```sql
   -- Check tool start times (should see max 3 tools with same started_at)
   SELECT tool_name, started_at, status 
   FROM tool_results 
   WHERE scan_job_id = '<scan_id>' 
   ORDER BY started_at;
   ```

**Expected Results:**
- ✅ Max 3 tools running concurrently (check `status = 'running'` at same time)
- ✅ Tools complete in waves (not all at once)
- ✅ Scan completes successfully

### 3. Verify Tool Status Updates in API

**Goal:** Verify that API returns proper tool statuses with all fields.

**Steps:**
1. Get scan details:
   ```bash
   curl http://localhost:8000/api/scans/<scan_id> \
     -H "X-Thandev-User-Id: <user_id>" \
     -H "X-Thandev-Tenant-Id: <tenant_id>" | jq '.tool_statuses'
   ```

2. Verify response structure:
   ```json
   {
     "tool_statuses": [
       {
         "tool_name": "nuclei",
         "status": "completed",  // or "pending", "running", "failed", "timed_out", "skipped"
         "started_at": "2025-01-XX...",
         "completed_at": "2025-01-XX...",
         "execution_time": 45.2,
         "error_code": null,  // or "timeout", "missing_binary", etc.
         "error_message": null
       }
     ]
   }
   ```

**Expected Results:**
- ✅ All tools have `status` field (not null)
- ✅ Status values are valid: `pending`, `running`, `completed`, `failed`, `timed_out`, `skipped`
- ✅ `started_at` and `completed_at` are set for completed tools
- ✅ `error_code` is set for failed/timed_out tools

### 4. Test Failure Scenarios

#### 4a. Missing Binary

**Goal:** Verify that missing tool binaries are handled gracefully.

**Steps:**
1. Temporarily rename a tool binary (e.g., `mv ~/go/bin/nuclei ~/go/bin/nuclei.bak`)

2. Create a scan that uses that tool

3. Check tool status:
   ```bash
   # Get scan status
   curl http://localhost:8000/api/scans/<scan_id> | jq '.tool_statuses[] | select(.tool_name == "nuclei")'
   ```

**Expected Results:**
- ✅ Tool status is `failed`
- ✅ `error_code` is `"missing_binary"`
- ✅ `error_message` contains user-friendly message
- ✅ Scan continues with other tools
- ✅ Scan status is `COMPLETED_WITH_ERRORS` (not `FAILED`)

#### 4b. Timeout

**Goal:** Verify that tool timeouts are handled gracefully.

**Steps:**
1. Create a scan with a tool that will timeout (e.g., Basic scan with nuclei - should timeout at 120s)

2. Monitor tool execution:
   ```bash
   # Watch tool status
   watch -n 5 'curl -s http://localhost:8000/api/scans/<scan_id> | jq ".tool_statuses[] | {tool_name, status, error_code}"'
   ```

**Expected Results:**
- ✅ Tool status changes: `pending` → `running` → `timed_out`
- ✅ `error_code` is `"timeout"`
- ✅ `execution_time` is close to timeout limit
- ✅ Scan continues with other tools
- ✅ Scan completes successfully

#### 4c. Target Unreachable

**Goal:** Verify that unreachable targets are handled gracefully.

**Steps:**
1. Create a scan with an unreachable target (e.g., `http://192.0.2.1` - RFC 5737 test address)

2. Check tool statuses

**Expected Results:**
- ✅ Tools that fail due to unreachable target have `status = "failed"`
- ✅ `error_code` is `"target_unreachable"` (if detected) or `"execution_error"`
- ✅ Scan completes with `COMPLETED_WITH_ERRORS` status

## Database Verification

Check the database directly to verify improvements:

```python
from app.core.database import SessionLocal
from app.models.finding import ToolResult, ToolExecutionStatus
from app.models.scan import ScanJob

db = SessionLocal()

# Get latest scan
scan = db.query(ScanJob).order_by(ScanJob.created_at.desc()).first()

# Check tool results
tool_results = db.query(ToolResult).filter(
    ToolResult.scan_job_id == scan.id
).all()

for tr in tool_results:
    print(f"{tr.tool_name}: {tr.status.value if tr.status else 'legacy'}")
    print(f"  Started: {tr.started_at}")
    print(f"  Completed: {tr.completed_at}")
    print(f"  Error code: {tr.error_code}")
    print(f"  Execution time: {tr.execution_time}s")
```

## Expected Behavior Summary

### Timeout Enforcement
- **Basic:** Tools timeout at 2 minutes (nuclei), 30 seconds (httpx)
- **Pro:** Tools timeout at 5 minutes (most tools)
- **Advanced:** Tools timeout at 10-15 minutes (heavier tools)

### Parallelism Limits
- **Basic:** Max 2 concurrent tools
- **Pro:** Max 3 concurrent tools
- **Advanced:** Max 4 concurrent tools

### Tool Status Lifecycle
1. `PENDING` - Tool is planned but not started
2. `RUNNING` - Tool is executing
3. `COMPLETED` - Tool finished successfully
4. `FAILED` - Tool failed (non-zero exit, error)
5. `TIMED_OUT` - Tool execution timed out
6. `SKIPPED` - Tool was skipped (e.g., missing binary)

### Scan Status Logic
- `COMPLETED` - At least one tool completed successfully
- `COMPLETED_WITH_ERRORS` - Some tools failed but at least one succeeded
- `FAILED` - No tools completed (all failed)

## Troubleshooting

### Issue: Tool status is always null
**Solution:** Run migration `0009_add_tool_status_tracking`:
```bash
alembic upgrade head
```

### Issue: Timeouts not enforced
**Solution:** Check that `timeout_seconds` is passed to `ToolExecutor.run_tool()`. Verify in `scan_orchestrator.py` that `get_tool_timeout()` is called.

### Issue: Parallelism not working
**Solution:** Check that `get_max_parallelism()` is used instead of `settings.MAX_PARALLEL_TOOLS` in `run_scan_for_job()`.

### Issue: Scan fails when tool fails
**Solution:** Verify that tool failures are caught and don't raise exceptions. Check `_run_single_tool()` error handling.

