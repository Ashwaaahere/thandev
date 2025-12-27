#!/bin/bash
# Bootstrap script for dev/local environment
# Creates tenant, user, and project with valid UUIDs
# Usage: scripts/bootstrap_dev.sh [target_url]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

# Default target URL
TARGET_URL="${1:-https://example.com}"

# Generate UUIDs
TENANT_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
USER_ID=$(python3 -c "import uuid; print(uuid.uuid4())")

echo "=" * 60
echo "Thandev Dev Bootstrap"
echo "=" * 60
echo ""
echo "This script will create:"
echo "  - Tenant ID: $TENANT_ID"
echo "  - User ID: $USER_ID"
echo "  - Project for: $TARGET_URL"
echo ""

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend is not running. Start it with: make backend"
    exit 1
fi

# Set environment to local for auto-creation
export ENVIRONMENT=local

# Create tenant (via API or direct DB)
echo "Creating tenant..."
TENANT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tenants \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -d "{\"name\": \"Dev Tenant\", \"plan\": \"pro\"}" || echo "")

if [ -z "$TENANT_RESPONSE" ] || echo "$TENANT_RESPONSE" | grep -q "error"; then
    echo "⚠️  Tenant creation via API failed, will rely on auto-creation"
else
    echo "✅ Tenant created"
fi

# Create user (via API or direct DB)
echo "Creating user..."
USER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -d "{\"email\": \"dev-user@example.com\", \"username\": \"dev-user\", \"password\": \"dev-password\"}" || echo "")

if [ -z "$USER_RESPONSE" ] || echo "$USER_RESPONSE" | grep -q "error"; then
    echo "⚠️  User creation via API failed, will rely on auto-creation"
else
    echo "✅ User created"
fi

# Create project
echo "Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -H "X-Thandev-Tenant-Id: $TENANT_ID" \
  -H "X-Thandev-User-Id: $USER_ID" \
  -d "{\"name\": \"Dev Project\", \"target_url\": \"$TARGET_URL\"}")

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Failed to create project"
    echo "Response: $PROJECT_RESPONSE"
    exit 1
fi

echo "✅ Project created: $PROJECT_ID"
echo ""

# Print summary
echo "=" * 60
echo "Bootstrap Complete!"
echo "=" * 60
echo ""
echo "Use these headers for API calls:"
echo "  X-Thandev-Tenant-Id: $TENANT_ID"
echo "  X-Thandev-User-Id: $USER_ID"
echo ""
echo "Project ID: $PROJECT_ID"
echo ""
echo "Example: Create a scan"
echo "  curl -X POST http://localhost:8000/api/scans \\"
echo "    -H \"X-Thandev-Tenant-Id: $TENANT_ID\" \\"
echo "    -H \"X-Thandev-User-Id: $USER_ID\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"project_id\": \"$PROJECT_ID\", \"scan_level\": \"basic\"}'"
echo ""

