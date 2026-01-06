"""
Unit tests for tool run recorder service.
"""
import pytest
from datetime import datetime, timezone

from app.services.tool_run_recorder import start_tool_run, finish_tool_run, update_tool_run_counts
from app.models.finding import Finding, ToolResult, ToolExecutionStatus, Severity
from app.models.scan import ScanJob, ScanStatus, ScanLevel
import uuid


@pytest.fixture
def demo_scan(db_session):
    """Create a demo scan for testing"""
    scan_id = f"test-scan-{uuid.uuid4()}"
    scan = ScanJob(
        id=scan_id,
        project_id=f"test-project-{uuid.uuid4()}",
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(scan)
    db_session.commit()
    return scan


def test_start_tool_run(db_session, demo_scan):
    """Test starting a tool run creates a ToolResult with PENDING status"""
    tool_run_id = start_tool_run(
        db=db_session,
        scan_id=demo_scan.id,
        tool_name="dalfox",
        meta={"tool_id": "dalfox", "timeout_seconds": 300}
    )
    
    assert tool_run_id is not None
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result is not None
    assert tool_result.scan_job_id == demo_scan.id
    assert tool_result.tool_name == "dalfox"
    assert tool_result.status == ToolExecutionStatus.PENDING
    assert tool_result.started_at is not None
    assert tool_result.meta == {"tool_id": "dalfox", "timeout_seconds": 300}


def test_finish_tool_run_success(db_session, demo_scan):
    """Test finishing a tool run with success status"""
    tool_run_id = start_tool_run(db_session, demo_scan.id, "dalfox")
    
    finish_tool_run(
        db=db_session,
        tool_run_id=tool_run_id,
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="Test output",
        stderr="",
        output_path="/path/to/output.json",
        duration_ms=5000
    )
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result.status == ToolExecutionStatus.COMPLETED
    assert tool_result.exit_code == 0
    assert tool_result.stdout_preview == "Test output"
    assert tool_result.stderr_preview == ""
    assert tool_result.output_path == "/path/to/output.json"
    assert tool_result.duration_ms == 5000
    assert tool_result.completed_at is not None


def test_finish_tool_run_truncates_preview(db_session, demo_scan):
    """Test that stdout/stderr are truncated to 1000 chars"""
    tool_run_id = start_tool_run(db_session, demo_scan.id, "dalfox")
    
    long_output = "x" * 2000
    finish_tool_run(
        db=db_session,
        tool_run_id=tool_run_id,
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        stdout=long_output,
        stderr="",
        output_path="/path/to/output.json",
        duration_ms=5000
    )
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert len(tool_result.stdout_preview) == 1000
    assert tool_result.stdout_preview == "x" * 1000


def test_finish_tool_run_computes_duration_from_execution_time(db_session, demo_scan):
    """Test that duration_ms is computed from execution_time if not provided"""
    tool_run_id = start_tool_run(db_session, demo_scan.id, "dalfox")
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    tool_result.execution_time = 10.5  # 10.5 seconds
    
    finish_tool_run(
        db=db_session,
        tool_run_id=tool_run_id,
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="",
        stderr="",
        output_path="/path/to/output.json",
        duration_ms=None  # Not provided
    )
    
    db_session.refresh(tool_result)
    assert tool_result.duration_ms == 10500  # 10.5 * 1000


def test_update_tool_run_counts(db_session, demo_scan):
    """Test updating parsed and created findings counts"""
    tool_run_id = start_tool_run(db_session, demo_scan.id, "dalfox")
    
    finish_tool_run(
        db=db_session,
        tool_run_id=tool_run_id,
        status=ToolExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="",
        stderr="",
        output_path="/path/to/output.json",
        duration_ms=5000
    )
    
    # Create 3 findings linked to this tool run (so DB count matches expected value)
    for i in range(3):
        finding = Finding(
            id=str(uuid.uuid4()),
            scan_job_id=demo_scan.id,
            tool_name="dalfox",
            tool_result_id=tool_run_id,
            title=f"Test Finding {i}",
            severity=Severity.HIGH,
            description="Test description",
        )
        db_session.add(finding)
    db_session.commit()
    
    update_tool_run_counts(db_session, tool_run_id, parsed_count=5, created_count=3)
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result.parsed_findings_count == 5
    assert tool_result.created_findings_count == 3  # Should match DB count (3 findings)


def test_finish_tool_run_failed(db_session, demo_scan):
    """Test finishing a tool run with failed status"""
    tool_run_id = start_tool_run(db_session, demo_scan.id, "nmap")
    
    finish_tool_run(
        db=db_session,
        tool_run_id=tool_run_id,
        status=ToolExecutionStatus.FAILED,
        exit_code=1,
        stdout="",
        stderr="ERROR: Target unreachable",
        output_path=None,
        duration_ms=15000
    )
    
    tool_result = db_session.query(ToolResult).filter(ToolResult.id == tool_run_id).first()
    assert tool_result.status == ToolExecutionStatus.FAILED
    assert tool_result.exit_code == 1
    assert tool_result.stderr_preview == "ERROR: Target unreachable"
    assert tool_result.output_path is None

