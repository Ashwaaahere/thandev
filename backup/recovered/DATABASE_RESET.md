# Database Reset for stack_info Column

## What Was Done

The SQLite database was dropped and recreated to include the new `stack_info` column.

### Database Files Removed:
- `thandev.db` - Main database file
- `thandev.db-shm` - Shared memory file
- `thandev.db-wal` - Write-ahead log file

### Database Recreated:
- Tables were automatically recreated by SQLAlchemy on next startup
- The `stack_info` column is now included in the `scan_jobs` table

## Next Steps

1. **Restart uvicorn** (if it's running):
   ```bash
   # Stop current uvicorn process (Ctrl+C)
   # Then restart:
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --port 8000
   ```

2. **Restart Celery worker** (if it's running):
   ```bash
   # Stop current worker (Ctrl+C)
   # Then restart:
   cd backend
   source .venv/bin/activate
   ./start_celery.sh
   # or
   PYTHONPATH=. celery -A app.tasks.celery_app worker --loglevel=info
   ```

3. **Verify the column exists**:
   ```bash
   cd backend
   python -c "
   from app.core.database import SessionLocal
   from app.models.scan import ScanJob
   from sqlalchemy import inspect
   
   db = SessionLocal()
   inspector = inspect(db.bind)
   columns = [col['name'] for col in inspector.get_columns('scan_jobs')]
   print('Columns:', columns)
   print('stack_info exists:', 'stack_info' in columns)
   db.close()
   "
   ```

## Important Notes

- **All existing data was lost** (this is expected in development)
- **New scans will have stack_info populated** automatically
- **You may need to recreate test projects** if you had any

## For Production

In production with PostgreSQL, you would use Alembic migrations instead:

```bash
alembic revision --autogenerate -m "Add stack_info column"
alembic upgrade head
```

But for local SQLite development, dropping and recreating is acceptable.



