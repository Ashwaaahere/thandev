# Root Cause Analysis: Dependency Scanning Issues

## Evidence Collected

### 1. Frontend Issues
**File**: `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`
- Line 2119-2122: TechDependenciesPanel correctly looks for `url_sca` artifact type
- Line 2129-2132: RepoDependenciesPanel correctly looks for `repo_sca` artifact type
- Line 414: Artifacts are only loaded when dependency tabs are activated
- **No GitHub prompt found in TechDependenciesPanel** - The component itself is clean

**File**: `frontend/components/Scans/TechDependenciesPanel.tsx`
- Line 61-72: Shows "No dependency scan results available" when artifact is null
- **No GitHub integration prompt** - Component is correct

### 2. Backend API Issues
**File**: `backend/app/api/scans.py`
- Line 2651: Endpoint defined as `@router.get("/{scan_id}/artifacts")`
- Line 2690-2692: Query looks correct: `ScanArtifact.scan_id == scan_id`
- **Issue**: Endpoint returns 404 - Route not found

**Test Result**:
```bash
curl http://localhost:8000/api/scans/{scan_id}/artifacts
# Returns: {"detail":"Not Found"}
```

### 3. Database Issues
**Query Result**:
```sql
SELECT id, scan_id, type, created_at FROM scan_artifacts ORDER BY created_at DESC LIMIT 5;
# Result: (0 rows)
```

**Conclusion**: No artifacts have ever been created.

### 4. Backend Job Enqueue Issues
**File**: `backend/app/services/dependency_scanner.py`
- Line 50: Tries to POST to `{runner_url}/api/jobs` (HTTP endpoint)
- Line 60-66: Uses httpx to call runner HTTP API
- **Problem**: Runner doesn't have HTTP endpoint - it uses Redis streams!

**File**: `services/thandev-runner/app/tasks.py`
- Line 831-837: Runner consumes from Redis stream `scan_step_requests`
- **No handler for dependency scan jobs** - Runner only processes "step requests"

### 5. Runner Implementation Issues
**File**: `services/thandev-runner/app/dependency_scanner.py`
- Line 19-92: `run_url_sca_job()` function exists and looks correct
- **Problem**: This function is never called because:
  1. Backend tries to enqueue via HTTP (doesn't exist)
  2. Runner doesn't listen for dependency scan jobs in Redis streams

## Root Causes

### CRITICAL ISSUE #1: Backend tries HTTP instead of Redis
**Location**: `backend/app/services/dependency_scanner.py:60-66`
- Backend attempts HTTP POST to runner
- Runner doesn't expose HTTP endpoint
- Jobs are never actually enqueued

### CRITICAL ISSUE #2: Runner doesn't handle dependency jobs
**Location**: `services/thandev-runner/app/tasks.py`
- Runner only processes "step requests" from Redis
- No handler for dependency scan job types (`url_sca`, `repo_sca`)
- Even if jobs were enqueued, runner wouldn't process them

### CRITICAL ISSUE #3: Artifacts endpoint 404
**Location**: `backend/app/api/scans.py:2651`
- Route defined but returns 404
- Need to verify router registration

### MINOR ISSUE #4: Frontend shows empty state correctly
- TechDependenciesPanel correctly shows "No results" when artifact is null
- This is expected behavior - not a bug
- **No GitHub prompt found** - User's observation may be from a different component or cached state

## Fix Strategy

1. **Fix Backend Job Enqueue**: Publish dependency jobs to Redis stream instead of HTTP
2. **Fix Runner Job Handler**: Add handler for dependency scan jobs in runner
3. **Fix Artifacts Endpoint**: Verify route registration and fix if needed
4. **Add Logging**: Add comprehensive logging to trace job flow
5. **Test End-to-End**: Verify Pro scan creates url_sca artifact
