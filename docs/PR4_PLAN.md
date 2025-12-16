# PR-4 Implementation Plan: Brain-Owned Closed-Loop Scanning

## Overview

PR-4 refactors the scanning architecture to:
1. **Brain owns the loop** - Brain decides next steps based on results + RAG
2. **Runner service separation** - Tool execution moves out of core into separate service
3. **Multi-tenant concurrency** - Support many concurrent sessions with isolated state
4. **Fix ffuf 404 false positives** - Implement baseline detection
5. **Fix Top Picks sorting** - Ensure severity-sorted and not stale

---

## Phase 0: Current Architecture Analysis

### Current Flow
1. **Core API** receives scan request → creates `ScanJob` → enqueues Celery task
2. **Celery task** (`run_scan_task`) calls `run_scan_for_job()`
3. **Orchestrator** (`scan_orchestrator.py`):
   - Calls brain `/v1/plan-scan` to get initial plan
   - Groups steps into waves (topological sort by dependencies)
   - Executes tools in parallel using `ThreadPoolExecutor`
   - Calls `ToolExecutor.run_step(tool_id, mode_id, params)`
   - Ingests findings via `findings_ingestor.py`
   - Calls brain `/v1/rag/ingest` after each tool
   - Calls brain `/v1/build-report-prompt` at end
4. **ToolExecutor** (`tools.py`):
   - Validates `tool_id/mode_id` against catalog
   - Maps to internal command execution
   - Returns results with `execution_time`
5. **Findings Ingestor** (`findings_ingestor.py`):
   - Parses tool output (JSON/XML)
   - Creates `Finding` records in DB
   - Handles per-tool idempotency

### Key Files
- `backend/app/services/scan_orchestrator.py` - Current orchestrator (1400+ lines)
- `backend/app/tasks/celery_app.py` - Celery task entrypoint
- `backend/app/services/tools.py` - Tool execution (3000+ lines)
- `backend/app/services/findings_ingestor.py` - Findings parsing (5000+ lines)
- `backend/app/services/brain_client.py` - Brain HTTP client
- `services/thandev-brain/app/api/v1.py` - Brain API endpoints
- `services/thandev-brain/app/planner/plan.py` - Planning logic

### Issues to Address
1. **Core still orchestrates** - Brain only provides initial plan, core executes it
2. **No closed-loop** - Brain can't adapt based on results mid-scan
3. **Execution in core** - Tools run in Celery workers that are part of core
4. **ffuf 404 false positives** - No baseline detection
5. **Top Picks may be stale** - Frontend/backend may show old data

---

## PR-4A: Brain-Owned Session Controller

### Architecture
```
Core API → Brain /v1/sessions/start → Brain Controller Worker
                                         ↓
                                    Redis Streams (scan_step_requests)
                                         ↓
                                    Runner Service
                                         ↓
                                    Redis Streams (scan_step_results)
                                         ↓
                                    Brain Controller (decides next step)
```

### Implementation Steps

#### 1. Session Management (Brain)
**File:** `services/thandev-brain/app/api/v1.py`

Add endpoints:
- `POST /v1/sessions/start` - Create session, return `session_id`
- `GET /v1/sessions/{session_id}` - Get session status
- `POST /v1/sessions/{session_id}/stop` - Stop session gracefully

**Session State Schema (Redis):**
```json
{
  "session_id": "uuid",
  "scan_job_id": "uuid",
  "org_id": "string",
  "project_id": "string",
  "target_url": "string",
  "scan_level": "basic|pro|advanced",
  "status": "running|completed|failed|stopped",
  "stop_reason_code": "budget_exceeded|diminishing_returns|confirmed_present|confirmed_absent|user_stopped",
  "current_step_count": 0,
  "total_runtime_sec": 0,
  "consecutive_failures": 0,
  "no_new_findings_iterations": 0,
  "last_updated": "iso8601",
  "created_at": "iso8601"
}
```

**Redis Key:** `session:{org_id}:{project_id}:{session_id}` (TTL: 24 hours)

#### 2. Queue Infrastructure (Redis Streams)
**File:** `services/thandev-brain/app/queue/streams.py`

**Stream: `scan_step_requests`**
```json
{
  "session_id": "uuid",
  "step_id": "uuid",
  "tool_id": "nuclei",
  "mode_id": "pro_web",
  "params": {},
  "target_ref": "http://example.com",
  "depends_on": [],
  "reason": "Initial scan",
  "org_id": "string",
  "project_id": "string",
  "scan_job_id": "uuid"
}
```

**Stream: `scan_step_results`**
```json
{
  "session_id": "uuid",
  "step_id": "uuid",
  "status": "success|failed|timeout",
  "execution_time_sec": 123.45,
  "findings_count": 5,
  "artifact_refs": ["file://...", "s3://..."],
  "error": null,
  "tool_output_summary": "..."
}
```

#### 3. Controller Worker
**File:** `services/thandev-brain/app/controller/session_controller.py`

