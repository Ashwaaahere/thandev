# Scan Pipeline Technical Notes

**Purpose:** Technical documentation of the scan execution pipeline, status tracking, and tool orchestration. For developers working on scan reliability and observability.

---

## Current Architecture

### Models

**ScanJob** (`backend/app/models/scan.py`):
- `id` (String, PK)
- `project_id` (String, FK) - Links to projects
- `scan_level` (Enum: BASIC, PRO, ADVANCED)
- `status` (Enum: PENDING, QUEUED, RUNNING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED, CANCELLED)
- `celery_task_id` (String) - Celery task tracking
- `brain_session_id` (String) - Brain service session tracking
- `summary` (JSON) - Results summary
- `stack_info` (JSON) - Target metadata (HTTP headers, etc.)
- `ai_plan` (JSON) - AI-generated scan plan
- `ai_status` (String) - AI planner status
- `error_message` (Text) - Error information
- `created_at`, `started_at`, `completed_at` - Timestamps
- Relationships: `findings`, `tool_results`, `project`

**ToolResult** (`backend/app/models/finding.py`):
- `id` (String, PK)
- `scan_job_id` (String, FK) - Links to scan job
- `tool_name` (String) - Tool identifier
- `output` (Text) - Raw tool output
- `exit_code` (Integer) - Tool exit code
- `execution_time` (Float) - Execution time in seconds
- `command` (String) - Command executed
- `error_message` (Text) - Error message if failed
- `timed_out` (Integer, 0/1) - Whether tool timed out
- `created_at` (DateTime) - Timestamp

**Current Limitations:**
- No per-tool status tracking (only ToolResult records)
- No planned tools list (tools are determined at runtime)
- Timeouts are hardcoded per tool (no scan-level configuration)
- Tool failures can cause silent "success" (scan completes with 0 findings)
- No parallelism control beyond `MAX_PARALLEL_TOOLS` setting

---

## Orchestration Flow

### 1. Scan Creation & Queuing

**Entry Point:** `POST /api/scans` → `backend/app/api/scans.py::create_scan()`

1. Creates `ScanJob` with `status = PENDING`
2. Calls `ScanOrchestrator.queue_scan()` → queues Celery task
3. Celery task: `backend/app/tasks/celery_app.py::run_scan_task()`
   - Updates status to `RUNNING`
   - Calls `run_scan_for_job()`

### 2. Scan Execution

**Main Function:** `backend/app/services/scan_orchestrator.py::run_scan_for_job()`

**Flow:**
1. **Stack Info Collection:**
   - HTTP HEAD/GET to target URL
   - Captures status_code, headers (Server, X-Powered-By, etc.)
   - Stores in `scan_job.stack_info`

2. **Scan Planning:**
   - **Option A (Brain Service):** POST `/v1/plan-scan` → returns plan with `waves[]`
   - **Option B (Fallback):** Uses `tool_matrix.py` → converts to plan format
   - Plan structure: `{ "waves": [{"phase": "...", "tools": [...]}] }`

3. **HTTP Security Header Checks:**
   - Runs before other tools
   - Analyzes headers for missing security headers
   - Creates Finding records via `ingest_http_header_findings()`

4. **Tool Execution (Waves):**
   - For each wave in plan:
     - Tools run in parallel (max `MAX_PARALLEL_TOOLS` concurrent)
     - Each tool: `_run_single_tool()` → `ToolExecutor.run_tool()` or `run_step()`
     - Results saved to `ToolResult` table
     - Findings ingested immediately after each tool

5. **Scan Completion:**
   - Updates `status = COMPLETED` or `COMPLETED_WITH_ERRORS`
   - Updates `completed_at` timestamp
   - Calls `update_findings_lifecycle_after_scan()` (for lifecycle tracking)

### 3. Tool Execution

