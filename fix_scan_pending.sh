#!/bin/bash
echo "=== Fixing Scan Pending Issue ==="
echo ""

# 1. Update Runner BACKEND_URL
echo "1. Updating runner BACKEND_URL..."
fly secrets set BACKEND_URL="http://thandev-backend.internal:8000" -a thandev-runner

# 2. Update Backend BRAIN_URL (ensure both are set)
echo ""
echo "2. Updating backend BRAIN_URL..."
fly secrets set \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  BRAIN_SERVICE_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend

# 3. Restart services
echo ""
echo "3. Restarting services..."
fly apps restart thandev-runner
fly apps restart thandev-backend
fly apps restart thandev-brain

echo ""
echo "✅ Fixes applied! Wait 30-60 seconds for services to restart."
echo "Then create a new scan and monitor logs."
