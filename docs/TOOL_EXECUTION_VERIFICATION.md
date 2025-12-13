# Tool Execution Verification Guide

**Purpose**: Verify that Nuclei, Nmap, and SSLScan are actually firing during scans

---

## Quick Reality Check

Based on code analysis, here's what **should** be happening:

### ✅ Expected Behavior

1. **Scan Profiles** (`backend/app/services/scan_profiles.py`):
   - **Basic**: Only `nuclei`
   - **Pro**: `nuclei` + `nmap`
   - **Advanced**: `nuclei` + `nmap` + `sslscan`

2. **Tool Execution** (`backend/app/services/scan_orchestrator.py`):
   - Tools are executed based on scan profile
   - Each tool execution creates a `ToolResult` record in database
   - Each tool execution writes output to `data/jobs/{job_id}/{tool}_output.json`

3. **Database Storage**:
   - `tool_results` table stores: `tool_name`, `exit_code`, `output`, `command`, `error_message`
   - Location: `backend/app/models/finding.py:76-101`

4. **File Storage**:
   - Output files written to: `data/jobs/{scan_job_id}/{tool_name}_output.json`
   - Location: `backend/app/services/scan_orchestrator.py:280`

---

## Verification Methods

### Method A: Check `tool_results` Table

**SQL Query**:
```sql
SELECT 
    tool_name,
    exit_code,
    LENGTH(output) AS output_bytes,
    execution_time,
    error_message,
    created_at
FROM tool_results
WHERE scan_job_id = '<scan_job_id>'
ORDER BY created_at ASC;
```

**Expected Results**:
- **Basic scan**: 1 row (nuclei)
- **Pro scan**: 2 rows (nuclei, nmap)
- **Advanced scan**: 3 rows (nuclei, nmap, sslscan)

**If you only see `nmap` rows**: Nuclei/SSLScan aren't being queued for that scan level.

### Method B: Check Output Files

**Command**:
```bash
cd /app/data/jobs/<scan_job_id>
ls -lh
```

**Expected Files**:
- **Basic**: `nuclei_output.json`
- **Pro**: `nuclei_output.json`, `nmap_output.json`
- **Advanced**: `nuclei_output.json`, `nmap_output.json`, `sslscan_output.json`

**If you only see `nmap_output.json`**: Other tools didn't execute.

---

## Automated Diagnostic Script

A diagnostic script has been created to automate these checks:

**Location**: `backend/check_tool_execution.py`

### Usage

#### Check a specific scan:
```bash
cd backend
python check_tool_execution.py <scan_job_id>
```

#### Check latest completed scan:
```bash
python check_tool_execution.py --latest
```

#### Check all recent scans:
```bash
python check_tool_execution.py --all
```

### What It Checks

1. **Scan Job Details**:
   - Status, level, timestamps
   - Error messages (if any)

2. **Database (`tool_results` table)**:
   - Which tools executed
   - Exit codes
   - Output sizes
   - Execution times
   - Errors
   - Compares against expected tools for scan level

3. **Output Files**:
   - Which files exist in `data/jobs/{scan_job_id}/`
   - File sizes
   - Preview of first line (for nuclei)

4. **Summary**:
   - ✅ All tools executed correctly
   - ⚠️ Partial execution (some tools missing)
   - ❌ No tool execution detected

### Example Output

```
============================================================
SCAN JOB DETAILS
============================================================

ID:          abc123...
Status:      completed
Level:       pro
Created:     2025-01-29 10:00:00
Started:     2025-01-29 10:00:05
Completed:   2025-01-29 10:05:30
Project ID:  xyz789...

============================================================
CHECKING tool_results TABLE FOR SCAN: abc123...
============================================================

✅ Found 2 tool execution(s):

Tool        Exit Code    Output Size      Time (s)      Error               
--------------------------------------------------------------------------------
✅ nuclei       0           12345           45.23                        
✅ nmap         0           5678            120.45                       

--------------------------------------------------------------------------------
Tools executed: nmap, nuclei
Expected tools (pro): nmap, nuclei

✅ All expected tools executed!

============================================================
CHECKING OUTPUT FILES FOR SCAN: abc123...
============================================================

✅ Directory exists: data/jobs/abc123...

✅ nuclei_output.json     12345 bytes
✅ nmap_output.json       5678 bytes
❌ sslscan_output.json    NOT FOUND

Files found: 2/3

============================================================
SUMMARY
============================================================

✅ All tools executed and output files created
```

---

## Code Flow Verification

### Where Tools Are Executed

**File**: `backend/app/services/scan_orchestrator.py`

**Function**: `run_scan_for_job(job: ScanJob)`

**Flow**:
1. Get scan profile for scan level (line 105)
2. Create job directory: `data/jobs/{job_id}/` (line 200)
3. For each tool in profile (line 242):
   - Execute tool via `ToolExecutor.run_tool()` (line 252)
   - Save `ToolResult` to database (line 267)
   - Write output to file: `{tool_name}_output.json` (line 280)
   - Parse findings (lines 316-330)

