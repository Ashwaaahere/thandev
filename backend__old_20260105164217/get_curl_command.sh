#!/bin/bash
# Helper script to generate complete curl command for testing scans

cd "$(dirname "$0")"
source venv/bin/activate

python << 'EOF'
from app.core.database import SessionLocal
from app.models.project import Project
db = SessionLocal()
try:
    p = db.query(Project).order_by(Project.created_at.desc()).first()
    if p:
        print("PROJECT_ID=\"" + p.id + "\"")
        print("USER_ID=\"" + p.owner_id + "\"")
        print("TENANT_ID=\"" + p.tenant_id + "\"")
        print("")
        print("# Complete curl command:")
        print("curl -s -X POST \"http://localhost:8000/api/scans\" \\")
        print("  -H \"Content-Type: application/json\" \\")
        print("  -H \"X-Thandev-User-Id: " + p.owner_id + "\" \\")
        print("  -H \"X-Thandev-Tenant-Id: " + p.tenant_id + "\" \\")
        print("  -d '{\"project_id\":\"" + p.id + "\",\"scan_level\":\"pro\"}' | jq")
    else:
        print("No projects found in database")
finally:
    db.close()
EOF

