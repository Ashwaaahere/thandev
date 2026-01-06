# Scan Flow Verification Checklist

This document provides a comprehensive verification plan to ensure the scan creation flow works correctly in production with zero failures and no machine thrashing.

## Prerequisites

- Backend deployed to Fly.io (`thandev-backend`)
- Frontend deployed to Vercel (or your hosting platform)
- Database migrations have been run
- Access to Fly.io CLI and logs

---

## A) Local Verification (Before Deploying)

### 1. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

**Expected**: Migrations run successfully, including `0025_fix_scanlevel_enum_values` which ensures enum values exist.

### 2. Verify Enum Values in Database

```bash
# Connect to your local PostgreSQL database
psql $DATABASE_URL

# Check enum values
SELECT enumlabel 
FROM pg_enum 
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
WHERE pg_type.typname = 'scanlevel'
ORDER BY enumsortorder;
```

**Expected Output**:
```
 enumlabel
----------
 basic
 pro
 advanced
(3 rows)
```

### 3. Run Unit Tests

```bash
cd backend
pytest tests/test_scan_level_enum.py -v
```

**Expected**: All tests pass, confirming:
- `normalize_scan_level()` works correctly
- `scan_level_to_enum()` converts strings to enums
- Pydantic serializes enums by value (lowercase strings)

### 4. Test Scan Creation Locally

```bash
# Start backend locally
cd backend
uvicorn app.main:app --reload

# In another terminal, test scan creation with various scan_level inputs
curl -X POST "http://localhost:8000/api/scans/quick" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "project_id": "YOUR_PROJECT_ID",
    "target_url": "https://www.itsecgames.com/",
    "scan_level": "basic"
  }'

# Test with uppercase (should work due to normalization)
curl -X POST "http://localhost:8000/api/scans/quick" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "project_id": "YOUR_PROJECT_ID",
    "target_url": "https://www.itsecgames.com/",
    "scan_level": "BASIC"
  }'
```

**Expected**: Both requests return `200 OK` or `201 Created` with a `scan_id` in the response.

### 5. Verify Database Row

```bash
# Check the created scan_job row
psql $DATABASE_URL

SELECT id, scan_level, status, created_at 
FROM scan_jobs 
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**: `scan_level` column shows `'basic'` (lowercase string), not `'BASIC'` or enum name.

---

## B) Fly.io Deployment Verification

### 1. Verify Fly.toml Configuration

```bash
cd backend
cat fly.toml | grep -A 10 "\[http_service\]"
```

**Expected Configuration**:
```toml
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

  [http_service.concurrency]
    type = "requests"
    soft_limit = 20
    hard_limit = 30
```

**Key Settings**:
- ✅ `min_machines_running = 1` (ensures at least one machine is always running)
- ✅ `auto_stop_machines = false` (prevents machines from auto-stopping)
- ✅ `auto_start_machines = true` (enables auto-start if needed)
- ✅ Concurrency limits configured (prevents overload)

### 2. Deploy to Fly.io

```bash
cd backend
fly deploy -a thandev-backend
```

**Expected**: Deployment succeeds without errors. Check logs for:
- ✅ No `NameError: name 'Union' is not defined`
- ✅ No `IndentationError`
- ✅ Application starts successfully
- ✅ Health check passes

### 3. Verify Machine Stability

```bash
# Check machine status
fly status -a thandev-backend

# List all machines
fly machines list -a thandev-backend

# Monitor logs for machine thrashing
fly logs -a thandev-backend | grep -E "(Starting machine|lease currently held|rate limit exceeded)"
```

**Expected**:
- ✅ Exactly 1 machine running (or configured count)
- ✅ No repeated "Starting machine" messages
- ✅ No "lease currently held" errors
- ✅ No "rate limit exceeded" errors
- ✅ Machine stays running (doesn't auto-stop)

### 4. Verify Health Endpoint

```bash
# Test health endpoint (should be lightweight, no DB work)
curl https://thandev-backend.fly.dev/health
```

**Expected Response**:
```json
{
  "status": "ok",
  "service": "thandev-backend",
  "version": "..."
}
```

**Verification**: Response time should be < 100ms (no database queries).

### 5. Verify Database Migrations Ran

```bash
# SSH into Fly machine and check Alembic version
fly ssh console -a thandev-backend -C "alembic current"

# Or check via API if you have an admin endpoint
```

**Expected**: Alembic version shows `0025_fix_scanlevel_enum` or later.

---

## C) Production Scan Creation Test

### 1. Test Scan Creation via API

```bash
# Replace with your actual backend URL and auth token
BACKEND_URL="https://thandev-backend.fly.dev"
AUTH_TOKEN="YOUR_TOKEN"
PROJECT_ID="YOUR_PROJECT_ID"

# Test with lowercase scan_level
curl -X POST "${BACKEND_URL}/api/scans/quick" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -d "{
    \"project_id\": \"${PROJECT_ID}\",
    \"target_url\": \"https://www.itsecgames.com/\",
    \"scan_level\": \"basic\"
  }"

# Test with uppercase scan_level (should normalize to lowercase)
curl -X POST "${BACKEND_URL}/api/scans/quick" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -d "{
    \"project_id\": \"${PROJECT_ID}\",
    \"target_url\": \"https://www.itsecgames.com/\",
    \"scan_level\": \"BASIC\"
  }"
```

**Expected**: Both requests return `200 OK` or `201 Created` with:
```json
{
  "project_id": "...",
  "scan_id": "..."
}
```

### 2. Verify Database Insert

```bash
# SSH into Fly machine and check the database
fly ssh console -a thandev-backend

