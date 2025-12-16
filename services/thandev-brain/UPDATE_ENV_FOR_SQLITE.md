# Update .env to Use SQLite

## Current Issue

The brain service is trying to connect to PostgreSQL, but:
- Backend uses SQLite (default: `sqlite:///./thandev.db`)
- PostgreSQL doesn't have tables yet
- SQLite database already has all tables

## Solution: Use SQLite for Indexing

Update `services/thandev-brain/.env` to use SQLite:

```env
# Change from PostgreSQL to SQLite
DATABASE_URL=sqlite:///../backend/thandev.db
```

**Or use absolute path:**
```env
DATABASE_URL=sqlite:////home/shree/ashwath/thandev/backend/thandev.db
```

## Full .env Configuration

```env
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

RAG_STORE_TYPE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=thandev_rag

EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Use SQLite (same as backend)
DATABASE_URL=sqlite:///../backend/thandev.db

CORE_BACKEND_URL=http://localhost:8000
```

## After Updating .env

Run indexing again:
```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings.py --limit 1000
```

## Alternative: Use PostgreSQL

If you want to use PostgreSQL instead:

1. **Run migrations on PostgreSQL:**
   ```bash
   cd backend
   source .venv/bin/activate
   # Update backend/.env: DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   alembic upgrade head
   ```

2. **Keep brain service .env pointing to PostgreSQL:**
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/thandev
   ```

## All Phases Status

✅ **All 5 phases are complete!**
- Phase 0: Repository Audit ✅
- Phase 1: Brain Service Skeleton ✅
- Phase 2: RAG Foundation ✅
- Phase 3: /plan-scan Implementation ✅
- Phase 4: /build-report-prompt Implementation ✅
- Phase 5: Core Backend Integration ✅

Just need to align database configuration!




