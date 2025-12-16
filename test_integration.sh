#!/bin/bash
# Integration test: 2 scans back-to-back to prove RAG changes planning

set -e

echo "=== Integration Test: RAG Planning ==="
echo ""

# Check services
echo "1. Checking services..."
if ! curl -s http://localhost:8001/v1/health > /dev/null; then
    echo "❌ Brain service not running on port 8001"
    exit 1
fi
echo "✅ Brain service running"

if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Core service not running on port 8000"
    exit 1
fi
echo "✅ Core service running"

if ! curl -s http://localhost:6333/health > /dev/null; then
    echo "❌ Qdrant not running on port 6333"
    exit 1
fi
echo "✅ Qdrant running"

echo ""
echo "2. Test target: http://www.itsecgames.com/"
echo ""

# Get auth token (you'll need to set this)
if [ -z "$AUTH_TOKEN" ]; then
    echo "⚠️  AUTH_TOKEN not set. Set it with: export AUTH_TOKEN=your_token"
    echo "   Or login via UI and get token from browser"
    exit 1
fi

TARGET="http://www.itsecgames.com/"
PROJECT_ID="test-project-id"  # Update with actual project ID

echo "3. Running Scan #1..."
SCAN1_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/scans" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"target_url\": \"$TARGET\", \"scan_level\": \"pro\", \"project_id\": \"$PROJECT_ID\"}")

SCAN1_ID=$(echo "$SCAN1_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -z "$SCAN1_ID" ]; then
    echo "❌ Failed to create scan #1"
    echo "Response: $SCAN1_RESPONSE"
    exit 1
fi

echo "✅ Scan #1 created: $SCAN1_ID"
echo "   Waiting for completion..."

# Wait for scan to complete (check status every 5 seconds, max 10 minutes)
for i in {1..120}; do
    sleep 5
    STATUS=$(curl -s "http://localhost:8000/api/scans/$SCAN1_ID" \
        -H "Authorization: Bearer $AUTH_TOKEN" | \
        python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null || echo "unknown")
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo "   Scan #1 status: $STATUS"
        break
    fi
    if [ $((i % 12)) -eq 0 ]; then
        echo "   Still running... ($((i*5))s elapsed)"
    fi
done

echo ""
echo "4. Running Scan #2 (same target)..."
SCAN2_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/scans" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"target_url\": \"$TARGET\", \"scan_level\": \"pro\", \"project_id\": \"$PROJECT_ID\"}")

SCAN2_ID=$(echo "$SCAN2_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -z "$SCAN2_ID" ]; then
    echo "❌ Failed to create scan #2"
    echo "Response: $SCAN2_RESPONSE"
    exit 1
fi

echo "✅ Scan #2 created: $SCAN2_ID"
echo "   Waiting for completion..."

# Wait for scan to complete
for i in {1..120}; do
    sleep 5
    STATUS=$(curl -s "http://localhost:8000/api/scans/$SCAN2_ID" \
        -H "Authorization: Bearer $AUTH_TOKEN" | \
        python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null || echo "unknown")
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo "   Scan #2 status: $STATUS"
        break
    fi
    if [ $((i % 12)) -eq 0 ]; then
        echo "   Still running... ($((i*5))s elapsed)"
    fi
done

echo ""
echo "5. Checking logs for RAG evidence..."
echo "   (Check brain service logs for RAG query evidence in scan #2)"
echo ""
echo "=== Test Complete ==="
echo ""
echo "Scan #1 ID: $SCAN1_ID"
echo "Scan #2 ID: $SCAN2_ID"
echo ""
echo "To verify RAG integration:"
echo "  1. Check brain logs for '/v1/rag/ingest' calls during scan #1"
echo "  2. Check brain logs for RAG queries during scan #2 planning"
echo "  3. Compare plans - scan #2 should use evidence from scan #1"



