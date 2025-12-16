# PR-1: Catalog + Strict Plan Validation - COMPLETE ✅

## Summary

PR-1 enforces a hard contract boundary so core and executor only accept `(tool_id, mode_id, params)`. No commands in planning. No tool picking in core.

## Changes Made

### 1. Tool Catalog v1 (Shared) ✅

**Location**: `services/thandev-brain/catalog/catalog.json`

- Already exists with strict validation (`additionalProperties: false` in all params_schema)
- Defines tools, modes, and parameter schemas
- NO command strings in catalog

**Shared Schemas**: `packages/thandev_schemas/`

- `catalog.py`: `ToolCatalog`, `ToolDefinition`, `ModeDefinition`
- `planning.py`: `PlanScanRequest`, `PlanScanResponse`, `PlanStep`, `Timeline`
- All schemas use `extra = "forbid"` for strict validation

### 2. Core-side PlanExecutionValidator ✅

**Location**: `backend/app/services/ai/plan_validation.py`

**Validates**:
- ✅ `tool_id`/`mode_id` exist in local catalog copy
- ✅ `params` validate against mode's params_schema (strict: `additionalProperties:false`)
- ✅ Dependencies form a DAG (no cycles)
- ✅ Policy limits (max_steps, max_parallelism, max_total_runtime_sec)
- ✅ Target types allowed (url/host/ip)

**Features**:
- Loads catalog from JSON file
- Builds indexes for fast lookup
- Topological sort for dependency validation
- JSON Schema validation with Draft202012Validator

### 3. ToolExecutor Refactored ✅

**Location**: `backend/app/services/tools.py`

**New Method**: `run_step(tool_id, mode_id, target_url, params, ...)`

- Accepts only allowlisted `(tool_id, mode_id)` combinations
- Maps catalog modes to internal tool parameters
- Commands built internally from catalog (not from plan)
- Legacy `run_tool()` method kept for backward compatibility during migration

**Internal Mapping**:
- `_map_mode_to_internal_params()`: Converts catalog params to internal format
- `_build_tool_mode_map()`: Builds index from catalog
- `_infer_scan_level_from_mode()`: Temporary helper for backward compatibility

### 4. Scan Orchestrator Updated ✅

**Location**: `backend/app/services/scan_orchestrator.py`

**Removed**:
- ❌ `from app.core.tool_matrix import get_tools_for_level` (main planning path)
- ❌ `from app.core.tool_matrix import get_enabled_tool_keys, is_tool_enabled_for_level` (AI planner second wave)
- ❌ Fallback to `tool_matrix` when planning fails (now fails scan if brain required)

**Added**:
- ✅ Brain service planning with validation
- ✅ `PlanExecutionValidator` integration
- ✅ Plan validation before execution
- ✅ `BRAIN_REQUIRED` config flag (default: `true`)
- ✅ Support for both `tool_id/mode_id` and legacy `name` formats in `_run_single_tool()`

**Planning Flow**:
1. Call brain service `/v1/plan-scan`
2. Validate plan with `PlanExecutionValidator`
3. Convert brain plan format to orchestrator waves
4. Execute steps using `tool_id/mode_id` format
5. If brain fails and `BRAIN_REQUIRED=true`, mark scan as FAILED

### 5. Unit Tests ✅

**Location**: `backend/tests/test_plan_validation.py`

**Tests**:
- ✅ `test_valid_plan_passes`: Valid plan passes validation
- ✅ `test_invalid_tool_id_rejected`: Invalid tool_id rejected
- ✅ `test_invalid_mode_id_rejected`: Invalid mode_id rejected
- ✅ `test_extra_params_rejected`: Extra params (not in schema) rejected
- ✅ `test_cyclic_depends_on_rejected`: Cyclic dependencies rejected
- ✅ `test_max_steps_limit`: Plans exceeding max_steps rejected
- ✅ `test_max_runtime_limit`: Plans exceeding max_total_runtime_sec rejected
- ✅ `test_target_type_validation`: Target type validation works
- ✅ `test_valid_params_pass`: Valid params pass validation
- ✅ `test_invalid_param_type_rejected`: Invalid param types rejected
- ✅ `test_dependency_on_nonexistent_step`: Dependencies on non-existent steps rejected
- ✅ `test_duplicate_step_id_rejected`: Duplicate step_ids rejected

## Acceptance Criteria Met ✅

- ✅ `backend/app/services/scan_orchestrator.py` has no imports/usage of `backend/app/core/tool_matrix.py` in the main path
- ✅ Plans contain no command strings (only `tool_id`, `mode_id`, `params`)
- ✅ `ToolExecutor` can only run allowlisted `(tool_id, mode_id)` modes
- ✅ Unit tests exist:
  - ✅ Invalid `tool_id` rejected
  - ✅ Invalid `mode_id` rejected
  - ✅ Extra params rejected
  - ✅ Cyclic `depends_on` rejected

## Configuration

**New Settings** (`backend/app/core/config.py`):
```python
BRAIN_SERVICE_URL: str = "http://localhost:8001"
BRAIN_SERVICE_ENABLED: bool = True
BRAIN_REQUIRED: bool = True  # NEW: Fail scan if brain unreachable
```

## Dependencies Added

- `jsonschema>=4.0.0` (for strict JSON Schema validation)

## Files Created/Modified

### Created:
- `backend/app/services/ai/plan_validation.py` - Plan validation logic
- `backend/tests/test_plan_validation.py` - Unit tests
- `backend/app/services/brain_client.py` - Brain service HTTP client (already existed, updated)

### Modified:
- `backend/app/services/tools.py` - Added `run_step()` method
- `backend/app/services/scan_orchestrator.py` - Removed tool_matrix, added validation
- `backend/app/core/config.py` - Added `BRAIN_REQUIRED` setting
- `backend/requirements.txt` - Added `jsonschema`

## Migration Notes

- Legacy `run_tool(tool_name, ...)` method still exists for backward compatibility
- `_run_single_tool()` supports both formats:
  - New: `{"tool_id": "nuclei", "mode_id": "basic_web", "config": {...}}`
  - Legacy: `{"name": "nuclei", "config": {...}}`
- AI planner second wave still uses legacy format (TODO: refactor to use brain service)

## Next Steps (PR-2)

1. Implement brain service MVP with deterministic rules
2. Make brain the only planner (remove legacy planner fallback)
3. Ensure core always calls brain (fail if brain unreachable and `BRAIN_REQUIRED=true`)

## Testing

Run tests:
```bash
cd backend
pytest tests/test_plan_validation.py -v
```

## Status

✅ **PR-1 COMPLETE** - Ready for PR-2