**ToolExecutor** (`backend/app/services/tools.py`):
- Supports: `nuclei`, `nmap`, `sslscan`, `httpx`, `ffuf`, `dalfox`, `sqlmap`
- Each tool method: `_run_nuclei()`, `_run_nmap()`, etc.
- Uses `subprocess.run()` or `asyncio.create_subprocess_exec()`
- Returns dict: `{ "output", "exit_code", "execution_time", "success", "error", "timed_out" }`

**Current Timeout Behavior:**
- Most tools: hardcoded `timeout=300` (5 minutes)
- Some tools: `timeout_seconds` from kwargs (default 300)
- Timeout handling: catches `subprocess.TimeoutExpired`, sets `timed_out=True`
- **Issue:** No scan-level timeout configuration

---

## Status Tracking

### Scan Status

**ScanStatus Enum:**
- `PENDING` - Created but not queued
- `QUEUED` - Queued in Celery
- `RUNNING` - Currently executing
- `COMPLETED` - All tools finished successfully
- `COMPLETED_WITH_ERRORS` - Some tools failed but scan finished
- `FAILED` - Scan failed (critical error)
- `CANCELLED` - User cancelled

**Current Status Logic:**
- Set to `RUNNING` when Celery task starts
- Set to `COMPLETED` if all tools succeed
- Set to `COMPLETED_WITH_ERRORS` if some tools fail
- Set to `FAILED` if critical error (DB error, etc.)

**Issue:** No per-tool status tracking. Only `ToolResult` records exist, but no "planned vs executed" tracking.

### Tool Status (Current)

**ToolResult Model:**
- Created after each tool execution
- Contains: `exit_code`, `execution_time`, `error_message`, `timed_out`
- **Issue:** No "pending" or "running" status - only exists after completion

**API Response:**
- `GET /api/scans/{scan_id}` → `ScanResponse` with `tool_statuses: List[ToolStatus]`
- Currently derived from `ToolResult` records (latest per tool)
- Status inferred: `completed` if `exit_code == 0`, `failed` if `exit_code != 0`, `timed_out` if `timed_out == 1`

**Issue:** No way to know which tools are planned vs executed. No "pending" or "running" status during execution.

---

## Timeouts

### Current Timeout Configuration

**Global Settings** (`backend/app/core/config.py`):
- `MAX_SCAN_TIMEOUT_SECONDS = 3600` (1 hour) - **Not currently enforced**
- `TOOL_EXECUTION_TIMEOUT_SECONDS = 900` (15 minutes) - **Not used consistently**

**Per-Tool Timeouts** (hardcoded in `tools.py`):
- `nuclei`: 300 seconds (5 minutes)
- `nmap`: 300 seconds (5 minutes)
- `sslscan`: 300 seconds (5 minutes)
- `httpx`: 30 seconds
- `ffuf`: 300 seconds (or from `timeout_seconds` kwarg, default 300)
- `dalfox`: 300 seconds (or from `timeout_seconds` kwarg, default 300)
- `sqlmap`: 300 seconds (or from `timeout_seconds` kwarg, default 300)

**Tool Matrix** (`backend/app/core/tool_matrix.py`):
- Some tools have `timeout_seconds` in config (e.g., `ffuf: 300`, `dalfox: 300`, `sqlmap: 300`)
- **Issue:** No scan-level timeout configuration

**Timeout Handling:**
- `subprocess.run(timeout=...)` raises `subprocess.TimeoutExpired`
- Caught in tool methods, returns `{"timed_out": True, "error": "Tool execution timed out..."}`
- Saved to `ToolResult.timed_out = 1`
- **Issue:** Timeout doesn't fail the scan, but also doesn't clearly mark tool as failed

---

## Parallelism

### Current Parallelism Control

**Configuration:**
- `MAX_PARALLEL_TOOLS = 5` (in `settings`)
- Used in `run_scan_for_job()`: `ThreadPoolExecutor(max_workers=min(len(tools), settings.MAX_PARALLEL_TOOLS))`

**Execution:**
- Tools within a wave run in parallel
- Waves run sequentially
- Each tool gets its own thread with thread-local DB session and event loop

**Issue:** No differentiation by scan level. Advanced scans can still run 5 tools in parallel, which may overload the system.

