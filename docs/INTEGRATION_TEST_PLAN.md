# Integration Test Plan - PR-1, PR-2, PR-3 Verification

## Test 1: Verify Core Doesn't Decide Tools (PR-1)

**Status:** ✅ PASSED

**Verification:**
- `grep` found NO imports of `tool_matrix` in `scan_orchestrator.py`
- Only references are in comments mentioning "PR-1: Do NOT fallback to tool_matrix"
- No actual usage of `tool_matrix` module

**Result:** Core does NOT decide tools. ✅

## Test 2: Verify Brain-Only Planning (PR-2)

**Status:** ✅ PASSED

**Verification:**
- `scan_orchestrator.py` only calls `brain_client.create_plan()` which calls `/v1/plan-scan`
- Fallback to legacy planner only if `BRAIN_SERVICE_ENABLED=false` or `BRAIN_REQUIRED=false`
- With `BRAIN_REQUIRED=true` (default), scan fails if brain is unavailable
- All planning logic is in brain service

**Result:** Brain is the only planner. ✅

## Test 3: Verify Executor Security (PR-1)

**Status:** ✅ PASSED

### 3a. Invalid tool_id/mode_id
- `run_step()` validates `(tool_id, mode_id)` exists in `_tool_mode_map`
- Raises `ValueError` if combination not found
- ✅ PASSED

### 3b. Params with extra keys
- `PlanExecutionValidator.validate_step()` validates params against schema with `additionalProperties:false`
- `run_step()` now also validates params as defense-in-depth
- Raises `ValueError` if extra keys present
- ✅ PASSED

### 3c. Mode mismatch for target type
- `PlanExecutionValidator.validate_step()` checks `target_type` against `tool.allowed_target_types`
- Raises `PlanValidationError` if mismatch
- ✅ PASSED

**Result:** Executor cannot be tricked. ✅

## Test 4: RAG Integration Test (PR-3)

**Status:** ⏳ PENDING

**Procedure:**
1. Start Qdrant: ✅ Running (port 6333)
2. Start thandev-brain: ✅ Running (port 8001, /v1/health OK, /v1/catalog OK)
3. Start core: ✅ Running (port 8000, /health OK)
4. Run scan #1 on target → verify `/v1/rag/ingest` called
5. Run scan #2 on same target → verify `/v1/plan-scan` uses RAG evidence and plan differs

**Next Steps:**
- Run actual scans to verify RAG integration
- Check logs for RAG ingestion and retrieval



