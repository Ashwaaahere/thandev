# Tenant Auto-Creation Fixes Summary

## Problem
POST /api/scans was failing in production-like environments with:
```
"Tenant with id '<uuid>' not found. Auto-creation is disabled in production."
```

## Solution
Implemented flexible auto-creation policy with explicit creation endpoints for production-like testing.

## Changes Made

### 1. Configuration (`backend/app/core/config.py`)

Added `TENANT_AUTOCREATE_ENABLED` config flag with smart defaults:

- **Default in `local`/`dev`/`test`/`development`:** `True` (enabled)
- **Default in `production`:** `False` (disabled)

**Override options:**
- `THANDEV_TENANT_AUTOCREATE=1` - Enable in non-production
- `THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD=1` - Enable in production (requires explicit dangerous flag)

### 2. Tenant Utils (`backend/app/core/tenant_utils.py`)

- Updated to use `settings.TENANT_AUTOCREATE_ENABLED` instead of hardcoded environment check
- Improved error messages to suggest using `POST /api/tenants`
- Maintains UUID validation (invalid IDs return 400, not 500)

### 3. Tenant Creation Endpoint (`backend/app/api/tenants.py`)

Added `POST /api/tenants` endpoint:
- **Local/dev/test:** No authentication required
- **Production:** Requires `X-Thandev-Admin-Token` header
- Auto-generates UUID if `id` not provided
- Validates plan values: `free`, `basic`, `pro`, `enterprise`

### 4. User Creation Endpoint (`backend/app/api/users.py`)

Added `POST /api/users` endpoint:
- **Local/dev/test:** No authentication required
- **Production:** Requires `X-Thandev-Admin-Token` header
- Auto-generates UUID if `id` not provided
- Validates tenant exists before creating user

### 5. Tests (`backend/tests/test_tenant_autocreate.py`)

Added comprehensive tests:
- ✅ Auto-creation enabled in local env
- ✅ Auto-creation disabled in production
- ✅ Tenant creation endpoint works in local
- ✅ Tenant creation blocked in production without token
- ✅ Tenant creation allowed in production with token
- ✅ UUID auto-generation
- ✅ User creation endpoint

## Usage Examples

### Complete Workflow: Create Tenant → User → Project → Scan

```bash
# 1. Generate UUIDs
TENANT_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
USER_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')

# 2. Create tenant
curl -X POST "http://localhost:8000/api/tenants" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$TENANT_ID\",
    \"name\": \"Test Tenant\",
    \"plan\": \"pro\"
  }" | python3 -m json.tool

# 3. Create user
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$USER_ID\",
    \"email\": \"test@example.com\",
    \"username\": \"testuser\",
    \"tenant_id\": \"$TENANT_ID\"
  }" | python3 -m json.tool

# 4. Create project
PROJECT_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -d '{
    "name": "Test Project",
    "target_url": "https://example.com"
  }')

PROJECT_ID=$(echo $PROJECT_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Project ID: $PROJECT_ID"

# 5. Create scan
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"scan_level\": \"basic\"
  }" | python3 -m json.tool
```

### Production with Admin Token

```bash
export THANDEV_ADMIN_TOKEN="your-secret-token"

# Create tenant (requires admin token in production)
curl -X POST "http://localhost:8000/api/tenants" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Admin-Token: $THANDEV_ADMIN_TOKEN" \
  -d '{
    "id": "YOUR-UUID-HERE",
    "name": "Production Tenant",
    "plan": "pro"
  }'
```

### Auto-Creation (Local/Dev Only)

```bash
# Set environment to local
export ENVIRONMENT=local

# Tenant and user will be auto-created when referenced
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -H "X-Thandev-Tenant-Id: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{
    "project_id": "PROJECT-UUID-HERE",
    "scan_level": "basic"
  }'
```

## Files Changed

1. `backend/app/core/config.py` - Added `TENANT_AUTOCREATE_ENABLED` logic
2. `backend/app/core/tenant_utils.py` - Updated to use config flag
3. `backend/app/api/tenants.py` - Added `POST /api/tenants` endpoint
4. `backend/app/api/users.py` - New file with `POST /api/users` endpoint
5. `backend/app/main.py` - Registered users router
6. `backend/app/schemas/tenant.py` - Added `TenantCreate` and `TenantResponse` schemas
7. `backend/tests/test_tenant_autocreate.py` - New test file
8. `backend/DEV_GUIDE.md` - New documentation

## Verification

### Test Auto-Creation Config
```bash
# Production: disabled
ENVIRONMENT=production python3 -c "from app.core.config import Settings; s = Settings(); print(f'Auto-create: {s.TENANT_AUTOCREATE_ENABLED}')"
# Output: Auto-create: False

# Local: enabled
ENVIRONMENT=local python3 -c "from app.core.config import Settings; s = Settings(); print(f'Auto-create: {s.TENANT_AUTOCREATE_ENABLED}')"
# Output: Auto-create: True
```

### Run Tests
```bash
pytest tests/test_tenant_autocreate.py -v
# All 7 tests should pass
```

### Test Endpoints
```bash
# Start server
export ENVIRONMENT=local
uvicorn app.main:app --reload

# In another terminal, test tenant creation
TENANT_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
curl -X POST "http://localhost:8000/api/tenants" \
  -H "Content-Type: application/json" \
  -d "{\"id\": \"$TENANT_ID\", \"name\": \"Test\", \"plan\": \"pro\"}" | python3 -m json.tool
```

## Important Notes

1. **UUID Requirement:** All IDs must be valid UUIDs (36 characters). Invalid IDs return `400 Bad Request`.

2. **Auto-Creation Policy:**
   - Enabled by default in `local`/`dev`/`test`/`development`
   - Disabled by default in `production`
   - Can be overridden with env vars (see config.py)

3. **Production Safety:**
   - Auto-creation disabled in production by default
   - Tenant/user creation endpoints require admin token in production
   - Explicit creation via API is the recommended approach for production

4. **Backward Compatibility:**
   - Existing behavior preserved for dev/test environments
   - Production behavior is now more strict (explicit creation required)
   - UUID validation prevents crashes from invalid IDs

