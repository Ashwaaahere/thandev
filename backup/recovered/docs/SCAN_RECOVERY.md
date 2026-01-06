# Scan Recovery System

## Overview

The scan recovery system automatically handles scans that were interrupted by system downtime. When the system restarts, it detects stale scans and either resumes them or marks them as failed based on configuration.

## How It Works

### On System Startup

When the FastAPI application starts, the recovery system:

1. **Finds Stale Scans**: Queries the database for scans in `RUNNING` or `QUEUED` status that were created within the last 24 hours (configurable)

2. **Checks Task Status**: For each scan, checks if its execution task is still active:
   - **Celery Tasks**: Uses `AsyncResult` to check if the Celery task is still running
   - **Brain Sessions**: Queries the brain service to check if the session is still active

3. **Recovers Stale Scans**: Based on the recovery mode:
   - **Requeue Mode** (default): Resumes the scan by requeuing it as a new Celery task
   - **Fail Mode**: Marks the scan as `FAILED` with an appropriate error message

### Detection Logic

A scan is considered stale if:

- **Celery Task**: The task is in a terminal state (`SUCCESS`, `FAILURE`, `REVOKED`, `REJECTED`) but the scan status is still `RUNNING` or `QUEUED`
- **Celery Task PENDING**: The task is `PENDING` but the scan was created more than 1 hour ago
- **Brain Session**: The session is in a terminal state (`completed`, `failed`, `cancelled`) but the scan status is still `RUNNING`
- **No Task ID**: The scan has no `celery_task_id` or `brain_session_id` and is older than 1 hour

A scan is considered active (not stale) if:

- The Celery task is `STARTED` or `RETRY`
- The brain session is `running` or `planning`
- The scan was recently created (less than 1 hour old) and has no task ID

## Configuration

The recovery system can be configured via environment variables:

```bash
# Enable/disable scan recovery on startup (default: true)
SCAN_RECOVERY_ENABLED=true

# Recovery mode: "requeue" (resume) or "fail" (cancel)
SCAN_RECOVERY_MODE=requeue

# Maximum age in hours for a scan to be considered stale (default: 24)
SCAN_RECOVERY_MAX_STALE_AGE_HOURS=24
```

### Recovery Modes

#### Requeue Mode (Default)

When a stale scan is detected:
- Creates a new Celery task for the scan
- Updates the scan's `celery_task_id` with the new task ID
- Sets scan status to `QUEUED`
- Clears any previous error messages

**Use Case**: When you want scans to automatically resume after system downtime.

#### Fail Mode

When a stale scan is detected:
- Marks the scan as `FAILED`
- Sets an error message explaining the scan was interrupted
- Sets `completed_at` timestamp

**Use Case**: When you want to cancel interrupted scans and require users to start new scans.

## Example Scenarios

### Scenario 1: System Crash During Scan

1. User starts a scan at 10:00 AM
2. Scan is queued and starts running
3. System crashes at 10:30 AM
4. System restarts at 11:00 AM
5. Recovery system detects the stale scan
6. **Requeue Mode**: Scan is requeued and resumes execution
7. **Fail Mode**: Scan is marked as failed

### Scenario 2: Celery Worker Restart

1. Scan is running via Celery task
2. Celery worker is restarted (task is lost)
3. Scan status is still `RUNNING` but task is gone
4. On next system startup, recovery detects stale scan
5. **Requeue Mode**: Scan is requeued with a new task
6. **Fail Mode**: Scan is marked as failed

### Scenario 3: Brain Service Restart

1. Scan is running via brain session
2. Brain service is restarted (session is lost)
3. Scan status is still `RUNNING` but session is gone
4. On next system startup, recovery detects stale scan
5. **Requeue Mode**: Scan is requeued (will create new brain session)
6. **Fail Mode**: Scan is marked as failed

## Manual Recovery

You can also trigger recovery manually by calling the recovery function:

```python
from app.services.scan_recovery import recover_scans_on_startup

# Recover with default settings
stats = recover_scans_on_startup()

# Recover with custom settings
stats = recover_scans_on_startup(
    recovery_mode="fail",
    max_stale_age_hours=48
)
```

## Monitoring

The recovery system logs detailed information about its operations:

```
INFO: Starting scan recovery on system startup...
INFO: Found 3 scans in RUNNING/QUEUED status to check
INFO: Scan abc123: Celery task is in terminal state (FAILURE) but scan status is RUNNING
INFO: Scan abc123: Requeued successfully (new task_id: xyz789)
INFO: Scan recovery completed: 3 scans checked, 2 requeued, 0 failed, 1 skipped, 0 errors
```

## Best Practices

1. **Monitor Recovery Logs**: Check startup logs to see how many scans were recovered
2. **Set Appropriate Stale Age**: Adjust `SCAN_RECOVERY_MAX_STALE_AGE_HOURS` based on your scan duration expectations
3. **Choose Recovery Mode**: Use `requeue` for automatic recovery, `fail` for manual intervention
4. **Regular System Restarts**: Recovery only runs on startup, so plan restarts during low-activity periods if possible

## Troubleshooting

### Scans Not Being Recovered

- Check that `SCAN_RECOVERY_ENABLED=true`
- Verify scans are within the `SCAN_RECOVERY_MAX_STALE_AGE_HOURS` window
- Check logs for errors during recovery

### Too Many Scans Being Recovered

- Reduce `SCAN_RECOVERY_MAX_STALE_AGE_HOURS` to only recover recent scans
- Consider switching to `fail` mode if you don't want automatic recovery

### Recovery Failing

- Check that Celery broker is accessible
- Verify database connection is working
- Check that brain service is accessible (if using brain sessions)
- Review error logs for specific failure reasons


