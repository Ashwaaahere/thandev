# Execution Time Fix - December 13, 2025

## Issue

**Problem:** Tools showed "N/A" for execution time in the frontend, even though tools were running successfully.

**Root Cause:** The `run_step` method (used by the new catalog-based tool execution) was not calculating `execution_time`, unlike the legacy `run_tool` method which did.

## Fix Applied

**File:** `backend/app/services/tools.py`

**Before:**
```python
async def run_step(...):
    # ...
    tool_runner = self.supported_tools[tool_id]
    result = await tool_runner(target_url, scan_level, **internal_kwargs)
    return result  # ❌ No execution_time!
```

**After:**
```python
async def run_step(...):
    # ...
    start_time = datetime.utcnow()
    
    try:
        tool_runner = self.supported_tools[tool_id]
        result = await tool_runner(target_url, scan_level, **internal_kwargs)
        
        # Calculate and add execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        result["execution_time"] = execution_time
        result["success"] = result.get("success", True)
        
        return result
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        return {
            "tool_name": tool_id,
            "success": False,
            "error": str(e),
            "output": "",
            "exit_code": -1,
            "execution_time": execution_time,  # ✅ Now included
        }
```

## Verification

- ✅ Syntax check passed
- ✅ No linter errors
- ✅ Matches `run_tool` behavior for consistency

## Expected Behavior

After restarting Celery worker:
- Tools will show actual execution times (e.g., "45.2s") instead of "N/A"
- Execution times will be accurate and stored in the database
- Frontend will display proper timing information

## Next Steps

**Restart Celery Worker:**
```bash
cd backend
source .venv/bin/activate
./start_celery.sh
```

Then run a new scan to see execution times displayed correctly.



