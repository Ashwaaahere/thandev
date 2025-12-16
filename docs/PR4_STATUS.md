# PR-4 Implementation Status

## ✅ PR-4A: Brain-Owned Session Controller (COMPLETED)

### Implemented:
1. **Session Models** (`app/models.py`):
   - `StartSessionRequest`, `StartSessionResponse`
   - `GetSessionResponse`, `StopSessionResponse`
   - `SessionState`, `SessionStatus`, `StopReasonCode`

2. **Session State Management** (`app/session/state.py`):
   - Redis-based session storage with tenant-aware keys
   - `create_session()`, `get_session()`, `update_session()`, `stop_session()`
   - Session locking (`acquire_session_lock()`, `release_session_lock()`)

3. **Redis Streams** (`app/queue/streams.py`):
   - `StepRequest` and `StepResult` message classes
   - `publish_step_request()`, `publish_step_result()`
   - `consume_step_requests()`, `read_step_results()`

4. **Session Endpoints** (`app/api/v1.py`):
   - `POST /v1/sessions/start` - Create and start session
   - `GET /v1/sessions/{session_id}` - Get session status
   - `POST /v1/sessions/{session_id}/stop` - Stop session

5. **Controller Worker** (`app/controller/session_controller.py`):
   - `run_session_loop()` - Main closed-loop logic
   - `check_stop_conditions()` - Budget and diminishing returns checks
   - `decide_next_steps()` - Uses existing planner
   - `update_session_from_results()` - Updates state from step results
   - `ingest_step_summaries()` - Ingests to RAG

### Configuration:
- Added Redis URL and session TTL to `app/core/config.py`
- Added session policy limits (max_steps, max_runtime, etc.)

### Next Steps:
- Start controller as background worker process (needs integration with FastAPI lifespan)
- Add session lookup by session_id only (currently needs org_id/project_id)

---

## ⏳ PR-4B: Separate Runner Service (IN PROGRESS)

### To Do:
1. Create `services/thandev-runner/` structure
2. Implement tool execution adapter
3. Implement Celery tasks or stream consumers
4. Implement findings ingestion

---

## ⏳ PR-4C: Fix ffuf 404 False Positives (PENDING)

### To Do:
1. Implement baseline detection in `_run_ffuf()`
2. Update `parse_ffuf_output()` to filter by baseline
3. Add tests

---

## ⏳ PR-4D: Fix Top Picks Sorting (PENDING)

### To Do:
1. Verify sorting in `generate_basic_report()` (already correct)
2. Verify sorting in frontend (already correct)
3. Ensure findings filtered by scan_job_id
4. Add unit test

---

## ⏳ PR-4E: Update Core Entrypoints (PENDING)

### To Do:
1. Add `brain_session_id` field to `ScanJob` model
2. Update scan start endpoint to call brain `/v1/sessions/start`
3. Add status endpoint that calls brain `/v1/sessions/{session_id}`
4. Update `brain_client.py` with `start_session()` method

---

## Notes

- PR-4A foundation is complete and ready for testing
- Controller worker needs to be started as a background process
- Runner service (PR-4B) is the next critical piece
- Bug fixes (PR-4C, PR-4D) are smaller and can be done in parallel



