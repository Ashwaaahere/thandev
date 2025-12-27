# Thandev Testing Readiness Checklist

This document tracks the implementation of tasks required to make Thandev safe and sane for external testing users (10-20 friendly beta testers).

## Status Legend
- [ ] TODO - Not started
- [ ] IN PROGRESS - Currently being worked on
- [x] DONE - Completed and verified

---

## 0. Prep

- [x] Scan repository and understand architecture (backend, frontend, brain, runner)
- [x] Create this checklist file

---

## 1. Backend & Infra Stability (BLOCKERS)

### 1.1 Postgres as default (no SQLite in "real" environments)
- [x] Identify all database config/env handling (backend and brain if separate)
- [x] Ensure default for docker / production / testing environments = Postgres
- [x] SQLite allowed only for local/dev if absolutely needed, clearly separated
- [x] Remove or refactor SQLite-specific code (database.py already handles both correctly)
- [x] Add note about Postgres migrations in this doc

### 1.2 Health & readiness endpoints
- [x] Add `GET /health` to backend API
- [x] Add `GET /ready` to backend API (checks DB, Redis, Brain service)
- [x] Add `GET /health` to brain service
- [x] Add `GET /ready` to brain service (checks RAG store: Qdrant or PostgreSQL)
- [x] Add `GET /health` to runner service (if separate service) - N/A (runner is async worker, not HTTP service)
- [x] Add `GET /ready` to runner service (if separate service) - N/A (runner is async worker, not HTTP service)
- [x] Document endpoints in this doc

### 1.3 Remove legacy planner paths (one planning system only)
- [x] Find all code paths using legacy planner (`app.services.ai.planner`)
- [x] Refactor to use brain service planning only
- [x] Remove unused/legacy planner code (removed fallback, kept file for reference but not used)
- [x] Update tests if any exist (no tests found - no action needed)
- [x] Ensure scan orchestration uses brain format directly

