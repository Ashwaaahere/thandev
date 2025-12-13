# Nuclei Integration Documentation

## Overview

This document describes the Nuclei vulnerability scanner integration in the Thandev security scanning platform. Nuclei v3.4.10 is used as the primary vulnerability detection engine.

## Integration Status

✅ **Production Ready**: The integration is complete and working correctly.

- Nuclei v3.4.10 is the supported version
- Uses `-jsonl` flag (NOT `-json`, which is not supported in v3.4.10)
- Handles both "findings detected" and "no findings" cases correctly
- Comprehensive logging distinguishes between success and errors

## How It Works

### 1. Command Construction

Nuclei commands are built in `backend/app/services/tools.py` in the `_run_nuclei()` method.

**Required flags (v3.4.10 compatible):**
- `-u <url>`: Target URL
- `-severity <levels>`: Severity filter based on scan level
- `-jsonl`: JSON Lines output format (one JSON object per line)
- `-silent`: Suppress non-JSON output (logs go to stderr)

**Optional performance flags:**
- `-rate-limit 50`: Limit to 50 requests per second
- `-timeout 10`: 10 second timeout per request
- `-retries 1`: Retry once on failure

**Template tags by scan level:**
- **basic**: `cve,vulnerability,exposure`
- **pro**: `cve,vulnerability,exposure,misconfig,default-login`
- **advanced**: `cve,vulnerability,exposure,misconfig,default-login,tech,ssl`

**DO NOT use:**
- `-json` (not supported in v3.4.10, use `-jsonl` instead)
- `-t <template_paths>` (can cause template update output issues)

### 2. Execution Flow

1. **Tool Execution** (`tools.py`):
   - Nuclei command is constructed with appropriate flags
   - Command is executed via `subprocess.run()`
   - stdout (JSONL findings) and stderr (logs) are captured separately
   - Exit code is checked

2. **File Writing** (`scan_orchestrator.py`):
   - stdout is written **exactly as-is** to `data/jobs/{scan_id}/nuclei_output.json`
   - If stdout is empty, file is 0 bytes (valid - means no findings)
   - No artificial `[]` fallback - empty file is the correct representation

3. **Parsing** (`findings_ingestor.py`):
   - `parse_nuclei_output()` reads the file line-by-line
   - Skips empty lines and non-JSON lines (tables, logs, etc.)
   - Returns list of parsed JSON objects
   - Returns empty list for missing or zero-byte files

4. **Ingestion** (`findings_ingestor.py`):
   - `ingest_nuclei_findings()` deletes existing findings for the scan (idempotent)
   - Creates `Finding` records for each parsed Nuclei result
   - Commits all findings in a single transaction

5. **Summary Generation** (`scan_orchestrator.py`):
   - AI report is generated after findings are ingested
   - `findings_count` and `risk_score` are calculated from DB findings

## Understanding "No Findings" vs "Error"

### Successful Scan with No Findings

**Indicators:**
- Exit code: `0`
- stdout: Empty (0 bytes)
- File: `nuclei_output.json` exists but is 0 bytes
- Logs: `"Nuclei scan {id} successful: no vulnerabilities found (target is clean)"`
- API: `findings_count: 0`, `risk_score: 0`

**This is correct behavior.** Not all targets have vulnerabilities matching Nuclei's templates.

