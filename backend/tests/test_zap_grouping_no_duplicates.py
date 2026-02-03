"""
Tests to ensure ZAP findings are grouped correctly and don't create duplicates.

This test verifies that:
1. Multiple ZAP cookie alerts with the same plugin_id and title create only ONE grouped finding
2. The grouped finding has affected_count > 1
3. No duplicate findings exist (both grouped and ungrouped versions)
"""
import pytest
from sqlalchemy.orm import Session
from app.models.finding import Finding, FindingInstance
from app.models.scan import ScanJob
from app.models.project import Project
from app.services.findings_ingestor import create_or_update_finding_with_normalizer


def test_zap_cookie_alert_grouping_no_duplicates(db_session: Session, test_project: Project):
    """Test that ZAP cookie alerts group correctly without creating duplicates."""
    # Create a test scan
    scan_job = ScanJob(
        id="test-scan-zap-grouping",
        project_id=test_project.id,
        user_id=test_project.owner_id,
        status="completed",
    )
    db_session.add(scan_job)
    db_session.commit()
    
    # Create 5 ZAP findings for "Cookie No HttpOnly Flag" with same plugin_id
    plugin_id = "10010"
    title = "Cookie No HttpOnly Flag"
    
    findings_created = []
    for i in range(5):
        finding_data = {
            "tool": "zap",
            "tool_name": "zap",
            "title": title,
            "description": f"Cookie without HttpOnly flag found on URL {i}",
            "severity": "low",
            "url": f"https://example.com/page{i}",
            "plugin_id": plugin_id,
            "zap_riskcode": 1,  # Low
            "zap_confidence": 2,  # High
            "raw_data": {
                "pluginId": plugin_id,
                "alert": title,
                "riskcode": 1,
                "confidence": 2,
            }
        }
        
        finding, instance = create_or_update_finding_with_normalizer(
            db=db_session,
            scan_job_id=scan_job.id,
            project_id=test_project.id,
            finding_data=finding_data,
        )
        findings_created.append(finding)
        db_session.commit()
    
    # Verify: Only ONE finding should exist for this plugin_id + title combination
    all_findings = db_session.query(Finding).filter(
        Finding.scan_job_id == scan_job.id,
        Finding.tool_name == "zap",
        Finding.plugin_id == plugin_id,
        Finding.title == title
    ).all()
    
    assert len(all_findings) == 1, f"Expected 1 finding, got {len(all_findings)}. Duplicates found!"
    
    # Verify the finding is grouped
    grouped_finding = all_findings[0]
    assert grouped_finding.affected_count >= 5, f"Expected affected_count >= 5, got {grouped_finding.affected_count}"
    assert grouped_finding.finding_key is not None, "Finding should have finding_key for grouping"
    
    # Verify instances exist
    instances = db_session.query(FindingInstance).filter(
        FindingInstance.finding_id == grouped_finding.id
    ).all()
    assert len(instances) >= 5, f"Expected at least 5 instances, got {len(instances)}"