**Loop Logic:**
```python
async def run_session_loop(session_id: str):
    while True:
        # 1. Load session state
        state = await load_session_state(session_id)
        
        # 2. Check stop conditions
        if should_stop(state):
            await stop_session(session_id, reason_code)
            break
        
        # 3. Retrieve RAG evidence
        rag_evidence = await query_rag_lanes(...)
        
        # 4. Decide next steps (1-N)
        next_steps = await decide_next_steps(state, rag_evidence)
        
        if not next_steps:
            await stop_session(session_id, "diminishing_returns")
            break
        
        # 5. Enqueue steps
        for step in next_steps:
            await enqueue_step_request(step)
        
        # 6. Wait for results (with timeout)
        results = await wait_for_step_results(session_id, step_ids, timeout=300)
        
        # 7. Update state
        await update_session_state(session_id, results)
        
        # 8. Ingest summaries to RAG
        await ingest_step_summaries(results)
```

**Stop Conditions:**
- `max_steps_total` (default: 20)
- `max_total_runtime_sec` (default: 3600)
- `max_consecutive_failures` (default: 3)
- `no_new_findings_iterations` (default: 3) - no new assets/signals/findings
- `confirmed_present` - high-confidence finding detected
- `confirmed_absent` - required confirmatory steps completed, negative evidence

#### 4. Multi-Tenant Safety
- **Redis locks:** `lock:session:{session_id}` (prevents double-processing)
- **Consumer groups:** Use Redis Streams consumer groups for parallel workers
- **Isolation:** Each session has isolated state key

**Deliverable:** `docs/PR4_BRAIN_LOOP.md` with detailed loop flow, queue schema, stop conditions

---

## PR-4B: Separate Runner Service

### Architecture
```
Runner Service (Celery workers or stream consumers)
  ↓
Consumes from: scan_step_requests
  ↓
Validates tool_id/mode_id/params (defense-in-depth)
  ↓
Executes tool (ToolExecutor or adapter)
  ↓
Ingests findings (direct DB or API)
  ↓
Publishes to: scan_step_results
```

### Implementation Steps

#### 1. Create Runner Service
**Directory:** `services/thandev-runner/`

**Structure:**
```
services/thandev-runner/
├── app/
│   ├── __init__.py
│   ├── main.py (optional CLI entrypoint)
│   ├── config.py
│   ├── celery_app.py (Celery worker app)
│   ├── tasks.py (step execution tasks)
│   ├── executor.py (tool execution adapter)
│   └── ingestion.py (findings ingestion)
├── requirements.txt
└── README.md
```

#### 2. Execution Adapter
**File:** `services/thandev-runner/app/executor.py`

**Interface:**
```python
class ToolExecutionAdapter(ABC):
    @abstractmethod
    async def execute_step(
        self,
        tool_id: str,
        mode_id: str,
        params: Dict[str, Any],
        target_ref: str,
        job_dir: Path,
    ) -> StepResult:
        """Execute a tool step and return results"""
```

**Implementation:**
- **LocalAdapter:** Uses `ToolExecutor` from `backend/app/services/tools.py` (today)
- **RemoteAdapter:** Calls remote job service (future)

#### 3. Celery Task (or Stream Consumer)
**File:** `services/thandev-runner/app/tasks.py`

**Option 1: Celery Task**
```python
@celery.task
def execute_scan_step(step_request: Dict[str, Any]):
    # Validate
    # Execute
    # Ingest
    # Publish result
```

**Option 2: Redis Streams Consumer**
```python
async def consume_step_requests():
    while True:
        messages = await stream_client.read("scan_step_requests", count=10)
        for msg in messages:
            await process_step_request(msg)
```

#### 4. Findings Ingestion
**File:** `services/thandev-runner/app/ingestion.py`

**Options:**
- **Direct DB:** Import `findings_ingestor` functions, write directly
- **API:** Call core `/api/v1/findings/batch` endpoint

**Recommendation:** Direct DB for performance, with tenant context validation

#### 5. Core Changes
**File:** `backend/app/tasks/celery_app.py`

**Split into:**
- `backend/app/tasks/celery_client.py` - Enqueue-only (lightweight)
- Keep `celery_app.py` for backward compatibility or remove if not needed

**Deliverable:** Runner service can scale horizontally, executes only allowlisted tools

---

## PR-4C: Fix ffuf 404 False Positives

### Problem
ffuf returns 404 pages as findings because wildcard 404 responses match all paths.

### Solution
1. **Baseline Detection:**
   - Request random path (e.g., `/THANDEV-BASELINE-{random}`)
   - Capture: status code, response size, word count, line count
   - Store as baseline signature

2. **Filtering:**
   - Exclude responses matching baseline signature
   - Exclude 404 status codes
   - Only allow relevant status codes (200, 204, 301, 302, 307, 401, 403)

### Implementation
**File:** `backend/app/services/tools.py` (or `services/thandev-runner/app/executor.py`)

**Changes:**
1. Add baseline request before ffuf execution
2. Store baseline in step context
3. Filter ffuf results using baseline
4. Update `parse_ffuf_output` to accept baseline filter

**File:** `backend/app/services/findings_ingestor.py`

