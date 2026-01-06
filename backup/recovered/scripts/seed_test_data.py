#!/usr/bin/env python3
"""
Seed script to create demo/test data for Thandev.

Creates:
- Demo organization/tenant
- Demo project
- Demo scan with deterministic results

Usage:
    python scripts/seed_test_data.py
    python scripts/seed_test_data.py --reset  # Delete existing demo data first
"""
import sys
import argparse
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.project import Project
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.models.finding import Finding, Severity, ToolResult, ToolExecutionStatus
from datetime import datetime, timezone
import uuid


def create_demo_tenant_and_user(db: Session) -> tuple[Tenant, User]:
    """Create demo tenant and user"""
    # Check if demo tenant already exists
    demo_tenant = db.query(Tenant).filter(Tenant.id == "demo-tenant").first()
    if demo_tenant:
        print("  ✓ Demo tenant already exists")
        demo_user = db.query(User).filter(User.tenant_id == demo_tenant.id).first()
        if not demo_user:
            demo_user = User(
                id="demo-user",
                email="demo@thandev.test",
                tenant_id=demo_tenant.id,
                name="Demo User"
            )
            db.add(demo_user)
            db.commit()
        return demo_tenant, demo_user
    
    demo_tenant = Tenant(
        id="demo-tenant",
        name="Demo Organization",
        slug="demo"
    )
    demo_user = User(
        id="demo-user",
        email="demo@thandev.test",
        tenant_id=demo_tenant.id,
        name="Demo User"
    )
    
    db.add(demo_tenant)
    db.add(demo_user)
    db.commit()
    print("  ✓ Created demo tenant and user")
    return demo_tenant, demo_user


def create_demo_project(db: Session, tenant: Tenant, user: User) -> Project:
    """Create demo project"""
    # Check if demo project already exists
    demo_project = db.query(Project).filter(Project.id == "demo-project").first()
    if demo_project:
        print("  ✓ Demo project already exists")
        return demo_project
    
    demo_project = Project(
        id="demo-project",
        name="Demo Test Site",
        target_url="http://testphp.vulnweb.com",
        tenant_id=tenant.id,
        owner_id=user.id,
        description="Demo project for testing Thandev scanner"
    )
    
    db.add(demo_project)
    db.commit()
    print("  ✓ Created demo project")
    return demo_project


def create_demo_scan(db: Session, project: Project) -> ScanJob:
    """Create a demo scan with deterministic results"""
    # Check if demo scan already exists
    demo_scan = db.query(ScanJob).filter(ScanJob.id == "demo-scan").first()
    if demo_scan:
        print("  ✓ Demo scan already exists")
        return demo_scan
    
    now = datetime.now(timezone.utc)
    demo_scan = ScanJob(
        id="demo-scan",
        project_id=project.id,
        scan_level=ScanLevel.PRO,
        status=ScanStatus.COMPLETED,
        created_at=now,
        started_at=now,
        completed_at=now,
        brain_session_id="demo-brain-session",
        summary={
            "risk_score": 65.5,
            "executive_summary": "Demo scan completed successfully. Found 3 security findings.",
            "top_risks": [
                {
                    "title": "Cross-Site Scripting (XSS) detected",
                    "severity": "medium",
                    "count": 1
                },
                {
                    "title": "HTTP surface exposed",
                    "severity": "info",
                    "count": 1
                },
                {
                    "title": "Open port detected",
                    "severity": "info",
                    "count": 1
                }
            ]
        }
    )
    
    db.add(demo_scan)
    db.commit()
    print("  ✓ Created demo scan")
    return demo_scan


