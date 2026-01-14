#!/bin/bash
# Diagnostic script to check why scans are pending

echo "=== DIAGNOSING SCAN PENDING ISSUE ==="
echo ""

echo "1. Checking Backend Secrets..."
echo "BRAIN_URL:"
fly secrets list -a thandev-backend | grep BRAIN_URL || echo "  ❌ BRAIN_URL not found"
echo "BRAIN_SERVICE_URL:"
fly secrets list -a thandev-backend | grep BRAIN_SERVICE_URL || echo "  ❌ BRAIN_SERVICE_URL not found"
echo ""

echo "2. Checking Runner Secrets..."
echo "BACKEND_URL:"
fly secrets list -a thandev-runner | grep BACKEND_URL || echo "  ❌ BACKEND_URL not found"
echo ""

echo "3. Checking Recent Backend Logs for Brain Calls..."
fly logs -a thandev-backend --no-tail 2>&1 | grep -iE "Starting brain|brain.*session|Failed.*brain|publish.*runner" | tail -10 || echo "  ❌ No brain/runner logs found"
echo ""

echo "4. Checking Recent Brain Logs for Session Creation..."
fly logs -a thandev-brain --no-tail 2>&1 | grep -iE "session|start|POST.*session" | tail -10 || echo "  ❌ No session creation logs found"
echo ""

echo "5. Checking Recent Runner Logs for Step Consumption..."
fly logs -a thandev-runner --no-tail 2>&1 | grep -iE "consume|step.*request|connection.*failed" | tail -10 || echo "  ❌ No step consumption logs found"
echo ""

echo "6. Checking Service Status..."
echo "Backend:"
fly status -a thandev-backend | grep -E "STATE|CHECKS" | head -2
echo "Brain:"
fly status -a thandev-brain | grep -E "STATE|CHECKS" | head -2
echo "Runner:"
fly status -a thandev-runner | grep -E "STATE|CHECKS" | head -3
echo ""

echo "=== DIAGNOSIS COMPLETE ==="
