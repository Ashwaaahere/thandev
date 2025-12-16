# Run Database Migrations Now

## Quick Command

```bash
cd /home/shree/ashwath/thandev/backend
source .venv/bin/activate  # or your venv
alembic upgrade head
```

## Or Use the Helper Script

```bash
cd /home/shree/ashwath/thandev/backend
./run_migrations.sh
```

## What This Does

This will create all the database tables:
- `findings` - Security findings
- `scan_jobs` - Scan execution records  
- `projects` - Project definitions
- `tenants` - Organization/tenant records
- `users` - User accounts
- `tool_results` - Raw tool outputs
- And other related tables

## After Migrations

Once migrations complete successfully, you can run the indexing script:

```bash
cd /home/shree/ashwath/thandev/services/thandev-brain
source venv/bin/activate
python scripts/index_findings.py --limit 1000
```

## Verify Migrations Worked

You can verify tables were created:

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d thandev
# Password: postgres

# List tables
\dt

# Should see: findings, scan_jobs, projects, tenants, users, etc.
```

## All Phases Status

✅ **All 5 phases are complete!**
- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

Just need to run migrations to create the database schema!




