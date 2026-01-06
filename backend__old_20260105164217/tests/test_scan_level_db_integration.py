"""
Integration test for ScanLevel enum database persistence

This test verifies that ScanLevel enum is correctly stored as lowercase values
in the database, not as enum names (uppercase).

CRITICAL: This test ensures the TypeDecorator.process_bind_param() correctly
extracts enum.value before binding to database.
"""
import pytest
from sqlalchemy import text
from app.models.scan import ScanJob, ScanLevel, ScanStatus
from app.core.database import SessionLocal, engine
from app.core.scan_utils import normalize_scan_level


@pytest.fixture
def db_session():
    """Create a database session for testing"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.mark.skipif(
    not engine.url.drivername.startswith('postgresql'),
    reason="PostgreSQL-specific test - requires PostgreSQL database"
)
def test_scan_level_stored_as_lowercase_value(db_session):
    """
    Test that ScanLevel.BASIC is stored as 'basic' (lowercase value) in database,
    not as 'BASIC' (enum name).
    
    This test verifies the TypeDecorator.process_bind_param() fix works correctly.
    """
    # Create a scan job with ScanLevel.BASIC enum instance
    scan_job = ScanJob(
        project_id="test-project-id",
        scan_level=ScanLevel.BASIC,  # Enum instance
        status=ScanStatus.PENDING,
    )
    
    db_session.add(scan_job)
    db_session.commit()
    db_session.refresh(scan_job)
    
    # Verify the scan_level was stored correctly
    assert scan_job.scan_level == ScanLevel.BASIC
    assert scan_job.scan_level.value == "basic"
    
    # CRITICAL: Query database directly to verify stored value is lowercase
    result = db_session.execute(
        text("SELECT scan_level FROM scan_jobs WHERE id = :id"),
        {"id": scan_job.id}
    )
    stored_value = result.scalar()
    
    # The stored value must be 'basic' (lowercase), not 'BASIC' (uppercase)
    assert stored_value == "basic", f"Expected 'basic', got '{stored_value}'"
    assert stored_value.islower(), f"Stored value must be lowercase, got '{stored_value}'"
    
    # Clean up
    db_session.delete(scan_job)
    db_session.commit()


@pytest.mark.skipif(
    not engine.url.drivername.startswith('postgresql'),
    reason="PostgreSQL-specific test - requires PostgreSQL database"
)
def test_scan_level_normalized_input_stored_correctly(db_session):
    """
    Test that normalize_scan_level() output (ScanLevel enum) is correctly stored.
    """
    # Normalize various inputs to ScanLevel enum
    basic_enum = normalize_scan_level("BASIC")
    pro_enum = normalize_scan_level("pro")
    advanced_enum = normalize_scan_level("Advanced")
    
    # Verify they're ScanLevel enum instances
    assert isinstance(basic_enum, ScanLevel)
    assert isinstance(pro_enum, ScanLevel)
    assert isinstance(advanced_enum, ScanLevel)
    
    # Create scan jobs with normalized enums
    scan_jobs = [
        ScanJob(project_id="test-project-1", scan_level=basic_enum, status=ScanStatus.PENDING),
        ScanJob(project_id="test-project-2", scan_level=pro_enum, status=ScanStatus.PENDING),
        ScanJob(project_id="test-project-3", scan_level=advanced_enum, status=ScanStatus.PENDING),
    ]
    
    for job in scan_jobs:
        db_session.add(job)
    db_session.commit()
    
    # Verify all stored values are lowercase
    for job in scan_jobs:
        db_session.refresh(job)
        result = db_session.execute(
            text("SELECT scan_level FROM scan_jobs WHERE id = :id"),
            {"id": job.id}
        )
        stored_value = result.scalar()
        
        assert stored_value.islower(), f"Stored value must be lowercase, got '{stored_value}'"
        assert stored_value in {"basic", "pro", "advanced"}, \
            f"Stored value must be one of: basic, pro, advanced, got '{stored_value}'"
    
    # Clean up
    for job in scan_jobs:
        db_session.delete(job)
    db_session.commit()

