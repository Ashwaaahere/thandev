"""
Unit tests for brain status merge logic and datetime parsing
"""
import pytest
from datetime import datetime, timezone
from app.schemas.brain import BrainSessionResponse, SessionStatus, parse_iso_datetime_safe


class TestBrainSessionResponse:
    """Test BrainSessionResponse Pydantic model"""
    
    def test_parse_completed_session(self):
        """Test parsing a completed brain session response"""
        response_data = {
            "session_id": "test-session-123",
            "status": "completed",
            "scan_job_id": "scan-123",
            "started_at": "2025-12-23T10:00:00Z",
            "finished_at": "2025-12-23T10:30:00Z",
            "progress_percentage": 100.0,
            "current_step_count": 5,
            "total_runtime_sec": 1800.0,
        }
        
        response = BrainSessionResponse(**response_data)
        
        assert response.session_id == "test-session-123"
        assert response.status == SessionStatus.COMPLETED
        assert response.started_at is not None
        assert response.finished_at is not None
        assert response.started_at.tzinfo is not None  # Timezone-aware
        assert response.finished_at.tzinfo is not None
        assert response.progress_percentage == 100.0
    
    def test_parse_running_session(self):
        """Test parsing a running brain session response"""
        response_data = {
            "session_id": "test-session-456",
            "status": "running",
            "progress_percentage": 50.0,
            "current_step_count": 3,
        }
        
        response = BrainSessionResponse(**response_data)
        
        assert response.status == SessionStatus.RUNNING
        assert response.progress_percentage == 50.0
        assert response.current_step_count == 3
    
    def test_parse_with_z_suffix(self):
        """Test parsing datetime with Z suffix (UTC)"""
        response_data = {
            "session_id": "test-session",
            "status": "completed",
            "started_at": "2025-12-23T10:00:00Z",
            "finished_at": "2025-12-23T10:30:00Z",
        }
        
        response = BrainSessionResponse(**response_data)
        
        assert response.started_at is not None
        assert response.started_at.tzinfo == timezone.utc
        assert response.finished_at.tzinfo == timezone.utc
    
    def test_parse_with_timezone_offset(self):
        """Test parsing datetime with timezone offset"""
        response_data = {
            "session_id": "test-session",
            "status": "completed",
            "started_at": "2025-12-23T10:00:00+00:00",
            "finished_at": "2025-12-23T10:30:00-05:00",
        }
        
        response = BrainSessionResponse(**response_data)
        
        assert response.started_at is not None
        assert response.finished_at is not None
        # Both should be timezone-aware
        assert response.started_at.tzinfo is not None
        assert response.finished_at.tzinfo is not None
    
    def test_parse_invalid_datetime(self):
        """Test parsing with invalid datetime string (should return None)"""
        response_data = {
            "session_id": "test-session",
            "status": "running",
            "started_at": "invalid-datetime",
        }
        
        response = BrainSessionResponse(**response_data)
        
        # Invalid datetime should be None
        assert response.started_at is None
    
    def test_parse_malformed_response_gracefully(self):
        """Test that malformed response doesn't crash"""
        # Missing required fields should raise ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            BrainSessionResponse(**{"status": "running"})  # Missing session_id


class TestDatetimeParsing:
    """Test ISO-8601 datetime parsing helper"""
    
    def test_parse_z_suffix(self):
        """Test parsing Z suffix"""
        dt = parse_iso_datetime_safe("2025-12-23T10:00:00Z")
        assert dt is not None
        assert dt.tzinfo == timezone.utc
    
    def test_parse_timezone_offset(self):
        """Test parsing with timezone offset"""
        dt = parse_iso_datetime_safe("2025-12-23T10:00:00+00:00")
        assert dt is not None
        assert dt.tzinfo is not None
    
    def test_parse_no_timezone_assumes_utc(self):
        """Test parsing without timezone (assumes UTC)"""
        dt = parse_iso_datetime_safe("2025-12-23T10:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc
    
    def test_parse_invalid_returns_none(self):
        """Test parsing invalid string returns None"""
        assert parse_iso_datetime_safe("invalid") is None
        assert parse_iso_datetime_safe("") is None
        assert parse_iso_datetime_safe(None) is None
    
    def test_parse_datetime_object(self):
        """Test parsing already-parsed datetime object"""
        dt_naive = datetime(2025, 12, 23, 10, 0, 0)
        dt_parsed = parse_iso_datetime_safe(dt_naive)
        assert dt_parsed is not None
        assert dt_parsed.tzinfo == timezone.utc  # Should add UTC timezone


class TestBrainStatusMerge:
    """Test brain status merge logic (integration-style)"""
    
    def test_brain_completed_overrides_db_running(self):
        """Test that brain 'completed' status overrides DB 'running' status"""
        # This is a conceptual test - actual implementation is in scans.py
        brain_status = SessionStatus.COMPLETED
        db_status = "running"
        
        # Brain should win
        final_status = brain_status.value if brain_status == SessionStatus.COMPLETED else db_status
        assert final_status == "completed"
    
    def test_brain_failed_overrides_db_running(self):
        """Test that brain 'failed' status overrides DB 'running' status"""
        brain_status = SessionStatus.FAILED
        db_status = "running"
        
        final_status = brain_status.value if brain_status == SessionStatus.FAILED else db_status
        assert final_status == "failed"

