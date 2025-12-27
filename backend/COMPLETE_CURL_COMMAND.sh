#!/bin/bash
# Complete curl command with real values

PROJECT_ID="test-project-0b5ccc58-914f-41af-813d-510eb8aa0b2c"
USER_ID="test-user-0b5ccc58-914f-41af-813d-510eb8aa0b2c"
TENANT_ID="test-tenant-0b5ccc58-914f-41af-813d-510eb8aa0b2c"

echo "Complete curl command:"
echo ""
echo "curl -s -X POST \"http://localhost:8000/api/scans\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Thandev-User-Id: $USER_ID\" \\"
echo "  -H \"X-Thandev-Tenant-Id: $TENANT_ID\" \\"
echo "  -d '{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}'"
echo ""
echo "Or with formatted output (if python available):"
echo ""
echo "curl -s -X POST \"http://localhost:8000/api/scans\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -H \"X-Thandev-User-Id: $USER_ID\" \\"
echo "  -H \"X-Thandev-Tenant-Id: $TENANT_ID\" \\"
echo "  -d '{\"project_id\":\"$PROJECT_ID\",\"scan_level\":\"pro\"}' | python -m json.tool"

