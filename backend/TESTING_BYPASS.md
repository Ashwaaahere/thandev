# Testing Plan Bypass Safety

## Current Issue

The API is returning a 500 error when creating scans. This is likely because:
- Brain service is enabled but not running
- The error happens before the bypass check

## Solution: Test with Brain Service Disabled

To test the bypass logic without brain service issues:

### Terminal 1: Start API Server

```bash
cd ~/thandev/backend
source venv/bin/activate

# For production bypass test:
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false  # Disable brain to avoid 500 errors
uvicorn app.main:app --reload
```

### Terminal 2: Test the Bypass

```bash
cd ~/thandev/backend
source venv/bin/activate

# Get the complete curl command:
./get_curl_command.sh

# Or use the test script:
./test_bypass_without_brain.sh
```

## Expected Results

### With ENVIRONMENT=production:
- **HTTP Status:** 403 Forbidden
- **Response:** `{"detail": "Your plan does not allow 'pro' scans. Allowed levels: basic."}`
- ✅ **Bypass is blocked** (correct behavior)

### With ENVIRONMENT=dev (and bypass flag):
- **HTTP Status:** 201 Created
- **Response:** Scan object with scan_id
- ✅ **Bypass works** (correct for dev environment)

## Complete Test Commands

### Test 1: Production Should Block
```bash
# Terminal 1:
export ENVIRONMENT=production
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false
uvicorn app.main:app --reload

# Terminal 2:
curl -s -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -H "X-Thandev-Tenant-Id: test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c" \
  -d '{"project_id":"test-project-0b5ccc58-914f-41af-813d-510eb8aa0b2c","scan_level":"pro"}' | python3 -m json.tool

# Expected: 403 with "plan does not allow" message
```

### Test 2: Dev Should Allow (with bypass flag)
```bash
# Terminal 1:
export ENVIRONMENT=dev
export THANDEV_DISABLE_PLAN_ENFORCEMENT=1
export BRAIN_SERVICE_ENABLED=false
uvicorn app.main:app --reload

# Terminal 2: (same curl command)
# Expected: 201 with scan created
```

## Alternative: Check Server Logs

If you're still getting 500 errors, check the server logs in the terminal where uvicorn is running. The logs will show the actual exception that's causing the 500 error.

## Note

The bypass logic itself is correct (verified by `test_bypass_safety.py`). The 500 error is a separate infrastructure issue (brain service, Celery, etc.) that needs to be resolved to test the bypass end-to-end.