### Tool Execution Logic

**File**: `backend/app/services/tools.py`

**Class**: `ToolExecutor`

**Methods**:
- `_run_nuclei()`: Executes Nuclei scanner
- `_run_nmap()`: Executes Nmap port scanner
- `_run_sslscan()`: Executes SSLScan TLS analyzer

**All tools are async and called via**:
```python
result = loop.run_until_complete(
    executor.run_tool(tool_name, target_url, scan_level, **kwargs)
)
```

---

## Common Issues & Solutions

### Issue 1: Only Nmap Executes

**Symptoms**:
- `tool_results` table only has `nmap` rows
- Only `nmap_output.json` exists

**Possible Causes**:
1. **Wrong scan level**: Check if scan was created with correct level
2. **Profile not loaded**: Check logs for "Retrieved profile for scan level"
3. **Tool execution failed silently**: Check `error_message` in `tool_results`

**Solution**:
```bash
# Check scan level
SELECT id, scan_level, status FROM scan_jobs WHERE id = '<scan_id>';

# Check tool results with errors
SELECT tool_name, exit_code, error_message 
FROM tool_results 
WHERE scan_job_id = '<scan_id>' AND error_message IS NOT NULL;
```

### Issue 2: Tools Execute But No Output Files

**Symptoms**:
- `tool_results` has rows
- No files in `data/jobs/{job_id}/`

**Possible Causes**:
1. **Directory creation failed**: Check logs for "Failed to create job directory"
2. **File write permissions**: Check if `data/jobs/` is writable
3. **Path issues**: Verify working directory

**Solution**:
```bash
# Check directory exists
ls -la data/jobs/

# Check permissions
ls -ld data/jobs/

# Check if directory was created for this scan
ls -la data/jobs/<scan_id>/
```

### Issue 3: Tools Fail with Errors

**Symptoms**:
- `exit_code != 0` in `tool_results`
- `error_message` populated

**Common Errors**:
- **Nuclei**: "Nuclei binary not found" → Install nuclei
- **Nmap**: "nmap: command not found" → Install nmap
- **SSLScan**: "sslscan not found" → Falls back to openssl

**Solution**:
```bash
# Check which tools are installed
which nuclei
which nmap
which sslscan

# Check tool versions
nuclei -version
nmap --version
sslscan --version
```

---

## Expected Tool Output Formats

### Nuclei
- **Format**: JSONL (one JSON object per line)
- **File**: `nuclei_output.json`
- **Example**:
```json
{"template-id":"CVE-2024-XXXX","info":{"name":"Vulnerability Name"},"matched-at":"https://example.com/path"}
```

### Nmap
- **Format**: XML
- **File**: `nmap_output.json` (despite .json extension, contains XML)
- **Example**:
```xml
<?xml version="1.0"?>
<nmaprun>
  <host>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
      </port>
    </ports>
  </host>
</nmaprun>
```

### SSLScan
- **Format**: JSON
- **File**: `sslscan_output.json`
- **Example**:
```json
{
  "host": "example.com",
  "port": 443,
  "ssl_version": "TLSv1.2"
}
```

---

## Quick Verification Checklist

For a completed scan, verify:

- [ ] Scan status is `completed`
- [ ] `tool_results` table has rows for expected tools
- [ ] All expected tools have `exit_code = 0`
- [ ] Output files exist in `data/jobs/{scan_id}/`
- [ ] Output files have content (size > 0)
- [ ] Findings were created in `findings` table
- [ ] No error messages in `tool_results.error_message`

---

## Next Steps

If tools are **NOT** executing:

1. **Check scan level**: Verify scan was created with correct level
2. **Check logs**: Look for tool execution logs in Celery worker output
3. **Check profile**: Verify `get_profile(scan_level)` returns correct tools
4. **Check tool availability**: Ensure tools are installed and in PATH
5. **Run diagnostic script**: Use `check_tool_execution.py` for automated analysis

If tools **ARE** executing but no findings:

1. **Check output files**: Verify files have content
2. **Check parsing**: Verify findings ingestor is parsing output correctly
3. **Check target**: Verify target URL is accessible and has vulnerabilities
4. **Check tool output**: Manually inspect output files for valid data

---

## Summary

**Code Analysis Confirms**:
- ✅ Tools are configured in scan profiles
- ✅ Tools are executed in orchestrator
- ✅ Results are saved to database (`tool_results` table)
- ✅ Output files are written to `data/jobs/{job_id}/`

**To Verify in Production**:
1. Run a scan (basic, pro, or advanced)
2. Wait for completion
3. Run diagnostic script: `python check_tool_execution.py --latest`
4. Review output for any missing tools or errors

**If issues found**:
- Check scan level matches expected tools
- Check tool installation and PATH
- Check logs for execution errors
- Check file system permissions

