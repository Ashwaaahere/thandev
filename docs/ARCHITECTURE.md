# Thandev Architecture Map

**Generated:** 2025-01-XX  
**Purpose:** Market-ready architecture documentation and conflict resolution

---

## 1. Current System Map

### A) Services & Entrypoints

```
┌─────────────────────────────────────────────────────────────────┐
│                         THANDEV MONOREPO                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Backend       │      │  thandev-brain   │      │ thandev-runner  │
│   (FastAPI)     │      │   (FastAPI)      │      │   (Async Loop)  │
│                 │      │                 │      │                 │
│ Entry:          │      │ Entry:           │      │ Entry:          │
│ main.py:8000    │      │ main.py:8001      │      │ main.py         │
│                 │      │                 │      │                 │
│ - API routes    │      │ - Planning       │      │ - Tool exec     │
│ - Orchestration │      │ - RAG queries    │      │ - Findings      │
│ - Persistence   │      │ - Session mgmt  │      │ - Redis streams │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
            ┌───────▼────────┐          ┌────────▼───────┐
            │   PostgreSQL   │          │     Redis       │
            │   (Database)    │          │  (Queue/Streams)│
            │                 │          │                 │
            │ - tenants      │          │ - Celery broker │
            │ - projects     │          │ - Redis streams │
            │ - scan_jobs    │          │   (step req/res)│
            │ - tool_results │          │                 │
            │ - findings     │          │                 │
            │ - notifications│          │                 │
            └────────────────┘          └─────────────────┘
```

**Communication Patterns:**
- **Backend ↔ Brain:** HTTP REST (brain_client.py)
- **Backend ↔ Runner:** Redis Streams (scan_step_requests, scan_step_results)
- **Brain ↔ Runner:** Redis Streams (brain publishes requests, runner publishes results)
- **Backend ↔ Celery:** Redis (Celery broker/result backend)
- **All ↔ PostgreSQL:** SQLAlchemy ORM

### B) Job Execution Types & Executors

| Job Type | Executor | Queue/Trigger | Status |
|----------|----------|---------------|--------|
| **Scan Execution** | **CONFLICT:** Both Celery AND Runner | Celery task OR Redis streams | ⚠️ DUPLICATE |
| **Plan Generation** | Brain service | HTTP call from backend | ✅ OK |
| **Tool Execution** | Runner (via streams) OR Celery (direct) | Redis streams OR Celery task | ⚠️ DUPLICATE |
| **NVD/KEV Ingestion** | Celery (scheduler.py) | Celery scheduled task | ✅ OK |
| **Notifications** | Backend (sync) | Direct DB write | ✅ OK |

**CONFLICT IDENTIFIED:**
- **Scan execution has TWO paths:**
  1. **Path A (Brain-enabled):** Backend → Brain → Redis Streams → Runner → Tools
  2. **Path B (Legacy/Celery):** Backend → Celery Task → scan_orchestrator.run_scan_for_job() → Tools (direct)

### C) Duplication/Overlap

**CRITICAL CONFLICTS:**

1. **Scan Execution Overlap:**
   - `backend/app/api/scans.py:create_scan()` routes to Brain if `BRAIN_SERVICE_ENABLED=true`
   - Brain publishes to Redis streams → Runner executes
   - **BUT** if Brain fails or is disabled, falls back to Celery task
   - Celery task calls `run_scan_for_job()` which executes tools DIRECTLY (bypasses Runner)
   - **Result:** Two execution paths, tools may run twice or status may be inconsistent

2. **Tool Execution Overlap:**
   - Runner executes tools via Redis streams (intended path)
   - Celery's `run_scan_for_job()` executes tools directly via `ToolExecutor` (legacy path)
   - Both write to same `tool_results` table → potential race conditions

3. **Database Connection Mismatch:**
   - Backend uses `DATABASE_URL` from `backend/.env`
   - Runner uses `DATABASE_URL` from `services/thandev-runner/.env` (defaults to SQLite if not set)
   - **Result:** "Scan job not found" errors when runner can't see backend's DB

### D) Environment Mode Flags

