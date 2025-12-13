#!/bin/bash
# Test script for basic scan loop end-to-end verification

set -e

API_URL="http://localhost:8000"
PROJECT_ID=""
SCAN_ID=""

echo "=== Thandev v2 Basic Scan Loop Test ==="
echo ""

# Step 1: Health check
echo "1. Testing health endpoint..."
HEALTH=$(curl -s "$API_URL/health")
echo "$HEALTH" | jq .
if [ "$(echo $HEALTH | jq -r '.status')" != "ok" ]; then
    echo "❌ Health check failed!"
    exit 1
fi
echo "✅ Health check passed"
echo ""

# Step 2: Create project (with unique name to avoid conflicts)
TIMESTAMP=$(date +%s)
PROJECT_NAME="Test Target $TIMESTAMP"
echo "2. Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST "$API_URL/api/projects" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"$PROJECT_NAME\",
    \"target_url\": \"https://example.com\",
    \"description\": \"Test project for scan validation\"
  }")
echo "$PROJECT_RESPONSE" | jq .

# Check if project creation failed due to duplicate name
if echo "$PROJECT_RESPONSE" | jq -e '.detail' | grep -q "already exists"; then
    echo "⚠️  Project with that name already exists, trying with different name..."
    PROJECT_NAME="Test Target Unique $TIMESTAMP"
    PROJECT_RESPONSE=$(curl -s -X POST "$API_URL/api/projects" \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"$PROJECT_NAME\",
        \"target_url\": \"https://example.com\",
        \"description\": \"Test project for scan validation\"
      }")
    echo "$PROJECT_RESPONSE" | jq .
fi

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
if [ "$PROJECT_ID" == "null" ] || [ -z "$PROJECT_ID" ]; then
    echo "❌ Failed to create project!"
    echo "Response: $PROJECT_RESPONSE"
    exit 1
fi
echo "✅ Project created: $PROJECT_ID"
echo ""

# Step 3: Create scan
echo "3. Creating basic scan..."
SCAN_RESPONSE=$(curl -s -X POST "$API_URL/api/scans" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"scan_level\": \"basic\"
  }")
echo "$SCAN_RESPONSE" | jq .
SCAN_ID=$(echo "$SCAN_RESPONSE" | jq -r '.id')
STATUS=$(echo "$SCAN_RESPONSE" | jq -r '.status')
if [ "$SCAN_ID" == "null" ] || [ -z "$SCAN_ID" ]; then
    echo "❌ Failed to create scan!"
    exit 1
fi
if [ "$STATUS" != "queued" ]; then
    echo "⚠️  Scan status is '$STATUS', expected 'queued'"
fi
echo "✅ Scan created: $SCAN_ID (status: $STATUS)"
echo ""

# Step 4: Poll scan status
echo "4. Polling scan status (waiting for completion)..."
MAX_WAIT=300  # 5 minutes
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    SCAN_STATUS=$(curl -s "$API_URL/api/scans/$SCAN_ID" | jq -r '.status')
    echo "  Status: $SCAN_STATUS (${ELAPSED}s elapsed)"
    
    if [ "$SCAN_STATUS" == "completed" ]; then
        echo "✅ Scan completed!"
        break
    elif [ "$SCAN_STATUS" == "failed" ]; then
        echo "❌ Scan failed!"
        curl -s "$API_URL/api/scans/$SCAN_ID" | jq '.error_message'
        exit 1
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$SCAN_STATUS" != "completed" ]; then
    echo "⚠️  Scan did not complete within $MAX_WAIT seconds"
fi
echo ""

# Step 5: Get final scan details
echo "5. Getting final scan details..."
FINAL_SCAN=$(curl -s "$API_URL/api/scans/$SCAN_ID")
echo "$FINAL_SCAN" | jq .

FINDINGS_COUNT=$(echo "$FINAL_SCAN" | jq '.findings | length')
SUMMARY_EXISTS=$(echo "$FINAL_SCAN" | jq 'has("summary") and .summary != null')

echo ""
echo "=== Verification ==="
echo "Findings count: $FINDINGS_COUNT"
echo "AI Summary exists: $SUMMARY_EXISTS"

if [ "$SUMMARY_EXISTS" == "true" ]; then
    echo "✅ AI Summary generated"
    echo "$FINAL_SCAN" | jq '.summary.executive_summary'
else
    echo "⚠️  AI Summary not found (may be expected if scan had no findings)"
fi

# Step 6: Check for output file
echo ""
echo "6. Checking for nuclei output file..."
if [ -f "data/jobs/$SCAN_ID/nuclei_output.json" ]; then
    echo "✅ Nuclei output file exists"
    FILE_SIZE=$(wc -c < "data/jobs/$SCAN_ID/nuclei_output.json")
    echo "   File size: $FILE_SIZE bytes"
else
    echo "⚠️  Nuclei output file not found at data/jobs/$SCAN_ID/nuclei_output.json"
fi

echo ""
echo "=== Test Complete ==="