**Changes:**
1. `parse_ffuf_output()` accepts optional `baseline_filter` parameter
2. Filter out matching responses
3. Add tests for baseline filtering

**Deliverable:** ffuf findings exclude 404/wildcard noise

---

## PR-4D: Fix Executive Summary Top Picks

### Problem
1. Top Picks may show stale data (from previous scans)
2. Sorting may not be correct (Critical→Low)

### Solution
1. **Backend:** Ensure `generate_basic_report()` filters by `scan_job_id`
2. **Frontend:** Ensure `generateTopRisks()` filters by current scan
3. **Sorting:** Verify severity order (critical=0, high=1, medium=2, low=3, info=4)

### Implementation

**File:** `backend/app/services/ai/reporter.py`
- Already sorts correctly (line 42-47)
- **Fix:** Ensure `findings` parameter is filtered by `scan_job_id` (caller responsibility)

**File:** `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`
- Line 475-483: Already sorts correctly
- **Fix:** Ensure `findings` is filtered to current scan (line 471 checks `scan?.status !== 'completed'`)

**File:** `backend/app/services/pdf_reports.py`
- Line 1234-1250: Already sorts correctly
- **Fix:** Ensure findings are filtered by scan_job_id

**Add Unit Test:**
```python
def test_top_risks_severity_sorting():
    findings = [
        Finding(severity=Severity.LOW, ...),
        Finding(severity=Severity.CRITICAL, ...),
        Finding(severity=Severity.HIGH, ...),
    ]
    top_risks = generate_basic_report(scan_job, findings)["top_risks"]
    assert top_risks[0]["severity"] == "critical"
    assert top_risks[1]["severity"] == "high"
    assert top_risks[2]["severity"] == "low"
```

**Deliverable:** Top Picks sorted Critical→Low, only from current scan

---

## PR-4E: Update Core Entrypoints

### Changes

**File:** `backend/app/api/projects.py` (or scan endpoint)

**Before:**
```python
# Enqueue Celery task
run_scan_task.delay(scan_job_id, target_url, scan_level, user_id)
```

**After:**
```python
# Call brain to start session
brain_client = get_brain_client()
session = await brain_client.start_session(
    scan_job_id=scan_job_id,
    target_url=target_url,
    scan_level=scan_level,
    org_id=org_id,
    project_id=project_id,
)
# Store session_id in ScanJob
scan_job.brain_session_id = session["session_id"]
```

**File:** `backend/app/models/scan.py`

**Add field:**
```python
brain_session_id = Column(String(36), nullable=True, index=True)
```

**File:** `backend/app/services/brain_client.py`

**Add method:**
```python
async def start_session(
    self,
    scan_job_id: str,
    target_url: str,
    scan_level: str,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Start a brain-controlled scan session"""
```

**Status Endpoint:**
```python
@router.get("/scans/{scan_job_id}/status")
async def get_scan_status(scan_job_id: str):
    # Get session_id from ScanJob
    # Call brain /v1/sessions/{session_id}
    # Return status + progress
```

**Deliverable:** Core starts brain session, stays out of orchestration

---

## Acceptance Criteria

### 1. Multi-Tenant Concurrency
- ✅ Run 10 concurrent sessions (different tenants/projects)
- ✅ Sessions do not leak state
- ✅ Queue processes steps fairly
- ✅ Budgets stop sessions

### 2. Brain Loop Adapts
- ✅ Brain changes next step based on new findings/signals
- ✅ RAG evidence influences planning mid-scan

### 3. ffuf Fixes
- ✅ ffuf findings do not show baseline 404 noise
- ✅ True 200/403 endpoints are detected

### 4. Top Picks Fixes
- ✅ Top Picks sorted Critical→Low
- ✅ Top Picks only from current scan (not stale)

### 5. Runner Separation
- ✅ Runner workers are separate from core process
- ✅ Runner can scale independently
- ✅ Runner validates tool_id/mode_id/params strictly

---

## Implementation Order

1. **PR-4A:** Brain session controller + queues (foundation)
2. **PR-4B:** Runner service separation (execution)
3. **PR-4C:** Fix ffuf 404 false positives (bug fix)
4. **PR-4D:** Fix Top Picks sorting (bug fix)
5. **PR-4E:** Update core entrypoints (integration)

---

## Dependencies

- **Redis:** Already available (Celery broker)
- **Qdrant:** Already available (RAG store)
- **PostgreSQL/SQLite:** Already available (core DB)

---

## Testing Strategy

1. **Unit Tests:**
   - Session controller loop logic
   - Stop conditions
   - ffuf baseline filtering
   - Top Picks sorting

2. **Integration Tests:**
   - 10 concurrent sessions
   - Brain adapts to findings
   - Runner executes steps correctly

3. **Manual Tests:**
   - Start session via core API
   - Monitor brain logs
   - Verify findings in DB
   - Check Top Picks in UI

---

## Documentation

- `docs/PR4_BRAIN_LOOP.md` - Detailed loop flow
- `services/thandev-runner/README.md` - Runner setup
- `services/thandev-brain/README.md` - Brain session API