| Flag | Location | Purpose | Production Safe? |
|------|----------|---------|------------------|
| `ENVIRONMENT` | `backend/app/core/config.py` | Controls auto-creation, DB defaults | ✅ Yes |
| `THANDEV_DISABLE_PLAN_ENFORCEMENT` | `backend/app/api/scans.py` | Bypass plan limits | ⚠️ Only in dev/test |
| `RUN_MANUAL_INTEGRATION` | Tests | Manual test flag | ✅ OK |
| `THANDEV_FAST_MANUAL` | Tests | Fast manual tests | ✅ OK |
| `THANDEV_PIPELINE_TOOLS` | Tests | Filter tools in tests | ✅ OK |
| `BRAIN_SERVICE_ENABLED` | `backend/app/core/config.py` | Enable/disable brain | ✅ Yes |
| `BRAIN_REQUIRED` | `backend/app/core/config.py` | Fail if brain unreachable | ✅ Yes |
| `TENANT_AUTOCREATE_ENABLED` | `backend/app/core/config.py` | Auto-create tenants/users | ⚠️ Only in dev/test |
| `THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD` | `backend/app/core/config.py` | Override for production | ❌ DANGEROUS |

**Bypass Safety Check:**
```python
# backend/app/api/scans.py:306-309
if (
    settings.ENVIRONMENT.strip().lower() in ("local", "dev", "test", "development")
    and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
):
```
✅ **SAFE:** Bypass only works in non-production environments.

### E) Database Models & Schema

**Canonical Models (from `backend/app/models/`):**

| Model | Table | Key Fields | ID Type |
|-------|-------|------------|---------|
| `Tenant` | `tenants` | `id`, `name`, `plan` | String(36) UUID |
| `User` | `users` | `id`, `email`, `tenant_id` | String(36) UUID |
| `Project` | `projects` | `id`, `name`, `target_url`, `tenant_id`, `owner_id` | String(36) UUID |
| `ScanJob` | `scan_jobs` | `id`, `project_id`, `scan_level`, `status`, `brain_session_id`, `celery_task_id` | String(36) UUID |
| `ToolResult` | `tool_results` | `id`, `scan_job_id`, `tool_name`, `status`, `error_code` | String(36) UUID |
| `Finding` | `findings` | `id`, `scan_job_id`, `severity`, `tool_result_id` | String(36) UUID |
| `Notification` | `notifications` | `id`, `tenant_id`, `owner_id`, `type`, `is_read` | String(36) UUID |

**Migrations:**
- Location: `backend/migrations/versions/`
- Latest: `0013_create_notifications_table.py` (creates notifications table)
- Alembic head should be at `0013_create_notifications_table`

**Schema Consistency:**
- ✅ All IDs are `String(36)` (UUID format)
- ✅ All timestamps use `DateTime(timezone=True)`
- ✅ Foreign keys properly indexed

---

## 2. Target Architecture (Market-Ready v1)

### Decision: Runner-Based Execution (Default)

**PRIMARY PATH (Brain + Runner):**
```
POST /api/scans
  ↓
Backend validates & creates ScanJob
  ↓
Brain service: start_session() → creates plan
  ↓
Brain publishes step requests → Redis Stream (scan_step_requests)
  ↓
Runner consumes → executes tools → ingests findings → publishes results
  ↓
Brain consumes results → updates plan → publishes next steps (loop)
  ↓
Brain marks scan complete → Backend updates ScanJob.status
```

**DEFAULT PATH (Brain Disabled - v1 Market Ready):**
```
POST /api/scans
  ↓
Backend validates & creates ScanJob
  ↓
Backend uses tool_matrix to determine tools for scan_level
  ↓
Backend publishes step requests → Redis Stream (scan_step_requests)
  ↓
Runner consumes → executes tools → ingests findings → publishes results
  ↓
Backend updates ScanJob.status based on tool results
```

**CELERY ROLE (v1):**
- ✅ **KEEP:** Only for scheduled ingestion tasks (NVD/KEV)
- ✅ **KEEP:** Optional scan execution if `USE_CELERY_SCAN_EXECUTION=true` (legacy mode)
- ❌ **DEFAULT:** Celery NOT required for scans (Runner is default)
- ❌ **REMOVED:** Direct tool execution from `run_scan_for_job()` when using Runner path

**Configuration:**
- `USE_CELERY_SCAN_EXECUTION=false` (default) → Runner path via Redis streams
- `USE_CELERY_SCAN_EXECUTION=true` → Legacy Celery path (for backward compatibility)

### Component Roles

