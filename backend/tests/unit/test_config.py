"""
Unit tests for configuration
"""
import pytest
from app.core.config import settings


def test_settings_loaded():
    """Test that settings are loaded"""
    assert settings.PROJECT_NAME is not None
    assert settings.VERSION is not None


def test_database_url_default():
    """Test database URL defaults"""
    # Should have a default value
    assert settings.DATABASE_URL is not None


def test_cors_origins_list():
    """Test CORS origins list property"""
    origins = settings.cors_origins_list
    assert isinstance(origins, list)
    assert len(origins) > 0



