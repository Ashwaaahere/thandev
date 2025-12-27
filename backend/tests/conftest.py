"""
Pytest configuration and fixtures
"""
import pytest
import tempfile
import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.tenant_utils import require_tenant, get_current_user
# Ensure all models are imported so Base.metadata is populated
from app import models  # noqa: F401
from app.main import app
from app.models.tenant import Tenant, PlanTier
from app.models.user import User
import uuid


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="session")
def test_db_engine():
    """Create a test database engine using SQLite in a temp file"""
    # Use a temporary file for the test database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    test_db_url = f"sqlite:///{temp_db.name}"
    
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup: drop tables and remove temp file
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    os.unlink(temp_db.name)


@pytest.fixture(scope="function")
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    
    # Clean database before each test
    Base.metadata.drop_all(bind=test_db_engine)
    Base.metadata.create_all(bind=test_db_engine)
    # Sanity check schema
    from sqlalchemy import inspect
    inspector = inspect(test_db_engine)
    user_cols = [col["name"] for col in inspector.get_columns("users")]
    assert "is_admin" in user_cols and "is_approved" in user_cols, "Test DB missing new user columns"
    
    # Create session
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


# ============================================================================
# FastAPI Dependency Overrides
# ============================================================================

def override_get_db(db: Session = None):
    """Override get_db dependency to use test session"""
    if db is None:
        # This should not happen in tests, but provide fallback
        from app.core.database import SessionLocal
        db = SessionLocal()
    try:
        yield db
    finally:
        pass  # Don't close here, fixture handles it


def override_require_tenant(tenant_id: str = None, user_id: str = None):
    """Override require_tenant to return a dummy tenant (no DB lookup)"""
    if tenant_id is None:
        tenant_id = str(uuid.uuid4())
    return Tenant(
        id=tenant_id,
        name=f"Test Tenant {tenant_id[:8]}",
        plan=PlanTier.PRO
    )


def override_get_current_user(user_id: str = None, tenant_id: str = None):
    """Override get_current_user to return a dummy user (no DB lookup)"""
    if user_id is None:
        user_id = str(uuid.uuid4())
    if tenant_id is None:
        tenant_id = str(uuid.uuid4())
    return User(
        id=user_id,
        email=f"test-{user_id[:8]}@example.com",
        username=f"testuser-{user_id[:8]}",
        hashed_password="",
        tenant_id=tenant_id
    )


# ============================================================================
# Test Client Fixture
# ============================================================================

@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """Create a TestClient with dependency overrides"""
    # Override get_db to use test session
    def get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = get_test_db
    
    # Create test client
    test_client = TestClient(app)
    
    yield test_client
    
    # Cleanup: clear all overrides
    app.dependency_overrides.clear()


# ============================================================================
# Seed Data Fixtures
# ============================================================================

@pytest.fixture
def seed_tenant_user(db_session):
    """Create and return a tenant and user in the test database"""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    tenant = Tenant(
        id=tenant_id,
        name=f"Test Tenant {tenant_id[:8]}",
        plan=PlanTier.PRO
    )
    user = User(
        id=user_id,
        email=f"test-{user_id[:8]}@example.com",
        username=f"testuser-{user_id[:8]}",
        hashed_password="",
        tenant_id=tenant_id
    )
    
    db_session.add(tenant)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.refresh(user)
    
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "tenant": tenant,
        "user": user,
    }


# ============================================================================
# Helper Functions
# ============================================================================

def auth_headers(tenant_id: str, user_id: str) -> dict:
    """Helper to create auth headers for API requests"""
    return {
        "X-Thandev-Tenant-Id": tenant_id,
        "X-Thandev-User-Id": user_id,
    }


# ============================================================================
# Catalog Fixture for Plan Validation Tests
# ============================================================================

@pytest.fixture(scope="session")
def test_catalog_path():
    """Find and return the catalog.json path for plan validation tests"""
    # Try multiple possible locations
    backend_dir = Path(__file__).parent.parent
    repo_root = backend_dir.parent
    
    possible_paths = [
        repo_root / "services" / "thandev-brain" / "catalog" / "catalog.json",
        repo_root / "packages" / "thandev_schemas" / "catalog" / "catalog.json",
        backend_dir / "catalog" / "catalog.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # If not found, create a minimal test catalog
    import json
    temp_catalog = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    minimal_catalog = {
        "tools": {
            "nuclei": {
                "modes": {
                    "basic_web": {
                        "params": {
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "severity": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            },
            "httpx": {
                "modes": {
                    "low": {"params": {}},
                    "medium": {"params": {}},
                    "high": {"params": {}}
                }
            },
            "sslscan": {
                "modes": {
                    "standard": {"params": {}, "target_types": ["https"]}
                }
            }
        }
    }
    json.dump(minimal_catalog, temp_catalog)
    temp_catalog.close()
    return Path(temp_catalog.name)