| Component | Role | Responsibilities |
|-----------|------|------------------|
| **Backend** | API + Orchestration | - HTTP API endpoints<br>- Tenant/user auth<br>- Plan enforcement<br>- Scan job creation<br>- Status queries<br>- Findings queries |
| **Brain** | Planning Only | - Generate scan plans<br>- Manage session state<br>- Publish step requests<br>- Consume step results<br>- Update plans based on results |
| **Runner** | Execution Only | - Consume step requests<br>- Execute tools (subprocess/remote)<br>- Ingest findings to DB<br>- Publish step results |
| **Celery** | Scheduled Tasks | - NVD/KEV ingestion<br>- Scheduled scans (future) |
| **Redis** | Queue + Streams | - Celery broker/backend<br>- Redis streams (step req/res) |
| **PostgreSQL** | Persistence | - All data storage |

---

## 3. Conflicts to Fix

### Priority 1: Critical (Blocks Functionality)

1. **DB URL Mismatch:**
   - **Problem:** Runner defaults to SQLite if `DATABASE_URL` not set
   - **Fix:** Ensure runner uses same `DATABASE_URL` as backend
   - **Location:** `services/thandev-runner/app/config.py:30-33`

2. **Dual Execution Path:**
   - **Problem:** Celery `run_scan_for_job()` executes tools directly, bypassing Runner
   - **Fix:** Remove direct tool execution from Celery path; always use Runner via streams
   - **Location:** `backend/app/services/scan_orchestrator.py:run_scan_for_job()`

3. **Scan Status Terminal States:**
   - **Problem:** Tools may remain "pending" when scan is terminal
   - **Fix:** On scan completion, mark all pending tools as "skipped" with `error_code=not_scheduled`
   - **Location:** `backend/app/api/scans.py:get_scan_status()`

### Priority 2: Important (Data Quality)

4. **Notifications Table Missing:**
   - **Problem:** Migrations may not be applied, causing 500s
   - **Fix:** Ensure `0013_create_notifications_table` is applied; add defensive handling
   - **Location:** `backend/app/api/notifications.py`

5. **Tool Status Filtering:**
   - **Problem:** Tools filtered by `THANDEV_PIPELINE_TOOLS` not marked as skipped
   - **Fix:** Mark filtered tools as `skipped` with `error_code=filtered_out`
   - **Location:** Brain/Backend when publishing step requests

### Priority 3: Configuration

6. **Environment Config Files:**
   - **Problem:** No `.env.example` files for services
   - **Fix:** Create `.env.example` for backend, runner, brain
   - **Location:** Service root directories

7. **Bootstrap Script:**
   - **Problem:** No clear path to create tenant/project in local/dev
   - **Fix:** Create bootstrap script or explicit endpoint
   - **Location:** `backend/scripts/bootstrap_local.sh` or `backend/app/api/dev.py`

---

## 4. Implementation Plan

### Phase 1: Fix DB & Execution Path (Critical)
1. Fix runner `DATABASE_URL` resolution
2. Remove direct tool execution from Celery path
3. Ensure all scans route through Runner (via streams)

### Phase 2: Fix Status & Migrations
4. Fix tool_statuses terminal state handling
5. Verify and apply migrations (notifications table)
6. Add defensive handling for missing tables

### Phase 3: Configuration & Bootstrap
7. Create `.env.example` files
8. Create bootstrap script for local/dev
9. Update docker-compose.dev.yml

### Phase 4: Tests & Verification
10. Fix tests (invalid tenant_id, notifications, tool_statuses)
11. Run smoke test end-to-end
12. Document manual test procedures

---

## 5. Verification Commands

```bash
# Check migrations
cd backend && python3 -m alembic current
cd backend && python3 -m alembic heads

# Check DB connections
python3 -c "from app.core.config import settings; print(settings.DATABASE_URL)"
cd services/thandev-runner && python3 -c "from app.config import settings; print(settings.DATABASE_URL)"

# Run tests
cd backend && pytest -m "not integration" -v

# Smoke test
curl -X POST http://localhost:8000/api/scans \
  -H "X-Thandev-Tenant-Id: <uuid>" \
  -H "X-Thandev-User-Id: <uuid>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<uuid>", "scan_level": "basic"}'
```

---

**Next Steps:** Begin Phase 1 fixes in priority order.

