"""
Tests for severity engine to ensure findings are not all INFO.
"""
import pytest
from app.core.severity import (
    normalize_severity,
    zap_to_severity,
    nuclei_to_severity,
    retire_to_severity,
    sslscan_to_severity,
    portfinding_to_severity,
    httpx_wappalyzer_to_severity,
    header_finding_to_severity,
    compute_overall_max_severity,
)
from app.models.finding import Severity


class TestNormalizeSeverity:
    """Test severity normalization"""
    
    def test_normalize_string(self):
        assert normalize_severity("critical") == Severity.CRITICAL
        assert normalize_severity("high") == Severity.HIGH
        assert normalize_severity("medium") == Severity.MEDIUM
        assert normalize_severity("low") == Severity.LOW
        assert normalize_severity("info") == Severity.INFO
    
    def test_normalize_enum(self):
        assert normalize_severity(Severity.CRITICAL) == Severity.CRITICAL
        assert normalize_severity(Severity.INFO) == Severity.INFO
    
    def test_normalize_none(self):
        assert normalize_severity(None) == Severity.INFO
    
    def test_normalize_invalid(self):
        assert normalize_severity("invalid") == Severity.INFO


class TestZAPSeverity:
    """Test ZAP severity mapping"""
    
    def test_zap_riskcode_mapping(self):
        # Test basic riskcode mapping
        severity, needs_verification = zap_to_severity(0, None)
        assert severity == Severity.INFO
        assert needs_verification == False
        
        severity, needs_verification = zap_to_severity(1, None)
        assert severity == Severity.LOW
        assert needs_verification == False
        
        severity, needs_verification = zap_to_severity(2, None)
        assert severity == Severity.MEDIUM
        assert needs_verification == False
        
        severity, needs_verification = zap_to_severity(3, None)
        assert severity == Severity.HIGH
        assert needs_verification == False
        
        severity, needs_verification = zap_to_severity(4, None)
        assert severity == Severity.CRITICAL
        assert needs_verification == False
    
    def test_zap_low_confidence_medium_high(self):
        # Low confidence + Medium/High risk -> needs verification
        severity, needs_verification = zap_to_severity(2, 0)  # Medium risk, Low confidence
        assert severity == Severity.MEDIUM
        assert needs_verification == True
        
        severity, needs_verification = zap_to_severity(3, "low")  # High risk, Low confidence
        assert severity == Severity.HIGH
        assert needs_verification == True
    
    def test_zap_confirmed_high_to_critical(self):
        # Confirmed High + severe attack pattern -> Critical
        severity, needs_verification = zap_to_severity(
            3,  # High risk
            3,  # Confirmed confidence
            "SQL Injection",
            {"description": "SQL injection vulnerability detected"}
        )
        assert severity == Severity.CRITICAL
        assert needs_verification == False
    
    def test_zap_confirmed_high_header_stays_high(self):
        # Confirmed High for headers should NOT escalate to Critical
        severity, needs_verification = zap_to_severity(
            3,  # High risk
            3,  # Confirmed confidence
            "Missing X-Content-Type-Options Header",
            {"description": "Missing security header"}
        )
        assert severity == Severity.HIGH  # Should NOT be Critical
        assert needs_verification == False
    
    def test_zap_confidence_normalization(self):
        # Test confidence normalization (string and int)
        severity, needs_verification = zap_to_severity(2, "Low")
        assert needs_verification == True
        
        severity, needs_verification = zap_to_severity(2, "Medium")
        assert needs_verification == False
        
        severity, needs_verification = zap_to_severity(2, 2)  # High confidence
        assert needs_verification == False


class TestNucleiSeverity:
    """Test Nuclei severity mapping"""
    
    def test_nuclei_template_severity(self):
        # Use template severity if provided
        template = {
            "info": {
                "severity": "high",
                "name": "Test Template"
            }
        }
        assert nuclei_to_severity(template) == Severity.HIGH
    
    def test_nuclei_critical_tags(self):
        # Critical tags should map to Critical
        template = {
            "info": {
                "tags": ["rce", "remote-code-execution"]
            }
        }
        assert nuclei_to_severity(template) == Severity.CRITICAL
        
        template = {
            "info": {
                "tags": ["sqli", "sql-injection"]
            }
        }
        assert nuclei_to_severity(template) == Severity.CRITICAL
    
    def test_nuclei_high_tags(self):
        # High tags should map to High
        template = {
            "info": {
                "tags": ["lfi", "ssrf"]
            }
        }
        assert nuclei_to_severity(template) == Severity.HIGH
    
    def test_nuclei_default_info(self):
        # Default to Info if no severity or tags
        template = {
            "info": {
                "name": "Test Template"
            }
        }
        assert nuclei_to_severity(template) == Severity.INFO


