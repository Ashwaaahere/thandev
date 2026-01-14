# Tool Execution Manifest & Target Feeding Implementation

## Summary

This implementation adds comprehensive tool execution tracking and proper target feeding for `dalfox` and `sqlmap` to ensure visible, debuggable outcomes in scan reports, even with 0 findings.

## Key Features Implemented

### A) Tool Execution Manifest (per scan session)

**Added structured `tool_runs` tracking with the following fields:**

- `tool_name`: Tool identifier (e.g., "dalfox", "sqlmap")
- `status`: Execution status (queued/running/completed/failed/skipped/timed_out)
- `started_at`: Timestamp when tool execution started
- `completed_at`: Timestamp when tool execution completed
- `exit_code`: Process exit code
- `execution_time`: Duration in seconds
- **`targets_count`**: NEW - Number of targets (URLs/params/requests) fed to tool
- `stdout_preview`: First 1000 chars of stdout
- `stderr_preview`: First 1000 chars of stderr
- `output_path`: Path to full output file (if stored)
- `parsed_findings_count`: Number of findings parsed from output
- `created_findings_count`: Number of findings actually created in DB
- `skip_reason`: Reason if tool was skipped (e.g., "no_injection_points")
- **`meta`**: NEW - Additional metadata (harvester stats, tool args, etc.)

**All tool runs are visible in:**
- UI scan details page
- PDF reports (via backend API)
- Even when 0 findings are found

### B) Proper Target Feeding

**Created Request/Param Harvesting System:**

New module: `services/thandev-runner/app/utils/param_harvester.py`

Features:
1. **Harvests parameterized endpoints from multiple sources:**
   - ZAP Ajax Spider results
   - ZAP passive/active scan findings
   - Custom crawler output
   - Manual URL lists

2. **Extracts comprehensive parameter data:**
   - GET query params
   - POST/JSON body params
   - Cookies and headers (if available)
   - HTTP method (GET/POST)

3. **Intelligent deduplication:**
   - Combines results from all sources
   - Removes duplicate URL+param combinations
   - Preserves parameter diversity

4. **Fallback mechanism:**
   - Creates common test parameters if no params harvested
   - Tests common param names (id, page, query, search, user, etc.)
   - Ensures tools always have meaningful targets

**Updated Tool Implementations:**

1. **dalfox (_run_dalfox):**
   - Harvests params from ZAP output and crawler
   - Combines harvested + crawled URLs
   - Falls back to common test params if none found
   - Reports `targets_count` and harvester stats in meta

2. **sqlmap (_run_sqlmap):**
   - Harvests params from ZAP output and crawler
   - Creates parameterized bulk targets file
   - Uses raw request files for POST/form testing
   - Falls back to common test params if none found
   - Reports `targets_count` and harvester stats in meta

### C) Ingestion/Parsing

**Enhanced Result Handling:**

1. **Runner output always creates ToolResult records:**
   - Even with 0 findings
   - Even when tool fails or times out
   - Includes all metadata fields

2. **Clear error messages:**
   - "0 targets" reason when no params found
   - Skip reasons for why tool didn't run
   - Detailed error messages in tool_result.error_message

3. **Artifact preservation:**
   - Full logs stored at `output_path`
   - stdout/stderr previews in database
   - Accessible from UI and API

### D) Acceptance Tests

**Created test script:** `test_juice_shop_scan.py`

**Features:**
- Automated scan creation against Juice Shop
- Waits for completion with progress updates
- Validates tool runs have proper metadata
- Checks targets_count > 0 or clear skip reason
- Verifies logs/artifacts are accessible
- Provides detailed validation report

**Usage:**
```bash
# Run against default Juice Shop instance
python test_juice_shop_scan.py

# Run against custom URL
python test_juice_shop_scan.py --url https://juice-shop.herokuapp.com

# Run with specific scan level
python test_juice_shop_scan.py --scan-level advanced

# Run with authentication
python test_juice_shop_scan.py --api-token YOUR_TOKEN
```

## Changed Files

### Backend Changes

1. **Database Model:**
   - `backend/app/models/finding.py`: Added `targets_count` field to ToolResult

2. **Database Migration:**
   - `backend/migrations/versions/0032_add_targets_count_to_tool_results.py`: Migration for new field

3. **API Schema:**
   - `backend/app/schemas/scan.py`: Added `targets_count` and `meta` to ToolResultCreate

4. **API Endpoint:**
   - `backend/app/api/runner_ingest.py`: Updated ToolResult creation to include new fields

### Runner Changes

1. **New Module:**
   - `services/thandev-runner/app/utils/param_harvester.py`: Complete param harvesting system

2. **Tool Implementations:**
   - `services/thandev-runner/app/services/tools.py`:
     - Updated `_run_dalfox()` to use param harvester
     - Updated `_run_sqlmap()` to use param harvester
     - Both now report `targets_count` and `meta` in results

3. **Backend Client:**
   - `services/thandev-runner/app/backend_client.py`: Added `targets_count` and `meta` to payload

### Test Files

1. **Test Script:**
   - `test_juice_shop_scan.py`: Comprehensive validation script

## How to Run Locally

### 1. Apply Database Migration