---

## Failure Handling

### Current Failure Behavior

**Tool Failures:**
- Tool execution errors caught in `ToolExecutor.run_tool()`
- Returns `{"success": False, "error": str(e)}`
- Saved to `ToolResult` with `error_message`
- **Issue:** Tool failure doesn't prevent scan from completing

**Scan Status on Tool Failure:**
- If all tools fail → `COMPLETED_WITH_ERRORS` (not `FAILED`)
- If some tools fail → `COMPLETED_WITH_ERRORS`
- **Issue:** Scan can complete with 0 findings if all tools fail silently

**Missing Binary:**
- Tools check for binary existence before running
- Returns `{"error": "Binary not found..."}`
- **Issue:** No clear "skipped" status - just fails

**Target Unreachable:**
- Some tools may fail if target is unreachable
- Error message stored in `ToolResult.error_message`
- **Issue:** No distinction between "target unreachable" and other errors

---

## API Surface

### Current API Endpoints

**GET /api/scans/{scan_id}** (`backend/app/api/scans.py::get_scan()`):
- Returns `ScanResponse` with:
  - `status` (ScanStatus enum)
  - `tool_statuses: List[ToolStatus]` (derived from ToolResult records)
  - `findings: List[FindingResponse]`
  - `summary`, `stack_info`, `ai_plan`, etc.

**ToolStatus Schema:**
- `tool_name: str`
- `status: str` (inferred: "completed" | "failed" | "timed_out")
- `started_at`, `completed_at`, `execution_time`, `error_message`

**Issue:** No "pending" or "running" status. Frontend can't show real-time progress.

---

## Planned Improvements