**Example targets that may produce 0 findings:**
- `http://itsecgames.com/` (legitimately clean or doesn't match current templates)
- Well-secured production applications
- Targets that don't match the template tags used

### Successful Scan with Findings

**Indicators:**
- Exit code: `0`
- stdout: Contains JSONL (one JSON object per line)
- File: `nuclei_output.json` has content (> 0 bytes)
- Logs: `"Nuclei scan {id} successful: found {N} bytes of output (vulnerabilities detected)"`
- API: `findings_count > 0`, `risk_score > 0`

**Example targets that should produce findings:**
- `http://testphp.vulnweb.com/` (intentionally vulnerable demo app)
- `http://demo.testfire.net/` (OWASP WebGoat-style demo)
- Applications with known vulnerabilities

### Failed Scan (Error)

**Indicators:**
- Exit code: `!= 0`
- Logs: `"Nuclei scan {id} failed: ..."` at WARNING or ERROR level
- Result includes `error` field with details
- Scan status may be `failed` or `completed` with `error_message`

**Common causes:**
- Invalid flags (e.g., using `-json` instead of `-jsonl`)
- Network timeouts
- Target unreachable
- Nuclei binary not found

## Testing

### Test Script

Use the provided test script to verify the integration:

```bash
# Test with a target that may have no findings (this is OK)
./test_nuclei_integration.sh http://itsecgames.com/ advanced

# Test with a known vulnerable demo target (should produce findings)
./test_nuclei_integration.sh http://testphp.vulnweb.com/ advanced
```

### Manual Testing

1. **Start backend + Celery:**
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   
   # In another terminal:
   cd backend
   source .venv/bin/activate
   ./start_celery.sh
   ```

2. **Trigger a scan:**
   ```bash
   curl -X POST "http://localhost:8000/api/scans/quick" \
     -H "Content-Type: application/json" \
     -d '{"target_url":"http://testphp.vulnweb.com/","scan_level":"advanced"}'
   ```

3. **Monitor scan status:**
   ```bash
   SCAN_ID=<scan_id_from_step_2>
   curl -s "http://localhost:8000/api/scans/$SCAN_ID" | python3 -m json.tool
   ```

4. **Check findings:**
   ```bash
   curl -s "http://localhost:8000/api/findings?limit=10&offset=0" | python3 -m json.tool
   ```

5. **Inspect output file:**
   ```bash
   ls -lh data/jobs/$SCAN_ID/nuclei_output.json
   wc -c data/jobs/$SCAN_ID/nuclei_output.json
   head -5 data/jobs/$SCAN_ID/nuclei_output.json
   ```

### Expected Log Messages

**Successful scan with findings:**
```
INFO: Nuclei v3.4.10 command for scan {id}: nuclei -u ... -severity ... -jsonl -silent ...
INFO: Nuclei completed for scan {id}: exit_code=0, stdout_bytes=1234, stderr_bytes=567
INFO: Nuclei scan {id} successful: found 1234 bytes of output (vulnerabilities detected)
INFO: Nuclei output written for scan {id}: 1234 bytes at data/jobs/{id}/nuclei_output.json
INFO: Parsed 5 nuclei findings from file for scan {id}
INFO: Ingested 5 nuclei findings into DB for scan {id}
```

**Successful scan with no findings:**
```
INFO: Nuclei v3.4.10 command for scan {id}: nuclei -u ... -severity ... -jsonl -silent ...
INFO: Nuclei completed for scan {id}: exit_code=0, stdout_bytes=0, stderr_bytes=567
INFO: Nuclei scan {id} successful: no vulnerabilities found (target is clean)
INFO: Nuclei output written for scan {id}: 0 bytes at data/jobs/{id}/nuclei_output.json
INFO: Nuclei output file is empty or missing for ...; treating as no findings
INFO: Parsed 0 nuclei findings from file for scan {id}
INFO: Ingested 0 nuclei findings into DB for scan {id}
```

**Failed scan:**
```
INFO: Nuclei v3.4.10 command for scan {id}: nuclei -u ... -severity ... -jsonl -silent ...
INFO: Nuclei completed for scan {id}: exit_code=1, stdout_bytes=0, stderr_bytes=123
WARNING: Nuclei scan {id} failed: Nuclei exited with code 1. stderr: ...
```

## Troubleshooting

### Issue: File is 0 bytes but I expected findings

**Possible causes:**
1. Target genuinely has no vulnerabilities matching Nuclei templates
2. Template tags don't match target's technology stack
3. Severity filter excludes all findings

**Solutions:**
- Test with a known vulnerable target (e.g., `testphp.vulnweb.com`)
- Check Celery logs for Nuclei stderr output
- Verify Nuclei templates are up to date: `nuclei -update-templates`

### Issue: "flag provided but not defined: -json"

**Cause:** Using `-json` flag which is not supported in Nuclei v3.4.10

**Solution:** The code uses `-jsonl` which is correct. If you see this error, check that no other code paths are using `-json`.

### Issue: Findings not appearing in database

**Check:**
1. Celery logs for parsing/ingestion errors
2. Database connection and transaction commits
3. File exists and has content: `ls -lh data/jobs/{scan_id}/nuclei_output.json`
4. Parser logs: Look for "Parsed X nuclei findings" messages

## Future Enhancements

Potential improvements (not implemented yet):
- Support for pluggable scanner abstraction (to add ZAP, Wapiti, etc.)
- Template path customization per scan level
- Real-time findings streaming (WebSocket)
- Custom template repository support

## Files

- `backend/app/services/tools.py`: Nuclei command construction and execution
- `backend/app/services/scan_orchestrator.py`: Scan orchestration and file writing
- `backend/app/services/findings_ingestor.py`: Parsing and database ingestion
- `backend/test_nuclei_integration.sh`: Integration test script
- `backend/NUCLEI_INTEGRATION.md`: This documentation