---

*Last Updated: January 2025*





**Purpose**: Verify that Nuclei, Nmap, and SSLScan are actually firing during scans

---

## Quick Reality Check

Based on code analysis, here's what **should** be happening:

### ✅ Expected Behavior

1. **Scan Profiles** (`backend/app/services/scan_profiles.py`):
   - **Basic**: Only `nuclei`
   - **Pro**: `nuclei` + `nmap`
   - **Advanced**: `nuclei` + `nmap` + `sslscan`

2. **Tool Execution** (`backend/app/services/scan_orchestrator.py`):
   - Tools are executed based on scan profile
   - Each tool execution creates a `ToolResult` record in database
   - Each tool execution writes output to `data/jobs/{job_id}/{tool}_output.json`

3. **Database Storage**:
   - `tool_results` table stores: `tool_name`, `exit_code`, `output`, `command`, `error_message`
   - Location: `backend/app/models/finding.py:76-101`

4. **File Storage**:
   - Output files written to: `data/jobs/{scan_job_id}/{tool_name}_output.json`
   - Location: `backend/app/services/scan_orchestrator.py:280`

---

## Verification Methods

### Method A: Check `tool_results` Table

**SQL Query**:
```sql
SELECT 
    tool_name,
    exit_code,
    LENGTH(output) AS output_bytes,
    execution_time,
    error_message,
    created_at
FROM tool_results
WHERE scan_job_id = '<scan_job_id>'
ORDER BY created_at ASC;
```

**Expected Results**:
- **Basic scan**: 1 row (nuclei)
- **Pro scan**: 2 rows (nuclei, nmap)
- **Advanced scan**: 3 rows (nuclei, nmap, sslscan)

**If you only see `nmap` rows**: Nuclei/SSLScan aren't being queued for that scan level.

### Method B: Check Output Files

**Command**:
```bash
cd /app/data/jobs/<scan_job_id>
ls -lh
```

**Expected Files**:
- **Basic**: `nuclei_output.json`
- **Pro**: `nuclei_output.json`, `nmap_output.json`
- **Advanced**: `nuclei_output.json`, `nmap_output.json`, `sslscan_output.json`

**If you only see `nmap_output.json`**: Other tools didn't execute.

---

## Automated Diagnostic Script

A diagnostic script has been created to automate these checks:

**Location**: `backend/check_tool_execution.py`

### Usage

#### Check a specific scan:
```bash
cd backend
python check_tool_execution.py <scan_job_id>
```

#### Check latest completed scan:
```bash
python check_tool_execution.py --latest
```

#### Check all recent scans:
```bash
python check_tool_execution.py --all
```

### What It Checks

1. **Scan Job Details**:
   - Status, level, timestamps
   - Error messages (if any)

2. **Database (`tool_results` table)**:
   - Which tools executed
   - Exit codes
   - Output sizes
   - Execution times
   - Errors
   - Compares against expected tools for scan level

3. **Output Files**:
   - Which files exist in `data/jobs/{scan_job_id}/`
   - File sizes
   - Preview of first line (for nuclei)

4. **Summary**:
   - ✅ All tools executed correctly
   - ⚠️ Partial execution (some tools missing)
   - ❌ No tool execution detected

### Example Output

```
============================================================
SCAN JOB DETAILS
============================================================

ID:          abc123...
Status:      completed
Level:       pro
Created:     2025-01-29 10:00:00
Started:     2025-01-29 10:00:05
Completed:   2025-01-29 10:05:30
Project ID:  xyz789...

============================================================
CHECKING tool_results TABLE FOR SCAN: abc123...
============================================================

✅ Found 2 tool execution(s):

Tool        Exit Code    Output Size      Time (s)      Error               
--------------------------------------------------------------------------------
✅ nuclei       0           12345           45.23                        
✅ nmap         0           5678            120.45                       

--------------------------------------------------------------------------------
Tools executed: nmap, nuclei
Expected tools (pro): nmap, nuclei

✅ All expected tools executed!

============================================================
CHECKING OUTPUT FILES FOR SCAN: abc123...
============================================================

✅ Directory exists: data/jobs/abc123...

✅ nuclei_output.json     12345 bytes
✅ nmap_output.json       5678 bytes
❌ sslscan_output.json    NOT FOUND

Files found: 2/3

============================================================
SUMMARY
============================================================

✅ All tools executed and output files created
```

---

## Code Flow Verification

### Where Tools Are Executed

**File**: `backend/app/services/scan_orchestrator.py`

**Function**: `run_scan_for_job(job: ScanJob)`

**Flow**:
1. Get scan profile for scan level (line 105)
2. Create job directory: `data/jobs/{job_id}/` (line 200)
3. For each tool in profile (line 242):
   - Execute tool via `ToolExecutor.run_tool()` (line 252)
   - Save `ToolResult` to database (line 267)
   - Write output to file: `{tool_name}_output.json` (line 280)
   - Parse findings (lines 316-330)

