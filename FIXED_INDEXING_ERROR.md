# Fixed: Indexing Script Error

## Error Fixed ✅

**Problem:** `No module named 'psycopg2'` when running indexing script

**Solution:**
1. Updated `requirements.txt` to include `psycopg2-binary>=2.9.0`
2. Fixed error message to correctly suggest `psycopg2-binary` (not `sqlalchemy`)
3. Updated script to use correct ingestion function (`ingest_prior_scan_findings`)

## Installation

```bash
cd services/thandev-brain
source venv/bin/activate

# Install the missing dependency
pip install psycopg2-binary

# Or install all from requirements.txt (now includes psycopg2-binary)
pip install -r requirements.txt
```

## Run Indexing Script

```bash
cd services/thandev-brain
source venv/bin/activate

# Index all findings (limit 1000)
python scripts/index_findings.py --limit 1000

# Index for specific project
python scripts/index_findings.py --project-id <project_id> --limit 500

# Index for specific org
python scripts/index_findings.py --org-id <org_id> --limit 1000
```

## Note

The script requires:
- `psycopg2-binary` - PostgreSQL adapter (pre-compiled, no dev libraries needed)
- `sqlalchemy` - Already in requirements.txt
- Database access via `DATABASE_URL` in `.env`

## All Phases Status

✅ **All 5 phases are complete!**

- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

No remaining phases - only post-implementation tasks (indexing, testing, monitoring).




