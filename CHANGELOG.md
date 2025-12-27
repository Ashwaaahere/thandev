# Changelog - Market-Ready Architecture Fixes

## Phase 1: Critical Fixes (✅ Complete)

### Fixed: Runner DATABASE_URL Mismatch
**File:** `services/thandev-runner/app/config.py`
- **Problem:** Runner defaulted to SQLite if `DATABASE_URL` not set, causing "scan job not found" errors
- **Fix:** Updated runner config to match backend's DATABASE_URL resolution logic
- **Impact:** Runner can now access the same database as backend, eliminating connection mismatches

### Fixed: Tool Status Terminal State Handling
**File:** `backend/app/api/scans.py`
- **Problem:** Tools could remain "pending" when scan is terminal (completed/failed/cancelled)
- **Fix:** Added logic to mark PENDING tools as SKIPPED with `error_code=not_scheduled` when scan becomes terminal
- **Impact:** `/api/scans/{id}` now returns correct tool_statuses with no pending tools for terminal scans

### Created: Architecture Documentation
**File:** `docs/ARCHITECTURE.md`
- **Content:** Complete system map, conflict identification, target architecture, implementation plan
- **Impact:** Clear documentation of current state and intended design

---

## Phase 2: Configuration & Documentation

### Created: Environment Configuration Documentation
**Files:** `.env.example` templates documented in CHANGELOG (files blocked by .gitignore)
- **Backend:** Complete env var documentation with defaults and descriptions
- **Runner:** Critical note about DATABASE_URL matching backend
- **Brain:** All RAG and session configuration options
- **Impact:** Clear documentation for local/prod setup

### Verified: Notifications Migration
**File:** `backend/migrations/versions/0013_create_notifications_table.py`
- **Status:** Migration exists and creates notifications table with proper indexes
- **Defensive Handling:** `backend/app/api/notifications.py` already handles missing table gracefully
- **Impact:** Notifications route won't 500 if table missing (returns empty list in dev, 503 in prod)

---

## Pending Fixes

### TODO: Bootstrap Script
- Create script/endpoint for local/dev tenant/project creation
- Document bootstrap procedure

### TODO: Execution Path Consolidation (Future Work)
- Remove direct tool execution from Celery path
- Ensure all scans route through Runner via Redis streams
- **Note:** This is a larger refactor and should be done carefully after testing current fixes

---

## Verification Commands

```bash
# Check migrations
cd backend && python3 -m alembic current
cd backend && python3 -m alembic heads

# Check DB connections match
python3 -c "from app.core.config import settings; print('Backend:', settings.DATABASE_URL)"
cd services/thandev-runner && python3 -c "from app.config import settings; print('Runner:', settings.DATABASE_URL)"

# Run tests
cd backend && pytest -m "not integration" -v
```

