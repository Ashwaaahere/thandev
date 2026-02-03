# Scan DF3C109E Diagnosis Guide

## Issue Reported
- Scan shows as **COMPLETED** but **no results/findings** are showing
- **ZAP and other tools** appear to have **failed**

## Potential Root Causes

### 1. **Tools Marked as Failed When They Shouldn't Be**
Tools can be marked as `FAILED` even if they executed successfully if:
- The `success` field in the tool result is `False`
- Exit code is non-zero (even if findings were produced)
- Error message is present (even if it's just a warning)

**Check:** Look at `tool_results` table for this scan:
```sql
SELECT 
    tool_name, 
    status, 
    exit_code, 
    error_message, 
    created_findings_count,
    output
FROM tool_results 
WHERE scan_job_id LIKE 'DF3C109E%'
ORDER BY created_at;
```

### 2. **Findings Ingestion Failed Silently**
Findings might not be created even if tools produced output:
- Ingestion errors are caught and logged but don't fail the tool result
- Check logs for `[INGEST-DEBUG]` messages
- Look for `findings_ingested` count vs `created_findings_count`

**Check:**
```sql
SELECT 
    tool_name,
    parsed_findings_count,  -- Findings received from runner
    created_findings_count   -- Findings actually created in DB
FROM tool_results 
WHERE scan_job_id LIKE 'DF3C109E%';
```

### 3. **ZAP Connection Issues**
ZAP specifically can fail if:
- ZAP API is unreachable (`thandev-zap.internal` DNS resolution fails)
- Connection timeout after retries
- Returns `success: False` with error message

**Check ZAP tool result:**
```sql
SELECT 
    tool_name,
    status,
    error_message,
    error_code,
    output
FROM tool_results 
WHERE scan_job_id LIKE 'DF3C109E%' 
  AND tool_name LIKE '%zap%';
```

### 4. **Tools Completed But Found Nothing**
Some tools might complete successfully but find 0 vulnerabilities:
- This is **normal** for clean targets
- Tools like `nuclei`, `dalfox` might return empty results
- Check if `created_findings_count = 0` but `status = COMPLETED`

### 5. **Scan Status vs Tool Status Mismatch**
Scan can be marked `COMPLETED` even if some tools failed:
- If at least one tool completed, scan is marked `COMPLETED` or `COMPLETED_WITH_ERRORS`
- Failed tools are still shown in the UI but scan appears "done"

## How to Diagnose

### Step 1: Check Scan Status
```sql
SELECT 
    id, 
    status, 
    scan_level, 
    url,
    created_at,
    started_at,
    completed_at,
    error_message
FROM scan_jobs 
WHERE id LIKE 'DF3C109E%';
```

### Step 2: Check All Tool Results
```sql
SELECT 
    tool_name,
    status,
    exit_code,
    timed_out,
    error_code,
    error_message,
    created_findings_count,
    parsed_findings_count,
    execution_time,
    created_at,
    started_at,
    completed_at
FROM tool_results 
WHERE scan_job_id LIKE 'DF3C109E%'
ORDER BY created_at;
```

### Step 3: Check Findings Count
```sql
SELECT 
    COUNT(*) as total_findings,
    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
    COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
    COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium,
    COUNT(CASE WHEN severity = 'low' THEN 1 END) as low,
    COUNT(CASE WHEN severity = 'info' THEN 1 END) as info,
    COUNT(DISTINCT tool_name) as tools_with_findings
FROM findings 
WHERE scan_job_id LIKE 'DF3C109E%';
```

### Step 4: Check Findings by Tool
```sql
SELECT 
    tool_name,
    COUNT(*) as count,
    COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
    COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
    COUNT(CASE WHEN severity = 'medium' THEN 1 END) as medium
FROM findings 
WHERE scan_job_id LIKE 'DF3C109E%'
GROUP BY tool_name
ORDER BY count DESC;
```

## Common Fixes

### If Tools Are Marked Failed But Should Be Completed:
1. Check if tools actually produced output
2. If output exists but `success=False`, the tool might have had a non-critical error
3. Consider updating tool result status if findings were created

### If ZAP Failed:
1. Check ZAP service is running: `docker ps | grep zap`
2. Check ZAP API is accessible from runner service
3. Verify DNS resolution for `thandev-zap.internal`
4. Check ZAP logs for connection errors

### If No Findings But Tools Completed:
1. This might be **normal** - target might be clean
2. Check if tools actually scanned the target (verify `output` field)
3. Some tools (like `nuclei`) return empty results for clean targets

### If Findings Ingestion Failed:
1. Check backend logs for `[INGEST-DEBUG]` messages
2. Look for exceptions during finding creation
3. Check if findings were received but not saved (compare `parsed_findings_count` vs `created_findings_count`)

## Next Steps

1. **Run the diagnostic script** (if database access is available):
   ```bash
   python3 debug_scan_results.py DF3C109E
   ```

2. **Check backend logs** for this scan ID:
   ```bash
   grep "DF3C109E" backend/logs/*.log | tail -100
   ```

3. **Check runner logs** for tool execution:
   ```bash
   grep "DF3C109E" services/thandev-runner/logs/*.log | tail -100
   ```

4. **Verify ZAP service** (if ZAP failed):
   ```bash
   docker ps | grep zap
   curl http://thandev-zap.internal:8090/JSON/core/view/version/
   ```

## Expected Behavior

- **Scan COMPLETED with findings**: Normal - tools found vulnerabilities
- **Scan COMPLETED with 0 findings**: Normal - target is clean, no vulnerabilities found
- **Scan COMPLETED_WITH_ERRORS**: Some tools failed but others succeeded
- **Scan FAILED**: All tools failed or no tools executed

If scan is COMPLETED but shows 0 findings, this might actually be correct if the target has no vulnerabilities!

