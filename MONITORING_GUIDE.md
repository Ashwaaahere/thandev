# Scan Monitoring Guide

## Quick Start

You just started a new scan! Here are ways to monitor it:

### Option 1: Using the API Monitoring Script (No Dependencies)
```bash
# Get your scan ID from the dashboard, then:
./monitor_scan_api.sh <scan_id> 5

# Example:
./monitor_scan_api.sh DF3C109E 5
```

### Option 2: Using Python Monitoring Script (Requires Dependencies)
```bash
# First install dependencies:
pip install sqlalchemy psycopg2-binary

# Then monitor:
python3 monitor_scan.py <scan_id> 5

# Or monitor the latest scan automatically:
python3 monitor_latest_scan.py
```

### Option 3: Check Dashboard
Just refresh your browser - the dashboard should show real-time updates!

## What to Look For

### ✅ Good Signs:
- Tools showing as "running" or "completed"
- Findings count increasing
- No error messages
- Progress percentage increasing

### ⚠️ Warning Signs:
- Tools stuck in "pending" for a long time
- Tools marked as "failed" immediately
- Error messages in tool status
- Scan stuck at 0% progress

### 🔍 If Tools Are Failing:

1. **Check ZAP Connection:**
   ```bash
   docker ps | grep zap
   curl http://thandev-zap.internal:8090/JSON/core/view/version/
   ```

2. **Check Backend Logs:**
   ```bash
   # Find logs for your scan ID
   grep "<scan_id>" backend/logs/*.log | tail -50
   ```

3. **Check Runner Logs:**
   ```bash
   grep "<scan_id>" services/thandev-runner/logs/*.log | tail -50
   ```

## Common Issues

### "All tools pending"
- Brain service might be stuck
- Check: `docker ps | grep brain`
- Fix: `docker compose restart thandev-brain`

### "ZAP failed"
- ZAP service might not be running
- Check: `docker ps | grep zap`
- Fix: `docker compose restart thandev-zap`

### "Scan completed but no findings"
- This might be **normal** if target has no vulnerabilities
- Check if tools actually ran (look at execution times)
- Check if findings were created but filtered out

## Getting Your Scan ID

1. **From Dashboard:** Look at the URL or scan card
2. **From Browser Console:** Check network requests
3. **From Database:** (if you have access)
   ```sql
   SELECT id, url, status, created_at 
   FROM scan_jobs 
   ORDER BY created_at DESC 
   LIMIT 5;
   ```

## Monitoring Tips

- **Refresh interval:** Use 5-10 seconds for active monitoring
- **Watch for patterns:** Tools usually run in sequence or parallel groups
- **Check findings:** Even if tools complete, findings might take a moment to appear
- **Be patient:** Some tools (like ZAP, nuclei) can take 10-30+ minutes

## Need Help?

If you see issues:
1. Note the scan ID
2. Check the tool statuses
3. Look for error messages
4. Check the diagnostic guide: `SCAN_DF3C109E_DIAGNOSIS.md`