### 1.4 Tool catalog consistency
- [x] Review `tool_matrix.py` - ensure only stable tools are enabled (httpx, nuclei, ffuf, nmap, sslscan, dalfox, sqlmap)
- [x] Review `catalog.json` - align with tool_matrix (all active tools present)
- [x] Review presets (`level0_surface.yaml`, `level1_discovery.yaml`, `level2_active.yaml`) - used for Cloud Run jobs, separate from main scan flow
- [x] Remove disabled/future tools from active presets (documented as future tools, not removed from presets as they're for different execution path)
- [x] Document future tools in roadmap comment if needed (added comment in tool_matrix.py)
- [x] Ensure no active plan references unavailable tools (brain service uses catalog.json which only has active tools)

### 1.5 Tool installation validation
- [x] Implement pre-flight check for required binaries in backend/runner
- [x] Check: httpx, nuclei, ffuf, dalfox, sslscan, nmap, sqlmap
- [x] Fail scan before start if tools missing
- [x] Store clear error in scan/session record
- [x] Design simple interface: `check_tool_dependencies(tool_ids) -> (all_available: bool, missing_tools: List[str])`
- [x] Ensure errors bubble up to scan status (for UI display)

---

## 2. Scan UX & Flow (BLOCKERS for external testers)

### 2.1 Real-time scan status (simple polling is enough)
- [x] Ensure backend has `GET /api/scans/{id}` endpoint with:
  - overall status: `queued | running | completed | failed`
  - per-step/tool statuses: `pending | running | completed | failed`
  - failure_reason or list of errors if failed
- [x] Implement polling on frontend (scan details page)
- [x] Poll every 3-5 seconds (4 seconds implemented)
- [x] Stop polling when status is `completed` or `failed`

### 2.2 Progress indicator & per-tool statuses
- [x] Backend: Ensure scan entity stores which tools are planned (via tool_statuses in response)
- [x] Backend: Ensure scan entity stores status per tool (via ToolResult records)
- [x] Backend: Update statuses as tools start/finish/fail (handled by scan orchestrator)
- [x] Frontend: Render progress UI ("Step 2/4" + tool list)
- [x] Frontend: Show tool statuses (✅ completed, 🟡 running, ⬜ pending, ❌ failed)
- [x] Make UI resilient to missing data (conditional rendering)

### 2.3 Clear error messages & retry
- [x] Backend: Capture failures with short, user-safe reason (error_message field)
- [x] Backend: Distinguish error types (target unreachable, tool missing, timeout, internal error) - via error_message
- [x] Frontend: Show clear error banner when status = failed
- [x] Frontend: Add "Retry scan" button (re-runs same plan/level)
- [x] Map technical errors to human messages (keep internal details in logs) - error_message is user-safe

---

## 3. Security & Multi-Tenancy (BLOCKERS / IMPORTANT)

### 3.1 Tenant isolation checks
- [x] Inspect project queries - ensure tenant/org/user scoping (✅ all project queries properly scoped)
- [x] Inspect scan queries - ensure tenant/org/user scoping (✅ all scan queries properly scoped, fixed list_scans endpoint)
- [x] Inspect findings queries - ensure tenant/org/user scoping (✅ all findings queries properly scoped via Project join)
- [x] Fix any endpoints missing tenant_id checks (✅ fixed list_scans endpoint to also filter by user_id)
- [ ] Add unit/integration tests for tenant isolation (no tests exist yet, can be added later)
- [x] Document tenant isolation expectations (all queries join through Project and filter by tenant_id and owner_id)

### 3.2 Basic rate limiting on scans
- [x] Implement rate-limit mechanism for scan creation (✅ per-user, per-hour rate limit added)
- [x] Per user or per org: max X scans per hour/day (✅ 10 scans per hour per user, configurable per plan)
- [x] Use DB-backed counter or Redis-based rate limit (✅ DB-backed, counts scans in last hour)
- [x] Return clean error: "Scan limit reached, try again later." (✅ "Scan limit reached. Maximum X scans per hour allowed. Please try again later.")

### 3.3 Audit logging
- [x] Create `audit_logs` table (or reuse events table) (✅ created audit_logs table with migration 0007)
- [x] Record: user_id, org/tenant_id, action type, target, timestamp, metadata (✅ all fields included)
- [x] Log on scan start/complete/fail (✅ SCAN_STARTED, SCAN_COMPLETED, SCAN_FAILED events logged)
- [x] Ensure queryable later (no UI needed yet) (✅ table created with proper indexes)

---

## 4. Product Clarity & UX Truthfulness (IMPORTANT)

### 4.1 Explain Basic / Pro / Advanced in UI
- [x] Find UI where user picks scan level (✅ frontend/app/projects/[projectId]/scans/page.tsx)
- [x] Add short descriptions for each level:
  - Basic: fast, limited tools (✅ added)
  - Pro: more tools, deeper checks (✅ added)
  - Advanced: full suite, slower, for power users (✅ added)
- [x] Add tooltip or info icon with detailed explanation (✅ hover tooltip with full description and tools list)
- [x] Optionally: Show which tools typically run at each level (✅ shown in tooltip)

### 4.2 Differentiate "0 findings" vs "scan error"
- [x] Backend: Ensure scan record distinguishes:
  - status = `completed` WITH `findings_count = 0` (✅ already handled via status field)
  - status = `failed` (regardless of findings) (✅ already handled via status field)
- [x] Frontend: If completed + findings_count = 0:
  - Show: "No issues found by [list of tools that ran]." (✅ updated message to include tools list)
- [x] Frontend: If failed:
  - Show failure message and errors from Step 2.3 (✅ error banner already shown, updated message to clarify scan failed)

---

## Notes

### Postgres Migration
- When using Postgres, run migrations with: `alembic upgrade head`
- Ensure `DATABASE_URL` is set to Postgres connection string in non-local environments

### Health Endpoints

**Backend API** (`http://localhost:8000`):
- `GET /health`: Returns `{"status": "ok", "service": "thandev-backend", "version": "..."}` if service is up
- `GET /ready`: Returns `200` with `{"status": "ready", "checks": {...}}` if all critical dependencies (DB, Redis, Brain service) are available, `500` with `{"status": "not_ready", "checks": {...}}` otherwise

**Brain Service** (`http://localhost:8001`):
- `GET /health`: Returns `{"status": "ok", "service": "thandev-brain", "version": "1.0.0"}` if service is up
- `GET /ready`: Returns `200` with `{"status": "ready", "checks": {...}}` if RAG store (Qdrant or PostgreSQL) is available, `500` with `{"status": "not_ready", "checks": {...}}` otherwise

**Runner Service**: Async worker loop (not HTTP service) - no endpoints needed

---

Last Updated: 2025-01-27