def test_zap_csrf_alert_grouping_no_duplicates(db_session: Session, test_project: Project):
    """Test that ZAP CSRF alerts group by form action path without creating duplicates."""
    # Create a test scan
    scan_job = ScanJob(
        id="test-scan-zap-csrf",
        project_id=test_project.id,
        user_id=test_project.owner_id,
        status="completed",
    )
    db_session.add(scan_job)
    db_session.commit()
    
    # Create 5 ZAP findings for "Absence of Anti-CSRF Tokens" with same form action
    plugin_id = "10202"
    title = "Absence of Anti-CSRF Tokens"
    form_action = "/upload.gtl"
    
    findings_created = []
    for i in range(5):
        finding_data = {
            "tool": "zap",
            "tool_name": "zap",
            "title": title,
            "description": f"CSRF token missing on form at {form_action}",
            "severity": "medium",
            "url": f"https://example.com/form{i}?action={form_action}",
            "plugin_id": plugin_id,
            "zap_riskcode": 2,  # Medium
            "zap_confidence": 2,  # High
            "raw_data": {
                "pluginId": plugin_id,
                "alert": title,
                "riskcode": 2,
                "confidence": 2,
            }
        }
        
        finding, instance = create_or_update_finding_with_normalizer(
            db=db_session,
            scan_job_id=scan_job.id,
            project_id=test_project.id,
            finding_data=finding_data,
        )
        findings_created.append(finding)
        db_session.commit()
    
    # Verify: Only ONE finding should exist for this plugin_id + title combination
    all_findings = db_session.query(Finding).filter(
        Finding.scan_job_id == scan_job.id,
        Finding.tool_name == "zap",
        Finding.plugin_id == plugin_id,
        Finding.title == title
    ).all()
    
    assert len(all_findings) == 1, f"Expected 1 finding, got {len(all_findings)}. Duplicates found!"
    
    # Verify the finding is grouped
    grouped_finding = all_findings[0]
    assert grouped_finding.affected_count >= 5, f"Expected affected_count >= 5, got {grouped_finding.affected_count}"


def test_httpx_surface_artifact_grouping(db_session: Session, test_project: Project):
    """Test that HTTPX 404 results are grouped into ScanArtifacts, not Findings."""
    from app.models.scan_artifact import ScanArtifact
    from app.services.findings_ingestor import ingest_httpx_findings
    
    # Create a test scan
    scan_job = ScanJob(
        id="test-scan-httpx",
        project_id=test_project.id,
        user_id=test_project.owner_id,
        status="completed",
    )
    db_session.add(scan_job)
    db_session.commit()
    
    # Create 30 HTTPX results with 404 status and same title
    httpx_results = []
    for i in range(30):
        httpx_results.append({
            "title": f"HTTP surface: https://uw.r.appspot.com/page{i} [404] Error 404 (Not Found)!!1",
            "description": f"HTTP Status: 404\nPage Title: Error 404 (Not Found)!!1",
            "severity": "info",
            "url": f"https://uw.r.appspot.com/page{i}",
            "raw_data": {
                "url": f"https://uw.r.appspot.com/page{i}",
                "status_code": 404,
                "title": "Error 404 (Not Found)!!1",
            }
        })
    
    # Ingest HTTPX findings
    artifact_ids = ingest_httpx_findings(
        db=db_session,
        scan_job_id=scan_job.id,
        httpx_results=httpx_results,
    )
    
    # Verify: HTTPX data should be stored as ScanArtifact, not Finding
    artifacts = db_session.query(ScanArtifact).filter(
        ScanArtifact.scan_id == scan_job.id,
        ScanArtifact.type == "httpx_surface"
    ).all()
    
    assert len(artifacts) > 0, "Expected at least one HTTPX surface artifact"
    
    # Verify: No HTTPX findings should exist in Findings table
    httpx_findings = db_session.query(Finding).filter(
        Finding.scan_job_id == scan_job.id,
        Finding.tool_name == "httpx"
    ).all()
    
    assert len(httpx_findings) == 0, f"Expected 0 HTTPX findings, got {len(httpx_findings)}. HTTPX should be artifacts, not findings!"
    
    # Verify: Artifact payload contains grouped 404 data
    artifact = artifacts[0]
    payload = artifact.payload if isinstance(artifact.payload, dict) else {}
    
    # Check that 404s are grouped
    out_of_scope_404s = payload.get("out_of_scope", {}).get("404_groups", [])
    assert len(out_of_scope_404s) > 0, "Expected grouped 404 data in artifact payload"
    
    # Verify grouping: 30 404s should be grouped (not 30 separate entries)
    total_404_count = sum(g.get("count", 0) for g in out_of_scope_404s)
    assert total_404_count >= 30, f"Expected at least 30 grouped 404s, got {total_404_count}"
    
    # Verify: Risk score should not be affected by HTTPX artifacts
    # (This is tested implicitly - if HTTPX were in Findings, they would affect risk score)