See implementation notes below for:
1. Per-scan-level and per-tool timeout configuration
2. Per-tool status tracking (pending/running/completed/failed/skipped)
3. Graceful failure handling (tool failures don't cause silent success)
4. Parallelism control by scan level
5. Enhanced API response with real-time tool status

---

## Implementation Notes

### Timeout Configuration

**New Configuration Structure:**
```python
SCAN_TIMEOUTS = {
    "basic": {
        "max_total_seconds": 600,  # 10 minutes
        "per_tool": {
            "nuclei": 120,  # 2 minutes
            "httpx": 30,
        }
    },
    "pro": {
        "max_total_seconds": 1800,  # 30 minutes
        "per_tool": {
            "nuclei": 300,  # 5 minutes
            "nmap": 300,
            "ffuf": 300,
            "dalfox": 300,
            ...
        }
    },
    "advanced": {
        "max_total_seconds": 3600,  # 1 hour
        "per_tool": {
            "nuclei": 600,  # 10 minutes
            "nmap": 600,
            "ffuf": 600,
            "dalfox": 600,
            "sqlmap": 900,  # 15 minutes
            ...
        }
    }
}
```

### Per-Tool Status Tracking

**New Model: ScanToolExecution** (optional, or use existing ToolResult with status field):
- `scan_job_id` (FK)
- `tool_name` (String)
- `status` (Enum: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
- `error_code` (String, nullable) - e.g., "timeout", "missing_binary", "target_unreachable"
- `error_message` (Text, nullable) - User-safe error message
- `started_at`, `completed_at`, `execution_time`

**Alternative:** Extend `ToolResult` model to include `status` field and `planned` flag.

### Graceful Failure

**New Logic:**
- Before scan: Create `ScanToolExecution` records for all planned tools (status = PENDING)
- During execution: Update status to RUNNING → COMPLETED/FAILED
- On failure: Set status = FAILED, store error_code and error_message
- After all tools: Set scan status:
  - `COMPLETED` if at least one tool completed successfully
  - `FAILED` only if no tools could run (all failed with critical errors)

### Parallelism Control

**New Configuration:**
```python
SCAN_PARALLELISM = {
    "basic": {"max_concurrent": 2},
    "pro": {"max_concurrent": 3},
    "advanced": {"max_concurrent": 4},
}
```

**Implementation:** Use scan-level max_concurrent instead of global `MAX_PARALLEL_TOOLS`.

---

## Implementation Status (After Improvements)

### ✅ Completed Improvements

1. **Per-Scan-Level and Per-Tool Timeouts** (`backend/app/core/scan_timeouts.py`):
   - Configuration for basic/pro/advanced scan levels
   - Per-tool timeout settings
   - Functions: `get_tool_timeout()`, `get_max_scan_timeout()`, `get_max_parallelism()`
   - Defaults:
     - Basic: 10 min total, 2 min per tool
     - Pro: 30 min total, 5 min per tool
     - Advanced: 1 hour total, 10-15 min per tool

2. **Per-Tool Status Tracking** (`backend/app/models/finding.py`):
   - Added `ToolExecutionStatus` enum: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, TIMED_OUT
   - Extended `ToolResult` model with:
     - `status` (ToolExecutionStatus enum)
     - `error_code` (String: "timeout", "missing_binary", "target_unreachable", etc.)
     - `started_at`, `completed_at` (DateTime timestamps)
   - Migration: `0009_add_tool_status_tracking.py`

3. **Graceful Failure Handling** (`backend/app/services/scan_orchestrator.py`):
   - Tools create PENDING records before execution
   - Status updated: PENDING → RUNNING → COMPLETED/FAILED/TIMED_OUT/SKIPPED
   - Tool failures don't crash the scan
   - Scan status logic:
     - `COMPLETED` if at least one tool completed successfully
     - `COMPLETED_WITH_ERRORS` if some tools failed but at least one succeeded
     - `FAILED` only if no tools completed (all failed)

4. **Parallelism Control** (`backend/app/core/scan_timeouts.py`):
   - Scan-level parallelism limits:
     - Basic: max 2 concurrent tools
     - Pro: max 3 concurrent tools
     - Advanced: max 4 concurrent tools
   - Used in `run_scan_for_job()` instead of global `MAX_PARALLEL_TOOLS`

5. **API Updates** (`backend/app/api/scans.py`):
   - `GET /api/scans/{scan_id}` now returns:
     - `tool_statuses[]` with `status`, `error_code`, `started_at`, `completed_at`
     - Status values: "pending", "running", "completed", "failed", "skipped", "timed_out"
   - Backward compatible with legacy records (infers status from exit_code/timed_out)

### Timeout Behavior

**Per-Tool Timeouts:**
- Enforced via `timeout_seconds` parameter passed to `ToolExecutor.run_tool()`
- Tools respect timeout from `scan_timeouts.py` configuration
- On timeout: tool status = TIMED_OUT, error_code = "timeout"

**Scan-Level Timeouts:**
- `get_max_scan_timeout()` returns max total scan duration
- **Note:** Not yet enforced at scan level (future improvement)
- Individual tool timeouts prevent tools from running indefinitely

### Failure Behavior

**Tool Failures:**
- Missing binary → status = FAILED, error_code = "missing_binary"
- Target unreachable → status = FAILED, error_code = "target_unreachable"
- Timeout → status = TIMED_OUT, error_code = "timeout"
- Execution error → status = FAILED, error_code = "execution_error"

**Scan Status:**
- Scan completes successfully if at least one tool succeeds
- Scan marked as FAILED only if no tools completed
- Failed tools are logged but don't prevent scan completion

### Parallelism Behavior

**Current Implementation:**
- Tools within a wave run in parallel (up to scan-level limit)
- Waves run sequentially
- Each tool gets its own thread with thread-local DB session

**Limits:**
- Basic: 2 concurrent tools
- Pro: 3 concurrent tools
- Advanced: 4 concurrent tools

---

## TODO / Future Improvements

- [ ] Enforce scan-level total timeout (currently only per-tool timeouts enforced)
- [ ] Add tests for timeout and failure scenarios
- [ ] Add UI indicators for tool status (pending/running/completed/failed)
- [ ] Consider adding tool retry logic for transient failures
- [ ] Add metrics/telemetry for tool execution times and failure rates

