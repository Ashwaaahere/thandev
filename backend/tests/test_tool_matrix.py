"""
Unit tests for tool_matrix module

Run with: python -m pytest tests/test_tool_matrix.py
Or: python tests/test_tool_matrix.py
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.tool_matrix import (
    get_tools_for_level,
    get_enabled_tool_keys,
    is_tool_enabled_for_level,
    TOOL_MATRIX,
)
from app.models.scan import ScanLevel


def test_basic_level_tools():
    """Test that BASIC level returns only nuclei"""
    tools = get_tools_for_level(ScanLevel.BASIC)
    assert len(tools) == 1
    assert tools[0]["key"] == "nuclei"
    assert tools[0]["enabled"] is True


def test_pro_level_tools():
    """Test that PRO level returns nuclei and nmap"""
    tools = get_tools_for_level(ScanLevel.PRO)
    assert len(tools) == 2
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert all(tool["enabled"] for tool in tools)


def test_advanced_level_tools():
    """Test that ADVANCED level returns all three tools"""
    tools = get_tools_for_level(ScanLevel.ADVANCED)
    assert len(tools) == 3
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert tools[2]["key"] == "sslscan"
    assert all(tool["enabled"] for tool in tools)


def test_string_input():
    """Test that string input works for backward compatibility"""
    basic_keys = get_enabled_tool_keys("basic")
    assert basic_keys == ["nuclei"]
    
    pro_keys = get_enabled_tool_keys("pro")
    assert pro_keys == ["nuclei", "nmap"]
    
    advanced_keys = get_enabled_tool_keys("advanced")
    assert advanced_keys == ["nuclei", "nmap", "sslscan"]


def test_is_tool_enabled_for_level():
    """Test is_tool_enabled_for_level helper"""
    # Basic level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.BASIC) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.BASIC) is False
    assert is_tool_enabled_for_level("sslscan", ScanLevel.BASIC) is False
    
    # Pro level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.PRO) is False
    
    # Advanced level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.ADVANCED) is True


def test_invalid_level():
    """Test that invalid scan level raises ValueError"""
    try:
        get_tools_for_level("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_tool_matrix_structure():
    """Test that TOOL_MATRIX has all scan levels"""
    assert ScanLevel.BASIC in TOOL_MATRIX
    assert ScanLevel.PRO in TOOL_MATRIX
    assert ScanLevel.ADVANCED in TOOL_MATRIX
    
    # Verify all tools have required fields
    for level, tools in TOOL_MATRIX.items():
        assert isinstance(tools, list)
        for tool in tools:
            assert "key" in tool
            assert "enabled" in tool
            assert isinstance(tool["key"], str)
            assert isinstance(tool["enabled"], bool)


if __name__ == "__main__":
    # Simple test runner
    print("Running tool_matrix tests...")
    
    test_basic_level_tools()
    print("✅ test_basic_level_tools passed")
    
    test_pro_level_tools()
    print("✅ test_pro_level_tools passed")
    
    test_advanced_level_tools()
    print("✅ test_advanced_level_tools passed")
    
    test_string_input()
    print("✅ test_string_input passed")
    
    test_is_tool_enabled_for_level()
    print("✅ test_is_tool_enabled_for_level passed")
    
    test_invalid_level()
    print("✅ test_invalid_level passed")
    
    test_tool_matrix_structure()
    print("✅ test_tool_matrix_structure passed")
    
    print("\n✅ All tests passed!")




Unit tests for tool_matrix module

Run with: python -m pytest tests/test_tool_matrix.py
Or: python tests/test_tool_matrix.py
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.tool_matrix import (
    get_tools_for_level,
    get_enabled_tool_keys,
    is_tool_enabled_for_level,
    TOOL_MATRIX,
)
from app.models.scan import ScanLevel


def test_basic_level_tools():
    """Test that BASIC level returns only nuclei"""
    tools = get_tools_for_level(ScanLevel.BASIC)
    assert len(tools) == 1
    assert tools[0]["key"] == "nuclei"
    assert tools[0]["enabled"] is True


def test_pro_level_tools():
    """Test that PRO level returns nuclei and nmap"""
    tools = get_tools_for_level(ScanLevel.PRO)
    assert len(tools) == 2
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert all(tool["enabled"] for tool in tools)


def test_advanced_level_tools():
    """Test that ADVANCED level returns all three tools"""
    tools = get_tools_for_level(ScanLevel.ADVANCED)
    assert len(tools) == 3
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert tools[2]["key"] == "sslscan"
    assert all(tool["enabled"] for tool in tools)


def test_string_input():
    """Test that string input works for backward compatibility"""
    basic_keys = get_enabled_tool_keys("basic")
    assert basic_keys == ["nuclei"]
    
    pro_keys = get_enabled_tool_keys("pro")
    assert pro_keys == ["nuclei", "nmap"]
    
    advanced_keys = get_enabled_tool_keys("advanced")
    assert advanced_keys == ["nuclei", "nmap", "sslscan"]


def test_is_tool_enabled_for_level():
    """Test is_tool_enabled_for_level helper"""
    # Basic level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.BASIC) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.BASIC) is False
    assert is_tool_enabled_for_level("sslscan", ScanLevel.BASIC) is False
    
    # Pro level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.PRO) is False
    
    # Advanced level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.ADVANCED) is True


def test_invalid_level():
    """Test that invalid scan level raises ValueError"""
    try:
        get_tools_for_level("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_tool_matrix_structure():
    """Test that TOOL_MATRIX has all scan levels"""
    assert ScanLevel.BASIC in TOOL_MATRIX
    assert ScanLevel.PRO in TOOL_MATRIX
    assert ScanLevel.ADVANCED in TOOL_MATRIX
    
    # Verify all tools have required fields
    for level, tools in TOOL_MATRIX.items():
        assert isinstance(tools, list)
        for tool in tools:
            assert "key" in tool
            assert "enabled" in tool
            assert isinstance(tool["key"], str)
            assert isinstance(tool["enabled"], bool)


if __name__ == "__main__":
    # Simple test runner
    print("Running tool_matrix tests...")
    
    test_basic_level_tools()
    print("✅ test_basic_level_tools passed")
    
    test_pro_level_tools()
    print("✅ test_pro_level_tools passed")
    
    test_advanced_level_tools()
    print("✅ test_advanced_level_tools passed")
    
    test_string_input()
    print("✅ test_string_input passed")
    
    test_is_tool_enabled_for_level()
    print("✅ test_is_tool_enabled_for_level passed")
    
    test_invalid_level()
    print("✅ test_invalid_level passed")
    
    test_tool_matrix_structure()
    print("✅ test_tool_matrix_structure passed")
    
    print("\n✅ All tests passed!")




Unit tests for tool_matrix module

Run with: python -m pytest tests/test_tool_matrix.py
Or: python tests/test_tool_matrix.py
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.tool_matrix import (
    get_tools_for_level,
    get_enabled_tool_keys,
    is_tool_enabled_for_level,
    TOOL_MATRIX,
)
from app.models.scan import ScanLevel


def test_basic_level_tools():
    """Test that BASIC level returns only nuclei"""
    tools = get_tools_for_level(ScanLevel.BASIC)
    assert len(tools) == 1
    assert tools[0]["key"] == "nuclei"
    assert tools[0]["enabled"] is True


def test_pro_level_tools():
    """Test that PRO level returns nuclei and nmap"""
    tools = get_tools_for_level(ScanLevel.PRO)
    assert len(tools) == 2
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert all(tool["enabled"] for tool in tools)


def test_advanced_level_tools():
    """Test that ADVANCED level returns all three tools"""
    tools = get_tools_for_level(ScanLevel.ADVANCED)
    assert len(tools) == 3
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert tools[2]["key"] == "sslscan"
    assert all(tool["enabled"] for tool in tools)


def test_string_input():
    """Test that string input works for backward compatibility"""
    basic_keys = get_enabled_tool_keys("basic")
    assert basic_keys == ["nuclei"]
    
    pro_keys = get_enabled_tool_keys("pro")
    assert pro_keys == ["nuclei", "nmap"]
    
    advanced_keys = get_enabled_tool_keys("advanced")
    assert advanced_keys == ["nuclei", "nmap", "sslscan"]


def test_is_tool_enabled_for_level():
    """Test is_tool_enabled_for_level helper"""
    # Basic level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.BASIC) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.BASIC) is False
    assert is_tool_enabled_for_level("sslscan", ScanLevel.BASIC) is False
    
    # Pro level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.PRO) is False
    
    # Advanced level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.ADVANCED) is True


def test_invalid_level():
    """Test that invalid scan level raises ValueError"""
    try:
        get_tools_for_level("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_tool_matrix_structure():
    """Test that TOOL_MATRIX has all scan levels"""
    assert ScanLevel.BASIC in TOOL_MATRIX
    assert ScanLevel.PRO in TOOL_MATRIX
    assert ScanLevel.ADVANCED in TOOL_MATRIX
    
    # Verify all tools have required fields
    for level, tools in TOOL_MATRIX.items():
        assert isinstance(tools, list)
        for tool in tools:
            assert "key" in tool
            assert "enabled" in tool
            assert isinstance(tool["key"], str)
            assert isinstance(tool["enabled"], bool)


if __name__ == "__main__":
    # Simple test runner
    print("Running tool_matrix tests...")
    
    test_basic_level_tools()
    print("✅ test_basic_level_tools passed")
    
    test_pro_level_tools()
    print("✅ test_pro_level_tools passed")
    
    test_advanced_level_tools()
    print("✅ test_advanced_level_tools passed")
    
    test_string_input()
    print("✅ test_string_input passed")
    
    test_is_tool_enabled_for_level()
    print("✅ test_is_tool_enabled_for_level passed")
    
    test_invalid_level()
    print("✅ test_invalid_level passed")
    
    test_tool_matrix_structure()
    print("✅ test_tool_matrix_structure passed")
    
    print("\n✅ All tests passed!")




Unit tests for tool_matrix module

Run with: python -m pytest tests/test_tool_matrix.py
Or: python tests/test_tool_matrix.py
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.tool_matrix import (
    get_tools_for_level,
    get_enabled_tool_keys,
    is_tool_enabled_for_level,
    TOOL_MATRIX,
)
from app.models.scan import ScanLevel


def test_basic_level_tools():
    """Test that BASIC level returns only nuclei"""
    tools = get_tools_for_level(ScanLevel.BASIC)
    assert len(tools) == 1
    assert tools[0]["key"] == "nuclei"
    assert tools[0]["enabled"] is True


def test_pro_level_tools():
    """Test that PRO level returns nuclei and nmap"""
    tools = get_tools_for_level(ScanLevel.PRO)
    assert len(tools) == 2
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert all(tool["enabled"] for tool in tools)


def test_advanced_level_tools():
    """Test that ADVANCED level returns all three tools"""
    tools = get_tools_for_level(ScanLevel.ADVANCED)
    assert len(tools) == 3
    assert tools[0]["key"] == "nuclei"
    assert tools[1]["key"] == "nmap"
    assert tools[2]["key"] == "sslscan"
    assert all(tool["enabled"] for tool in tools)


def test_string_input():
    """Test that string input works for backward compatibility"""
    basic_keys = get_enabled_tool_keys("basic")
    assert basic_keys == ["nuclei"]
    
    pro_keys = get_enabled_tool_keys("pro")
    assert pro_keys == ["nuclei", "nmap"]
    
    advanced_keys = get_enabled_tool_keys("advanced")
    assert advanced_keys == ["nuclei", "nmap", "sslscan"]


def test_is_tool_enabled_for_level():
    """Test is_tool_enabled_for_level helper"""
    # Basic level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.BASIC) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.BASIC) is False
    assert is_tool_enabled_for_level("sslscan", ScanLevel.BASIC) is False
    
    # Pro level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.PRO) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.PRO) is False
    
    # Advanced level
    assert is_tool_enabled_for_level("nuclei", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("nmap", ScanLevel.ADVANCED) is True
    assert is_tool_enabled_for_level("sslscan", ScanLevel.ADVANCED) is True


def test_invalid_level():
    """Test that invalid scan level raises ValueError"""
    try:
        get_tools_for_level("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_tool_matrix_structure():
    """Test that TOOL_MATRIX has all scan levels"""
    assert ScanLevel.BASIC in TOOL_MATRIX
    assert ScanLevel.PRO in TOOL_MATRIX
    assert ScanLevel.ADVANCED in TOOL_MATRIX
    
    # Verify all tools have required fields
    for level, tools in TOOL_MATRIX.items():
        assert isinstance(tools, list)
        for tool in tools:
            assert "key" in tool
            assert "enabled" in tool
            assert isinstance(tool["key"], str)
            assert isinstance(tool["enabled"], bool)


if __name__ == "__main__":
    # Simple test runner
    print("Running tool_matrix tests...")
    
    test_basic_level_tools()
    print("✅ test_basic_level_tools passed")
    
    test_pro_level_tools()
    print("✅ test_pro_level_tools passed")
    
    test_advanced_level_tools()
    print("✅ test_advanced_level_tools passed")
    
    test_string_input()
    print("✅ test_string_input passed")
    
    test_is_tool_enabled_for_level()
    print("✅ test_is_tool_enabled_for_level passed")
    
    test_invalid_level()
    print("✅ test_invalid_level passed")
    
    test_tool_matrix_structure()
    print("✅ test_tool_matrix_structure passed")
    
    print("\n✅ All tests passed!")