class TestRetireSeverity:
    """Test Retire.js severity mapping"""
    
    def test_retire_medium_vulnerability(self):
        # Known vulnerability -> Medium
        finding = {
            "component": "jquery",
            "version": "1.0.0",
            "vulnerabilities": [{"info": ["Some vulnerability"]}]
        }
        assert retire_to_severity(finding) == Severity.MEDIUM
    
    def test_retire_high_impact_old_version(self):
        # High impact + old version -> High
        finding = {
            "component": "jquery",
            "version": "0.9.0",  # Old version
            "vulnerabilities": [{"info": ["XSS vulnerability"]}]
        }
        assert retire_to_severity(finding) == Severity.HIGH


class TestSSLScanSeverity:
    """Test SSLScan severity mapping"""
    
    def test_sslscan_deprecated_protocol(self):
        # Deprecated protocols -> Medium
        finding = {
            "title": "SSLv2 detected",
            "description": "Deprecated protocol"
        }
        assert sslscan_to_severity(finding) == Severity.MEDIUM
    
    def test_sslscan_weak_cipher(self):
        # Weak ciphers -> Medium
        finding = {
            "title": "RC4 cipher detected",
            "description": "Weak cipher"
        }
        assert sslscan_to_severity(finding) == Severity.MEDIUM
    
    def test_sslscan_expired_cert(self):
        # Expired cert -> Low
        finding = {
            "title": "Expired certificate",
            "description": "Certificate has expired"
        }
        assert sslscan_to_severity(finding) == Severity.LOW


class TestPortFindingSeverity:
    """Test port/service finding severity"""
    
    def test_port_info(self):
        # Open port alone -> Info
        assert portfinding_to_severity("http", 80, "", "") == Severity.INFO
    
    def test_redis_unauth_critical(self):
        # Redis without auth -> Critical
        assert portfinding_to_severity(
            "redis",
            6379,
            "authentication disabled",
            "Redis open"
        ) == Severity.CRITICAL
    
    def test_admin_panel_high(self):
        # Admin panels -> High
        assert portfinding_to_severity(
            "tomcat",
            8080,
            "",
            "Tomcat Manager"
        ) == Severity.HIGH


class TestHeaderFindingSeverity:
    """Test security header finding severity"""
    
    def test_missing_header_low(self):
        # Missing headers -> Low
        finding = {
            "title": "Missing X-Content-Type-Options",
            "evidence": ""
        }
        assert header_finding_to_severity("X-Content-Type-Options", finding) == Severity.LOW
    
    def test_cors_misconfig_high(self):
        # CORS misconfig -> High
        finding = {
            "title": "CORS misconfiguration",
            "evidence": "Access-Control-Allow-Origin: * with credentials",
            "description": "Dangerous CORS config"
        }
        assert header_finding_to_severity("CORS", finding) == Severity.HIGH


class TestOverallMaxSeverity:
    """Test overall max severity computation"""
    
    def test_max_severity_critical(self):
        findings = [
            {"severity": Severity.INFO},
            {"severity": Severity.MEDIUM},
            {"severity": Severity.CRITICAL},
            {"severity": Severity.LOW},
        ]
        assert compute_overall_max_severity(findings) == Severity.CRITICAL
    
    def test_max_severity_empty(self):
        assert compute_overall_max_severity([]) == Severity.INFO


class TestSeverityNotAllInfo:
    """Integration test to ensure findings are not all INFO"""
    
    def test_zap_findings_mixed_severity(self):
        """Test that ZAP findings produce mixed severities"""
        zap_findings = [
            zap_to_severity(0, None)[0],  # Info
            zap_to_severity(1, None)[0],  # Low
            zap_to_severity(2, None)[0],  # Medium
            zap_to_severity(3, None)[0],  # High
        ]
        
        severities = [f.severity if hasattr(f, 'severity') else f for f in zap_findings]
        assert Severity.INFO in severities
        assert Severity.LOW in severities
        assert Severity.MEDIUM in severities
        assert Severity.HIGH in severities
        # Not all INFO
        assert not all(s == Severity.INFO for s in severities)
    
    def test_nuclei_findings_mixed_severity(self):
        """Test that Nuclei findings produce mixed severities"""
        nuclei_templates = [
            {"info": {"severity": "info"}},
            {"info": {"severity": "low"}},
            {"info": {"severity": "medium"}},
            {"info": {"severity": "high"}},
            {"info": {"tags": ["rce"]}},  # Should be Critical
        ]
        
        severities = [nuclei_to_severity(t) for t in nuclei_templates]
        assert Severity.INFO in severities
        assert Severity.LOW in severities
        assert Severity.MEDIUM in severities
        assert Severity.HIGH in severities
        assert Severity.CRITICAL in severities
        # Not all INFO
        assert not all(s == Severity.INFO for s in severities)

