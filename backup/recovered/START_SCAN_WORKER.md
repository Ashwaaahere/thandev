# Starting the Scan Worker

The scan is showing as "queued" but not running because the Celery worker is not started.

## Prerequisites

1. **Redis must be running** (Celery uses Redis as message broker)
2. **Celery worker must be running** (processes queued scan tasks)

## Step 1: Start Redis

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not running, start Redis:
# Option 1: Using systemd (if installed)
sudo systemctl start redis

# Option 2: Using Docker
docker run -d -p 6379:6379 redis:latest

# Option 3: Manual start (if installed locally)
redis-server
```

## Step 2: Start Celery Worker

**In a NEW terminal window:**

```bash
cd /home/ashwath/thandev/backend
source venv/bin/activate

# Option 1: Using helper script (recommended)
./start_celery.sh

# Option 2: Manual command
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
```

**Expected output:**
```
celery@hostname v5.4.0 (opalescent)
...
[tasks]
  . app.tasks.celery_app.enrich_pending
  . app.tasks.celery_app.ingest_kev
  . app.tasks.celery_app.ingest_nvd
  . thandev.run_scan_task
...
celery@hostname ready.
```

## Step 3: Verify Worker is Processing Tasks

Once the worker is running, it should automatically pick up the queued scan. You should see logs like:

```
[INFO] Starting scan 7a6cf46e-8ffe-480e-860b-bd784dffb9fb for https://example.com at level basic
```

## Check Scan Status

```bash
curl -s "http://localhost:8000/api/scans/7a6cf46e-8ffe-480e-860b-bd784dffb9fb" \
  -H "X-Thandev-User-Id: fd66cacf-cdd0-4be3-b1ed-aac6355c4600" \
  -H "X-Thandev-Tenant-Id: 249d35fe-d655-4866-8aec-6368c6677937" \
  | python3 -m json.tool
```

The status should change from "queued" to "running" and then "completed" once the worker processes it.

## Troubleshooting

### Redis Connection Error

If you see errors like:
```
Error: Unable to connect to Redis at localhost:6379
```

**Fix:** Start Redis (see Step 1)

### Celery Worker Not Picking Up Tasks

1. Check Redis is running: `redis-cli ping`
2. Check Celery worker logs for errors
3. Verify the task is in the queue:
   ```bash
   redis-cli
   > KEYS celery*
   > LLEN celery  # Check queue length
   ```

### Worker Starts But Immediately Exits

Check for import errors or missing dependencies:
```bash
cd /home/ashwath/thandev/backend
source venv/bin/activate
python -c "from app.tasks.celery_app import celery; print('OK')"
```

