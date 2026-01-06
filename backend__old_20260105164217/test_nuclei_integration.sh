#!/bin/bash
# Test script to verify Nuclei integration is working
#
# Usage:
#   ./test_nuclei_integration.sh [target_url] [scan_level]
#
# Examples:
#   # Test with default target (may have no findings - this is OK)
#   ./test_nuclei_integration.sh http://itsecgames.com/ advanced
#
#   # Test with a known vulnerable demo target (should produce findings)
#   ./test_nuclei_integration.sh http://testphp.vulnweb.com/ advanced
#
# For a target that actually yields findings with default nuclei templates,
# try something like:
#   ./test_nuclei_integration.sh http://testphp.vulnweb.com/ advanced

set -e

API_BASE="${API_BASE:-http://localhost:8000}"
TARGET="${1}"
SCAN_LEVEL="${2:-advanced}"

# Show usage if no target provided
if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target_url> [scan_level]"
    echo ""
    echo "Examples:"
    echo "  # Test with default target (may have no findings - this is OK)"
    echo "  $0 http://itsecgames.com/ advanced"
    echo ""
    echo "  # Test with a known vulnerable demo target (should produce findings)"
    echo "  $0 http://testphp.vulnweb.com/ advanced"
    echo ""
    exit 1
fi

echo "=========================================="
echo "Nuclei Integration Test"
echo "=========================================="
echo "Target: $TARGET"
echo "Scan Level: $SCAN_LEVEL"
echo "API Base: $API_BASE"
echo ""

# Step 1: Trigger scan
echo "Step 1: Triggering scan..."
RESPONSE=$(curl -s -X POST "$API_BASE/api/scans/quick" \
  -H "Content-Type: application/json" \
  -d "{\"target_url\":\"$TARGET\",\"scan_level\":\"$SCAN_LEVEL\"}")

SCAN_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['scan_id'])" 2>/dev/null || echo "")
PROJECT_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['project_id'])" 2>/dev/null || echo "")

if [ -z "$SCAN_ID" ]; then
    echo "❌ Failed to create scan. Response: $RESPONSE"
    exit 1
fi

echo "✅ Scan created: $SCAN_ID"
echo "   Project ID: $PROJECT_ID"
echo ""

# Step 2: Poll until completed
echo "Step 2: Waiting for scan to complete..."
MAX_WAIT=600  # 10 minutes
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS=$(curl -s "$API_BASE/api/scans/$SCAN_ID" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
    
    if [ "$STATUS" = "completed" ]; then
        echo "✅ Scan completed!"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ Scan failed!"
        curl -s "$API_BASE/api/scans/$SCAN_ID" | python3 -m json.tool | grep -A 5 "error_message"
        exit 1
    fi
    
    echo "   Status: $STATUS (waiting...)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$STATUS" != "completed" ]; then
    echo "❌ Scan did not complete within $MAX_WAIT seconds"
    exit 1
fi

echo ""

# Step 3: Check scan details
echo "Step 3: Checking scan details..."
SCAN_DETAILS=$(curl -s "$API_BASE/api/scans/$SCAN_ID")
FINDINGS_COUNT=$(echo "$SCAN_DETAILS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('summary', {}).get('findings_count', 0) if d.get('summary') else 0)" 2>/dev/null || echo "0")
RISK_SCORE=$(echo "$SCAN_DETAILS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('summary', {}).get('risk_score', 0) if d.get('summary') else 0)" 2>/dev/null || echo "0")

echo "   Findings Count: $FINDINGS_COUNT"
echo "   Risk Score: $RISK_SCORE"
echo ""

# Step 4: Check output file
echo "Step 4: Checking Nuclei output file..."
OUTPUT_FILE="data/jobs/$SCAN_ID/nuclei_output.json"
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(wc -c < "$OUTPUT_FILE" | tr -d ' ')
    LINE_COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')
    echo "   ✅ File exists: $OUTPUT_FILE"
    echo "   File size: $FILE_SIZE bytes"
    echo "   Line count: $LINE_COUNT"
    
    if [ "$FILE_SIZE" -gt 0 ]; then
        echo "   First 3 lines:"
        head -3 "$OUTPUT_FILE" | sed 's/^/      /'
    else
        echo "   ⚠️  File is empty (0 bytes) - Nuclei found no vulnerabilities"
    fi
else
    echo "   ❌ File does not exist: $OUTPUT_FILE"
fi
echo ""

# Step 5: Check findings API
echo "Step 5: Checking findings API..."
FINDINGS_RESPONSE=$(curl -s "$API_BASE/api/findings?limit=10&offset=0")
TOTAL_FINDINGS=$(echo "$FINDINGS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
ITEMS_COUNT=$(echo "$FINDINGS_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['items']))" 2>/dev/null || echo "0")

echo "   Total findings: $TOTAL_FINDINGS"
echo "   Items returned: $ITEMS_COUNT"

if [ "$TOTAL_FINDINGS" -gt 0 ]; then
    echo "   ✅ Findings detected! First finding:"
    echo "$FINDINGS_RESPONSE" | python3 -m json.tool | head -20 | sed 's/^/      /'
else
    echo "   ⚠️  No findings in database (this is OK if Nuclei found nothing)"
fi
echo ""

# Step 6: Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Scan ID: $SCAN_ID"
echo "Status: completed"
echo "Findings Count: $FINDINGS_COUNT"
echo "Risk Score: $RISK_SCORE"
echo "Output File Size: ${FILE_SIZE:-N/A} bytes"
echo "Total Findings in DB: $TOTAL_FINDINGS"
echo ""

if [ "$FINDINGS_COUNT" -gt 0 ] || [ "$TOTAL_FINDINGS" -gt 0 ]; then
    echo "✅ SUCCESS: Findings were detected and ingested!"
elif [ "${FILE_SIZE:-0}" -eq 0 ]; then
    echo "⚠️  NOTE: Nuclei found no vulnerabilities for this target."
    echo "   This is expected behavior - not all targets have vulnerabilities."
    echo "   The system is working correctly."
else
    echo "⚠️  WARNING: File has content but no findings were ingested."
    echo "   Check Celery logs for parsing/ingestion errors."
fi

echo ""
echo "To view full scan details:"
echo "  curl -s '$API_BASE/api/scans/$SCAN_ID' | python3 -m json.tool"
echo ""
echo "To view all findings:"
echo "  curl -s '$API_BASE/api/findings?limit=100&offset=0' | python3 -m json.tool"