### Tool Execution Logic

**File**: `backend/app/services/tools.py`

**Class**: `ToolExecutor`

**Methods**:
- `_run_nuclei()`: Executes Nuclei scanner
- `_run_nmap()`: Executes Nmap port scanner
- `_run_sslscan()`: Executes SSLScan TLS analyzer

**All tools are async and called via**:
```python
result = loop.run_until_complete(
    executor.run_tool(tool_name, target_url, scan_level, **kwargs)
)
```

---

## Common Issues & Solutions

### Issue 1: Only Nmap Executes

**Symptoms**:
- `tool_results` table only has `nmap` rows
- Only `nmap_output.json` exists

**Possible Causes**:
1. **Wrong scan level**: Check if scan was created with correct level
2. **Profile not loaded**: Check logs for "Retrieved profile for scan level"
3. **Tool execution failed silently**: Check `error_message` in `tool_results`

**Solution**:
```bash
# Check scan level
SELECT id, scan_level, status FROM scan_jobs WHERE id = '<scan_id>';

# Check tool results with errors
SELECT tool_name, exit_code, error_message 
FROM tool_results 
WHERE scan_job_id = '<scan_id>' AND error_message IS NOT NULL;
```

### Issue 2: Tools Execute But No Output Files

**Symptoms**:
- `tool_results` has rows
- No files in `data/jobs/{job_id}/`

**Possible Causes**:
1. **Directory creation failed**: Check logs for "Failed to create job directory"
2. **File write permissions**: Check if `data/jobs/` is writable
3. **Path issues**: Verify working directory

**Solution**:
```bash
# Check directory exists
ls -la data/jobs/

# Check permissions
ls -ld data/jobs/

# Check if directory was created for this scan
ls -la data/jobs/<scan_id>/
```

### Issue 3: Tools Fail with Errors

**Symptoms**:
- `exit_code != 0` in `tool_results`
- `error_message` populated

**Common Errors**:
- **Nuclei**: "Nuclei binary not found" → Install nuclei
- **Nmap**: "nmap: command not found" → Install nmap
- **SSLScan**: "sslscan not found" → Falls back to openssl

**Solution**:
```bash
# Check which tools are installed
which nuclei
which nmap
which sslscan

# Check tool versions
nuclei -version
nmap --version
sslscan --version
```

---

## Expected Tool Output Formats

### Nuclei
- **Format**: JSONL (one JSON object per line)
- **File**: `nuclei_output.json`
- **Example**:
```json
{"template-id":"CVE-2024-XXXX","info":{"name":"Vulnerability Name"},"matched-at":"https://example.com/path"}
```

### Nmap
- **Format**: XML
- **File**: `nmap_output.json` (despite .json extension, contains XML)
- **Example**:
```xml
<?xml version="1.0"?>
<nmaprun>
  <host>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
      </port>
    </ports>
  </host>
</nmaprun>
```

### SSLScan
- **Format**: JSON
- **File**: `sslscan_output.json`
- **Example**:
```json
{
  "host": "example.com",
  "port": 443,
  "ssl_version": "TLSv1.2"
}
```

---

## Quick Verification Checklist

For a completed scan, verify:

- [ ] Scan status is `completed`
- [ ] `tool_results` table has rows for expected tools
- [ ] All expected tools have `exit_code = 0`
- [ ] Output files exist in `data/jobs/{scan_id}/`
- [ ] Output files have content (size > 0)
- [ ] Findings were created in `findings` table
- [ ] No error messages in `tool_results.error_message`

---

## Next Steps

If tools are **NOT** executing:

1. **Check scan level**: Verify scan was created with correct level
2. **Check logs**: Look for tool execution logs in Celery worker output
3. **Check profile**: Verify `get_profile(scan_level)` returns correct tools
4. **Check tool availability**: Ensure tools are installed and in PATH
5. **Run diagnostic script**: Use `check_tool_execution.py` for automated analysis

If tools **ARE** executing but no findings:

1. **Check output files**: Verify files have content
2. **Check parsing**: Verify findings ingestor is parsing output correctly
3. **Check target**: Verify target URL is accessible and has vulnerabilities
4. **Check tool output**: Manually inspect output files for valid data

---

## Summary

**Code Analysis Confirms**:
- ✅ Tools are configured in scan profiles
- ✅ Tools are executed in orchestrator
- ✅ Results are saved to database (`tool_results` table)
- ✅ Output files are written to `data/jobs/{job_id}/`

**To Verify in Production**:
1. Run a scan (basic, pro, or advanced)
2. Wait for completion
3. Run diagnostic script: `python check_tool_execution.py --latest`
4. Review output for any missing tools or errors

**If issues found**:
- Check scan level matches expected tools
- Check tool installation and PATH
- Check logs for execution errors
- Check file system permissions

