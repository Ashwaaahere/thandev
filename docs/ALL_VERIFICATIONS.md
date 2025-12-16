# Complete Verification - All Requirements

## ✅ 1. Core Doesn't Decide Tools (PR-1)

**Check:** `scan_orchestrator.py` does NOT import/use `tool_matrix.py`

**Result:**
```bash
$ grep -i "tool_matrix" backend/app/services/scan_orchestrator.py
# No matches found (only comments)
```

**Status:** ✅ **VERIFIED** - No tool_matrix usage

---

## ✅ 2. Brain-Only Planning (PR-2)

**Check:** Only planning call is brain `/v1/plan-scan`

**Code Flow:**
1. `scan_orchestrator.py:570` → `brain_client.create_plan()`
2. `brain_client.py:create_plan()` → `POST /v1/plan-scan`
3. No fallback unless `BRAIN_SERVICE_ENABLED=false` or `BRAIN_REQUIRED=false`

**Status:** ✅ **VERIFIED** - Brain is the only planner

---

## ✅ 3. Executor Security (PR-1)

### 3a. Invalid tool_id/mode_id

**Location:** `backend/app/services/tools.py:174-181`

```python
if mode_key not in self._tool_mode_map:
    raise ValueError(f"Invalid tool_id/mode_id combination...")
```

**Status:** ✅ **VERIFIED** - Rejects unknown combinations

### 3b. Params with Extra Keys

**Location:** 
- `backend/app/services/ai/plan_validation.py:224-240` (plan level)
- `backend/app/services/tools.py:192-210` (executor level - defense-in-depth)

```python
strict_schema["additionalProperties"] = False
validator.validate(params)  # Raises ValidationError if extra keys
```

**Status:** ✅ **VERIFIED** - Rejects extra params (validated twice)

### 3c. Target Type Mismatch

**Location:** `backend/app/services/ai/plan_validation.py:203-209`

```python
if target_type not in allowed_types:
    raise PlanValidationError(f"Tool does not support target type...")
```

**Status:** ✅ **VERIFIED** - Rejects incompatible target types

---

## ⏳ 4. RAG Integration Test (PR-3)

**Status:** Ready for testing

**Services:**
- ✅ Qdrant: Running (port 6333)
- ✅ Brain: Running (port 8001, `/v1/health` OK, `/v1/catalog` OK)
- ✅ Core: Running (port 8000, `/health` OK)

**Implementation:**
- ✅ RAG ingestion: `/v1/rag/ingest` endpoint implemented
- ✅ RAG retrieval: `query_rag_lanes()` in planner
- ✅ Qdrant query: Fixed to use vector directly

**Test Procedure:**
1. Run scan #1 → verify `/v1/rag/ingest` called (check logs)
2. Run scan #2 → verify RAG evidence used in planning (check brain logs)
3. Compare plans → scan #2 should reference prior findings

**Test Script:** `test_integration.sh`

---

## All Fixes Applied

1. ✅ Qdrant query API: Use `list[float]` vector directly
2. ✅ Execution time: Added to `run_step` method
3. ✅ ThreadPoolExecutor: Fixed indentation
4. ✅ Param validation: Added defense-in-depth in executor

---

## Summary

| Requirement | Status |
|-------------|--------|
| PR-1: Core doesn't decide tools | ✅ VERIFIED |
| PR-2: Brain-only planning | ✅ VERIFIED |
| PR-1: Executor security | ✅ VERIFIED |
| PR-3: RAG integration | ⏳ READY FOR TEST |

**All code requirements verified. Ready for integration testing.**



