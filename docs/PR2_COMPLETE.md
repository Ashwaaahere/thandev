# PR-2: Brain MVP + Brain-Only Planning - COMPLETE ✅

## Summary

PR-2 makes the thandev-brain service the only planner. Core always calls brain, and if brain is unreachable and `BRAIN_REQUIRED=true`, the scan fails with a clear error.

## Changes Made

### 1. Brain Service Skeleton ✅

**Location**: `services/thandev-brain/`

**Structure**:
- ✅ `app/main.py` - FastAPI application with lifespan management
- ✅ `app/api/v1.py` - API endpoints:
  - `GET /v1/health` - Health check
  - `GET /v1/catalog` - Returns catalog.json + version
  - `POST /v1/plan-scan` - Generate scan plan
  - `POST /v1/build-report-prompt` - Build report prompt package
- ✅ `app/core/config.py` - Configuration with policy limits
- ✅ `app/models.py` - Pydantic models for requests/responses

### 2. Brain Client Integration (Core) ✅

**Location**: `backend/app/services/brain_client.py`

**Features**:
- ✅ HTTP client for brain service
- ✅ `create_plan()` - Calls `/v1/plan-scan`
- ✅ `build_report_prompt()` - Calls `/v1/build-report-prompt`
- ✅ Proper error handling and timeout management
- ✅ Response validation using Pydantic schemas

### 3. Brain-Only Planning Enforcement ✅

**Location**: `backend/app/services/scan_orchestrator.py`

**Changes**:
- ✅ Core calls brain service for all planning
- ✅ Plan validation using `PlanExecutionValidator` (from PR-1)
- ✅ `BRAIN_REQUIRED` config flag (default: `true`)
- ✅ If brain fails and `BRAIN_REQUIRED=true`, scan marked as FAILED
- ✅ Legacy planner fallback only if `BRAIN_SERVICE_ENABLED=false` or `BRAIN_REQUIRED=false`
- ✅ Clear error messages when brain is required but unavailable

**Planning Flow**:
1. Call brain `/v1/plan-scan` with target_url, scan_level, stack_info
2. Validate returned plan with `PlanExecutionValidator`
3. Convert brain plan format to orchestrator waves
4. Execute steps using `tool_id/mode_id` format

### 4. Brain Planner MVP Logic (Rules-Only) ✅

**Location**: `services/thandev-brain/app/planner/plan.py`

**Rules Implemented**:
- ✅ **Rule 1**: Base tools based on scan level
  - `basic`: nuclei (basic_web) + httpx (low)
  - `pro`: nuclei (pro_web) + nmap (top_ports) + httpx (medium) + ffuf (pro) + dalfox (standard)
  - `advanced`: nuclei (advanced_web) + nmap (full_ports_scripts) + httpx (high) + ffuf (advanced) + dalfox (standard) + sqlmap (sqli_light)
- ✅ **Rule 2**: TLS endpoint → add sslscan
- ✅ **Rule 3**: Prior CVE signals → nuclei cve_fast (follow-up)
- ✅ **Rule 4**: Params-based app fingerprint → dalfox constrained mode
- ✅ **Rule 5**: Server error (5xx) → remove heavy tools (nmap, sslscan)

**Features**:
- ✅ RAG evidence retrieval (stub - returns empty evidence for now)
- ✅ Deterministic rule application
- ✅ Plan validation (tool/mode exists, params validate, DAG acyclic, policy limits)
- ✅ Timeline calculation
- ✅ Dependency management

## Configuration

**Core Settings** (`backend/app/core/config.py`):
```python
BRAIN_SERVICE_URL: str = "http://localhost:8001"
BRAIN_SERVICE_ENABLED: bool = True
BRAIN_REQUIRED: bool = True  # NEW: Fail scan if brain unreachable
```

**Brain Settings** (`services/thandev-brain/app/core/config.py`):
```python
BRAIN_MAX_STEPS: int = 20
BRAIN_MAX_PARALLELISM: int = 5
BRAIN_MAX_TOTAL_RUNTIME_SEC: int = 3600
```

## Acceptance Criteria Met ✅

- ✅ Brain service can run locally and core can call it
- ✅ Core refuses to plan locally (no tool_matrix) when brain is available
- ✅ If brain is down and `BRAIN_REQUIRED=true`, core marks scan as FAILED with clear message
- ✅ Plans returned are valid and executed via ToolExecutor's allowlisted mapping
- ✅ Brain planner uses deterministic rules (no LLM calls in MVP)

## Files Created/Modified

### Created:
- `backend/app/services/brain_client.py` - Brain service HTTP client (already existed, verified)

### Modified:
- `backend/app/services/scan_orchestrator.py` - Brain-only planning enforcement
- `backend/app/core/config.py` - Added `BRAIN_REQUIRED` setting

### Already Existed (Verified):
- `services/thandev-brain/app/main.py` - FastAPI app
- `services/thandev-brain/app/api/v1.py` - API endpoints
- `services/thandev-brain/app/planner/plan.py` - Rules-based planner
- `services/thandev-brain/app/core/config.py` - Configuration

## Testing

### Manual Test Steps:

1. **Start brain service**:
   ```bash
   cd services/thandev-brain
   python -m uvicorn app.main:app --port 8001
   ```

2. **Test health endpoint**:
   ```bash
   curl http://localhost:8001/v1/health
   ```

3. **Test plan generation**:
   ```bash
   curl -X POST http://localhost:8001/v1/plan-scan \
     -H "Content-Type: application/json" \
     -d '{
       "target_url": "https://example.com",
       "scan_level": "pro",
       "stack_info": {}
     }'
   ```

4. **Test core integration**:
   - Start core backend
   - Create a scan job
   - Verify brain is called and plan is generated
   - If brain is down and `BRAIN_REQUIRED=true`, verify scan fails with clear error

## Error Handling

**Brain Unreachable**:
- If `BRAIN_REQUIRED=true`: Scan marked as FAILED with error message
- If `BRAIN_REQUIRED=false`: Falls back to legacy planner (with warning)

**Invalid Plan**:
- Plan validation fails → Scan marked as FAILED
- Clear error message about validation failure

**Brain Service Error**:
- HTTP errors → Logged and propagated
- Timeout errors → Logged and handled based on `BRAIN_REQUIRED`

## Next Steps (PR-3)

1. Implement RAG ingestion from core → brain
2. Add retrieval lanes in brain planning (use real evidence)
3. Implement `/build-report-prompt` with RAG evidence
4. Test end-to-end with real scan data

## Status

✅ **PR-2 COMPLETE** - Brain MVP implemented and integrated. Core enforces brain-only planning when `BRAIN_REQUIRED=true`.




