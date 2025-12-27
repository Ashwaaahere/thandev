"""
Unit tests for dalfox output normalization and ingestion
"""
import pytest
import json
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from app.services.scan_orchestrator import _normalize_dalfox_output
from app.services.findings_ingestor import parse_dalfox_output, ingest_dalfox_findings


class TestDalfoxOutputNormalization:
    """Test dalfox output normalization at write time"""
    
    def test_normalize_empty_string(self):
        """Test normalizing empty string to []"""
        result = _normalize_dalfox_output("")
        assert result == "[]"
        # Should be valid JSON
        assert json.loads(result) == []
    
    def test_normalize_empty_dict(self):
        """Test normalizing {} to []"""
        result = _normalize_dalfox_output("{}")
        assert result == "[]"
        assert json.loads(result) == []
    
    def test_normalize_empty_dict_in_array(self):
        """Test normalizing [{}] to []"""
        result = _normalize_dalfox_output("[{}]")
        assert result == "[]"
        assert json.loads(result) == []
    
    def test_normalize_multiple_empty_dicts(self):
        """Test normalizing [{}] to []"""
        result = _normalize_dalfox_output("[{}, {}]")
        assert result == "[]"
        assert json.loads(result) == []
    
    def test_normalize_preserves_valid_findings(self):
        """Test that valid findings are preserved"""
        valid_output = json.dumps([
            {
                "type": "V",
                "param": "test",
                "payload": "<script>alert(1)</script>",
                "data": "http://example.com?test=value"
            }
        ])
        result = _normalize_dalfox_output(valid_output)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["param"] == "test"
    
    def test_normalize_filters_empty_from_mixed(self):
        """Test that empty dicts are filtered from mixed array"""
        mixed_output = json.dumps([
            {"type": "V", "param": "test"},
            {},
            {"type": "V", "param": "test2"},
            {}
        ])
        result = _normalize_dalfox_output(mixed_output)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert all("param" in item for item in parsed)
    
    def test_normalize_invalid_json_returns_as_is(self):
        """Test that invalid JSON is returned as-is"""
        invalid = "not json at all"
        result = _normalize_dalfox_output(invalid)
        assert result == invalid


class TestDalfoxParsing:
    """Test dalfox output parsing"""
    
    def test_parse_empty_file(self, tmp_path):
        """Test parsing empty file returns empty list"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text("")
        
        results = parse_dalfox_output(output_file)
        assert results == []
    
    def test_parse_empty_array(self, tmp_path):
        """Test parsing [] returns empty list"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text("[]")
        
        results = parse_dalfox_output(output_file)
        assert results == []
    
    def test_parse_placeholder_array(self, tmp_path):
        """Test parsing [{}] returns empty list (filtered)"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text("[{}]")
        
        results = parse_dalfox_output(output_file)
        assert results == []
    
    def test_parse_valid_finding(self, tmp_path):
        """Test parsing valid finding"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text(json.dumps([
            {
                "type": "V",
                "param": "test",
                "payload": "<script>alert(1)</script>",
                "data": "http://example.com?test=value"
            }
        ]))
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 1
        assert results[0]["param"] == "test"
    
    def test_parse_filters_empty_dicts(self, tmp_path):
        """Test that empty dicts are filtered during parsing"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text(json.dumps([
            {"type": "V", "param": "test"},
            {},
            {"type": "V", "param": "test2"}
        ]))
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 2
        assert all("param" in r for r in results)
    
    def test_parse_ndjson_format(self, tmp_path):
        """Test parsing NDJSON format (one JSON object per line)"""
        output_file = tmp_path / "dalfox_output.json"
        # NDJSON: one JSON object per line
        output_file.write_text(
            '{"type": "V", "param": "test1", "data": "http://example.com?test1=value"}\n'
            '{"type": "V", "param": "test2", "data": "http://example.com?test2=value"}'
        )
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 2
        assert results[0]["param"] == "test1"
        assert results[1]["param"] == "test2"
    
    def test_parse_ndjson_with_empty_lines(self, tmp_path):
        """Test parsing NDJSON with empty lines (should skip them)"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text(
            '{"type": "V", "param": "test1", "data": "http://example.com?test1=value"}\n'
            '\n'  # Empty line
            '{"type": "V", "param": "test2", "data": "http://example.com?test2=value"}'
        )
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 2
    
    def test_parse_json_array_format(self, tmp_path):
        """Test parsing JSON array format (starts with [)"""
        output_file = tmp_path / "dalfox_output.json"
        output_file.write_text(json.dumps([
            {"type": "V", "param": "test1", "data": "http://example.com?test1=value"},
            {"type": "V", "param": "test2", "data": "http://example.com?test2=value"}
        ]))
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 2
        assert results[0]["param"] == "test1"
        assert results[1]["param"] == "test2"
    
    def test_parse_prefers_json_array_over_ndjson(self, tmp_path):
        """Test that JSON array format is preferred when file starts with ["""
        output_file = tmp_path / "dalfox_output.json"
        # This looks like it could be NDJSON but starts with [ so should be parsed as array
        output_file.write_text('[\n{"type": "V", "param": "test1"}\n]')
        
        results = parse_dalfox_output(output_file)
        assert len(results) == 1
        assert results[0]["param"] == "test1"


