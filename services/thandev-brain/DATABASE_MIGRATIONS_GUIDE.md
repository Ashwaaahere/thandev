# Database Migrations Guide

## Error: Table "findings" does not exist

This error means the database is connected, but the tables haven't been created yet. You need to run database migrations.

## Solution: Run Database Migrations

### Option 1: Run Migrations Locally

```bash
cd /home/shree/ashwath/thandev/backend

# Make sure you're in the backend virtual environment
source .venv/bin/activate  # or your venv path

# Run migrations
alembic upgrade head
```

### Option 2: Run Migrations via Docker Compose

```bash
cd /home/shree/ashwath/thandev

# Make sure services are running
docker-compose up -d postgres

# Run migrations in the API container
docker-compose exec api alembic upgrade head
```

### Option 3: Run Migrations Manually

If you need to run migrations directly:

```bash
cd /home/shree/ashwath/thandev/backend

# Check current migration status
alembic current

# Upgrade to latest
alembic upgrade head

# Or create a new migration (if needed)
alembic revision --autogenerate -m "description"
```

## Verify Tables Exist

After running migrations, verify tables were created:

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d thandev
# Password: postgres

# List tables
\dt

# Check if findings table exists
SELECT * FROM findings LIMIT 1;
```

## Expected Tables

After migrations, you should have:
- `findings` - Security findings
- `scan_jobs` - Scan execution records
- `projects` - Project definitions
- `tenants` - Organization/tenant records
- `users` - User accounts
- `tool_results` - Raw tool outputs
- And other related tables

## After Migrations

Once migrations are complete, you can run the indexing script:

```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings.py --limit 1000
```

## All Phases Status

✅ **All 5 phases are complete!**
- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

The implementation is complete - just need to set up the database schema!




