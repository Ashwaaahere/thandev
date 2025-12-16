# Event Loop Fix - December 13, 2025

## Issue

**Error:** `UnboundLocalError: cannot access local variable 'loop' where it is not associated with a value`

**Location:** `backend/app/services/scan_orchestrator.py`

**Root Cause:** The `loop` variable was being used at lines 516 and 563 (for RAG ingestion and brain planning) before it was defined at line 728.

## Fix Applied

### 1. Moved Loop Initialization Earlier ✅

**Before:** Loop was initialized at line 728 (after stack_info collection)

**After:** Loop is now initialized at line 505 (right after stack_info is saved)

```python
# Initialize event loop for async operations (brain client calls)
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
```

### 2. Removed Duplicate Initialization ✅

Removed the duplicate loop initialization at line 728 since it's now initialized earlier.

## Loop Usage Points

The loop is now available for all async operations:

1. **Line 516:** RAG ingestion (tech fingerprint)
2. **Line 563:** Brain service planning
3. **Line 381:** RAG ingestion (findings after tool completion)
4. **Line 742:** HTTP security header checks
5. **Line 1229:** RAG ingestion (all findings after scan)
6. **Line 1291:** Report prompt generation

## Verification

- ✅ Syntax check passed
- ✅ No linter errors
- ✅ All imports verified
- ✅ Loop initialization logic tested

## Next Steps

**IMPORTANT:** Restart Celery worker to apply the fix:

```bash
# Stop current Celery worker (Ctrl+C)
cd backend
source .venv/bin/activate
./start_celery.sh
```

## Files Modified

- `backend/app/services/scan_orchestrator.py` - Moved loop initialization earlier



