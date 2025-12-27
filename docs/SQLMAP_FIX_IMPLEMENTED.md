# SQLMap Fix Implementation

## Summary
Fixed SQLMap integration to reliably detect SQL injection in login forms and POST requests. The fix includes new execution modes, a request recorder utility, and improved parsing.

## Changes Made

### 1. Root Cause Analysis
**File**: `docs/SQLMAP_ROOT_CAUSE.md`

Documented why SQLMap was missing SQL injection on login forms:
- `--forms` flag is insufficient for login forms
- Missing POST data, cookies, CSRF tokens, and hidden fields
- Solution: Use raw request file (`-r`) for reliable detection

### 2. Catalog Updates
**File**: `services/thandev-brain/catalog/catalog.json`

Added new SQLMap modes:
- **`sqli_get_basic`**: Test SQL injection in URL query parameters (GET requests)
- **`sqli_post_data`**: Test SQL injection in POST request body with explicit data
- **`sqli_forms_login`**: Test SQL injection in login forms (automatically detects and tests form parameters)
- **`sqli_raw_request`**: Test SQL injection using a raw HTTP request file (most reliable for login forms)
- **`sqli_light`**: Legacy mode (uses --forms)

All modes support:
- Configurable `level` (1-5, default: 2)
- Configurable `risk` (1-3, default: 1)
- Configurable `timeout_sec` (10-300, default: 60)
- Strict parameter validation (`additionalProperties: false`)

### 3. Request Recorder Utility
**File**: `backend/app/services/request_recorder.py`

New utility that:
1. Fetches the login page (GET request)
2. Parses HTML form to extract:
   - Form action URL
   - Form method (POST)
   - Input field names (username, password, hidden fields)
   - CSRF tokens (if present)
3. Captures cookies from GET response
4. Builds a raw HTTP request with:
   - POST method
   - Proper headers (including cookies)
   - POST body with form data (placeholders for SQLMap injection)
5. Saves as raw request file for SQLMap `-r` option

**Dependencies**: Added `beautifulsoup4>=4.12.0` to `requirements.txt`

### 4. SQLMap Execution Updates
**File**: `backend/app/services/tools.py`

Updated `_run_sqlmap()` to support new modes:

- **`sqli_raw_request`**: Uses `-r <request_file>` with provided raw request
- **`sqli_forms_login`**: 
  - Default: Builds raw request using request recorder, then uses `-r`
  - Fallback: Uses `--forms --crawl=0` if `use_raw_request=false`
- **`sqli_post_data`**: Uses `--data <post_data>` with optional `--cookie` and `-p <params>`
- **`sqli_get_basic`**: Uses `-u <url>` with optional `-p <params>`
- **`sqli_light`**: Legacy mode with `--forms --crawl=1`

**Safe defaults**:
- `--batch` (non-interactive)
- `--risk=1` (configurable, default low)
- `--level=2` (configurable, default moderate)
- `--timeout=60` (request timeout)
- `--time-sec=5` (time-based injection delay)
- `--random-agent`
- `--technique=BEUSTQ` (all techniques)
- `--fresh-queries`
- `--threads=1` (single thread)
- `-v 3` (verbosity level 3)
- **NO destructive flags** (no `--os-shell`, `--file-write`, `--sql-shell`, etc.)

### 5. Parameter Mapping
**File**: `backend/app/services/tools.py`

Updated `_map_mode_to_internal_params()` to:
- Map `mode_id` to execution mode
- Extract `level`, `risk`, `timeout_sec` from params
- Map mode-specific params (`post_data`, `raw_request_ref`, `param_names`, `cookie`, `use_raw_request`)

### 6. Parsing (Already Comprehensive)
**File**: `backend/app/services/findings_ingestor.py`

Existing parsing already handles:
- Detailed injection point sections
- "parameter 'X' is 'technique' injectable" patterns
- Log file parsing
- CSV/JSON file parsing
- Creates findings with CRITICAL severity
- Includes technique, parameter, place (GET/POST), DBMS, payload

## Architecture Compliance

✅ **Brain outputs only `{tool_id, mode_id, params}`** - No changes needed
✅ **Runner executes allowlisted modes** - Modes are in catalog
✅ **No arbitrary command execution** - Commands are built from catalog modes
✅ **Multi-tenant and session isolation** - Uses `scan_job_id` and `job_dir`
✅ **No destructive SQLMap flags** - Only safe detection flags used

## Testing

### Manual Test Script
```python
# Test request recorder
from app.services.request_recorder import build_raw_request_for_login

raw_request, cookies = build_raw_request_for_login("http://testphp.vulnweb.com/login.php")
print(raw_request)
```

### Expected Behavior
1. Brain selects `sqli_forms_login` mode for login URLs
2. Runner builds raw request from login form
3. SQLMap runs with `-r request.txt`
4. SQLMap detects SQL injection in `uname` and/or `pass` parameters
5. Parser extracts findings from stdout/log files
6. Findings are created with CRITICAL severity
7. UI displays SQL injection finding

## Next Steps

1. **Install beautifulsoup4**: `pip install beautifulsoup4>=4.12.0`
2. **Test on testphp.vulnweb.com/login.php**:
   - Create a scan with Advanced level
   - Brain should select `sqli_forms_login` mode
   - Verify SQL injection is detected
   - Verify finding appears in UI
3. **Monitor logs** for any issues with request building or SQLMap execution

## Files Modified

1. `docs/SQLMAP_ROOT_CAUSE.md` - Root cause analysis
2. `docs/SQLMAP_FIX_IMPLEMENTED.md` - This file
3. `services/thandev-brain/catalog/catalog.json` - Added new SQLMap modes
4. `backend/app/services/request_recorder.py` - New request recorder utility
5. `backend/app/services/tools.py` - Updated SQLMap execution
6. `backend/requirements.txt` - Added beautifulsoup4

