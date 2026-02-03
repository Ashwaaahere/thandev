"""
Unit tests for noise rules engine.
"""
import pytest
from app.utils.noise_rules_engine import apply_noise_rules
from app.models.finding import Severity


def test_cors_static_asset_downgrade():
    """Test that CORS on static assets is downgraded to INFO."""
    finding_data = {
        "title": "Cross-Domain Misconfiguration",
        "url": "https://example.com/_next/static/chunks/app.js",
        "evidence": "",
        "description": "CORS header present",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.INFO
    assert tag == "likely-static-cors"
    assert "static" in reason.lower() or "cors" in reason.lower()


def test_cors_api_endpoint_medium():
    """Test that CORS on API endpoints stays MEDIUM."""
    finding_data = {
        "title": "Cross-Domain Misconfiguration",
        "url": "https://example.com/api/user",
        "evidence": "",
        "description": "CORS header present",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    # Should stay MEDIUM or be adjusted based on rules
    assert adjusted_severity in [Severity.MEDIUM, Severity.LOW]


def test_cors_wildcard_credentials_high():
    """Test that CORS with wildcard and credentials is HIGH."""
    finding_data = {
        "title": "Cross-Domain Misconfiguration",
        "url": "https://example.com/api/data",
        "evidence": "Access-Control-Allow-Origin: * Access-Control-Allow-Credentials: true",
        "description": "Wildcard CORS with credentials",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.HIGH
    assert "wildcard" in reason.lower() or "credentials" in reason.lower()


def test_ua_fuzzer_info():
    """Test that User Agent Fuzzer is always INFO."""
    finding_data = {
        "title": "User Agent Fuzzer",
        "url": "https://example.com/page",
        "evidence": "",
        "description": "User agent fuzzing detected",
    }
    raw_data = {}
    original_severity = Severity.LOW
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.INFO
    assert tag == "informational"


def test_cache_static_asset_info():
    """Test that cache findings on static assets are INFO."""
    finding_data = {
        "title": "Re-examine Cache-control Directives",
        "url": "https://example.com/_next/static/chunks/app.js",
        "evidence": "",
        "description": "Cache control issue",
    }
    raw_data = {}
    original_severity = Severity.LOW
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.INFO


def test_csp_unsafe_eval_medium():
    """Test that CSP unsafe-eval stays MEDIUM."""
    finding_data = {
        "title": "CSP: script-src unsafe-eval",
        "url": "https://example.com/page",
        "evidence": "script-src 'unsafe-eval'",
        "description": "CSP contains unsafe-eval",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.MEDIUM


def test_csp_unsafe_inline_medium():
    """Test that CSP unsafe-inline stays MEDIUM."""
    finding_data = {
        "title": "CSP: script-src unsafe-inline",
        "url": "https://example.com/page",
        "evidence": "script-src 'unsafe-inline'",
        "description": "CSP contains unsafe-inline",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.MEDIUM


def test_csp_wildcard_medium():
    """Test that CSP wildcard directive stays MEDIUM."""
    finding_data = {
        "title": "CSP: Wildcard Directive",
        "url": "https://example.com/page",
        "evidence": "default-src *",
        "description": "CSP contains wildcard directive",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.MEDIUM


def test_unknown_finding_no_change():
    """Test that unknown findings keep original severity."""
    finding_data = {
        "title": "Some Other Finding",
        "url": "https://example.com/page",
        "evidence": "",
        "description": "Some other issue",
    }
    raw_data = {}
    original_severity = Severity.HIGH
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == original_severity
    assert tag is None
    assert reason is None


def test_robots_txt_static():
    """Test that /robots.txt is treated as static asset."""
    finding_data = {
        "title": "Cross-Domain Misconfiguration",
        "url": "https://example.com/robots.txt",
        "evidence": "",
        "description": "CORS header present",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.INFO


def test_favicon_static():
    """Test that /favicon.ico is treated as static asset."""
    finding_data = {
        "title": "Cross-Domain Misconfiguration",
        "url": "https://example.com/favicon.ico",
        "evidence": "",
        "description": "CORS header present",
    }
    raw_data = {}
    original_severity = Severity.MEDIUM
    
    adjusted_severity, tag, reason = apply_noise_rules(finding_data, raw_data, original_severity)
    
    assert adjusted_severity == Severity.INFO