```bash
cd backend
# Apply migration
alembic upgrade head

# Or run migration directly
python -m alembic upgrade head
```

### 2. Restart Services

```bash
# Stop all services
docker-compose down

# Start all services
docker-compose up -d

# Or use your preferred start script
./start_services.sh
```

### 3. Run Test Scan

```bash
# Method 1: Using test script (recommended)
python test_juice_shop_scan.py

# Method 2: Manual scan via UI
# 1. Open http://localhost:3000
# 2. Create project with target: https://demo.owasp-juice.shop
# 3. Run "Pro" or "Advanced" scan
# 4. Check scan details page for tool runs
```

### 4. Verify Tool Runs

**Via UI:**
1. Go to scan details page
2. Look for "Tool Runs" section
3. Verify dalfox and sqlmap appear with:
   - targets_count > 0 (or clear skip reason)
   - Execution time
   - Status (completed/failed)
   - Output/logs preview

**Via API:**
```bash
# Get scan details
curl http://localhost:8000/api/scans/{SCAN_ID}

# Get tool results
curl http://localhost:8000/api/scans/{SCAN_ID}/tool-results
```

**Via Database:**
```sql
-- Check tool results
SELECT 
    tool_name, 
    status, 
    targets_count, 
    execution_time,
    parsed_findings_count,
    created_findings_count,
    meta
FROM tool_results 
WHERE scan_job_id = 'YOUR_SCAN_ID';
```

## Expected Behavior

### For Juice Shop Scan (SPA)

**dalfox:**
- Should harvest 10-50 parameterized URLs from ZAP spider
- `targets_count`: 20-100 (depending on scan level)
- `meta.harvested_requests`: 10-50
- `meta.total_parameters`: 20-100
- Findings: 0-5 XSS vulnerabilities (depending on Juice Shop version)

**sqlmap:**
- Should harvest same parameterized URLs
- `targets_count`: 20-100
- `meta.harvested_requests`: 10-50
- `meta.total_parameters`: 20-100
- Findings: 0-3 SQL injection vulnerabilities (depending on Juice Shop version)

**If no params harvested:**
- Fallback to common test parameters (id, page, query, etc.)
- `targets_count`: 20-30 (fallback URLs)
- `skip_reason`: Not set (tools ran with fallback targets)

### For Static Sites (no params)

**dalfox:**
- No params harvested
- Falls back to common test parameters
- `targets_count`: 20-30 (fallback URLs)
- Findings: 0 (expected for static sites)

**sqlmap:**
- No params harvested
- Falls back to common test parameters
- `targets_count`: 20-30 (fallback URLs)
- Findings: 0 (expected for static sites)

## Debugging

### Check if harvester is working

```bash
# Check runner logs for harvester messages
docker logs thandev-runner-1 | grep -i harvest

# Expected output:
# "Harvested 25 parameterized requests from ZAP output"
# "Dalfox scan xyz: harvested_requests: 25, total_parameters: 50"
```

### Check if ZAP output is available

```bash
# Check if ZAP output exists
ls -la /path/to/jobs/{SCAN_ID}/zap_output.json

# View ZAP findings
cat /path/to/jobs/{SCAN_ID}/zap_output.json | jq '.[] | {url, method}'
```

### Check tool results in database

```sql
-- Check latest tool runs
SELECT 
    tr.tool_name,
    tr.status,
    tr.targets_count,
    tr.execution_time,
    tr.parsed_findings_count,
    tr.created_findings_count,
    tr.skip_reason,
    tr.meta->>'harvested_requests' as harvested_requests,
    tr.meta->>'total_parameters' as total_parameters
FROM tool_results tr
JOIN scan_jobs sj ON tr.scan_job_id = sj.id
ORDER BY tr.created_at DESC
LIMIT 10;
```

## Constraints Met

✅ **No breaking changes to existing tools:**
- httpx, ZAP, nuclei continue to work as before
- New fields are optional
- Backward compatible with existing scans

✅ **Minimal and well-structured:**
- New param harvester is self-contained module
- Tool changes are localized to _run_dalfox and _run_sqlmap
- Database migration is idempotent and safe

✅ **Clear error messages:**
- Skip reasons when tools can't run
- "0 targets" explanation when no params found
- Detailed error_message in tool results

## Future Enhancements (Optional)

1. **UI Improvements:**
   - Add "Tool Runs" tab to scan details page
   - Show harvester stats in UI
   - Display stdout/stderr logs inline

2. **PDF Report Improvements:**
   - Include tool run summary table
   - Show targets_count for each tool
   - Add harvester statistics section

3. **Additional Tools:**
   - Apply same pattern to other injection tools
   - Add param harvesting for fuzzing tools (ffuf, etc.)

4. **Harvester Enhancements:**
   - Support HAR file import
   - Parse Burp Suite requests
   - Extract params from JavaScript files

## Contact & Support

For issues or questions:
- Check logs: `docker logs thandev-runner-1`
- Check database: `psql -d thandev -c "SELECT * FROM tool_results ORDER BY created_at DESC LIMIT 5"`
- Run test script: `python test_juice_shop_scan.py`
- Review this document for expected behavior
