#!/usr/bin/env python3
"""
Enhanced seed script to create comprehensive demo/test data for Thandev.

Creates:
- Demo organization/tenant
- Demo project
- Demo scan with:
  - Tool runs: dalfox (success w/ 1 finding), nuclei (success w/ 0 findings), nmap (failed)
  - Corresponding findings with realistic fields
  - ToolResult records with all new fields populated

Usage:
    python scripts/seed_tester_demo.py
    python scripts/seed_tester_demo.py --reset  # Delete existing demo data first
"""
import sys
import argparse
from pathlib import Path
import json

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
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid


def create_demo_tenant_and_user(db: Session, user_email: Optional[str] = None, user_id: Optional[str] = None) -> tuple[Tenant, User]:
    """
    Create or find demo tenant and user.
    
    If user_email is provided, finds/creates user with that email.
    Otherwise, uses the first user in the database, or creates demo-user.
    """
    # If user_email provided, find that user (don't create new one)
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant:
                print(f"  ✓ Using existing user: {user.email} (user_id: {user.id}, tenant: {tenant.id})")
                return tenant, user
            else:
                # User exists but tenant doesn't - create tenant
                tenant_id = user.tenant_id or user.id
                tenant = Tenant(
                    id=tenant_id,
                    name=f"Tenant for {user.email}"
                )
                db.add(tenant)
                db.commit()
                print(f"  ✓ Created tenant for existing user: {user.email}")
                return tenant, user
        else:
            print(f"  ⚠ User with email '{user_email}' not found in database.")
            print(f"  ⚠ Please ensure you're logged in first, or the user exists.")
            print(f"  ⚠ Falling back to first user in database...")
            # Fall through to find first user
    
    # Try to find first user in database
    user = db.query(User).first()
    if user:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant:
            print(f"  ✓ Using existing user: {user.email} (tenant: {tenant.id})")
            return tenant, user
        else:
            # User exists but tenant doesn't - create tenant
            tenant = Tenant(
                id=user.tenant_id or user.id,
                name=f"Tenant for {user.email}"
            )
            db.add(tenant)
            db.commit()
            print(f"  ✓ Created tenant for existing user: {user.email}")
            return tenant, user
    
    # No users found - create demo user
    print("  ⚠ No users found in database. Creating demo user.")
    print("  ⚠ Note: You may need to use --user-email to specify your actual user email.")
    demo_user_id = "demo-user"
    demo_tenant = Tenant(
        id="demo-tenant",
        name="Demo Organization"
    )
    demo_user = User(
        id=demo_user_id,
        email="demo@thandev.test",
        username="demo-user",
        full_name="Demo User",
        hashed_password="demo-password-hash",  # Dummy password for demo
        tenant_id="demo-tenant"
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
    started_at = now - timedelta(minutes=5)
    completed_at = now - timedelta(minutes=1)
    
    demo_scan = ScanJob(
        id="demo-scan",
        project_id=project.id,
        scan_level=ScanLevel.PRO,
        status=ScanStatus.COMPLETED,
        created_at=now - timedelta(minutes=10),
        started_at=started_at,
        completed_at=completed_at,
        brain_session_id="demo-brain-session",
        summary={
            "risk_score": 65.5,
            "executive_summary": "Demo scan completed successfully. Found 1 security finding.",
            "findings_count": 1,
            "top_risks": [
                {
                    "title": "Cross-Site Scripting (XSS) detected",
                    "severity": "medium",
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
    
    # Get dalfox tool result ID to link finding
    dalfox_tool_result = db.query(ToolResult).filter(
        ToolResult.scan_job_id == scan.id,
        ToolResult.tool_name == "dalfox"  # Canonical lowercase name
    ).first()
    
    if not dalfox_tool_result:
        print("  ⚠ Warning: Dalfox tool result not found, creating finding without tool_result_id")
    
    now = datetime.now(timezone.utc)
    
    # Demo XSS finding (from dalfox) - realistic finding
    # Use canonical tool_name (lowercase "dalfox")
    xss_finding = Finding(
        id="demo-finding-xss",
        scan_job_id=scan.id,
        project_id=scan.project_id,
        tool_name="dalfox",  # Canonical lowercase name
        tool="dalfox",  # Also set tool field for backward compatibility
        tool_result_id=dalfox_tool_result.id if dalfox_tool_result else None,  # Link to tool run (v2)
        title="Cross-Site Scripting (XSS) detected",
        description="Dalfox identified a potential Cross-Site Scripting (XSS) issue in parameter 'test'. The application reflects user input without proper sanitization, allowing malicious scripts to be executed in the victim's browser.",
        severity=Severity.MEDIUM,
        vuln_type="xss",
        url="http://testphp.vulnweb.com/search.php",
        parameter="test",
        http_method="GET",
        raw_data=json.dumps({
            "type": "V",
            "param": "test",
            "payload": "<script>alert(1)</script>",
            "data": "http://testphp.vulnweb.com/search.php?test=<script>alert(1)</script>"
        }),
        evidence="<script>alert(1)</script>",
        created_at=now
    )
    
    db.add(xss_finding)
    db.commit()
    print("  ✓ Created 1 demo finding (Dalfox XSS)")


def create_demo_tool_results(db: Session, scan: ScanJob):
    """Create demo tool results with all new fields populated"""
    existing = db.query(ToolResult).filter(ToolResult.scan_job_id == scan.id).count()
    if existing > 0:
        print(f"  ✓ Demo tool results already exist ({existing} results)")
        return
    
    now = datetime.now(timezone.utc)
    job_dir = Path(backend_dir) / "data" / "jobs" / scan.id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Dalfox: success with 1 finding
    dalfox_started = scan.started_at + timedelta(seconds=10)
    dalfox_completed = dalfox_started + timedelta(seconds=30)
    dalfox_output_file = job_dir / "dalfox_output.json"
    
    # Create realistic dalfox output file
    dalfox_output = json.dumps([{
        "type": "V",
        "param": "test",
        "payload": "<script>alert(1)</script>",
        "data": "http://testphp.vulnweb.com/search.php?test=<script>alert(1)</script>",
        "url": "http://testphp.vulnweb.com/search.php"
    }])
    dalfox_output_file.write_text(dalfox_output)
    
    dalfox_result = ToolResult(
        id="demo-tool-result-dalfox",
        scan_job_id=scan.id,
        tool_name="dalfox",
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        execution_time=30.5,
        duration_ms=30500,
        output_path=str(dalfox_output_file),
        stdout_preview=dalfox_output[:1000],
        stderr_preview="",
        parsed_findings_count=1,
        created_findings_count=1,
        command="dalfox url http://testphp.vulnweb.com/search.php --format json --silence",
        created_at=dalfox_started,
        started_at=dalfox_started,
        completed_at=dalfox_completed,
        meta={
            "tool_id": "dalfox",
            "timeout_seconds": 300,
            "version": "v2.9.0"
        }
    )
    
    # 2. Nuclei: success with 0 findings
    nuclei_started = scan.started_at + timedelta(seconds=45)
    nuclei_completed = nuclei_started + timedelta(seconds=60)
    nuclei_output_file = job_dir / "nuclei_output.json"
    nuclei_output_file.write_text("[]")  # Empty results
    
    nuclei_result = ToolResult(
        id="demo-tool-result-nuclei",
        scan_job_id=scan.id,
        tool_name="nuclei",
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        execution_time=60.0,
        duration_ms=60000,
        output_path=str(nuclei_output_file),
        stdout_preview="[]",
        stderr_preview="",
        parsed_findings_count=0,
        created_findings_count=0,
        command="nuclei -u http://testphp.vulnweb.com -json",
        created_at=nuclei_started,
        started_at=nuclei_started,
        completed_at=nuclei_completed,
        meta={
            "tool_id": "nuclei",
            "timeout_seconds": 600,
            "version": "v3.0.0"
        }
    )
    
    # 3. Nmap: failed (exit_code != 0)
    nmap_started = scan.started_at + timedelta(seconds=110)
    nmap_completed = nmap_started + timedelta(seconds=15)
    nmap_output_file = job_dir / "nmap_output.json"
    nmap_output_file.write_text("")  # Empty due to failure
    
    nmap_result = ToolResult(
        id="demo-tool-result-nmap",
        scan_job_id=scan.id,
        tool_name="nmap",
        status=ToolExecutionStatus.FAILED,
        exit_code=1,
        execution_time=15.0,
        duration_ms=15000,
        output_path=str(nmap_output_file),
        stdout_preview="",
        stderr_preview="ERROR: Target host unreachable or firewall blocking",
        parsed_findings_count=0,
        created_findings_count=0,
        command="nmap -p 80,443,8080 testphp.vulnweb.com -oJ",
        error_message="Target host unreachable or firewall blocking",
        error_code="target_unreachable",
        created_at=nmap_started,
        started_at=nmap_started,
        completed_at=nmap_completed,
        meta={
            "tool_id": "nmap",
            "timeout_seconds": 300,
            "version": "7.94"
        }
    )
    
    db.add(dalfox_result)
    db.add(nuclei_result)
    db.add(nmap_result)
    db.commit()
    print("  ✓ Created 3 demo tool results (dalfox success, nuclei success, nmap failed)")


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
    
    # Also delete output files
    job_dir = Path(backend_dir) / "data" / "jobs" / "demo-scan"
    if job_dir.exists():
        import shutil
        shutil.rmtree(job_dir)
    
    db.commit()
    print("  ✓ Deleted all demo data")


def main():
    parser = argparse.ArgumentParser(description="Seed comprehensive demo/test data for Thandev")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo data before creating new data"
    )
    parser.add_argument(
        "--user-email",
        type=str,
        help="Email of user to create demo data for (default: use first user in database)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="User ID to create demo data for (takes precedence over --user-email). "
             "Use this if NextAuth session uses a different ID than database email lookup."
    )
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        if args.reset:
            reset_demo_data(db)
        
        print("Creating comprehensive demo data...")
        
        tenant, user = create_demo_tenant_and_user(db, user_email=args.user_email, user_id=args.user_id)
        project = create_demo_project(db, tenant, user)
        scan = create_demo_scan(db, project)
        # Create tool results first, then findings (findings need tool_result_id)
        create_demo_tool_results(db, scan)
        create_demo_findings(db, scan)
        
        print("\n✅ Demo data created successfully!")
        print(f"\nDemo scan ID: {scan.id}")
        print(f"Demo project ID: {project.id}")
        print(f"Demo tenant ID: {tenant.id}")
        print(f"\nTool runs created:")
        print(f"  - Dalfox: Success • 1 finding")
        print(f"  - Nuclei: Success • 0 findings")
        print(f"  - Nmap: Failed")
        print(f"\nYou can now view the demo scan in the UI at:")
        print(f"  /projects/{project.id}/scans/{scan.id}")
        
    except Exception as e:
        print(f"\n❌ Error creating demo data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

