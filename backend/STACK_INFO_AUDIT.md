# Stack Info Audit and Fix Summary

## Audit Results

### 1. ScanJob Model ✅
**File**: `app/models/scan.py` (line 47)

**Column Definition**:
```python
stack_info = Column(JSON().with_variant(Text, "sqlite"), nullable=True)
```

- ✅ Column exists and is named `stack_info`
- ✅ Type: `JSON` with SQLite variant as `Text` (for compatibility)
- ✅ Nullable: `True`
- ✅ Added documentation comment explaining database migration requirements

**Note**: In development with SQLite, if the `scan_jobs` table was created BEFORE the `stack_info` column was added, you may need to:
- Drop and recreate the database file, OR
- Run Alembic migrations to add the column

### 2. Pydantic Schema ✅
**File**: `app/schemas/scan.py` (line 46)

**Field Definition**:
```python
stack_info: Optional[Dict[str, Any]] = None
```

- ✅ Field exists in `ScanResponse` model
- ✅ Type: `Optional[Dict[str, Any]]`
- ✅ Default: `None`
- ✅ Used by `GET /api/scans/{id}` endpoint (line 99)

### 3. Orchestrator: Setting stack_info ✅
**File**: `app/services/scan_orchestrator.py` (lines 131-169)

**Implementation**:
- ✅ `stack_info` is built at the **very beginning** of `run_scan_for_job()`
- ✅ Set **before any tool execution or early returns** (except for fatal errors like missing job/project)
- ✅ Uses existing database session pattern (`db = SessionLocal()`)
- ✅ Commits to database immediately after setting: `db.add(scan_job)`, `db.commit()`, `db.refresh(scan_job)`
- ✅ Includes:
  - `target_url`: From `job.project.target_url`
  - `scan_level`: From `job.scan_level.value`
  - `http` (optional): HTTP response info with `status_code` and `headers` (server, content_type, x_powered_by)

**Code Location**:
```python
# Lines 131-169 in app/services/scan_orchestrator.py
stack_info: Dict[str, Any] = {
    "target_url": target_url,
    "scan_level": getattr(scan_job.scan_level, "value", str(scan_job.scan_level)),
}

# Try HTTP request (with error handling)
# ...

# Persist to DB BEFORE running tools
scan_job.stack_info = stack_info
db.add(scan_job)
db.commit()
db.refresh(scan_job)
```

### 4. Usage for All Scan Levels ✅
**File**: `app/tasks/celery_app.py` (line 71)

- ✅ `run_scan_for_job()` is called for **all scan levels** (basic, pro, advanced)
- ✅ Called from `run_scan_task()` Celery task
- ✅ No early returns before `stack_info` is set (except fatal errors)

**Flow**:
```
Celery Task (run_scan_task)
  ↓
run_scan_for_job(scan_job)
  ↓
1. Build stack_info (lines 131-162)
2. Save stack_info to DB (lines 164-169) ← SET BEFORE TOOLS
3. Plan scan
4. Execute tools
5. Generate AI report
```

### 5. Database Column ✅
- ✅ Column exists in database: `stack_info` (verified)
- ✅ Type: JSON (SQLite stores as TEXT)
- ✅ Nullable: True

**Note**: Existing scans created before this feature will have `stack_info = None`. New scans will have `stack_info` populated.

## Summary

### Where stack_info is defined:
- **Model**: `app/models/scan.py` line 47
  - Type: `Column(JSON().with_variant(Text, "sqlite"), nullable=True)`

### Where it is set:
- **File**: `app/services/scan_orchestrator.py`
- **Function**: `run_scan_for_job(job: ScanJob)`
- **Lines**: 131-169
- **Timing**: Set **before any tool execution**, immediately after loading project

### Which response model exposes it:
- **File**: `app/schemas/scan.py` line 46
- **Model**: `ScanResponse`
- **Field**: `stack_info: Optional[Dict[str, Any]] = None`
- **Endpoint**: `GET /api/scans/{id}` (line 99 in `app/api/scans.py`)

## Testing

To verify stack_info is working:

1. **Create a new scan**:
   ```bash
   curl -X POST http://localhost:8000/api/scans \
     -H "Content-Type: application/json" \
     -d '{"project_id": "your-project-id", "scan_level": "basic"}'
   ```

2. **Wait for scan to complete** (check status)

3. **Get scan details**:
   ```bash
   curl http://localhost:8000/api/scans/{scan_id}
   ```

4. **Verify stack_info is present**:
   ```json
   {
     "id": "...",
     "stack_info": {
       "target_url": "https://example.com",
       "scan_level": "basic",
       "http": {
         "status_code": 200,
         "headers": {
           "server": "nginx",
           "content_type": "text/html",
           "x_powered_by": null
         }
       }
     },
     ...
   }
   ```

## Fixes Applied

1. ✅ Updated model column to use `JSON().with_variant(Text, "sqlite")` for SQLite compatibility
2. ✅ Added documentation comment about database migrations
3. ✅ Refactored stack_info collection to be more explicit and follow user's requested pattern
4. ✅ Ensured stack_info is set before any tool execution
5. ✅ Added explicit `db.add()`, `db.commit()`, and `db.refresh()` calls
6. ✅ Improved error handling and logging

## Notes

- Existing scans will have `stack_info = None` (they were created before this feature)
- New scans will automatically have `stack_info` populated
- If HTTP request fails, `stack_info` will still contain `target_url` and `scan_level`
- The column was manually added to the database in development (see earlier fix)



