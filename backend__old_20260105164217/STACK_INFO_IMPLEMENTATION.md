# Stack Info Implementation Summary

## Overview

Added a lightweight `stack_info` field to `ScanJob` to collect metadata about the target for future AI planning. This information is gathered before running scan tools and stored in the database.

## Changes Made

### 1. Database Model (`app/models/scan.py`)

**Added column:**
```python
# Stack information for AI planning (lightweight metadata about target)
stack_info = Column(JSON, nullable=True)
```

- Type: `JSON` (nullable)
- Purpose: Store lightweight metadata about the target for AI planning
- Location: Added after `summary` column, before `error_message`

### 2. API Schema (`app/schemas/scan.py`)

**Updated `ScanResponse` schema:**
```python
stack_info: Optional[Dict[str, Any]] = None
```

- Optional field that will be included in GET `/api/scans/{id}` responses
- Returns `None` if not set, or a dictionary with stack information

### 3. Orchestrator Logic (`app/services/scan_orchestrator.py`)

**Added stack_info collection in `run_scan_for_job()`:**

The stack_info is built **before running tools** and includes:

1. **Basic Information** (always present):
   ```python
   {
       "target_url": job.project.target_url,
       "scan_level": job.scan_level.value,
   }
   ```

2. **HTTP Information** (if available):
   - Attempts a lightweight HTTP HEAD request (5 second timeout)
   - Falls back to GET if HEAD fails
   - Extracts relevant headers:
     - `Server`
     - `X-Powered-By`
     - `Content-Type`
     - `X-Frame-Options`
     - `X-Content-Type-Options`
   - Includes HTTP status code
   
   Example:
   ```python
   {
       "target_url": "https://example.com",
       "scan_level": "basic",
       "http": {
           "status_code": 200,
           "headers": {
               "Server": "nginx",
               "Content-Type": "text/html"
           }
       }
   }
   ```

3. **Error Handling**:
   - If HTTP request fails, logs a warning and continues
   - Uses minimal stack_info (target_url + scan_level) if HTTP fails
   - Does not block scan execution

4. **Persistence**:
   - Saved to `scan_job.stack_info` before running tools
   - Committed to database immediately
   - Available for all scan levels (basic, pro, advanced)

## Implementation Details

### HTTP Request Strategy

1. **First attempt**: `HEAD` request (cheaper, no body)
2. **Fallback**: `GET` request with `stream=True` (if HEAD fails)
3. **Timeout**: 5 seconds (keeps it lightweight)
4. **Redirects**: Allowed (follows redirects)

### Safety Features

- ✅ Short timeout (5 seconds) prevents hanging
- ✅ Exception handling ensures scan continues even if HTTP fails
- ✅ Minimal stack_info (target_url + scan_level) always available
- ✅ Logs warnings for debugging without failing the scan
- ✅ Works for all scan levels (basic, pro, advanced)

### Example stack_info Output

**With HTTP info:**
```json
{
    "target_url": "https://example.com",
    "scan_level": "basic",
    "http": {
        "status_code": 200,
        "headers": {
            "Server": "nginx/1.18.0",
            "Content-Type": "text/html; charset=UTF-8"
        }
    }
}
```

**Without HTTP info (if request fails):**
```json
{
    "target_url": "https://example.com",
    "scan_level": "basic"
}
```

## Usage

### API Response

When fetching a scan via `GET /api/scans/{id}`, the response will include:

```json
{
    "id": "...",
    "project_id": "...",
    "scan_level": "basic",
    "status": "completed",
    "stack_info": {
        "target_url": "https://example.com",
        "scan_level": "basic",
        "http": {
            "status_code": 200,
            "headers": {
                "Server": "nginx",
                "Content-Type": "text/html"
            }
        }
    },
    ...
}
```

### Future AI Planning

The `stack_info` field can be used by AI planning logic to:
- Identify the web server stack (from `Server` header)
- Determine content type (from `Content-Type` header)
- Adjust scan strategy based on detected technologies
- Optimize tool selection based on target characteristics

## Files Modified

1. **`app/models/scan.py`** - Added `stack_info` column
2. **`app/schemas/scan.py`** - Added `stack_info` to `ScanResponse`
3. **`app/services/scan_orchestrator.py`** - Added stack_info collection logic

## Testing

The implementation has been tested:
- ✅ Model includes `stack_info` column
- ✅ Schema includes `stack_info` field
- ✅ HTTP request logic works correctly
- ✅ Error handling gracefully falls back to minimal stack_info
- ✅ Works for all scan levels

## Notes

- The HTTP request is intentionally lightweight (5 second timeout)
- If the target is unreachable or times out, the scan continues with minimal stack_info
- The `stack_info` is collected before running tools, so it's available for future AI planning
- Currently, the stack_info is not used by the scan execution logic (as requested)



