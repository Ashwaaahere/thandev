# Deployment Notes

## 2025-01-27: Fix Fly.io backend startup and database schema

**Issue:** Backend crash-looping on Fly.io with:
1. `ImportError: email-validator is not installed` (fixed in previous commit)
2. `psycopg2.errors.UndefinedTable: relation "users" does not exist` - migrations referenced `users` table but never created it

**Root Causes:**
- Missing `users`, `tenants`, and `projects` tables in migrations (migrations 0014, 0016 assumed they existed)
- No startup script to wait for DB connectivity before running migrations
- Migrations ran via `release_command` which could fail silently

**Fixes:**
1. **Created migration `0020_create_core_tables_users_tenants_projects.py`** - Idempotent migration that creates `tenants`, `users`, and `projects` tables if they don't exist
2. **Created `entrypoint.sh`** - Startup script that:
   - Waits for PostgreSQL to be ready (with retries)
   - Runs `init_db.py` for initialization
   - Runs `alembic upgrade head` to apply migrations
   - Starts uvicorn server
3. **Updated `Dockerfile`** - Uses `entrypoint.sh` as ENTRYPOINT instead of direct CMD
4. **Updated `fly.toml`** - Removed `release_command` (migrations now handled by entrypoint)
5. **Added canonical DB URL comments** - Documented that `DATABASE_URL` is the single source of truth for both app and Alembic
6. **Added `/healthz` endpoint** - Alternative health check endpoint for Fly.io

**Files Changed:**
- `backend/migrations/versions/0020_create_core_tables_users_tenants_projects.py` - New migration
- `backend/entrypoint.sh` - New startup script
- `backend/Dockerfile` - Updated to use entrypoint
- `backend/fly.toml` - Removed release_command
- `backend/app/core/config.py` - Added canonical DB URL comment
- `backend/migrations/env.py` - Added canonical DB URL comment
- `backend/app/main.py` - Added `/healthz` endpoint

**Verification:**
- Migration is idempotent (can run multiple times safely)
- Entrypoint handles both PostgreSQL (with wait) and SQLite (no wait)
- Health endpoints: `/health` and `/healthz` both return 200 OK

**Deployment:**
- Merge `fix/fly-backend-startup-db-schema` branch
- Run `fly deploy -a thandev-backend` - container will rebuild with new entrypoint
- Check logs: `fly logs -a thandev-backend` to confirm:
  - "Database is ready!"
  - "Running Alembic migrations..."
  - "Starting application..."
  - No "relation users does not exist" errors

---

## 2025-01-27: Fix email-validator dependency

**Issue:** Fly.io backend crash on startup with `ImportError: email-validator is not installed, run 'pip install pydantic[email]'`

**Root Cause:** Backend uses `EmailStr` from Pydantic in `app/schemas/auth.py`, but `email-validator` package was not included in `requirements.txt`.

**Fix:** Added `email-validator>=2.0.0` to `backend/requirements.txt`. The Dockerfile installs dependencies via `pip install -r requirements.txt`, so this fix is automatically included in the container build.

**Files Changed:**
- `backend/requirements.txt` - Added `email-validator>=2.0.0`

**Verification:**
- Dependency is installed during Docker build (line 67: `RUN pip install --no-cache-dir -r requirements.txt`)
- EmailStr import works: `from pydantic import EmailStr`

**Deployment:**
- Merge `fix/fly-email-validator` branch
- Run `fly deploy` - container will rebuild with new dependency
- Check logs: `fly logs -a thandev-backend` to confirm successful boot

