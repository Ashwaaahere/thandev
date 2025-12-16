# Brain Service Fixes - December 13, 2025

## Issues Fixed

### 1. Parameter Mismatch in `create_tech_fingerprint_document()` ✅

**Error:** `create_tech_fingerprint_document() got an unexpected keyword argument 'stack_info'`

**Location:** `services/thandev-brain/app/api/rag.py`

**Root Cause:** The function signature expects `tech_stack` but we were passing `stack_info`.

**Fix:** Updated the call to extract `tech_stack` from `stack_info`:

```python
# Before:
doc = create_tech_fingerprint_document(
    target=fingerprint.get("target", ""),
    stack_info=fingerprint.get("stack_info", {}),  # Wrong parameter name
    ...
)

# After:
stack_info = fingerprint.get("stack_info", {})
tech_stack = stack_info if isinstance(stack_info, dict) else {}

doc = create_tech_fingerprint_document(
    target=fingerprint.get("target", ""),
    tech_stack=tech_stack,  # Correct parameter name
    ...
)
```

### 2. NoneType Errors in Planning ✅

**Error:** `'NoneType' object has no attribute 'get'`

**Location:** `services/thandev-brain/app/planner/plan.py`

**Root Cause:** Code was calling `.get()` on potentially None values without checking.

**Fixes Applied:**

1. **Tech Fingerprint Access (Line 130):**
   ```python
   # Before:
   tech_stack = rag_evidence.get("tech_fingerprint", {}).get("tech_stack", {})
   
   # After:
   tech_fingerprint = rag_evidence.get("tech_fingerprint")
   tech_stack = {}
   if tech_fingerprint and isinstance(tech_fingerprint, dict):
       tech_stack = tech_fingerprint.get("tech_stack", {})
   ```

2. **HTTP Status Access (Line 148):**
   ```python
   # Before:
   http_status = stack_info.get("http", {}).get("status_code")
   
   # After:
   http_status = None
   if stack_info and isinstance(stack_info, dict):
       http_info = stack_info.get("http", {})
       if isinstance(http_info, dict):
           http_status = http_info.get("status_code")
   ```

3. **Tech Fingerprint Result Access (Line 240):**
   ```python
   # Before:
   tech_fingerprint = tech_fingerprint_results[0].get("metadata", {})
   
   # After:
   result = tech_fingerprint_results[0]
   if result and isinstance(result, dict):
       tech_fingerprint = result.get("metadata", {})
   ```

## Files Modified

1. `services/thandev-brain/app/api/rag.py` - Fixed parameter name
2. `services/thandev-brain/app/planner/plan.py` - Added None checks (3 locations)

## Verification

- ✅ Syntax checks passed
- ✅ No linter errors
- ✅ All None checks added

## Next Steps

**IMPORTANT:** Restart brain service to apply fixes:

```bash
cd services/thandev-brain
source venv/bin/activate
./start_brain.sh
```

After restarting, the brain service should:
- ✅ Accept tech fingerprint ingestion requests
- ✅ Generate scan plans without NoneType errors
- ✅ Handle missing/null data gracefully



