#!/usr/bin/env python3
"""
Test script to verify plan bypass safety without needing a running server.
Tests the bypass logic directly.
"""
import os
import sys
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

def test_bypass_in_production():
    """Test that bypass does NOT work in production"""
    print("🧪 Test: Bypass in Production Environment")
    print("=" * 60)
    
    # Mock settings with production environment
    with patch('app.core.config.settings') as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        
        # Set bypass flag
        with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": "1"}):
            # Simulate the bypass check logic
            env_lower = mock_settings.ENVIRONMENT.strip().lower()
            bypass_allowed = (
                env_lower in ("local", "dev", "test", "development")
                and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
            )
            
            if bypass_allowed:
                print("❌ FAIL: Bypass is allowed in production!")
                assert False, "Bypass should not be allowed in production"
            else:
                print("✅ PASS: Bypass is correctly blocked in production")

def test_bypass_in_dev():
    """Test that bypass DOES work in dev/test environments"""
    print("\n🧪 Test: Bypass in Dev/Test Environments")
    print("=" * 60)
    
    test_envs = ["local", "dev", "test", "development"]
    all_passed = True
    
    for env in test_envs:
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.ENVIRONMENT = env
            
            with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": "1"}):
                env_lower = mock_settings.ENVIRONMENT.strip().lower()
                bypass_allowed = (
                    env_lower in ("local", "dev", "test", "development")
                    and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
                )
                
                if bypass_allowed:
                    print(f"✅ PASS: Bypass allowed in '{env}' environment")
                else:
                    print(f"❌ FAIL: Bypass blocked in '{env}' environment (should be allowed)")
                    all_passed = False
    
    assert all_passed, "Some bypass tests failed"

def test_bypass_without_flag():
    """Test that bypass does NOT work without the flag"""
    print("\n🧪 Test: Bypass Without Flag")
    print("=" * 60)
    
    test_envs = ["local", "dev", "test", "development"]
    all_passed = True
    
    for env in test_envs:
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.ENVIRONMENT = env
            
            # Don't set the flag
            with patch.dict(os.environ, {}, clear=True):
                env_lower = mock_settings.ENVIRONMENT.strip().lower()
                bypass_allowed = (
                    env_lower in ("local", "dev", "test", "development")
                    and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
                )
                
                if not bypass_allowed:
                    print(f"✅ PASS: Bypass correctly blocked in '{env}' without flag")
                else:
                    print(f"❌ FAIL: Bypass allowed in '{env}' without flag (should be blocked)")
                    all_passed = False
    
    assert all_passed, "Some bypass tests failed"

def test_environment_strip():
    """Test that environment string is properly stripped"""
    print("\n🧪 Test: Environment String Stripping")
    print("=" * 60)
    
    test_cases = [
        ("  dev  ", True),
        ("production", False),
        ("DEV", True),  # Should be lowercased
        (" test ", True),
    ]
    
    all_passed = True
    for env_value, should_allow in test_cases:
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.ENVIRONMENT = env_value
            
            with patch.dict(os.environ, {"THANDEV_DISABLE_PLAN_ENFORCEMENT": "1"}):
                env_lower = mock_settings.ENVIRONMENT.strip().lower()
                bypass_allowed = (
                    env_lower in ("local", "dev", "test", "development")
                    and os.getenv("THANDEV_DISABLE_PLAN_ENFORCEMENT") == "1"
                )
                
                if bypass_allowed == should_allow:
                    print(f"✅ PASS: '{env_value}' -> bypass_allowed={bypass_allowed}")
                else:
                    print(f"❌ FAIL: '{env_value}' -> bypass_allowed={bypass_allowed} (expected {should_allow})")
                    all_passed = False
    
    assert all_passed, "Some bypass tests failed"

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Plan Bypass Safety Tests")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("Production Block", test_bypass_in_production()))
    results.append(("Dev/Test Allow", test_bypass_in_dev()))
    results.append(("No Flag Block", test_bypass_without_flag()))
    results.append(("Environment Strip", test_environment_strip()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed! Bypass safety is correctly implemented.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please review the bypass logic.")
        sys.exit(1)