def create_demo_findings(db: Session, scan: ScanJob):
    """Create demo findings for the scan"""
    # Check if findings already exist
    existing = db.query(Finding).filter(Finding.scan_job_id == scan.id).count()
    if existing > 0:
        print(f"  ✓ Demo findings already exist ({existing} findings)")
        return
    
    now = datetime.now(timezone.utc)
    
    # Demo XSS finding (from dalfox)
    xss_finding = Finding(
        id="demo-finding-xss",
        scan_job_id=scan.id,
        project_id=scan.project_id,
        tool_name="dalfox",
        title="Cross-Site Scripting (XSS) detected",
        description="Dalfox identified a potential Cross-Site Scripting (XSS) issue in parameter 'test'.",
        severity=Severity.MEDIUM,
        vuln_type="xss",
        url="http://testphp.vulnweb.com/search.php",
        parameter="test",
        http_method="GET",
        raw_data='{"type":"V","param":"test","payload":"<script>alert(1)</script>","data":"http://testphp.vulnweb.com/search.php?test=value"}',
        created_at=now
    )
    
    # Demo HTTP surface finding (from httpx)
    http_finding = Finding(
        id="demo-finding-http",
        scan_job_id=scan.id,
        project_id=scan.project_id,
        tool_name="httpx",
        title="HTTP surface: http://testphp.vulnweb.com/login.php",
        description="Page Title: login page\nTechnologies: DreamWeaver, Nginx:1.19.0, PHP:5.6.40, Ubuntu",
        severity=Severity.INFO,
        url="http://testphp.vulnweb.com/login.php",
        http_method="GET",
        raw_data='{"url":"http://testphp.vulnweb.com/login.php","title":"login page","tech":["DreamWeaver","Nginx:1.19.0","PHP:5.6.40","Ubuntu"]}',
        created_at=now
    )
    
    # Demo port finding (from nmap)
    port_finding = Finding(
        id="demo-finding-port",
        scan_job_id=scan.id,
        project_id=scan.project_id,
        tool_name="nmap",
        title="Open port 80/tcp (http) on testphp.vulnweb.com",
        description="Open HTTP port detected",
        severity=Severity.INFO,
        url="http://testphp.vulnweb.com:80",
        raw_data='{"host":"testphp.vulnweb.com","ip":"44.228.249.3","port":"80","protocol":"tcp","service":"http"}',
        created_at=now
    )
    
    db.add(xss_finding)
    db.add(http_finding)
    db.add(port_finding)
    db.commit()
    print("  ✓ Created 3 demo findings")


def create_demo_tool_results(db: Session, scan: ScanJob):
    """Create demo tool results for the scan"""
    existing = db.query(ToolResult).filter(ToolResult.scan_job_id == scan.id).count()
    if existing > 0:
        print(f"  ✓ Demo tool results already exist ({existing} results)")
        return
    
    now = datetime.now(timezone.utc)
    
    tools = ["nmap", "httpx", "dalfox"]
    for tool_name in tools:
        tool_result = ToolResult(
            id=f"demo-tool-result-{tool_name}",
            scan_job_id=scan.id,
            tool_name=tool_name,
            status=ToolExecutionStatus.COMPLETED,
            exit_code=0,
            execution_time=30.5,
            created_at=now,
            started_at=now,
            completed_at=now
        )
        db.add(tool_result)
    
    db.commit()
    print("  ✓ Created demo tool results")


def reset_demo_data(db: Session):
    """Delete all demo data"""
    print("Resetting demo data...")
    
    # Delete in correct order (respecting foreign keys)
    db.query(Finding).filter(Finding.scan_job_id == "demo-scan").delete()
    db.query(ToolResult).filter(ToolResult.scan_job_id == "demo-scan").delete()
    db.query(ScanJob).filter(ScanJob.id == "demo-scan").delete()
    db.query(Project).filter(Project.id == "demo-project").delete()
    db.query(User).filter(User.id == "demo-user").delete()
    db.query(Tenant).filter(Tenant.id == "demo-tenant").delete()
    
    db.commit()
    print("  ✓ Deleted all demo data")


def main():
    parser = argparse.ArgumentParser(description="Seed demo/test data for Thandev")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo data before creating new data"
    )
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.reset:
            reset_demo_data(db)
        
        print("Creating demo data...")
        
        tenant, user = create_demo_tenant_and_user(db)
        project = create_demo_project(db, tenant, user)
        scan = create_demo_scan(db, project)
        create_demo_findings(db, scan)
        create_demo_tool_results(db, scan)
        
        print("\n✅ Demo data created successfully!")
        print(f"\nDemo scan ID: {scan.id}")
        print(f"Demo project ID: {project.id}")
        print(f"Demo tenant ID: {tenant.id}")
        print(f"\nYou can now view the demo scan in the UI.")
        
    except Exception as e:
        print(f"\n❌ Error creating demo data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