class TestDalfoxIngestion:
    """Test dalfox findings ingestion validation"""
    
    def test_ingest_skips_empty_dict(self, db_session, scan_job):
        """Test that empty dicts are skipped during ingestion"""
        dalfox_results = [{}]
        
        findings = ingest_dalfox_findings(db_session, scan_job.id, dalfox_results)
        
        assert len(findings) == 0
    
    def test_ingest_skips_dict_without_meaningful_fields(self, db_session, scan_job):
        """Test that dicts without meaningful fields are skipped"""
        dalfox_results = [{"some_random_field": "value"}]
        
        findings = ingest_dalfox_findings(db_session, scan_job.id, dalfox_results)
        
        assert len(findings) == 0
    
    def test_ingest_skips_dict_without_url_or_param(self, db_session, scan_job):
        """Test that dicts without URL or param are skipped"""
        dalfox_results = [{"type": "V"}]  # Has type but no URL/param
        
        findings = ingest_dalfox_findings(db_session, scan_job.id, dalfox_results)
        
        assert len(findings) == 0
    
    def test_ingest_creates_finding_with_valid_data(self, db_session, scan_job):
        """Test that valid finding data creates a finding"""
        dalfox_results = [{
            "type": "V",
            "param": "test",
            "payload": "<script>alert(1)</script>",
            "data": "http://example.com?test=value"
        }]
        
        findings = ingest_dalfox_findings(db_session, scan_job.id, dalfox_results)
        
        assert len(findings) == 1
        assert findings[0].parameter == "test"
        assert findings[0].vuln_type == "xss"
        assert findings[0].tool_name == "dalfox"
    
    def test_ingest_handles_data_field(self, db_session, scan_job):
        """Test that 'data' field is recognized as URL source"""
        dalfox_results = [{
            "type": "V",
            "param": "test",
            "data": "http://example.com?test=value"  # data field instead of url
        }]
        
        findings = ingest_dalfox_findings(db_session, scan_job.id, dalfox_results)
        
        assert len(findings) == 1
        assert findings[0].url is not None


# Pytest fixtures for database tests
@pytest.fixture
def scan_job(db_session):
    """Create a test scan job with unique IDs"""
    from app.models.scan import ScanJob, ScanLevel, ScanStatus
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.models.user import User
    
    # Generate unique IDs for each test run to avoid UNIQUE constraint violations
    unique_id = str(uuid.uuid4())
    tenant_id = f"test-tenant-{unique_id}"
    user_id = f"test-user-{unique_id}"
    project_id = f"test-project-{unique_id}"
    scan_id = f"test-scan-{unique_id}"
    
    # Create minimal test data
    tenant = Tenant(id=tenant_id, name=f"Test Tenant {unique_id}")
    user = User(
        id=user_id,
        email=f"test-{unique_id}@example.com",
        username=f"testuser-{unique_id}",
        hashed_password="hashed",
        tenant_id=tenant.id
    )
    project = Project(
        id=project_id,
        name=f"Test Project {unique_id}",
        target_url="http://example.com",
        tenant_id=tenant.id,
        owner_id=user.id
    )
    scan_job = ScanJob(
        id=scan_id,
        project_id=project.id,
        scan_level=ScanLevel.BASIC,
        status=ScanStatus.RUNNING
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.add(project)
    db_session.add(scan_job)
    db_session.commit()
    
    return scan_job

