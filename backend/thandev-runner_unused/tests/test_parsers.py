"""
Unit tests for findings parsers
"""
import pytest
import json
import tempfile
from pathlib import Path

from app.findings.parsers import parse_nuclei_output, parse_httpx_output, parse_sslscan_output


def test_parse_nuclei_output_empty_file():
    """Test parsing empty nuclei output file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        f.write("")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_nuclei_output(path)
        assert findings == []
    finally:
        path.unlink()


def test_parse_nuclei_output_single_finding():
    """Test parsing single nuclei finding"""
    nuclei_finding = {
        "template-id": "test-template",
        "info": {
            "name": "Test Vulnerability",
            "severity": "high",
            "description": "Test description",
            "tags": ["xss", "sqli"]
        },
        "matched-at": "https://example.com/test",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        f.write(json.dumps(nuclei_finding) + "\n")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_nuclei_output(path)
        assert len(findings) == 1
        finding = findings[0]
        assert finding["tool_id"] == "nuclei"
        assert finding["severity"] == "high"
        assert finding["url"] == "https://example.com/test"
        assert finding["title"] == "Test Vulnerability"
        assert "raw" in finding
    finally:
        path.unlink()


def test_parse_httpx_output_empty_file():
    """Test parsing empty httpx output file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        f.write("")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_httpx_output(path)
        assert findings == []
    finally:
        path.unlink()


def test_parse_httpx_output_single_finding():
    """Test parsing single httpx finding"""
    httpx_finding = {
        "url": "https://example.com",
        "status_code": 200,
        "title": "Example Page",
        "tech": ["PHP", "MySQL"]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        f.write(json.dumps(httpx_finding) + "\n")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_httpx_output(path)
        assert len(findings) == 1
        finding = findings[0]
        assert finding["tool_id"] == "httpx"
        assert finding["severity"] == "info"
        assert finding["url"] == "https://example.com"
        assert "raw" in finding
    finally:
        path.unlink()


def test_parse_sslscan_output_empty_file():
    """Test parsing empty sslscan output file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write("")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_sslscan_output(path)
        assert findings == []
    finally:
        path.unlink()


def test_parse_sslscan_output_json():
    """Test parsing sslscan JSON output"""
    sslscan_data = {
        "host": "example.com",
        "port": 443,
        "ssl_version": {
            "SSLv2": {"status": "enabled"},
            "SSLv3": {"status": "disabled"},
            "TLSv1.0": {"status": "enabled"}
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write(json.dumps(sslscan_data))
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_sslscan_output(path)
        assert len(findings) >= 2  # Should find SSLv2 and TLSv1.0 issues
        assert any(f["severity"] == "high" for f in findings)
        assert any("SSLv2" in f["title"] for f in findings)
    finally:
        path.unlink()


def test_parse_nuclei_output_multiple_findings():
    """Test parsing multiple nuclei findings"""
    findings_data = [
        {
            "template-id": "template-1",
            "info": {"name": "Finding 1", "severity": "critical", "description": "Desc 1"},
            "matched-at": "https://example.com/1"
        },
        {
            "template-id": "template-2",
            "info": {"name": "Finding 2", "severity": "medium", "description": "Desc 2"},
            "matched-at": "https://example.com/2"
        }
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
        for finding in findings_data:
            f.write(json.dumps(finding) + "\n")
        f.flush()
        path = Path(f.name)
    
    try:
        findings = parse_nuclei_output(path)
        assert len(findings) == 2
        assert findings[0]["severity"] == "critical"
        assert findings[1]["severity"] == "medium"
    finally:
        path.unlink()

