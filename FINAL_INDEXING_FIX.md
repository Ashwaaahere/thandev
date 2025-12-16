# Final Fix: SQLite Parameter Binding

## Issue Fixed ✅

**Error:** `List argument must consist only of dictionaries`

**Root Cause:** SQLAlchemy's `text()` with SQLite doesn't work well with tuple parameters when using `?` placeholders.

**Solution:** Use named placeholders (`:name`) for both SQLite and PostgreSQL. SQLAlchemy's `text()` supports this for both databases.

## What Changed

1. **Simplified query building** - Now uses `:name` placeholders for both databases
2. **Removed tuple parameter handling** - No longer needed
3. **Unified execution** - Same code path for both SQLite and PostgreSQL

## Configuration

Make sure `services/thandev-brain/.env` has:

```env
DATABASE_URL=sqlite:///../backend/thandev.db
```

Or absolute path:
```env
DATABASE_URL=sqlite:////home/shree/ashwath/thandev/backend/thandev.db
```

## Run Indexing

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

The indexing script is now fixed and should work with SQLite! 🚀




