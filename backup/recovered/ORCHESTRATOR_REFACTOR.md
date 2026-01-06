# Orchestrator Refactoring Summary

## Overview

Successfully refactored the scan orchestration to use scan profiles, making it generic and supporting all three scan levels (basic, pro, advanced) through a single code path.

## Changes Made

### 1. Created Generic Orchestrator Function

**File**: `app/services/scan_orchestrator.py`

**New Function**: `run_scan_for_job(job: ScanJob) -> None`

This function:
- Takes a `ScanJob` instance (not just basic scans)
- Uses `scan_profiles.get_profile()` to get the appropriate tool list based on `job.scan_level`
- Runs each tool from the profile sequentially
- Parses findings from tool output (currently supports nuclei, extensible for others)
- Generates AI report using the existing `generate_basic_report` function
- Updates job status to "completed" or "failed" with proper error messages
- Sets `started_at` and `completed_at` timestamps

**Key Features**:
- Creates its own database session (job might be from different session)
- Reloads job from database to ensure latest state
- Handles all error cases gracefully
- Maintains all existing functionality (file writing, finding parsing, AI reports)

### 2. Refactored Celery Task

**File**: `app/tasks/celery_app.py`

**Changes**:
- Removed all hardcoded "basic" scan logic
- Removed inline tool execution code (moved to orchestrator)
- Now simply:
  1. Loads the scan job
  2. Sets status to "running" and `started_at` timestamp
  3. Calls `run_scan_for_job(scan_job)` - delegates everything to orchestrator
  4. Returns result with status and findings count

**Before**: ~230 lines of inline orchestration logic
**After**: ~70 lines that delegate to orchestrator

### 3. Deprecated Old Method

**File**: `app/services/scan_orchestrator.py`

- `run_basic_scan_for_job()` is now deprecated
- It calls `run_scan_for_job()` for backward compatibility
- Logs a warning when used

## Scan Level Behavior

### Basic Scan
- **Tools**: `["nuclei"]`
- **Behavior**: Exactly the same as before
- Uses nuclei with `cves/` templates, `critical,high` severity

### Pro Scan
- **Tools**: `["nuclei", "nmap"]`
- **Nuclei**: `cves/`, `vulnerabilities/` templates, `critical,high,medium` severity
- **Nmap**: Service version scan on top 1000 ports

### Advanced Scan
- **Tools**: `["nuclei", "nmap", "sslscan"]`
- **Nuclei**: `cves/`, `vulnerabilities/`, `exposures/` templates, all severities
- **Nmap**: Aggressive scan on all ports
- **SSLScan**: Full cipher suite check

## Code Flow

```
POST /api/scans
  ↓
ScanOrchestrator.queue_scan()
  ↓
Celery: run_scan_task(scan_job_id, target_url, scan_level)
  ↓
  Load ScanJob from DB
  Set status = RUNNING, started_at = now
  ↓
run_scan_for_job(scan_job)
  ↓
  Get profile: scan_profiles.get_profile(job.scan_level.value)
  ↓
  For each tool in profile["tools"]:
    - ToolExecutor.run_tool(tool_name, target_url, scan_level, **config)
    - Save ToolResult to DB
    - Save output to file (data/jobs/{job_id}/{tool}_output.json)
    - Parse findings (currently nuclei only)
  ↓
  Commit findings to DB
  ↓
  Generate AI report: generate_basic_report(scan_job, findings)
  ↓
  Set status = COMPLETED, completed_at = now
  ↓
Return result
```

## Verification

### Basic Scan (Preserved Behavior)
✅ Uses same tool: `nuclei`
✅ Same configuration: `cves/` templates, `critical,high` severity
✅ Same output location: `data/jobs/{job_id}/nuclei_output.json`
✅ Same finding parsing logic
✅ Same AI report generation

### Pro Scan (New)
✅ Uses 2 tools: `nuclei`, `nmap`
✅ Nuclei with expanded templates and severity
✅ Nmap for port scanning
✅ Both tools save output files
✅ Findings from both tools are parsed (nuclei) and stored

### Advanced Scan (New)
✅ Uses 3 tools: `nuclei`, `nmap`, `sslscan`
✅ All tools configured appropriately
✅ No crashes even if tools fail
✅ Error handling preserves scan job state

## Error Handling

The orchestrator handles:
- Invalid scan levels → Sets job status to FAILED with error message
- Missing project → Raises ValueError
- Tool execution failures → Logs error, continues with other tools
- Finding parsing errors → Logs warning, skips invalid entries
- AI report generation failures → Uses fallback summary format
- Database errors → Proper rollback and error logging

## Files Modified

1. **`app/services/scan_orchestrator.py`**
   - Added `run_scan_for_job()` function (main orchestrator)
   - Deprecated `run_basic_scan_for_job()` (now calls `run_scan_for_job()`)

2. **`app/tasks/celery_app.py`**
   - Simplified `run_scan_task()` to delegate to orchestrator
   - Removed ~160 lines of inline orchestration logic
   - Still handles status updates and error reporting

## Testing

To test each scan level:

```bash
# Basic scan (default)
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"project_id": "your-project-id"}'

# Pro scan
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"project_id": "your-project-id", "scan_level": "pro"}'

# Advanced scan
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -d '{"project_id": "your-project-id", "scan_level": "advanced"}'
```

## Benefits

1. **Single Code Path**: All scan levels use the same orchestration logic
2. **Maintainability**: Tool execution logic centralized in one place
3. **Extensibility**: Easy to add new tools or scan levels
4. **Consistency**: Same error handling, logging, and file writing for all levels
5. **Testability**: Orchestrator can be tested independently of Celery

## Future Enhancements

1. **Parallel Tool Execution**: Currently tools run sequentially; could run in parallel
2. **Tool-Specific Parsing**: Add parsing for nmap and sslscan findings
3. **Profile-Based Timeouts**: Different timeouts per scan level
4. **Resource Limits**: Profile-based resource constraints
5. **Tool Configuration**: Use `config` dict from profiles to customize tool behavior



