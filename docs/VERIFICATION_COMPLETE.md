# Complete Verification Report - PR-1, PR-2, PR-3

## ✅ Test 1: Core Doesn't Decide Tools (PR-1)

**Requirement:** `scan_orchestrator.py` must NOT import or use `tool_matrix.py`

**Verification:**
```bash
grep -i "tool_matrix" backend/app/services/scan_orchestrator.py
# Result: No matches found (only comments mentioning "PR-1: Do NOT fallback")
```

**Status:** ✅ **PASSED**
- No imports of `tool_matrix`
- No usage of `tool_matrix` module
- Only comments reference it for documentation

---

## ✅ Test 2: Brain-Only Planning (PR-2)

**Requirement:** Only planning call is brain `/v1/plan-scan`

**Verification:**
- `scan_orchestrator.py` only calls `brain_client.create_plan()` → `/v1/plan-scan`
- Fallback to legacy planner ONLY if:
  - `BRAIN_SERVICE_ENABLED=false` OR
  - `BRAIN_REQUIRED=false` (default is `true`)
- With `BRAIN_REQUIRED=true`, scan fails if brain is unavailable
- All planning logic is in `services/thandev-brain/app/planner/plan.py`

**Status:** ✅ **PASSED**
- Brain is the only planner in normal operation
- Legacy planner only used if explicitly disabled

---

## ✅ Test 3: Executor Cannot Be Tricked (PR-1 Security)

### 3a. Invalid tool_id/mode_id

**Code Location:** `backend/app/services/tools.py:174-181`

```python
mode_key = (tool_id, mode_id)
if mode_key not in self._tool_mode_map:
    raise ValueError(
        f"Invalid tool_id/mode_id combination: ({tool_id}, {mode_id}). "
        f"Available combinations: {available}"
    )
```

**Status:** ✅ **PASSED**
- Validates against `_tool_mode_map` (loaded from catalog)
- Raises `ValueError` if combination not found

### 3b. Params with Extra Keys

**Code Location:** 
- `backend/app/services/ai/plan_validation.py:224-240` (plan validation)
- `backend/app/services/tools.py:192-210` (defense-in-depth in executor)

```python
# Plan validation (before execution)
strict_schema = dict(params_schema)
if "additionalProperties" not in strict_schema:
    strict_schema["additionalProperties"] = False
validator = Draft202012Validator(strict_schema)
validator.validate(step.params)

# Executor validation (defense-in-depth)
params_schema = mode_config.get("params_schema", {})
if params_schema:
    strict_schema = dict(params_schema)
    if "additionalProperties" not in strict_schema:
        strict_schema["additionalProperties"] = False
    validator = Draft202012Validator(strict_schema)
    validator.validate(params)
```

**Status:** ✅ **PASSED**
- Validates at plan level (before execution)
- Validates again at executor level (defense-in-depth)
- Both enforce `additionalProperties:false`

### 3c. Mode Mismatch for Target Type

**Code Location:** `backend/app/services/ai/plan_validation.py:203-209`

```python
allowed_types = tool_def.get("allowed_target_types", [])
if target_type not in allowed_types:
    raise PlanValidationError(
        f"Tool '{step.tool_id}' does not support target type '{target_type}'. "
        f"Allowed types: {allowed_types}"
    )
```

**Status:** ✅ **PASSED**
- Validates target type compatibility at plan validation
- Happens before any tools are executed
- Raises `PlanValidationError` if mismatch

---

## ⏳ Test 4: RAG Integration (PR-3)

**Requirement:** RAG changes planning on 2nd scan

**Status:** ⏳ **READY FOR TESTING**

**Services Status:**
- ✅ Qdrant: Running (port 6333)
- ✅ Brain Service: Running (port 8001, `/v1/health` OK, `/v1/catalog` OK)
- ✅ Core Service: Running (port 8000, `/health` OK)

**Fixed Issues:**
- ✅ Qdrant query API: Changed from `NearestQuery` to direct `list[float]` vector
- ✅ Execution time: Added to `run_step` method
- ✅ ThreadPoolExecutor: Fixed indentation (tools now execute)

**Test Procedure:**
1. Run scan #1 on `http://www.itsecgames.com/`
2. Verify logs show `/v1/rag/ingest` called
3. Run scan #2 on same target
4. Verify `/v1/plan-scan` uses RAG evidence (check brain logs)
5. Compare plans - scan #2 should reference prior findings

**Test Script:** `test_integration.sh` (created)

---

## Summary

| Test | Status | Notes |
|------|--------|-------|
| PR-1: Core doesn't decide tools | ✅ PASSED | No tool_matrix imports |
| PR-2: Brain-only planning | ✅ PASSED | Only calls `/v1/plan-scan` |
| PR-1: Invalid tool_id/mode_id | ✅ PASSED | Validates against catalog |
| PR-1: Extra params keys | ✅ PASSED | Validates with `additionalProperties:false` |
| PR-1: Target type mismatch | ✅ PASSED | Validates at plan level |
| PR-3: RAG integration | ⏳ READY | Services running, ready for test |

**All PR-1 and PR-2 requirements verified. PR-3 ready for integration testing.**