# Connect to database
psql $DATABASE_URL

# Check the most recent scan_job
SELECT id, scan_level, status, created_at 
FROM scan_jobs 
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**: 
- ✅ `scan_level` column shows `'basic'` (lowercase string)
- ✅ No `'BASIC'` or enum name values
- ✅ Row was inserted successfully

### 3. Monitor Backend Logs

```bash
# Watch logs during scan creation
fly logs -a thandev-backend | grep -E "(quick_scan|scan_level|INVALID_SCAN_LEVEL|DB_COMMIT_FAILED)"
```

**Expected Logs**:
- ✅ `"Normalized scan_level: 'BASIC' -> 'basic'"` (or similar)
- ✅ No `"INVALID_SCAN_LEVEL"` errors
- ✅ No `"DB_COMMIT_FAILED"` errors
- ✅ No `"invalid input value for enum scanlevel: 'BASIC'"` errors

### 4. Test from Frontend UI

1. Navigate to the Security Scanner page in your frontend
2. Select a project
3. Enter a target URL
4. Select scan level (Basic, Pro, or Advanced)
5. Click "Start Scan"

**Expected**:
- ✅ No `[object Object]` error popups
- ✅ Scan starts successfully
- ✅ Success message or toast appears
- ✅ Scan appears in the scans list

### 5. Verify Error Handling

Test error cases to ensure readable error messages:

```bash
# Test with invalid scan_level
curl -X POST "${BACKEND_URL}/api/scans/quick" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -d "{
    \"project_id\": \"${PROJECT_ID}\",
    \"target_url\": \"https://www.itsecgames.com/\",
    \"scan_level\": \"invalid\"
  }"
```

**Expected**: Returns `400 Bad Request` with readable error message:
```json
{
  "detail": {
    "code": "INVALID_SCAN_LEVEL",
    "message": "Invalid scan_level: 'invalid'. Must be one of: advanced, basic, pro",
    "allowed": ["basic", "pro", "advanced"],
    "received": "invalid"
  }
}
```

---

## D) Regression Prevention

### 1. Automated Tests

Run the full test suite to ensure no regressions:

```bash
cd backend
pytest tests/test_scan_level_enum.py -v
pytest tests/integration/test_scan_creation.py -v
```

### 2. Code Review Checklist

Before merging changes that affect scan creation:

- ✅ `ScanLevel` enum values are lowercase strings
- ✅ SQLAlchemy Enum uses `native_enum=True` and `create_type=False`
- ✅ Pydantic schemas have `use_enum_values=True` in `model_config`
- ✅ `normalize_scan_level()` handles all input variations
- ✅ Error messages are user-friendly (not `[object Object]`)
- ✅ Database migrations are idempotent

### 3. Database Schema Verification

Periodically verify the database schema matches expectations:

```sql
-- Check enum type values
SELECT enumlabel 
FROM pg_enum 
JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
WHERE pg_type.typname = 'scanlevel'
ORDER BY enumsortorder;

-- Check column type
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'scan_jobs' AND column_name = 'scan_level';
```

**Expected**:
- ✅ Enum values: `basic`, `pro`, `advanced` (all lowercase)
- ✅ Column type: `USER-DEFINED` with `udt_name = 'scanlevel'`

---

## E) Troubleshooting

### Issue: "invalid input value for enum scanlevel: 'BASIC'"

**Cause**: SQLAlchemy is using enum name instead of value.

**Fix**: 
1. Verify `ScanLevel` enum values are lowercase: `BASIC = "basic"`
2. Verify SQLAlchemy Enum configuration uses `native_enum=True` and `create_type=False`
3. Ensure `normalize_scan_level()` is called before creating `ScanJob`
4. Run migration `0025_fix_scanlevel_enum_values` to ensure enum values exist

### Issue: Machine Thrashing (repeated "Starting machine" / "lease held")

**Cause**: Multiple machines trying to start simultaneously or auto-stop/auto-start loop.

**Fix**:
1. Verify `fly.toml` has `min_machines_running = 1` and `auto_stop_machines = false`
2. Scale down to 1 machine: `fly scale count 1 -a thandev-backend`
3. Stop extra machines: `fly machines stop <machine_id> -a thandev-backend`
4. Wait for leases to expire (usually 10-30 seconds)

### Issue: Frontend shows "[object Object]" error

**Cause**: Error object is being displayed directly instead of extracting message.

**Fix**:
1. Verify `frontend/lib/errorUtils.ts` exists and exports `getErrorMessage()`
2. Verify `SecurityScannerClient.tsx` uses `await getErrorMessage(error)` for all error handling
3. Ensure error message is always converted to string before displaying

### Issue: Health Check Failing

**Cause**: Health endpoint might be doing heavy work (DB queries, external calls).

**Fix**:
1. Verify `/health` endpoint is lightweight (no DB queries)
2. Use `/ready` endpoint for dependency checks (DB, Redis, etc.)
3. Ensure health check timeout is sufficient in `fly.toml`

---

## Summary

After completing all verification steps:

✅ **Enum Fix**: Scan creation uses lowercase enum values (`'basic'`, `'pro'`, `'advanced'`)  
✅ **Error Handling**: Frontend displays readable error messages (never `[object Object]`)  
✅ **Fly Stability**: Backend maintains 1 always-on machine with no thrashing  
✅ **Regression Safety**: Unit tests prevent enum mismatch from returning  

**All systems operational. Scan flow is 100% working in production.**

