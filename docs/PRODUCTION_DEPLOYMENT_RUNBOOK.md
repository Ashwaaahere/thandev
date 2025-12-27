# Thandev Production Deployment Runbook

**Last Updated:** 2025-01-27  
**Purpose:** Operational procedures for deploying and maintaining Thandev in production

---

## Table of Contents

1. [Deployment Process](#deployment-process)
2. [Database Migrations](#database-migrations)
3. [Schema Drift Recovery](#schema-drift-recovery)
4. [Health Checks](#health-checks)
5. [Troubleshooting](#troubleshooting)

---

## Deployment Process

### Standard Deployment

1. **Push code to GitHub** (triggers Vercel for frontend automatically)
2. **Deploy backend services to Fly.io:**
   ```bash
   cd backend
   fly deploy
   ```
   - Migrations run automatically via `release_command` in `fly.toml`
   - Migrations execute **once per deploy**, not on every machine boot
   - Runtime command only starts `uvicorn` (no migrations)

### Migration Execution

**Important:** Migrations run via Fly.io `release_command`, not in runtime boot.

- **Location:** `backend/fly.toml` → `[deploy] release_command`
- **Command:** `python init_db.py && alembic upgrade head`
- **When:** Runs once per deployment, before new machines start
- **Why:** Prevents migration conflicts and ensures schema consistency

---

## Database Migrations

### Migration Strategy

1. **Migrations are idempotent:** Can be run multiple times safely
2. **Migrations run during deploy:** Via Fly.io `release_command`
3. **Runtime does NOT run migrations:** Only starts the application server

### Manual Migration Commands

If you need to run migrations manually (e.g., for debugging):

```bash
# Connect to Fly.io machine
fly ssh console -a thandev-backend

# Run migrations manually
cd /app
alembic upgrade head

# Check current migration version
alembic current

# View migration history
alembic history
```

### Migration Files

- **Location:** `backend/migrations/versions/`
- **Latest:** `0019_fix_schema_idempotent.py` (ensures critical indexes/constraints exist)
- **All migrations:** Checked for idempotency and safe re-execution

---

## Schema Drift Recovery

If the database schema drifts from expected state (e.g., manual changes, failed migrations):

### Step 1: Check Current State

```bash
# Connect to database
fly postgres connect -a <postgres-app-name>

# Or via DATABASE_URL
psql $DATABASE_URL

# Check Alembic version table
SELECT * FROM alembic_version;

# Check if critical indexes exist
SELECT indexname FROM pg_indexes WHERE tablename = 'threat_item' AND indexname = 'idx_threat_item_cve_id';

# Check if constraints exist
SELECT conname FROM pg_constraint WHERE conrelid = 'scan_jobs'::regclass AND conname = 'check_status';
```

### Step 2: Fix Schema Drift

**Option A: Stamp to current migration (if schema matches)**
```bash
# If schema is correct but Alembic version is wrong
alembic stamp head
```

**Option B: Run migrations from scratch**
```bash
# If schema is missing elements
alembic upgrade head
```

**Option C: Manual fix + stamp**
```bash
# 1. Manually fix schema issues
# 2. Stamp to correct version
alembic stamp <revision>
# 3. Continue with normal migrations
alembic upgrade head
```

### Step 3: Verify Schema

```bash
# Run idempotent migration to ensure critical elements exist
alembic upgrade head

# Check application health
curl https://thandev-backend.fly.dev/health
curl https://thandev-backend.fly.dev/ready
```

---

## Health Checks

### Endpoints

- **Health:** `GET /health` - Basic liveness check
- **Ready:** `GET /ready` - Checks database, Redis, and Brain service connectivity

### Manual Health Check

```bash
# From local machine
curl https://thandev-backend.fly.dev/health
curl https://thandev-backend.fly.dev/ready

# From Fly.io machine
fly ssh console -a thandev-backend
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Expected Responses

**Health:**
```json
{"status": "ok"}
```

**Ready:**
```json
{
  "status": "ready",
  "database": "ok",
  "redis": "ok",
  "brain_service": "ok"
}
```

---

## Troubleshooting

### Migration Fails During Deploy

**Symptoms:**
- Deployment fails with migration error
- Machines restart repeatedly
- Logs show `Migration error` or `Database schema error`

**Solution:**
1. Check logs: `fly logs -a thandev-backend`
2. Identify the failing migration
3. Connect to database and check schema state
4. Use schema drift recovery steps above
5. Redeploy after fixing

### Machine Restarts on Boot

**Symptoms:**
- Machines reach max restart count
- Application never starts listening on port 8000

**Possible Causes:**
1. **Migration running on boot (old config):** Should not happen with new setup
2. **Database connection failure:** Check `DATABASE_URL` in Fly secrets
3. **Missing environment variables:** Check all required env vars are set
4. **Application crash:** Check application logs for errors

**Solution:**
1. Check logs: `fly logs -a thandev-backend`
2. Verify `release_command` is set in `fly.toml` (migrations should NOT run on boot)
3. Verify runtime command is only `uvicorn` (no `alembic upgrade`)
4. Check environment variables: `fly secrets list -a thandev-backend`

### Transaction Abort Errors

**Symptoms:**
- `InFailedSqlTransaction` errors in migration logs
- Index/constraint creation fails

**Solution:**
- Migrations now use `CREATE INDEX IF NOT EXISTS` and `DO $$` blocks
- If still occurring, check migration `0019_fix_schema_idempotent.py` is applied
- Run `alembic upgrade head` manually to apply idempotent fixes

### Schema Out of Sync

**Symptoms:**
- Application errors about missing tables/columns
- Alembic version doesn't match actual schema

**Solution:**
1. Check Alembic version: `alembic current`
2. Check actual schema: Connect to database and inspect tables
3. Use schema drift recovery steps
4. If needed, manually fix and stamp: `alembic stamp <revision>`

---

## Quick Reference

### Fly.io Commands

```bash
# Deploy backend
cd backend && fly deploy

# View logs
fly logs -a thandev-backend

# SSH into machine
fly ssh console -a thandev-backend

# Check secrets
fly secrets list -a thandev-backend

# Set secret
fly secrets set KEY=value -a thandev-backend

# Check machine status
fly status -a thandev-backend
```

### Alembic Commands

```bash
# Run migrations
alembic upgrade head

# Check current version
alembic current

# View history
alembic history

# Stamp to specific version (if schema matches)
alembic stamp <revision>

# Create new migration
alembic revision -m "description"
```

---

## Notes

- **Migrations run via Fly release_command:** Do not run Alembic in runtime boot
- **All migrations are idempotent:** Safe to run multiple times
- **Schema drift recovery:** Use `alembic stamp` + `alembic upgrade` as needed
- **Health checks:** Always verify `/health` and `/ready` after deployment

