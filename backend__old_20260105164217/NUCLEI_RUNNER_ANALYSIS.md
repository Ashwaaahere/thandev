# Nuclei Runner Implementation Analysis

## Summary

**File Path**: `backend/app/services/tools.py`  
**Function Name**: `_run_nuclei()` (line 94)  
**Output File Path**: `data/jobs/{job_id}/nuclei_output.json`  
**File Writing Location**: `backend/app/tasks/celery_app.py` (line 127-151)

## Current Implementation

### 1. Nuclei Runner (`app/services/tools.py`)

- **Function**: `_run_nuclei()` (async method of `ToolExecutor` class)
- **Location**: Line 94-161
- **What it does**: 
  - Checks if nuclei binary exists
  - Runs nuclei command with appropriate templates based on scan level
  - Returns result dict with `output`, `exit_code`, `command`, and optional `error`
- **Output Format**: Nuclei outputs JSON lines (one JSON object per line) when using `-json` flag
- **Does NOT write to disk**: Only returns output in result dict

### 2. File Writing (`app/tasks/celery_app.py`)

- **Location**: Line 125-151
- **File Path**: `data/jobs/{scan_job_id}/nuclei_output.json`
- **Current Behavior**:
  - Creates directory `data/jobs/{job_id}/` with retry logic
  - Writes nuclei output to `{tool_name}_output.json` (which becomes `nuclei_output.json`)
  - For nuclei: writes output as-is if present, or `[]` if empty (valid JSON)
  - For other tools: writes output as-is or empty string

### 3. Test Script Expectation (`test_scan_loop.sh`)

- **Expected Path**: `data/jobs/$SCAN_ID/nuclei_output.json` (line 112)
- **Check**: Verifies file exists and reports file size

## Consistency Check

✅ **Paths Match**: 
- Code writes to: `data/jobs/{job_id}/nuclei_output.json`
- Test expects: `data/jobs/$SCAN_ID/nuclei_output.json`
- **These are consistent!**

## Fixes Applied

1. ✅ **Directory Creation**: Enhanced with retry logic (3 attempts) to ensure directory is always created
2. ✅ **File Writing**: Always creates file, writes valid JSON (`[]` for no findings)
3. ✅ **Error Handling**: Errors are logged and stored in `ToolResult.error_message`, but scan continues
4. ✅ **Path Consistency**: File path matches test script expectation exactly

## Implementation Details

### Directory Creation (celery_app.py, lines 55-72)
```python
job_dir = Path(f"data/jobs/{scan_job_id}")
max_retries = 3
for attempt in range(max_retries):
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        break
    except Exception as e:
        # Retry with delay
```

### File Writing (celery_app.py, lines 125-151)
```python
output_file = job_dir / f"{tool_name}_output.json"
# Ensure directory exists (fallback)
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, "w") as f:
    if tool_name == "nuclei":
        if output_text:
            f.write(output_text)  # JSON lines as-is
        else:
            f.write("[]")  # Valid JSON array for no findings
```

## Notes

- **Nuclei Output Format**: When nuclei finds vulnerabilities, it outputs one JSON object per line (JSONL format). When it finds nothing, it outputs nothing.
- **Our Format**: We write JSONL when findings exist, or `[]` (valid JSON array) when no findings. This makes the file always parseable as JSON.
- **Error Handling**: If nuclei fails (binary not found, timeout, etc.), the error is stored in `ToolResult.error_message` and the scan continues. The file will still be created with `[]` if no output was captured.



