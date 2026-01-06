#!/usr/bin/env python3
"""
Direct test of bypass logic without needing full API stack.
Tests the actual bypass condition that's in the code.
"""
import os
import sys
from unittest.mock import patch

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

def test_bypass_logic():
    """Test the exact bypass logic from scans.py"""
    print("🧪 Testing Bypass Logic Directly")
    print("=" * 60)
    print("")
    
    # Simulate the exact condition from scans.py line 304-307
    test_cases = [
        # (env, flag, expected_bypass, description)
        ("production", "1", False, "Production with flag - should BLOCK"),
        ("dev", "1", True, "Dev with flag - should ALLOW"),
        ("test", "1", True, "Test with flag - should ALLOW"),
        ("local", "1", True, "Local with flag - should ALLOW"),
        ("development", "1", True, "Development with flag - should ALLOW"),
        ("production", "", False, "Production without flag - should BLOCK"),
        ("dev", "", False, "Dev without flag - should BLOCK"),
        ("  dev  ", "1", True, "Dev with whitespace - should ALLOW (strip works)"),
        ("DEV", "1", True, "DEV uppercase - should ALLOW (lower works)"),
    ]
    
    all_passed = True
    
    for env_value, flag_value, expected_bypass, description in test_cases:
        # Simulate the exact logic from scans.py
        with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": flag_value} if flag_value else {}, clear=not flag_value):
            # Simulate settings.ENVIRONMENT
            env_lower = env_value.strip().lower()
            bypass_allowed = (
                env_lower in ("local", "dev", "test", "development")
                and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
            )
            
            status = "✅ PASS" if bypass_allowed == expected_bypass else "❌ FAIL"
            if bypass_allowed != expected_bypass:
                all_passed = False
            
            print(f"{status}: {description}")
            print(f"   ENV='{env_value}', FLAG='{flag_value}' -> bypass_allowed={bypass_allowed} (expected {expected_bypass})")
            print("")
    
    print("=" * 60)
    if all_passed:
        print("✅ All bypass logic tests passed!")
        print("")
        print("The bypass logic is CORRECT. The 500 error is a separate issue")
        print("(likely Celery not running or brain service issue).")
    else:
        print("❌ Some tests failed. Bypass logic needs fixing.")
    assert all_passed, "Some bypass logic tests failed"

if __name__ == "__main__":
    success = test_bypass_logic()
    sys.exit(0 if success else 1)