---

*Last Updated: January 2025*





**Purpose**: Verify that Nuclei, Nmap, and SSLScan are actually firing during scans

---

## Quick Reality Check

Based on code analysis, here's what **should** be happening:

### ✅ Expected Behavior

1. **Scan Profiles** (`backend/app/services/scan_profiles.py`):
   - **Basic**: Only `nuclei`
   - **Pro**: `nuclei` + `nmap`
   - **Advanced**: `nuclei` + `nmap` + `sslscan`

2. **Tool Execution** (`backend/app/services/scan_orchestrator.py`):
   - Tools are executed based on scan profile
   - Each tool execution creates a `ToolResult` record in database
   - Each tool execution writes output to `data/jobs/{job_id}/{tool}_output.json`

3. **Database Storage**:
   - `tool_results` table stores: `tool_name`, `exit_code`, `output`, `command`, `error_message`
   - Location: `backend/app/models/finding.py:76-101`

4. **File Storage**:
   - Output files written to: `data/jobs/{scan_job_id}/{tool_name}_output.json`
   - Location: `backend/app/services/scan_orchestrator.py:280`

---

## Verification Methods

### Method A: Check `tool_results` Table

**SQL Query**:
```sql
SELECT 
    tool_name,
    exit_code,
    LENGTH(output) AS output_bytes,
    execution_time,
    error_message,
    created_at
FROM tool_results
WHERE scan_job_id = '<scan_job_id>'
ORDER BY created_at ASC;
```

**Expected Results**:
- **Basic scan**: 1 row (nuclei)
- **Pro scan**: 2 rows (nuclei, nmap)
- **Advanced scan**: 3 rows (nuclei, nmap, sslscan)

**If you only see `nmap` rows**: Nuclei/SSLScan aren't being queued for that scan level.

### Method B: Check Output Files

**Command**:
```bash
cd /app/data/jobs/<scan_job_id>
ls -lh
```

**Expected Files**:
- **Basic**: `nuclei_output.json`
- **Pro**: `nuclei_output.json`, `nmap_output.json`
- **Advanced**: `nuclei_output.json`, `nmap_output.json`, `sslscan_output.json`

**If you only see `nmap_output.json`**: Other tools didn't execute.

---

## Automated Diagnostic Script

A diagnostic script has been created to automate these checks:

**Location**: `backend/check_tool_execution.py`

### Usage

#### Check a specific scan:
```bash
cd backend
python check_tool_execution.py <scan_job_id>
```

#### Check latest completed scan:
```bash
python check_tool_execution.py --latest
```

#### Check all recent scans:
```bash
python check_tool_execution.py --all
```

### What It Checks

1. **Scan Job Details**:
   - Status, level, timestamps
   - Error messages (if any)

2. **Database (`tool_results` table)**:
   - Which tools executed
   - Exit codes
   - Output sizes
   - Execution times
   - Errors
   - Compares against expected tools for scan level

3. **Output Files**:
   - Which files exist in `data/jobs/{scan_job_id}/`
   - File sizes
   - Preview of first line (for nuclei)

4. **Summary**:
   - ✅ All tools executed correctly
   - ⚠️ Partial execution (some tools missing)
   - ❌ No tool execution detected

### Example Output

```
============================================================
SCAN JOB DETAILS
============================================================

ID:          abc123...
Status:      completed
Level:       pro
Created:     2025-01-29 10:00:00
Started:     2025-01-29 10:00:05
Completed:   2025-01-29 10:05:30
Project ID:  xyz789...

============================================================
CHECKING tool_results TABLE FOR SCAN: abc123...
============================================================

✅ Found 2 tool execution(s):

Tool        Exit Code    Output Size      Time (s)      Error               
--------------------------------------------------------------------------------
✅ nuclei       0           12345           45.23                        
✅ nmap         0           5678            120.45                       

--------------------------------------------------------------------------------
Tools executed: nmap, nuclei
Expected tools (pro): nmap, nuclei

✅ All expected tools executed!

============================================================
CHECKING OUTPUT FILES FOR SCAN: abc123...
============================================================

✅ Directory exists: data/jobs/abc123...

✅ nuclei_output.json     12345 bytes
✅ nmap_output.json       5678 bytes
❌ sslscan_output.json    NOT FOUND

Files found: 2/3

============================================================
SUMMARY
============================================================

✅ All tools executed and output files created
```

---

## Code Flow Verification

### Where Tools Are Executed

**File**: `backend/app/services/scan_orchestrator.py`

**Function**: `run_scan_for_job(job: ScanJob)`

**Flow**:
1. Get scan profile for scan level (line 105)
2. Create job directory: `data/jobs/{job_id}/` (line 200)
3. For each tool in profile (line 242):
   - Execute tool via `ToolExecutor.run_tool()` (line 252)
   - Save `ToolResult` to database (line 267)
   - Write output to file: `{tool_name}_output.json` (line 280)
   - Parse findings (lines 316-330)

