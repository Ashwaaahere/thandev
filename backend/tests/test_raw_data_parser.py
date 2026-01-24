"""
Hard regression tests for raw data parser and ZAP severity extraction.
"""
import pytest
import json
from app.utils.raw_data_parser import parse_raw_json, extract_zap_metadata
from app.core.severity import zap_to_severity
from app.models.finding import Severity


def test_parse_raw_json_dict():
    """Test parsing when raw is already a dict."""
    raw = {"riskcode": 2, "confidence": 2, "alert": "Test Alert"}
    result = parse_raw_json(raw)
    assert isinstance(result, dict)
    assert result["riskcode"] == 2
    assert result["confidence"] == 2


def test_parse_raw_json_single_encoded():
    """Test parsing single-encoded JSON string."""
    raw = json.dumps({"riskcode": 2, "confidence": 2, "alert": "Test Alert"})
    result = parse_raw_json(raw)
    assert isinstance(result, dict)
    assert result["riskcode"] == 2
    assert result["confidence"] == 2


def test_parse_raw_json_double_encoded():
    """Test parsing double-encoded JSON string (regression test)."""
    inner = {"riskcode": 2, "confidence": 2, "alert": "Test Alert"}
    outer = json.dumps(json.dumps(inner))  # Double-encoded
    result = parse_raw_json(outer)
    assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"
    assert result["riskcode"] == 2, f"Expected riskcode=2, got {result.get('riskcode')}"
    assert result["confidence"] == 2


def test_extract_zap_metadata_from_double_encoded():
    """Test extracting ZAP metadata from double-encoded JSON."""
    inner = {
        "riskcode": 2,
        "confidence": 2,
        "alert": "Cross Site Scripting",
        "cweid": "79",
        "wascid": "6",
        "pluginId": "40012",
        "alertRef": "40012-1"
    }
    outer = json.dumps(json.dumps(inner))  # Double-encoded
    meta = extract_zap_metadata(outer)
    assert meta["riskcode"] == 2
    assert meta["confidence"] == 2
    assert meta["alert"] == "Cross Site Scripting"
    assert meta["wascid"] == 6
    assert meta["pluginId"] == "40012"


def test_zap_severity_from_double_encoded():
    """CRITICAL: Test that riskcode=2 from double-encoded JSON results in MEDIUM severity."""
    inner = {
        "riskcode": 2,
        "confidence": 2,
        "alert": "Cross Site Scripting (Reflected)"
    }
    outer = json.dumps(json.dumps(inner))  # Double-encoded
    
    # Extract metadata
    meta = extract_zap_metadata(outer)
    riskcode = meta["riskcode"]
    confidence = meta["confidence"]
    alert = meta["alert"]
    
    # Compute severity
    severity, needs_verification = zap_to_severity(riskcode, confidence, alert, meta["raw_dict"])
    
    # CRITICAL ASSERTION: riskcode=2 must result in MEDIUM, NOT INFO
    assert severity == Severity.MEDIUM, f"Expected MEDIUM for riskcode=2, got {severity}"
    assert not needs_verification  # High confidence, so no verification needed


def test_zap_severity_riskcode_2_not_info():
    """CRITICAL: Test that riskcode=2 never results in INFO severity."""
    test_cases = [
        (2, 0, Severity.MEDIUM, True),   # Low confidence -> needs verification
        (2, 1, Severity.MEDIUM, False),  # Medium confidence
        (2, 2, Severity.MEDIUM, False),  # High confidence
        (2, 3, Severity.MEDIUM, False), # Confirmed confidence
    ]
    
    for riskcode, confidence, expected_severity, expected_needs_verification in test_cases:
        severity, needs_verification = zap_to_severity(riskcode, confidence, "Test Alert", {})
        assert severity == expected_severity, f"riskcode={riskcode}, confidence={confidence}: expected {expected_severity}, got {severity}"
        assert severity != Severity.INFO, f"riskcode={riskcode} must NEVER result in INFO severity"
        assert needs_verification == expected_needs_verification


def test_extract_zap_metadata_handles_string_riskcode():
    """Test that string riskcodes are converted to integers."""
    raw = {"riskcode": "2", "confidence": "2"}
    meta = extract_zap_metadata(raw)
    assert meta["riskcode"] == 2
    assert isinstance(meta["riskcode"], int)


def test_extract_zap_metadata_handles_string_confidence():
    """Test that string confidence values are converted to integers."""
    test_cases = [
        ("Low", 0),
        ("low", 0),
        ("0", 0),
        ("Medium", 1),
        ("medium", 1),
        ("1", 1),
        ("High", 2),
        ("high", 2),
        ("2", 2),
        ("Confirmed", 3),
        ("confirmed", 3),
        ("3", 3),
    ]
    
    for conf_str, expected_int in test_cases:
        raw = {"riskcode": 2, "confidence": conf_str}
        meta = extract_zap_metadata(raw)
        assert meta["confidence"] == expected_int, f"confidence='{conf_str}' should map to {expected_int}"


def test_parse_raw_json_handles_none():
    """Test that None input returns empty dict."""
    result = parse_raw_json(None)
    assert result == {}


def test_parse_raw_json_handles_invalid_json():
    """Test that invalid JSON returns empty dict with logging."""
    result = parse_raw_json("not valid json {")
    assert result == {}


def test_extract_zap_metadata_defaults():
    """Test that missing riskcode/confidence default to 0."""
    raw = {"alert": "Test Alert"}
    meta = extract_zap_metadata(raw)
    assert meta["riskcode"] == 0
    assert meta["confidence"] == 0

