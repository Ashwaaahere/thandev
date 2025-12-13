# Scan Levels Implementation

## Summary

Successfully implemented support for three scan levels: "basic", "pro", and "advanced" with proper validation and profile-based tool configuration.

## Changes Made

### 1. Scan Level Validation (`app/schemas/scan.py`)

**Updated `ScanCreate` schema:**
- Made `scan_level` optional with default value `ScanLevel.BASIC`
- FastAPI automatically validates enum values and returns 422 with clear error messages for invalid values
- Default behavior: If `scan_level` is not provided, it defaults to "basic"

**Example API usage:**
```bash
# Without scan_level (defaults to "basic")
POST /api/scans
{
  "project_id": "123"
}

# With explicit scan_level
POST /api/scans
{
  "project_id": "123",
  "scan_level": "pro"
}

# Invalid scan_level returns 422
POST /api/scans
{
  "project_id": "123",
  "scan_level": "invalid"
}
# Response: 422 Unprocessable Entity
# Error message includes allowed values: basic, pro, advanced
```

### 2. Scan Profiles Module (`app/services/scan_profiles.py`)

**Created new module with:**

#### Tool Registry
- `VALID_TOOLS`: List of supported tool identifiers
  - `"nuclei"` - Nuclei vulnerability scanner
  - `"nmap"` - Nmap port scanner
  - `"sslscan"` - SSL/TLS configuration scanner

#### Scan Profiles Configuration
```python
SCAN_PROFILES = {
    "basic": {
        "tools": [{"name": "nuclei", "config": {...}}]
    },
    "pro": {
        "tools": [
            {"name": "nuclei", "config": {...}},
            {"name": "nmap", "config": {...}}
        ]
    },
    "advanced": {
        "tools": [
            {"name": "nuclei", "config": {...}},
            {"name": "nmap", "config": {...}},
            {"name": "sslscan", "config": {...}}
        ]
    }
}
```

#### Helper Functions

**`get_profile(scan_level: str) -> Dict[str, Any]`**
- Returns the full profile configuration for a scan level
- Raises `ValueError` with clear error message if scan level is invalid
- Validates that all tools in the profile are supported

**`get_tool_names(scan_level: str) -> List[str]`**
- Convenience function to get just the list of tool names
- Used by Celery task to determine which tools to run

**`validate_tool_name(tool_name: str) -> bool`**
- Checks if a tool name is valid and supported

### 3. Celery Task Integration (`app/tasks/celery_app.py`)

**Updated to use scan profiles:**
- Replaced hardcoded `tools_to_run` dictionary with `get_tool_names()` from scan_profiles
- Added error handling for invalid scan levels
- Improved logging to show which profile is being used

**Before:**
```python
tools_to_run = {
    "basic": ["nuclei"],
    "pro": ["nuclei", "nmap"],
    "advanced": ["nuclei", "nmap", "sslscan"],
}
tools = tools_to_run.get(scan_level, ["nuclei"])
```

**After:**
```python
from app.services.scan_profiles import get_tool_names
try:
    tools = get_tool_names(scan_level)
    logger.info(f"Using scan profile '{scan_level}': {len(tools)} tools configured")
except ValueError as e:
    # Handle invalid scan level
    scan_job.status = ScanStatus.FAILED
    scan_job.error_message = f"Invalid scan level: {str(e)}"
    # ...
```

## Tool Configurations

### Basic Scan
- **Tools**: `nuclei`
- **Nuclei Config**:
  - Templates: `cves/`
  - Severity: `critical`, `high`

### Pro Scan
- **Tools**: `nuclei`, `nmap`
- **Nuclei Config**:
  - Templates: `cves/`, `vulnerabilities/`
  - Severity: `critical`, `high`, `medium`
- **Nmap Config**:
  - Scan type: `service_version`
  - Top ports: `1000`

### Advanced Scan
- **Tools**: `nuclei`, `nmap`, `sslscan`
- **Nuclei Config**:
  - Templates: `cves/`, `vulnerabilities/`, `exposures/`
  - Severity: `critical`, `high`, `medium`, `low`
- **Nmap Config**:
  - Scan type: `aggressive`
  - Top ports: `all`
- **SSLScan Config**:
  - Check all ciphers: `True`

## Validation

### FastAPI Validation
- Uses `ScanLevel` enum, so FastAPI automatically validates
- Invalid values return `422 Unprocessable Entity`
- Error message includes allowed values

### Profile Validation
- `get_profile()` validates scan level and raises `ValueError` if invalid
- Warns if profile references unsupported tools
- All tool names must match `VALID_TOOLS` list

## Testing

### Test Scan Profiles
```python
from app.services.scan_profiles import get_profile, get_tool_names

# Get profile
profile = get_profile("basic")
tools = get_tool_names("basic")  # Returns: ["nuclei"]

# Error handling
try:
    get_profile("invalid")
except ValueError as e:
    print(e)  # "Invalid scan level: 'invalid'. Allowed values are: basic, pro, advanced"
```

### Test Schema Default
```python
from app.schemas.scan import ScanCreate

# Default to "basic"
scan = ScanCreate(project_id="123")
assert scan.scan_level == ScanLevel.BASIC

# Explicit value
scan = ScanCreate(project_id="123", scan_level="pro")
assert scan.scan_level == ScanLevel.PRO
```

## Files Modified

1. `app/schemas/scan.py` - Made `scan_level` optional with default
2. `app/services/scan_profiles.py` - **NEW** - Profile configuration module
3. `app/tasks/celery_app.py` - Updated to use scan profiles

## Next Steps

The scan profiles are ready to use. The tool configurations in the profiles are currently informational - the actual tool execution still uses the scan_level parameter passed to each tool's `_run_*` method. Future enhancements could:

1. Use the `config` dictionaries in profiles to customize tool behavior
2. Add more tools to the profiles as they become available
3. Add profile-specific timeouts or resource limits



