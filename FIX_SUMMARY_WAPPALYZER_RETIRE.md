# Fix Summary: Wappalyzer and Retire.js Not Showing in "Tools Executed"

## Problem
Wappalyzer and retire.js were executed as part of dependency scanning but didn't appear in the "Tools Executed" section because they only created artifacts, not ToolResult entries.

## Root Cause
1. **Backend file missing in container**: `dependency_scanner.py` wasn't in the Docker container
2. **No ToolResult creation**: Dependency scanning tools didn't create ToolResult entries like regular security tools

## Fixes Applied

### 1. Backend: Added Redis Publishing
- Modified `backend/app/services/dependency_scanner.py` to publish jobs to Redis stream
- Added Redis connection and error handling
- ✅ **File copied to container** (needs rebuild for permanent fix)

### 2. Runner: Added ToolResult Creation
- Modified `services/thandev-runner/app/dependency_scanner.py` to create ToolResult entries
- Added `create_dependency_tool_result()` function
- Creates entries for both wappalyzer and retire.js after execution
- Shows correct findings count and execution time

### 3. Runner: Added Dependency Worker
- Created `services/thandev-runner/app/dependency_worker.py` to consume dependency jobs
- Modified `services/thandev-runner/app/tasks.py` to run both workers in parallel
- ✅ **Dependency worker is running** (logs confirm)

## Current Status

✅ **Backend**: Can import dependency_scanner module
✅ **Backend**: Redis connection works
✅ **Runner**: Dependency worker is running
✅ **Code**: ToolResult creation code is in place

## Next Steps

### Immediate (Test Now)
1. **Create a new Pro scan** from the UI
2. **Monitor logs**:
   ```bash
   # Backend
   docker compose -f docker-compose.fly-local.yml logs backend --tail 50 -f | grep dependency
   
   # Runner
   docker compose -f docker-compose.fly-local.yml logs thandev-runner --tail 50 -f | grep -E "dependency|wappalyzer|retire"
   ```
3. **Check "Tools Executed"** section - wappalyzer and retire should appear

### Permanent Fix (After Testing)
Rebuild backend container to include dependency_scanner.py:
```bash
docker compose -f docker-compose.fly-local.yml build backend
docker compose -f docker-compose.fly-local.yml up -d backend
```

## Expected Behavior

When you create a Pro scan:

1. **Backend logs**: "Enqueuing dependency scan job: scan_id=..."
2. **Backend logs**: "Successfully enqueued dependency scan job ... to Redis stream"
3. **Runner logs**: "Received X dependency scan job(s)"
4. **Runner logs**: "Processing dependency scan job: scan_id=..., job_type=url_sca"
5. **Runner logs**: "Created ToolResult entry for wappalyzer"
6. **Runner logs**: "Created ToolResult entry for retire"
7. **UI**: Both tools appear in "Tools Executed" section with:
   - Status: Success/Failed
   - Findings: Count of technologies (wappalyzer) or vulnerabilities (retire)
   - Duration: Execution time
   - Exit code: 0 or 1

## Verification Commands

```bash
# Check if jobs are in Redis
docker exec thandev-redis-1 redis-cli XLEN dependency_scan_jobs

# Check ToolResult entries
docker exec thandev-postgres-1 psql -U postgres -d thandev -c "
SELECT scan_job_id, tool_name, status, created_at 
FROM tool_results 
WHERE tool_name IN ('wappalyzer', 'retire') 
ORDER BY created_at DESC 
LIMIT 5;
"

# Check artifacts
docker exec thandev-postgres-1 psql -U postgres -d thandev -c "
SELECT scan_id, type, created_at 
FROM scan_artifacts 
WHERE type = 'url_sca' 
ORDER BY created_at DESC 
LIMIT 3;
"
```

## Note

The `dependency_scanner.py` file was manually copied to the container. For a permanent fix, rebuild the backend container:
```bash
docker compose -f docker-compose.fly-local.yml build backend
```
