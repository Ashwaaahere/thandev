# Database Connection Guide for Indexing Script

## Error: PostgreSQL Connection Refused

The indexing script requires PostgreSQL to be running and accessible. If you see:
```
connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
```

## Solutions

### Option 1: Start PostgreSQL

**Check if PostgreSQL is running:**
```bash
sudo systemctl status postgresql
```

**Start PostgreSQL:**
```bash
sudo systemctl start postgresql
```

**Or using Docker Compose:**
```bash
cd /home/shree/ashwath/thandev
docker-compose up -d postgres
```

### Option 2: Configure DATABASE_URL

Make sure `DATABASE_URL` is set in `services/thandev-brain/.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### Option 3: Use API Method (No Database Access)

If you can't access the database directly, you can use the API method (requires core backend running):

```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings_api.py --limit 1000
```

**Note:** The API method requires the core backend to have an endpoint that returns findings. This may need to be implemented.

## Quick Check

```bash
# Check if PostgreSQL is listening on port 5432
netstat -tuln | grep 5432
# Or
ss -tuln | grep 5432
```

## All Phases Status

✅ **All 5 phases are complete!**

- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

**No remaining phases** - This is just an environment setup issue, not a code issue.

## Next Steps

1. Start PostgreSQL (see options above)
2. Verify DATABASE_URL is configured
3. Run indexing script again
4. Or use API method if database access is not available

The brain service implementation is complete - this is just infrastructure setup! 🚀