### Tool Execution Logic

**File**: `backend/app/services/tools.py`

**Class**: `ToolExecutor`

**Methods**:
- `_run_nuclei()`: Executes Nuclei scanner
- `_run_nmap()`: Executes Nmap port scanner
- `_run_sslscan()`: Executes SSLScan TLS analyzer

**All tools are async and called via**:
```python
result = loop.run_until_complete(
    executor.run_tool(tool_name, target_url, scan_level, **kwargs)
)
```

---

## Common Issues & Solutions

### Issue 1: Only Nmap Executes

**Symptoms**:
- `tool_results` table only has `nmap` rows
- Only `nmap_output.json` exists

**Possible Causes**:
1. **Wrong scan level**: Check if scan was created with correct level
2. **Profile not loaded**: Check logs for "Retrieved profile for scan level"
3. **Tool execution failed silently**: Check `error_message` in `tool_results`

**Solution**:
```bash
# Check scan level
SELECT id, scan_level, status FROM scan_jobs WHERE id = '<scan_id>';

# Check tool results with errors
SELECT tool_name, exit_code, error_message 
FROM tool_results 
WHERE scan_job_id = '<scan_id>' AND error_message IS NOT NULL;
```

### Issue 2: Tools Execute But No Output Files

**Symptoms**:
- `tool_results` has rows
- No files in `data/jobs/{job_id}/`

**Possible Causes**:
1. **Directory creation failed**: Check logs for "Failed to create job directory"
2. **File write permissions**: Check if `data/jobs/` is writable
3. **Path issues**: Verify working directory

**Solution**:
```bash
# Check directory exists
ls -la data/jobs/

# Check permissions
ls -ld data/jobs/

# Check if directory was created for this scan
ls -la data/jobs/<scan_id>/
```

### Issue 3: Tools Fail with Errors

**Symptoms**:
- `exit_code != 0` in `tool_results`
- `error_message` populated

**Common Errors**:
- **Nuclei**: "Nuclei binary not found" → Install nuclei
- **Nmap**: "nmap: command not found" → Install nmap
- **SSLScan**: "sslscan not found" → Falls back to openssl

**Solution**:
```bash
# Check which tools are installed
which nuclei
which nmap
which sslscan

# Check tool versions
nuclei -version
nmap --version
sslscan --version
```

---

## Expected Tool Output Formats

### Nuclei
- **Format**: JSONL (one JSON object per line)
- **File**: `nuclei_output.json`
- **Example**:
```json
{"template-id":"CVE-2024-XXXX","info":{"name":"Vulnerability Name"},"matched-at":"https://example.com/path"}
```

### Nmap
- **Format**: XML
- **File**: `nmap_output.json` (despite .json extension, contains XML)
- **Example**:
```xml
<?xml version="1.0"?>
<nmaprun>
  <host>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
      </port>
    </ports>
  </host>
</nmaprun>
```

### SSLScan
- **Format**: JSON
- **File**: `sslscan_output.json`
- **Example**:
```json
{
  "host": "example.com",
  "port": 443,
  "ssl_version": "TLSv1.2"
}
```

---

## Quick Verification Checklist

For a completed scan, verify:

- [ ] Scan status is `completed`
- [ ] `tool_results` table has rows for expected tools
- [ ] All expected tools have `exit_code = 0`
- [ ] Output files exist in `data/jobs/{scan_id}/`
- [ ] Output files have content (size > 0)
- [ ] Findings were created in `findings` table
- [ ] No error messages in `tool_results.error_message`

---

## Next Steps

If tools are **NOT** executing:

1. **Check scan level**: Verify scan was created with correct level
2. **Check logs**: Look for tool execution logs in Celery worker output
3. **Check profile**: Verify `get_profile(scan_level)` returns correct tools
4. **Check tool availability**: Ensure tools are installed and in PATH
5. **Run diagnostic script**: Use `check_tool_execution.py` for automated analysis

If tools **ARE** executing but no findings:

1. **Check output files**: Verify files have content
2. **Check parsing**: Verify findings ingestor is parsing output correctly
3. **Check target**: Verify target URL is accessible and has vulnerabilities
4. **Check tool output**: Manually inspect output files for valid data

---

## Summary

**Code Analysis Confirms**:
- ✅ Tools are configured in scan profiles
- ✅ Tools are executed in orchestrator
- ✅ Results are saved to database (`tool_results` table)
- ✅ Output files are written to `data/jobs/{job_id}/`

**To Verify in Production**:
1. Run a scan (basic, pro, or advanced)
2. Wait for completion
3. Run diagnostic script: `python check_tool_execution.py --latest`
4. Review output for any missing tools or errors

**If issues found**:
- Check scan level matches expected tools
- Check tool installation and PATH
- Check logs for execution errors
- Check file system permissions

---

