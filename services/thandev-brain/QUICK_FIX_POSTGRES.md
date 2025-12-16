# Quick Fix: PostgreSQL Connection

## Issue
PostgreSQL connection refused at `localhost:5432`

## Solution

### Step 1: Start PostgreSQL via Docker Compose

```bash
cd /home/shree/ashwath/thandev
docker-compose up -d postgres
```

Wait a few seconds for PostgreSQL to start, then verify:
```bash
docker ps | grep postgres
```

### Step 2: Update .env File

Update `services/thandev-brain/.env` with the correct DATABASE_URL:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
```

This matches the docker-compose.yml configuration:
- User: `postgres`
- Password: `postgres`
- Database: `thandev`
- Host: `localhost` (or `postgres` if connecting from within Docker network)
- Port: `5432`

### Step 3: Run Indexing Script

```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings.py --limit 1000
```

## Alternative: Use API Method (No Database Access)

If you can't access the database directly:

```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings_api.py --limit 1000
```

**Note:** This requires the core backend to be running and have an endpoint that returns findings.

## Verify PostgreSQL is Running

```bash
# Check Docker containers
docker ps | grep postgres

# Check if port 5432 is listening
netstat -tuln | grep 5432
# Or
ss -tuln | grep 5432

# Test connection
psql -h localhost -U postgres -d thandev
# Password: postgres
```

## All Phases Status

✅ **All 5 phases are complete!**
- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

The implementation is complete - this is just infrastructure setup!




