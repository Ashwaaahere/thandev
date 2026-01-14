# Comprehensive Forensic Fixes - End-to-End XSS Detection & Scan Reliability

## Executive Summary

This document details all fixes applied to ensure Nuclei and Dalfox can reliably detect XSS vulnerabilities and that scans complete successfully with proper timeout handling and findings ingestion.

## Critical Issues Fixed

### 1. Timeout Not Passed from Backend to Runner Service

**Problem**: When backend publishes scan steps to runner service via Redis streams, `timeout_seconds` was not being included in the `params` dict. This caused tools to use default timeouts (300s) instead of scan-level-specific timeouts (600s for Pro).

**Root Cause**: `publish_scan_steps_to_runner()` in `backend/app/services/runner_client.py` was not extracting timeout from `scan_timeouts.py` and adding it to params.

**Fix**:
- Modified `publish_scan_steps_to_runner()` to:
  - Import `get_tool_timeout` from `scan_timeouts.py`
  - Calculate `timeout_seconds` for each tool based on scan level
  - Add `timeout_seconds` and `scan_level` to params before publishing
  - Added logging to track timeout values being passed

**Files Changed**:
- `backend/app/services/runner_client.py`

### 2. Runner Service Not Extracting timeout_seconds from Params

**Problem**: Runner service's `ToolExecutor.run_step()` was not extracting `timeout_seconds` from params and passing it to tool execution functions.

**Root Cause**: `_map_mode_to_internal_params()` was checking for `timeout_sec` (singular) but backend was passing `timeout_seconds` (plural). Also, the extraction happened after mode mapping, so it wasn't being passed through.

**Fix**:
- Modified `run_step()` to:
  - Extract `timeout_seconds` and `scan_level` from params BEFORE mode mapping
  - Pass them directly to `internal_kwargs`
  - Added logging to track timeout extraction
- Modified `_map_mode_to_internal_params()` to:
  - Check for both `timeout_seconds` and `timeout_sec` (backward compatibility)
  - Prioritize params over constraints
  - Added debug logging

**Files Changed**:
- `services/thandev-runner/app/services/tools.py`

### 3. Nuclei Timeout Calculation Missing Warning

**Problem**: Nuclei timeout calculation was using default 300s if `timeout_seconds` wasn't in kwargs, but wasn't warning about it.

**Fix**:
- Added warning log when `timeout_seconds` is not provided
- Logs available kwargs keys for debugging
- Improved timeout calculation logging to show base timeout, calculated timeout, and scan level

**Files Changed**:
- `services/thandev-runner/app/services/tools.py` (in `_run_nuclei()`)

### 4. Dalfox Timeout Calculation Missing Warning

**Problem**: Dalfox timeout calculation was using default if `timeout_seconds` wasn't in kwargs, but wasn't warning about it.

**Fix**:
- Added warning log when `timeout_seconds` is not provided
- Logs available kwargs keys for debugging
- Improved timeout calculation logging to show timeout value and scan level

**Files Changed**:
- `services/thandev-runner/app/services/tools.py` (in `_run_dalfox()`)

### 5. Insufficient Logging for Tool Execution

**Problem**: When tools completed suspiciously fast (e.g., dalfox in 0.3s), there was no logging to help diagnose the issue.

**Fix**:
- Added comprehensive logging for both Nuclei and Dalfox:
  - Log URLs being scanned (first 10)
  - Log full command being executed
  - Log execution start time
  - Log execution duration and exit code
  - Warn if execution is suspiciously fast (< 1s for dalfox, < 5s for nuclei with many URLs)
  - Log stdout/stderr lengths for debugging

**Files Changed**:
- `services/thandev-runner/app/services/tools.py` (in `_run_nuclei()` and `_run_dalfox()`)

### 6. Crawler Failure Not Properly Logged

**Problem**: When crawler found no URLs, tools would skip execution but the error wasn't clear enough.

**Fix**:
- Changed log level from `warning` to `error` when crawler finds no URLs
- Added more context: target URL, scan level, number of URLs found
- Changed exit code from 0 to -1 for skipped tools (to indicate failure)
- Improved error messages to be more descriptive

**Files Changed**:
- `services/thandev-runner/app/services/tools.py` (in `_run_nuclei()` and `_run_dalfox()`)

## Verification Steps

### 1. Verify Timeout Flow

```bash
# Check backend logs when scan starts
docker logs thandev-backend-1 | grep "timeout_seconds"

# Check runner logs when tool executes
docker logs thandev-runner-1 | grep "timeout_seconds\|timeout"

# Should see:
# - Backend: "Publishing step for nuclei with timeout_seconds=600"
# - Runner: "Using timeout_seconds=600 from params for nuclei"
# - Runner: "Nuclei timeout for X URLs: Ys (base from kwargs: 600s, scan_level: pro)"
```

### 2. Verify Tool Execution

```bash
# Check runner logs for tool execution
docker logs thandev-runner-1 | grep -A 5 "About to execute"

# Should see:
# - "About to execute with X URLs, timeout=Ys"
# - "URLs to scan (first 10): ..."
# - "Execution completed in Xs (timeout was Ys, exit_code=0)"
```

### 3. Verify Findings Ingestion

```bash
# Check backend logs for findings ingestion
docker logs thandev-backend-1 | grep "findings_ingested\|Ingesting findings"

# Should see:
# - "Ingesting findings for scan X, tool=nuclei: Y findings in payload"
# - "Created tool result ... findings=Y"
```

## Testing Checklist

- [ ] Create a Pro scan on a target with known XSS vulnerabilities
- [ ] Verify backend logs show `timeout_seconds=600` for nuclei and dalfox
- [ ] Verify runner logs show timeout being extracted from params
- [ ] Verify nuclei runs for at least 600s (or times out at 600s if many URLs)
- [ ] Verify dalfox runs for at least 600s (or completes successfully)
- [ ] Verify findings are ingested for both tools
- [ ] Verify scan status is `COMPLETED` or `COMPLETED_WITH_ERRORS` (not `FAILED` if some tools succeed)

## Files Modified

1. `backend/app/services/runner_client.py`
   - Added timeout extraction and passing to runner service

2. `services/thandev-runner/app/services/tools.py`
   - Added timeout extraction from params
   - Added comprehensive logging for tool execution
   - Improved error handling for crawler failures
   - Added warnings for missing timeouts

## Next Steps

1. **Restart Services**: Apply changes by restarting backend and runner services
   ```bash
   docker-compose restart backend thandev-runner
   ```

2. **Run Test Scan**: Create a Pro scan on a test target to verify fixes

3. **Monitor Logs**: Watch logs for timeout warnings and execution details

4. **Verify Findings**: Check that XSS findings are detected and ingested

## Known Limitations

- If crawler fails completely, tools will skip execution (this is expected behavior)
- Timeout calculation assumes at least 30s per URL for Nuclei (may need adjustment for very large targets)
- Dalfox timeout is increased for Pro/Advanced when using `--deep-domxss` (adds headless browser overhead)

## Related Documents

- `XSS_DETECTION_FIXES.md` - Previous fixes for XSS detection
- `SCAN_FAILURE_FIXES.md` - Previous fixes for scan status logic