*Last Updated: January 2025*





**Purpose**: Verify that Nuclei, Nmap, and SSLScan are actually firing during scans

---

## Quick Reality Check

Based on code analysis, here's what **should** be happening:

### ✅ Expected Behavior

1. **Scan Profiles** (`backend/app/services/scan_profiles.py`):
   - **Basic**: Only `nuclei`
   - **Pro**: `nuclei` + `nmap`
   - **Advanced**: `nuclei` + `nmap` + `sslscan`

2. **Tool Execution** (`backend/app/services/scan_orchestrator.py`):
   - Tools are executed based on scan profile
   - Each tool execution creates a `ToolResult` record in database
   - Each tool execution writes output to `data/jobs/{job_id}/{tool}_output.json`

3. **Database Storage**:
   - `tool_results` table stores: `tool_name`, `exit_code`, `output`, `command`, `error_message`
   - Location: `backend/app/models/finding.py:76-101`

4. **File Storage**:
   - Output files written to: `data/jobs/{scan_job_id}/{tool_name}_output.json`
   - Location: `backend/app/services/scan_orchestrator.py:280`

---

## Verification Methods

### Method A: Check `tool_results` Table

**SQL Query**:
```sql
SELECT 
    tool_name,
    exit_code,
    LENGTH(output) AS output_bytes,
    execution_time,
    error_message,
    created_at
FROM tool_results
WHERE scan_job_id = '<scan_job_id>'
ORDER BY created_at ASC;
```

**Expected Results**:
- **Basic scan**: 1 row (nuclei)
- **Pro scan**: 2 rows (nuclei, nmap)
- **Advanced scan**: 3 rows (nuclei, nmap, sslscan)

**If you only see `nmap` rows**: Nuclei/SSLScan aren't being queued for that scan level.

### Method B: Check Output Files

**Command**:
```bash
cd /app/data/jobs/<scan_job_id>
ls -lh
```

**Expected Files**:
- **Basic**: `nuclei_output.json`
- **Pro**: `nuclei_output.json`, `nmap_output.json`
- **Advanced**: `nuclei_output.json`, `nmap_output.json`, `sslscan_output.json`

**If you only see `nmap_output.json`**: Other tools didn't execute.

---

## Automated Diagnostic Script

A diagnostic script has been created to automate these checks:

**Location**: `backend/check_tool_execution.py`

### Usage

#### Check a specific scan:
```bash
cd backend
python check_tool_execution.py <scan_job_id>
```

#### Check latest completed scan:
```bash
python check_tool_execution.py --latest
```

#### Check all recent scans:
```bash
python check_tool_execution.py --all
```

### What It Checks

1. **Scan Job Details**:
   - Status, level, timestamps
   - Error messages (if any)

2. **Database (`tool_results` table)**:
   - Which tools executed
   - Exit codes
   - Output sizes
   - Execution times
   - Errors
   - Compares against expected tools for scan level

3. **Output Files**:
   - Which files exist in `data/jobs/{scan_job_id}/`
   - File sizes
   - Preview of first line (for nuclei)

4. **Summary**:
   - ✅ All tools executed correctly
   - ⚠️ Partial execution (some tools missing)
   - ❌ No tool execution detected

### Example Output

```
============================================================
SCAN JOB DETAILS
============================================================

ID:          abc123...
Status:      completed
Level:       pro
Created:     2025-01-29 10:00:00
Started:     2025-01-29 10:00:05
Completed:   2025-01-29 10:05:30
Project ID:  xyz789...

============================================================
CHECKING tool_results TABLE FOR SCAN: abc123...
============================================================

✅ Found 2 tool execution(s):

Tool        Exit Code    Output Size      Time (s)      Error               
--------------------------------------------------------------------------------
✅ nuclei       0           12345           45.23                        
✅ nmap         0           5678            120.45                       

--------------------------------------------------------------------------------
Tools executed: nmap, nuclei
Expected tools (pro): nmap, nuclei

✅ All expected tools executed!

============================================================
CHECKING OUTPUT FILES FOR SCAN: abc123...
============================================================

✅ Directory exists: data/jobs/abc123...

✅ nuclei_output.json     12345 bytes
✅ nmap_output.json       5678 bytes
❌ sslscan_output.json    NOT FOUND

Files found: 2/3

============================================================
SUMMARY
============================================================

✅ All tools executed and output files created
```

---

## Code Flow Verification

### Where Tools Are Executed

**File**: `backend/app/services/scan_orchestrator.py`

**Function**: `run_scan_for_job(job: ScanJob)`

**Flow**:
1. Get scan profile for scan level (line 105)
2. Create job directory: `data/jobs/{job_id}/` (line 200)
3. For each tool in profile (line 242):
   - Execute tool via `ToolExecutor.run_tool()` (line 252)
   - Save `ToolResult` to database (line 267)
   - Write output to file: `{tool_name}_output.json` (line 280)
   - Parse findings (lines 316-330)

