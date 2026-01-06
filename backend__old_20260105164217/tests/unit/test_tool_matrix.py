"""
Unit tests for tool matrix functionality
"""
import pytest
from app.core.tool_matrix import get_tools_for_level, get_enabled_tool_keys, is_tool_enabled_for_level
from app.models.scan import ScanLevel


def test_get_tools_for_level_basic():
    """Test getting tools for basic scan level"""
    tools = get_tools_for_level(ScanLevel.BASIC)
    assert len(tools) > 0
    assert any(tool["key"] == "nuclei" for tool in tools)


def test_get_tools_for_level_string():
    """Test getting tools using string level"""
    tools = get_tools_for_level("pro")
    assert len(tools) > 0


def test_get_enabled_tool_keys():
    """Test getting enabled tool keys"""
    keys = get_enabled_tool_keys(ScanLevel.ADVANCED)
    assert isinstance(keys, list)
    assert "sqlmap" in keys


def test_is_tool_enabled_for_level():
    """Test checking if tool is enabled for level"""
    assert is_tool_enabled_for_level("nuclei", ScanLevel.BASIC) is True
    assert is_tool_enabled_for_level("sqlmap", ScanLevel.BASIC) is False
    assert is_tool_enabled_for_level("sqlmap", ScanLevel.ADVANCED) is True



