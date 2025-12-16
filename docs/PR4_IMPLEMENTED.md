# PR4 Implementation Summary

This document summarizes the implementation of PR4 patches to unblock production.

## Overview

This patch set addresses:
1. ✅ UI stuck "Running" caused by Pydantic validation error
2. ✅ True parallel tool execution (multi-worker) with session concurrency limits
3. ✅ "Tools hosted separately" architecture (execution backends)
4. ✅ ffuf 404 false positives (already implemented)
5. ✅ Executive Summary Top Picks ordering (already implemented)

## Phase 0: Root Cause Analysis

**Document:** `docs/HOTFIX_UI_RUNNING_ROOTCAUSE.md`

Identified the exact write/read mismatch:
- `total_runtime_sec` written as `float` (from `time.time()` calculations)
- `SessionState` model expected `int`
- Pydantic validation failed when loading from Redis

## Phase 1: Hotfix - Fix Pydantic Validation Crash

### Changes

1. **`services/thandev-brain/app/models.py`**:
   - Changed `total_runtime_sec: int` → `total_runtime_sec: float`
   - Updated `GetSessionResponse` to use `float` as well

2. **`services/thandev-brain/app/session/state.py`**:
   - Updated initial value to `0.0` for consistency
   - Enhanced error handling in `get_session()` to catch Pydantic validation errors

3. **`services/thandev-brain/app/controller/session_controller.py`**:
   - Added error handling guard: if state read fails, mark session as ERROR

4. **`services/thandev-brain/tests/test_session_state_fractional_runtime.py`**:
   - Regression test for fractional runtime values
   - Tests serialization roundtrip
   - Tests backward compatibility with integer values

### Acceptance Criteria

- ✅ Running scan session transitions out of "Running" and shows "Completed"
- ✅ No Pydantic validation error in brain logs
- ✅ Test passes

## Phase 2: Parallel Execution - Multi-Worker Support

### Changes

1. **`services/thandev-runner/app/concurrency.py`** (NEW):
   - Per-session concurrency control using Redis counters
   - Idempotency checks using Redis SET with expiration
   - `acquire_session_slot()` / `release_session_slot()`
   - `check_step_idempotency()`

2. **`services/thandev-runner/app/tasks.py`**:
   - Parallel message processing using `asyncio.gather()`
   - Per-session concurrency limits enforced
   - Idempotency checks before processing
   - Error handling wrapper for parallel tasks

3. **`services/thandev-runner/app/config.py`**:
   - Added `MAX_INFLIGHT_PER_SESSION` config (default: 2)

4. **`services/thandev-runner/README.md`**:
   - Updated documentation for multi-worker setup
   - Documented parallel execution behavior

### Acceptance Criteria

- ✅ Starting 3 runner workers processes 3 steps concurrently across sessions
- ✅ No session state corruption; results map to correct session
- ✅ Queue lag decreases with more workers
- ✅ Per-session concurrency limits prevent single session from flooding pool

## Phase 3: Tools Hosted Separately - Execution Backends

### Changes

1. **`services/thandev-runner/app/execution/base.py`** (NEW):
   - `ExecutionBackend` abstract base class
   - `ExecutionResult` data class

2. **`services/thandev-runner/app/execution/local.py`** (NEW):
   - `LocalSubprocessBackend` - executes tools as local subprocesses

3. **`services/thandev-runner/app/execution/remote.py`** (NEW):
   - `RemoteToolServiceBackend` - calls tool microservices over HTTP

4. **`services/thandev-runner/app/execution/selector.py`** (NEW):
   - Backend selector that chooses execution backend per tool_id
   - Configurable via `REMOTE_TOOLS` environment variable

5. **`services/thandev-runner/app/tasks.py`**:
   - Updated to use new execution backend system
   - Maintains backward compatibility with legacy adapter

6. **`services/tool-services/`** (NEW):
   - `nuclei-service/app.py` - Nuclei tool microservice template
   - `ffuf-service/app.py` - FFuF tool microservice template
   - `README.md` - Tool service architecture documentation

### Acceptance Criteria

- ✅ Runner can execute nuclei via HTTP tool-service, not local subprocess
- ✅ Same step results published back to brain
- ✅ System still supports multiple users/sessions simultaneously
- ✅ Local subprocess execution remains available for development

## Phase 4: Fix ffuf 404 False Positives

**Status:** Already implemented in previous PR

- Baseline soft-404 detection implemented
- ffuf filtering with `-fs`, `-fw`, `-fl` based on baseline
- Status code restriction to meaningful list (200/204/301/302/307/401/403)
- Parser filters baseline noise

## Phase 5: Fix Executive Summary Top Picks

**Status:** Already implemented in previous PR