### Tool Execution Logic

**File**: `backend/app/services/tools.py`

**Class**: `ToolExecutor`

**Methods**:
- `_run_nuclei()`: Executes Nuclei scanner
- `_run_nmap()`: Executes Nmap port scanner
- `_run_sslscan()`: Executes SSLScan TLS analyzer

**All tools are async and called via**:
```python
result = loop.run_until_complete(
    executor.run_tool(tool_name, target_url, scan_level, **kwargs)
)
```

---

## Common Issues & Solutions

### Issue 1: Only Nmap Executes

**Symptoms**:
- `tool_results` table only has `nmap` rows
- Only `nmap_output.json` exists

**Possible Causes**:
1. **Wrong scan level**: Check if scan was created with correct level
2. **Profile not loaded**: Check logs for "Retrieved profile for scan level"
3. **Tool execution failed silently**: Check `error_message` in `tool_results`

**Solution**:
```bash
# Check scan level
SELECT id, scan_level, status FROM scan_jobs WHERE id = '<scan_id>';

# Check tool results with errors
SELECT tool_name, exit_code, error_message 
FROM tool_results 
WHERE scan_job_id = '<scan_id>' AND error_message IS NOT NULL;
```

### Issue 2: Tools Execute But No Output Files

**Symptoms**:
- `tool_results` has rows
- No files in `data/jobs/{job_id}/`

**Possible Causes**:
1. **Directory creation failed**: Check logs for "Failed to create job directory"
2. **File write permissions**: Check if `data/jobs/` is writable
3. **Path issues**: Verify working directory

**Solution**:
```bash
# Check directory exists
ls -la data/jobs/

# Check permissions
ls -ld data/jobs/

# Check if directory was created for this scan
ls -la data/jobs/<scan_id>/
```

### Issue 3: Tools Fail with Errors

**Symptoms**:
- `exit_code != 0` in `tool_results`
- `error_message` populated

**Common Errors**:
- **Nuclei**: "Nuclei binary not found" → Install nuclei
- **Nmap**: "nmap: command not found" → Install nmap
- **SSLScan**: "sslscan not found" → Falls back to openssl

**Solution**:
```bash
# Check which tools are installed
which nuclei
which nmap
which sslscan

# Check tool versions
nuclei -version
nmap --version
sslscan --version
```

---

## Expected Tool Output Formats

### Nuclei
- **Format**: JSONL (one JSON object per line)
- **File**: `nuclei_output.json`
- **Example**:
```json
{"template-id":"CVE-2024-XXXX","info":{"name":"Vulnerability Name"},"matched-at":"https://example.com/path"}
```

### Nmap
- **Format**: XML
- **File**: `nmap_output.json` (despite .json extension, contains XML)
- **Example**:
```xml
<?xml version="1.0"?>
<nmaprun>
  <host>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
      </port>
    </ports>
  </host>
</nmaprun>
```

### SSLScan
- **Format**: JSON
- **File**: `sslscan_output.json`
- **Example**:
```json
{
  "host": "example.com",
  "port": 443,
  "ssl_version": "TLSv1.2"
}
```

---

## Quick Verification Checklist

For a completed scan, verify:

- [ ] Scan status is `completed`
- [ ] `tool_results` table has rows for expected tools
- [ ] All expected tools have `exit_code = 0`
- [ ] Output files exist in `data/jobs/{scan_id}/`
- [ ] Output files have content (size > 0)
- [ ] Findings were created in `findings` table
- [ ] No error messages in `tool_results.error_message`

---

## Next Steps

If tools are **NOT** executing:

1. **Check scan level**: Verify scan was created with correct level
2. **Check logs**: Look for tool execution logs in Celery worker output
3. **Check profile**: Verify `get_profile(scan_level)` returns correct tools
4. **Check tool availability**: Ensure tools are installed and in PATH
5. **Run diagnostic script**: Use `check_tool_execution.py` for automated analysis

If tools **ARE** executing but no findings:

1. **Check output files**: Verify files have content
2. **Check parsing**: Verify findings ingestor is parsing output correctly
3. **Check target**: Verify target URL is accessible and has vulnerabilities
4. **Check tool output**: Manually inspect output files for valid data

---

## Summary

**Code Analysis Confirms**:
- ✅ Tools are configured in scan profiles
- ✅ Tools are executed in orchestrator
- ✅ Results are saved to database (`tool_results` table)
- ✅ Output files are written to `data/jobs/{job_id}/`

**To Verify in Production**:
1. Run a scan (basic, pro, or advanced)
2. Wait for completion
3. Run diagnostic script: `python check_tool_execution.py --latest`
4. Review output for any missing tools or errors

**If issues found**:
- Check scan level matches expected tools
- Check tool installation and PATH
- Check logs for execution errors
- Check file system permissions

---

*Last Updated: January 2025*





