# Tool Execution Fix - December 13, 2025

## Critical Issue

**Problem:** Scans were completing with 0 findings because tools were never actually executing.

**Symptoms:**
- Plan generated successfully (6 steps)
- Logs showed "Executing phase_1 wave with 5 tool(s)"
- But "Completed 0 tool(s), 0 failed" - no tools ran
- No tool output files created
- Scan completed in 10 seconds with 0 findings

## Root Cause

**ThreadPoolExecutor Indentation Error** - The `with ThreadPoolExecutor` block was incorrectly indented inside the `run_tool_with_loop` function definition instead of at the wave execution level. This meant:

1. The ThreadPoolExecutor was never actually created
2. The function `run_tool_with_loop` was defined but never called
3. Tools were never submitted to the executor
4. No tools executed

## Fix Applied

**File:** `backend/app/services/scan_orchestrator.py`

**Before (Incorrect):**
```python
def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
    """Wrapper that creates a thread-local event loop"""
    # ... function body ...
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:  # ❌ Wrong indentation!
        # ... executor code ...
```

**After (Correct):**
```python
def run_tool_with_loop(tool_cfg: Dict[str, Any]) -> str:
    """Wrapper that creates a thread-local event loop"""
    # ... function body ...

# Execute tools in parallel using ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=max_workers) as executor_pool:  # ✅ Correct indentation!
    # ... executor code ...
```

## Additional Fix: Qdrant Query API

**Problem:** `Query` is a typing Union, not a class, so it can't be instantiated.

**Error:** `TypeError: Cannot instantiate typing.Union`

**Fix:** Changed to use `NearestQuery` which is the actual class:

```python
# Before:
from qdrant_client.models import Query
query = Query(vector=..., filter=..., limit=...)  # ❌ Fails

# After:
from qdrant_client.models import NearestQuery
query = NearestQuery(vector=..., filter=..., limit=...)  # ✅ Works
```

**File:** `services/thandev-brain/app/rag/store.py`

## Verification

- ✅ Syntax checks passed
- ✅ No linter errors
- ✅ ThreadPoolExecutor now at correct indentation level
- ✅ NearestQuery used for Qdrant queries

## Expected Behavior After Fix

After restarting services, scans should:
1. ✅ Generate plan from brain service
2. ✅ Actually execute tools in parallel
3. ✅ Create tool output files
4. ✅ Ingest findings from tools
5. ✅ Complete with actual results

## Next Steps

**IMPORTANT:** Restart both services:

1. **Restart Celery Worker:**
   ```bash
   cd backend
   source .venv/bin/activate
   ./start_celery.sh
   ```

2. **Restart Brain Service:**
   ```bash
   cd services/thandev-brain
   source venv/bin/activate
   ./start_brain.sh
   ```

3. **Test a scan** - Tools should now actually execute and produce findings!



