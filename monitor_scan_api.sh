#!/bin/bash
# Simple scan monitoring script using API calls
# Usage: ./monitor_scan_api.sh <scan_id> [refresh_interval]

SCAN_ID="${1}"
REFRESH="${2:-5}"

if [ -z "$SCAN_ID" ]; then
    echo "Usage: $0 <scan_id> [refresh_interval]"
    echo "Example: $0 DF3C109E 5"
    exit 1
fi

# Get API base URL from environment or use default
API_BASE="${NEXT_PUBLIC_API_BASE:-http://localhost:8000}"

echo "📊 Monitoring Scan: $SCAN_ID"
echo "   API: $API_BASE"
echo "   Refresh: ${REFRESH}s"
echo "   Press Ctrl+C to stop"
echo ""

while true; do
    # Clear screen
    clear
    
    # Get scan status
    RESPONSE=$(curl -s "${API_BASE}/api/scans/${SCAN_ID}" \
        -H "Content-Type: application/json" \
        2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to connect to API at $API_BASE"
        echo "   Check if backend is running and NEXT_PUBLIC_API_BASE is set correctly"
        sleep $REFRESH
        continue
    fi
    
    # Extract status using jq if available, otherwise use grep
    if command -v jq &> /dev/null; then
        STATUS=$(echo "$RESPONSE" | jq -r '.status // "unknown"')
        URL=$(echo "$RESPONSE" | jq -r '.url // "N/A"')
        PROGRESS=$(echo "$RESPONSE" | jq -r '.progress // 0')
        TOOLS=$(echo "$RESPONSE" | jq -r '.tools // [] | length')
        FINDINGS_COUNT=$(echo "$RESPONSE" | jq -r '.summary.findings_count // 0')
        
        echo "📊 Scan: ${SCAN_ID:0:8}... | Status: ${STATUS^^} | Progress: ${PROGRESS}%"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "URL: $URL"
        echo "Tools: $TOOLS"
        echo "Findings: $FINDINGS_COUNT"
        echo ""
        
        # Show tool statuses if available
        if echo "$RESPONSE" | jq -e '.tool_statuses' > /dev/null 2>&1; then
            echo "🔧 Tool Status:"
            echo "$RESPONSE" | jq -r '.tool_statuses[] | "\(.tool_name): \(.status) (\(.execution_time // 0)s)"' | while read line; do
                if [[ $line == *"completed"* ]]; then
                    echo "✅ $line"
                elif [[ $line == *"failed"* ]]; then
                    echo "❌ $line"
                elif [[ $line == *"running"* ]]; then
                    echo "🔄 $line"
                elif [[ $line == *"pending"* ]]; then
                    echo "⏳ $line"
                else
                    echo "   $line"
                fi
            done
        fi
    else
        # Fallback without jq
        echo "📊 Scan: ${SCAN_ID:0:8}..."
        echo "$RESPONSE" | grep -o '"status":"[^"]*"' | head -1
        echo ""
        echo "⚠️  Install 'jq' for better output: sudo apt-get install jq"
        echo "   Raw response:"
        echo "$RESPONSE" | head -20
    fi
    
    # Check if scan is complete
    if [[ "$STATUS" == "completed" ]] || [[ "$STATUS" == "completed_with_errors" ]] || [[ "$STATUS" == "failed" ]]; then
        echo ""
        echo "✅ Scan ${STATUS^^}!"
        echo "   Press Ctrl+C to exit"
        sleep $REFRESH
        break
    fi
    
    echo ""
    echo "⏱️  Next update in ${REFRESH}s... (Press Ctrl+C to stop)"
    sleep $REFRESH
done


