# How to Retry Publishing Scan Steps

## Method 1: Using the Python Script

```bash
# Get scan details first to get tenant_id and user_id
python3 retry_scan_publish.py <scan_id> <backend_url> <tenant_id> <user_id>

# Example:
python3 retry_scan_publish.py c7e26f8b-e950-45b5-8cda-891651a5c34b \
  https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io \
  8b6a9a85-a892-4a26-a0fc-3f0a8c0d8468 \
  d36da182-2f87-4c52-9ab2-b8a7dcd28bcf
```

## Method 2: Using curl

```bash
curl -X POST "https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io/api/scans/<scan_id>/retry-publish" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: <tenant_id>" \
  -H "X-Thandev-User-Id: <user_id>"
```

## Method 3: Get Scan Details First

To get the tenant_id and user_id for a scan:

```bash
# Run this to get scan details
docker run --rm --network host \
  -e DATABASE_URL="postgresql://postgres.kooxcykmlwonxqdushgt:6ySBsM6lRK8JSMQu@aws-0-us-west-2.pooler.supabase.com:6543/postgres" \
  -v $(pwd)/check_scan_tools.py:/app/check_tools.py \
  python:3.11-slim bash -c "pip install -q sqlalchemy psycopg2-binary && python -c \"
import sys
sys.path.insert(0, '/app')
from check_tools import *
scan_id = '<your_scan_id>'
query = text('SELECT s.id, p.tenant_id, s.user_id FROM scan_jobs s JOIN projects p ON s.project_id = p.id WHERE s.id = :sid')
result = session.execute(query, {'sid': scan_id}).fetchone()
if result:
    print(f'Scan ID: {result[0]}')
    print(f'Tenant ID: {result[1]}')
    print(f'User ID: {result[2]}')
\""
```

## For Scan C7E26F8B:

**Scan ID (full):** `c7e26f8b-e950-45b5-8cda-891651a5c34b`  
**Tenant ID:** `8b6a9a85-a892-4a26-a0fc-3f0a8c0d8468`  
**User ID:** `d36da182-2f87-4c52-9ab2-b8a7dcd28bcf`  
**Backend URL:** `https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`

**Command:**
```bash
curl -X POST "https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io/api/scans/c7e26f8b-e950-45b5-8cda-891651a5c34b/retry-publish" \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: 8b6a9a85-a892-4a26-a0fc-3f0a8c0d8468" \
  -H "X-Thandev-User-Id: d36da182-2f87-4c52-9ab2-b8a7dcd28bcf"
```

## Note

The endpoint may return 404 if:
1. The backend hasn't fully restarted with the new code yet (wait 1-2 minutes after deployment)
2. The route path is incorrect
3. The scan doesn't exist or doesn't belong to the tenant

If you get 404, wait a minute and try again, or check the backend logs to see if the route is registered.

