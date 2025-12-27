# Thandev Backend Development Guide

## Environment Setup

### Recommended Local Environment

For local development, set:
```bash
export ENVIRONMENT=local
```

This enables:
- Tenant/user auto-creation (no need to manually create tenants/users)
- SQLite database by default (unless `DATABASE_URL` is set)
- Development-friendly defaults

### Database Setup

1. **PostgreSQL (Recommended for production-like testing):**
   ```bash
   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   alembic upgrade head
   ```

2. **SQLite (Default for local development):**
   ```bash
   # No setup needed - database file created automatically
   ```

## API Headers

All authenticated endpoints require:
- `X-Thandev-User-Id`: Valid UUID (36 characters)
- `X-Thandev-Tenant-Id`: Valid UUID (36 characters)

**Important:** IDs must be valid UUIDs. Invalid IDs (like `test-tenant-...`) will return `400 Bad Request`.

### Generating UUIDs

```bash
# In bash
python3 -c 'import uuid; print(uuid.uuid4())'

# Or use uuidgen (if available)
uuidgen
```

## Creating Tenants and Users

### Auto-Creation (Local/Dev/Test Only)

In `local`, `dev`, `test`, or `development` environments, tenants and users are automatically created when referenced in headers.

**Example:**
```bash
# Tenant and user will be auto-created if they don't exist
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -H "X-Thandev-Tenant-Id: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"project_id":"...","scan_level":"basic"}'
```

### Explicit Creation (Recommended for Production-Like Testing)

For production-like testing or when auto-creation is disabled, use explicit creation endpoints:

#### 1. Create Tenant

```bash
# In local/dev/test: No authentication required
curl -X POST "http://localhost:8000/api/tenants" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "YOUR-UUID-HERE",
    "name": "My Test Tenant",
    "plan": "pro"
  }'

# In production: Requires admin token
export THANDEV_ADMIN_TOKEN="your-secret-token"
curl -X POST "http://localhost:8000/api/tenants" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Admin-Token: $THANDEV_ADMIN_TOKEN" \
  -d '{
    "id": "YOUR-UUID-HERE",
    "name": "My Test Tenant",
    "plan": "pro"
  }'
```

**Plans:** `free`, `basic`, `pro`, `enterprise`

**Note:** If `id` is not provided, a UUID will be auto-generated.

#### 2. Create User

```bash
# In local/dev/test: No authentication required
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "YOUR-UUID-HERE",
    "email": "user@example.com",
    "username": "testuser",
    "tenant_id": "TENANT-UUID-HERE"
  }'

# In production: Requires admin token
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Admin-Token: $THANDEV_ADMIN_TOKEN" \
  -d '{
    "id": "YOUR-UUID-HERE",
    "email": "user@example.com",
    "username": "testuser",
    "tenant_id": "TENANT-UUID-HERE"
  }'
```

**Note:** User must belong to an existing tenant. Create tenant first.

#### 3. Create Project

```bash
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: USER-UUID-HERE" \
  -H "X-Thandev-Tenant-Id: TENANT-UUID-HERE" \
  -d '{
    "name": "My Test Project",
    "target_url": "https://example.com",
    "description": "Test project for scanning"
  }'
```

#### 4. Create Scan

```bash
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: USER-UUID-HERE" \
  -H "X-Thandev-Tenant-Id: TENANT-UUID-HERE" \
  -d '{
    "project_id": "PROJECT-UUID-HERE",
    "scan_level": "basic"
  }'
```

## Complete Example Workflow

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
  }"

# 3. Create user
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$USER_ID\",
    \"email\": \"test@example.com\",
    \"username\": \"testuser\",
    \"tenant_id\": \"$TENANT_ID\"
  }"

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

# 5. Create scan
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"scan_level\": \"basic\"
  }"
```

## Configuration

### Tenant Auto-Creation

Auto-creation behavior is controlled by `TENANT_AUTOCREATE_ENABLED`:

- **Default in `local`/`dev`/`test`/`development`:** `True` (enabled)
- **Default in `production`:** `False` (disabled)

**Override with environment variable:**
```bash
# Enable in non-production
export THANDEV_TENANT_AUTOCREATE=1

# Enable in production (requires dangerous flag)
export THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD=1
```

**Note:** Production auto-creation requires both:
1. `ENVIRONMENT=production`
2. `THANDEV_DANGEROUS_ALLOW_AUTOCREATE_IN_PROD=1`

This is intentionally difficult to enable for safety.

## Troubleshooting

### "Tenant with id '...' not found. Auto-creation is disabled."

**Solution:**
1. Create tenant explicitly via `POST /api/tenants`
2. Or set `ENVIRONMENT=local` for local development
3. Or enable auto-creation with `THANDEV_TENANT_AUTOCREATE=1` (non-production only)

### "Invalid tenant_id. Must be a valid UUID"

**Solution:** Use valid UUID format (36 characters). Generate with:
```bash
python3 -c 'import uuid; print(uuid.uuid4())'
```

### "Notifications table not found"

**Solution:** Run migrations:
```bash
alembic upgrade head
```

In dev/test, missing table returns empty list. In production, returns 503.

## Running Tests

```bash
# Run all non-integration tests
pytest -m "not integration" -v

# Run specific test files
pytest tests/test_tenant_autocreate.py -v
pytest tests/test_tenant_id_validation.py -v
```

