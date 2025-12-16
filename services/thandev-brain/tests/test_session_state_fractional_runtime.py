"""
Regression test for fractional runtime_sec validation issue
Tests that SessionState can load successfully with fractional total_runtime_sec values
"""
import pytest
import json
from datetime import datetime
from app.models import SessionState, SessionStatus
from app.session.state import get_session, create_session, update_session


@pytest.mark.asyncio
async def test_session_state_loads_fractional_runtime():
    """
    Test that SessionState can be loaded from Redis JSON with fractional total_runtime_sec.
    
    This is a regression test for the issue where:
    - execution_time_sec values are floats (from time.time())
    - total_runtime_sec is calculated as sum of floats
    - Redis stores fractional values (e.g., 12.34)
    - Pydantic validation must accept float, not just int
    """
    # Create a session
    session = await create_session(
        scan_job_id="test_job_123",
        target_url="http://example.com",
        scan_level="basic",
    )
    
    # Update with fractional runtime (simulating real-world scenario)
    fractional_runtime = 12.34  # This is what happens when summing execution_time_sec values
    await update_session(
        session.org_id,
        session.project_id,
        session.session_id,
        {"total_runtime_sec": fractional_runtime}
    )
    
    # Attempt to load the session - this should NOT raise ValidationError
    loaded_session = await get_session(
        session.org_id,
        session.project_id,
        session.session_id
    )
    
    # Verify session loaded successfully
    assert loaded_session is not None, "Session should load successfully with fractional runtime"
    assert loaded_session.total_runtime_sec == 12.34, "Fractional runtime should be preserved"
    assert isinstance(loaded_session.total_runtime_sec, float), "total_runtime_sec should be float"


@pytest.mark.asyncio
async def test_session_state_serialization_roundtrip():
    """
    Test that SessionState can be serialized to JSON and deserialized with fractional runtime.
    """
    # Create session state with fractional runtime
    state_dict = {
        "session_id": "test_session_123",
        "scan_job_id": "test_job_123",
        "org_id": None,
        "project_id": None,
        "target_url": "http://example.com",
        "scan_level": "basic",
        "status": "running",
        "current_step_count": 2,
        "total_runtime_sec": 45.67,  # Fractional value
        "consecutive_failures": 0,
        "no_new_findings_iterations": 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat(),
    }
    
    # Serialize to JSON (simulating Redis storage)
    json_str = json.dumps(state_dict)
    
    # Deserialize and create SessionState (simulating Redis read)
    loaded_dict = json.loads(json_str)
    loaded_dict["created_at"] = datetime.fromisoformat(loaded_dict["created_at"])
    loaded_dict["last_updated"] = datetime.fromisoformat(loaded_dict["last_updated"])
    loaded_dict["status"] = SessionStatus(loaded_dict["status"])
    
    # This should NOT raise ValidationError
    session_state = SessionState(**loaded_dict)
    
    assert session_state.total_runtime_sec == 45.67
    assert isinstance(session_state.total_runtime_sec, float)


@pytest.mark.asyncio
async def test_session_state_integer_runtime_still_works():
    """
    Test that integer runtime values still work (backward compatibility).
    """
    # Create session state with integer runtime
    state_dict = {
        "session_id": "test_session_456",
        "scan_job_id": "test_job_456",
        "org_id": None,
        "project_id": None,
        "target_url": "http://example.com",
        "scan_level": "basic",
        "status": "running",
        "current_step_count": 1,
        "total_runtime_sec": 10,  # Integer value (should be converted to float)
        "consecutive_failures": 0,
        "no_new_findings_iterations": 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat(),
    }
    
    # Serialize and deserialize
    json_str = json.dumps(state_dict)
    loaded_dict = json.loads(json_str)
    loaded_dict["created_at"] = datetime.fromisoformat(loaded_dict["created_at"])
    loaded_dict["last_updated"] = datetime.fromisoformat(loaded_dict["last_updated"])
    loaded_dict["status"] = SessionStatus(loaded_dict["status"])
    
    session_state = SessionState(**loaded_dict)
    
    # Integer should be accepted and stored as float
    assert session_state.total_runtime_sec == 10.0
    assert isinstance(session_state.total_runtime_sec, float)

