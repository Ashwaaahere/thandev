# Scan CC168BD6 Investigation Report

## Summary
Investigation of scan `cc168bd6-0f67-4363-ad58-f2f7d483555f` to determine why tools are failing or results are not showing in the UI.

## Key Findings

### 1. Enumeration Tools (httpx, gau, katana, arjun)
**Status**: Results ARE in the database and ARE being displayed in the UI

- **Storage**: Enumeration tools store results in the `asset_inventory` artifact, NOT as separate `ToolResult` entries
- **UI Display**: Frontend correctly displays enumeration tools from the `/api/scans/{scan_id}/inventory` endpoint
- **Current State**:
  - HTTPX enumeration: `error="No output from httpx"` - This was from BEFORE our fix was applied
  - Katana: ✅ Working - Found 1 URL
  - GAU: ✅ Working - Found 0 URLs (expected for this target)
  - Arjun: ✅ Working - Tested 1 URL, found 0 params (expected)

**Root Cause**: The scan was created at `2026-02-03 22:20:22` (before our enumeration httpx fix was applied). The fix is now in place, but this scan needs to be re-run to see the fix.

### 2. Scan Tool httpx (ProjectDiscovery httpx)
**Status**: FAILED - Binary detection issue

- **Error**: `ProjectDiscovery httpx binary not found. The system has Python httpx (HTTP client) installed, but we need ProjectDiscovery httpx (security scanner).`
- **Binary Location**: `/usr/local/bin/httpx` EXISTS in the runner container
- **Binary Works**: The binary is functional and responds to commands
- **Detection Issue**: The binary detection test in `app/services/tools.py` is failing to detect the binary

**Root Cause**: The detection test runs `httpx -u https://example.com -silent -json` with a 5-second timeout. The test might be:
1. Timing out
2. Failing for network reasons
3. Not properly handling the test result

**Fix Needed**: Improve the httpx binary detection logic to:
1. Check if file exists first before running test
2. Use a simpler test (e.g., `httpx -version`) instead of a network request
3. Add better error handling

### 3. Other Scan Tools
**Status**: Working correctly

- **nmap**: ✅ COMPLETED - Found 1 finding
- **sslscan**: ✅ COMPLETED - No findings (expected)
- **wappalyzer**: ✅ COMPLETED - No findings (expected, filtered from tools list)
- **retire**: ✅ COMPLETED - No findings (expected, filtered from tools list)

## Data Flow Verification

### ✅ Backend Received Data
- Inventory was posted successfully: `POST /api/runner/scans/{scan_id}/inventory` returned 201
- Tool results were posted successfully: `POST /api/runner/scans/{scan_id}/tool-results` returned 201 for all tools

### ✅ Database Contains Data
- Inventory artifact exists with enumeration results
- Tool results exist for: httpx (failed), nmap (completed), sslscan (completed), wappalyzer (completed), retire (completed)

### ✅ UI Can Access Data
- `/api/scans/{scan_id}/tools` returns tool results correctly
- `/api/scans/{scan_id}/inventory` returns enumeration results correctly
- Frontend correctly displays enumeration tools from inventory

## Issues Identified

### Issue 1: Enumeration httpx Error (FIXED, but scan needs re-run)
- **Status**: Code fix is in place
- **Action**: Re-run scan to see the fix in action
- **Location**: `services/thandev-runner/app/enumeration.py` - `run_httpx()` function

### Issue 2: Scan Tool httpx Binary Detection (NEEDS FIX)
- **Status**: Binary exists but detection fails
- **Action**: Fix binary detection logic
- **Location**: `services/thandev-runner/app/services/tools.py` - httpx binary detection (lines 1574-1611)

## Recommendations

1. **Fix httpx binary detection**: Update the detection logic to use `-version` flag instead of network request
2. **Re-run scan**: After fixes, trigger a new scan to verify all tools work correctly
3. **Monitor logs**: Check runner logs during httpx detection to see why the test is failing

## Next Steps

1. Fix the httpx binary detection in `app/services/tools.py`
2. Test the fix with a new scan
3. Verify all tools execute and results appear in UI


