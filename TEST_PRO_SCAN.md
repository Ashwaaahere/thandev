# Testing Pro Scan - Wappalyzer and Retire.js

## Steps to Test

1. **Ensure services are running**:
   ```bash
   docker compose -f docker-compose.fly-local.yml ps
   ```

2. **Create a new Pro scan** from the UI:
   - Go to a project
   - Click "New Scan" or similar
   - Select "Pro" scan type
   - Enter a target URL (e.g., `https://demo.owasp-juice.shop`)
   - Submit

3. **Monitor backend logs**:
   ```bash
   docker compose -f docker-compose.fly-local.yml logs backend --tail 50 -f | grep -i dependency
   ```
   
   Look for:
   - "Enqueuing dependency scan job: scan_id=..."
   - "Successfully enqueued dependency scan job ... to Redis stream"

4. **Check Redis stream**:
   ```bash
   docker exec thandev-redis-1 redis-cli XLEN dependency_scan_jobs
   docker exec thandev-redis-1 redis-cli XREAD COUNT 1 STREAMS dependency_scan_jobs 0
   ```

5. **Monitor runner logs**:
   ```bash
   docker compose -f docker-compose.fly-local.yml logs thandev-runner --tail 50 -f | grep -i "dependency\|wappalyzer\|retire"
   ```
   
   Look for:
   - "Received X dependency scan job(s)"
   - "Processing dependency scan job: scan_id=..., job_type=url_sca"
   - "Created ToolResult entry for wappalyzer"
   - "Created ToolResult entry for retire"

6. **Check database**:
   ```bash
   # Check ToolResult entries
   docker exec thandev-postgres-1 psql -U postgres -d thandev -c "
   SELECT id, scan_job_id, tool_name, status, created_at 
   FROM tool_results 
   WHERE tool_name IN ('wappalyzer', 'retire') 
   ORDER BY created_at DESC 
   LIMIT 5;
   "
   
   # Check artifacts
   docker exec thandev-postgres-1 psql -U postgres -d thandev -c "
   SELECT id, scan_id, type, created_at 
   FROM scan_artifacts 
   WHERE type = 'url_sca' 
   ORDER BY created_at DESC 
   LIMIT 3;
   "
   ```

7. **Check UI**:
   - Go to the scan report page
   - Click on "Tools Executed" tab/section
   - Verify wappalyzer and retire appear in the list

## Expected Results

After creating a Pro scan, you should see:

1. ✅ Backend logs show job enqueued
2. ✅ Redis stream has 1 message
3. ✅ Runner logs show job processed
4. ✅ Database has 2 ToolResult entries (wappalyzer + retire)
5. ✅ Database has 1 artifact entry (url_sca)
6. ✅ UI shows wappalyzer and retire in "Tools Executed"

## Troubleshooting

If tools don't appear:

1. **Check if jobs are being published**: Look for "Enqueuing dependency scan job" in backend logs
2. **Check if jobs are being consumed**: Look for "Processing dependency scan job" in runner logs
3. **Check if tools are installed**: Runner logs should show if wappalyzer/retire are missing
4. **Check ToolResult creation**: Look for "Created ToolResult entry" in runner logs
5. **Check database**: Verify entries exist in tool_results table
