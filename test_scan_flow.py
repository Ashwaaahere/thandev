#!/usr/bin/env python3
"""
Test script to verify scan execution and findings ingestion
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.scan import ScanJob
from app.models.finding import Finding, ToolResult
from app.models.project import Project
import json

def test_scan_results(scan_id: str):
    """Test if a scan has findings and tool results"""
    db: Session = SessionLocal()
    try:
        # Get scan
        scan = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
        if not scan:
            print(f"❌ Scan {scan_id} not found")
            return
        
        print(f"✅ Scan found: {scan_id}")
        print(f"   Status: {scan.status}")
        print(f"   Level: {scan.scan_level}")
        print(f"   Created: {scan.created_at}")
        
        # Check tool results
        tool_results = db.query(ToolResult).filter(ToolResult.scan_job_id == scan_id).all()
        print(f"\n📊 Tool Results: {len(tool_results)}")
        for tr in tool_results:
            output_size = len(tr.output) if tr.output else 0
            print(f"   - {tr.tool_name}: exit_code={tr.exit_code}, output_size={output_size} bytes, timed_out={tr.timed_out}")
            if tr.error_message:
                print(f"     Error: {tr.error_message[:100]}")
        
        # Check findings
        findings = db.query(Finding).filter(Finding.scan_job_id == scan_id).all()
        print(f"\n🔍 Findings: {len(findings)}")
        for f in findings[:10]:  # Show first 10
            print(f"   - {f.tool_name}: {f.title} ({f.severity.value})")
        if len(findings) > 10:
            print(f"   ... and {len(findings) - 10} more")
        
        # Check output files
        job_dir = backend_path / "data" / "jobs" / scan_id
        if job_dir.exists():
            output_files = list(job_dir.glob("*_output.json"))
            print(f"\n📁 Output Files: {len(output_files)}")
            for f in output_files:
                size = f.stat().st_size
                print(f"   - {f.name}: {size} bytes")
                if size > 0 and size < 1000:
                    # Show preview for small files
                    try:
                        content = f.read_text()[:200]
                        print(f"     Preview: {content}")
                    except:
                        pass
        else:
            print(f"\n❌ Job directory not found: {job_dir}")
        
        # Check summary
        if scan.summary:
            try:
                if isinstance(scan.summary, str):
                    summary = json.loads(scan.summary)
                else:
                    summary = scan.summary
                print(f"\n📋 Summary:")
                print(f"   Risk Score: {summary.get('risk_score', 'N/A')}")
                print(f"   Findings Count: {summary.get('findings_count', 'N/A')}")
            except:
                print(f"\n⚠️  Summary exists but couldn't parse")
        
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_scan_flow.py <scan_id>")
        print("\nTo find a scan ID, check the database or recent scans")
        sys.exit(1)
    
    scan_id = sys.argv[1]
    test_scan_results(scan_id)

