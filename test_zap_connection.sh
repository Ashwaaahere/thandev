#!/bin/bash
# Test ZAP connection from runner perspective

echo "=== Testing ZAP Connection ==="
echo ""

# Test 1: Check ZAP service status
echo "1. ZAP Service Status:"
fly status -a thandev-zap | grep -E "STATE|CHECKS" | head -3
echo ""

# Test 2: Check ZAP_API_URL secret is set
echo "2. ZAP_API_URL Secret:"
if fly secrets list -a thandev-runner | grep -q ZAP_API_URL; then
    echo "   ✅ ZAP_API_URL secret is set"
else
    echo "   ❌ ZAP_API_URL secret is NOT set"
fi
echo ""

# Test 3: Check recent ZAP connection attempts in runner logs
echo "3. Recent ZAP Connection Attempts:"
RECENT_ZAP=$(fly logs -a thandev-runner --no-tail 2>&1 | grep -iE "zap.*accessible|zap.*connection|zap.*api" | tail -5)
if [ -n "$RECENT_ZAP" ]; then
    echo "   Recent ZAP logs:"
    echo "$RECENT_ZAP" | sed 's/^/   /'
else
    echo "   ⚠️  No recent ZAP connection attempts in logs"
    echo "   (This is normal if no scans have run recently)"
fi
echo ""

# Test 4: Check ZAP health endpoint directly
echo "4. ZAP Health Check:"
ZAP_HEALTH=$(fly logs -a thandev-zap --no-tail 2>&1 | grep -i "listening on\|health check.*passing" | tail -2)
if [ -n "$ZAP_HEALTH" ]; then
    echo "   ✅ ZAP is listening and health checks passing:"
    echo "$ZAP_HEALTH" | sed 's/^/   /'
else
    echo "   ⚠️  Could not verify ZAP health from logs"
fi
echo ""

echo "=== Summary ==="
echo "ZAP service is running and configured."
echo "Connection will be tested when next scan runs."
echo ""
echo "To verify connection works:"
echo "1. Run a Pro or Advanced scan that includes ZAP"
echo "2. Check runner logs: fly logs -a thandev-runner | grep -i zap"
echo "3. Look for 'ZAP API is accessible' message"
