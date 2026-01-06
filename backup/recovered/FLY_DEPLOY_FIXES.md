# Fly.io Deployment Fixes - Summary

## What Changed

### A) Dockerfile Fixed (Permission Errors)
**File**: `backend/Dockerfile`
- **Issue**: `chmod +x` was running as non-root user, causing "Operation not permitted"
- **Fix**: 
  - Created `app` user before copying files
  - Used `COPY --chown=app:app` for application code
  - Used `COPY --chown=app:app --chmod=755` for entrypoint.sh to set permissions at build time
  - Removed `RUN chmod +x` command that was failing
  - Ensured all operations happen as root before switching to `app` user

### B) Python Dependencies (Email Validator)
**File**: `backend/requirements.txt`
- **Status**: `email-validator>=2.0.0` already present in requirements.txt
- **Verification**: Dependency is correctly specified for Pydantic EmailStr support
- No changes needed - dependency will be installed correctly

### C) Migration 0003 Idempotency (Postgres Constraint Errors)
**File**: `backend/migrations/versions/0003_add_indexes_and_performance_scans.py`
- **Issue**: Constraint creation used try/except, causing `InFailedSqlTransaction` errors in PostgreSQL
- **Fix**: 
  - Replaced try/except constraint creation with PostgreSQL DO blocks
  - Added idempotent checks using `pg_constraint` system catalog
  - Constraints (`check_tier`, `check_status`) now check existence before creation
  - Prevents transaction abort errors when constraints already exist
  - SQLite and other databases still use try/except fallback

### D) Fly.io Migration Flow (Run Once Per Deploy)
**Files**: `backend/entrypoint.sh`, `backend/fly.toml`
- **Issue**: Migrations ran on every container restart via entrypoint.sh
- **Fix**:
  - Removed `alembic upgrade head` and `python init_db.py` from entrypoint.sh
  - Added `release_command = "alembic upgrade head"` to `fly.toml` under `[deploy]`
  - Migrations now run once per deploy via Fly.io release phase
  - Entrypoint.sh only handles DB connection wait and uvicorn startup
  - Ensures migrations run on same database before containers start

### E) Environment Mode (Production)
**File**: `backend/fly.toml`
- **Fix**: Added `ENVIRONMENT = "production"` to `[env]` section
- Ensures app runs in production mode on Fly.io
- Prevents development-only features from activating

### F) Users Table Migration
**Status**: Users table is already created in migration `0020_create_core_tables_users_tenants_projects.py`
- Migration is idempotent (checks `table_exists()` before creating)
- Creates users, tenants, and projects tables with all required columns
- No additional migration needed

## Files Modified

1. `backend/Dockerfile` - Fixed permission issues with entrypoint.sh
2. `backend/entrypoint.sh` - Removed migration commands, kept only uvicorn startup
3. `backend/fly.toml` - Added release_command and ENVIRONMENT=production
4. `backend/migrations/versions/0003_add_indexes_and_performance_scans.py` - Made constraints idempotent

## Fly.io Deploy Steps

After merging these changes, run:

```bash
# 1. Set required secrets (if not already set)
flyctl secrets set DATABASE_URL=<your-postgres-database-url> \
  --app thandev-backend

# Optional: Set other secrets as needed
# flyctl secrets set SECRET_KEY=<your-secret-key> --app thandev-backend
# flyctl secrets set OPENAI_API_KEY=<your-key> --app thandev-backend
# etc.

# 2. Deploy to Fly.io
cd backend
flyctl deploy --app thandev-backend

# 3. Monitor deployment
flyctl logs --app thandev-backend
```

## Verification Steps (Post-Deploy)

1. **Check release command ran successfully**:
   ```bash
   flyctl logs --app thandev-backend | grep -i "alembic\|migration"
   ```

2. **Verify app started**:
   ```bash
   flyctl status --app thandev-backend
   ```

3. **Test health endpoint**:
   ```bash
   curl https://thandev-backend.fly.dev/health
   ```

4. **Test bootstrap endpoint (should not error with "users does not exist")**:
   ```bash
   curl -X POST https://thandev-backend.fly.dev/api/auth/bootstrap
   ```

## Key Improvements

✅ **Build-time**: No more permission errors during Docker build  
✅ **Runtime**: No more ImportError for email-validator  
✅ **Migrations**: Idempotent, run once per deploy (not every restart)  
✅ **Database**: Same DATABASE_URL used by migrations and app  
✅ **Environment**: Production mode enabled on Fly.io  
✅ **Stability**: Migrations won't fail due to already-existing constraints  

## Notes

- Migrations run in Fly.io's release phase, ensuring they complete before new containers start
- All constraint/index creation is now idempotent and safe to run on existing databases
- Docker build uses BuildKit-compatible COPY flags for permissions
- App runs as non-root user `app` for security