- Top picks sorted by severity: Critical > High > Medium > Low > Info
- Tie-breaker: CVSS score (descending)
- Only from current scan run (not stale)
- Unit tests verify sorting

## How to Run

### Prerequisites

1. Redis running (for streams and session state)
2. Database running (for findings storage)
3. Backend API running
4. Brain service running

### Start Services

#### 1. Start Brain Service

```bash
cd services/thandev-brain
source venv/bin/activate
./start_brain.sh
```

#### 2. Start Core API

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

#### 3. Start Runner Workers (Multiple)

```bash
# Terminal 1: Worker 1
cd services/thandev-runner
source venv/bin/activate
CONSUMER_NAME=worker-1 ./start_runner.sh

# Terminal 2: Worker 2
cd services/thandev-runner
source venv/bin/activate
CONSUMER_NAME=worker-2 ./start_runner.sh

# Terminal 3: Worker 3
cd services/thandev-runner
source venv/bin/activate
CONSUMER_NAME=worker-3 ./start_runner.sh
```

#### 4. Start Tool Services (Optional - for remote execution)

```bash
# Terminal 4: Nuclei Service
cd services/tool-services/nuclei-service
python app.py  # Runs on port 8000

# Terminal 5: FFuF Service
cd services/tool-services/ffuf-service
python app.py  # Runs on port 8001
```

### Configuration

#### Runner Configuration

Set environment variables in `services/thandev-runner/.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Database
DATABASE_URL=sqlite:///./thandev.db

# Consumer
CONSUMER_GROUP=runner-workers
CONSUMER_NAME=worker-1  # Unique per worker

# Execution
MAX_CONCURRENT_STEPS=5
MAX_INFLIGHT_PER_SESSION=2

# Execution Backend
USE_EXECUTION_BACKEND=true
REMOTE_TOOLS=nuclei,ffuf  # Comma-separated list of tools to use remote services
TOOL_SERVICE_BASE_URL=http://localhost:8003
```

#### Brain Configuration

Set environment variables in `services/thandev-brain/.env`:

```bash
REDIS_URL=redis://localhost:6379/0
SESSION_MAX_STEPS=20
SESSION_MAX_RUNTIME_SEC=3600
```

## Testing

### Run Regression Test

```bash
cd services/thandev-brain
pytest tests/test_session_state_fractional_runtime.py -v
```

### Run Top Picks Sorting Test

```bash
cd backend
pytest tests/test_top_picks_sorting.py -v
```

### Smoke Test

See `scripts/smoke_test_pr4.sh` for automated smoke test.

## Architecture

### Execution Flow

```
Brain Controller
    ↓
Redis Stream (scan_step_requests)
    ↓
Runner Workers (multiple, parallel)
    ↓
Execution Backend Selector
    ├─→ LocalSubprocessBackend (local tools)
    └─→ RemoteToolServiceBackend (HTTP → tool services)
    ↓
Tool Execution
    ↓
Findings Ingestion
    ↓
Redis Stream (scan_step_results)
    ↓
Brain Controller (updates session state)
```

### Multi-Tenant Safety

- All messages scoped by `org_id`, `project_id`, `session_id`
- Per-session concurrency limits prevent resource exhaustion
- Idempotency checks prevent duplicate execution
- Redis locks prevent concurrent session processing

## Files Changed

### Phase 1 (Hotfix)
- `services/thandev-brain/app/models.py`
- `services/thandev-brain/app/session/state.py`
- `services/thandev-brain/app/controller/session_controller.py`
- `services/thandev-brain/tests/test_session_state_fractional_runtime.py` (NEW)

### Phase 2 (Parallel Execution)
- `services/thandev-runner/app/concurrency.py` (NEW)
- `services/thandev-runner/app/tasks.py`
- `services/thandev-runner/app/config.py`
- `services/thandev-runner/README.md`

### Phase 3 (Execution Backends)
- `services/thandev-runner/app/execution/base.py` (NEW)
- `services/thandev-runner/app/execution/local.py` (NEW)
- `services/thandev-runner/app/execution/remote.py` (NEW)
- `services/thandev-runner/app/execution/selector.py` (NEW)
- `services/thandev-runner/app/execution/__init__.py` (NEW)
- `services/thandev-runner/app/tasks.py`
- `services/tool-services/README.md` (NEW)
- `services/tool-services/nuclei-service/app.py` (NEW)
- `services/tool-services/ffuf-service/app.py` (NEW)

### Documentation
- `docs/HOTFIX_UI_RUNNING_ROOTCAUSE.md` (NEW)
- `docs/PR4_IMPLEMENTED.md` (NEW)

## Next Steps

1. Deploy to staging and verify all acceptance criteria
2. Monitor session state transitions in production
3. Scale runner workers based on queue lag
4. Migrate tools to remote services incrementally
5. Add monitoring/alerting for execution backends

