"""
Unit tests for finding_normalizer module.

Tests:
- URL normalization
- Static asset detection
- ZAP rule family categorization
- Finding key computation (deduplication)
- Severity normalization (de-noising)
"""
import pytest
from app.utils.finding_normalizer import (
    normalize_url,
    is_static_asset_path,
    zap_rule_family,
    group_scope_for_zap,
    compute_evidence_signature,
    compute_finding_key,
    normalize_severity_for_finding,
    normalize_and_group_finding,
)
from app.models.finding import Severity
from app.utils.dalfox_instance_meta import parse_dalfox_evidence_snippet


class TestURLNormalization:
    """Test URL normalization functions"""
    
    def test_normalize_url_basic(self):
        """Test basic URL normalization"""
        assert normalize_url("https://example.com/path") == "https://example.com/path"
        assert normalize_url("https://example.com/path?query=1") == "https://example.com/path?query=1"
        assert normalize_url("https://example.com/path#fragment") == "https://example.com/path"
    
    def test_normalize_url_static_asset_strips_query(self):
        """Test that static assets strip query params"""
        assert normalize_url("https://example.com/_next/static/app.js?hash=123", strip_query_for_static=True) == "https://example.com/_next/static/app.js"
        assert normalize_url("https://example.com/app.css?v=1", strip_query_for_static=True) == "https://example.com/app.css"
    
    def test_normalize_url_lowercase(self):
        """Test URL lowercase normalization"""
        assert normalize_url("HTTPS://EXAMPLE.COM/PATH") == "https://example.com/path"
    
    def test_normalize_url_removes_default_ports(self):
        """Test that default ports are removed"""
        assert normalize_url("https://example.com:443/path") == "https://example.com/path"
        assert normalize_url("http://example.com:80/path") == "http://example.com/path"


class TestStaticAssetDetection:
    """Test static asset detection"""
    
    def test_is_static_asset_path_next_static(self):
        """Test _next/static detection"""
        assert is_static_asset_path("/_next/static/app.js") is True
        assert is_static_asset_path("/_next/static/chunks/main.js") is True
    
    def test_is_static_asset_path_extensions(self):
        """Test file extension detection"""
        assert is_static_asset_path("/app.js") is True
        assert is_static_asset_path("/style.css") is True
        assert is_static_asset_path("/image.png") is True
        assert is_static_asset_path("/font.woff2") is True
        assert is_static_asset_path("/app.js.map") is True
    
    def test_is_static_asset_path_filenames(self):
        """Test specific filename detection"""
        assert is_static_asset_path("/robots.txt") is True
        assert is_static_asset_path("/favicon.ico") is True
        assert is_static_asset_path("/sitemap.xml") is True
    
    def test_is_static_asset_path_not_static(self):
        """Test that non-static paths return False"""
        assert is_static_asset_path("/api/user") is False
        assert is_static_asset_path("/dashboard") is False
        assert is_static_asset_path("/") is False


class TestZAPRuleFamily:
    """Test ZAP rule family categorization"""
    
    def test_zap_rule_family_cors(self):
        """Test CORS rule family detection"""
        assert zap_rule_family("10020", "Cross-Domain Misconfiguration") == "cors"
        assert zap_rule_family("10021", "CORS Misconfiguration") == "cors"
        assert zap_rule_family(None, "Cross-Domain Misconfiguration") == "cors"
        assert zap_rule_family(None, "CORS") == "cors"
    
    def test_zap_rule_family_cache(self):
        """Test cache rule family detection"""
        assert zap_rule_family("10015", "Retrieved from Cache") == "cache"
        assert zap_rule_family(None, "Retrieved from Cache") == "cache"
        assert zap_rule_family(None, "Cache-Control") == "cache"
    
    def test_zap_rule_family_ua_fuzzer(self):
        """Test UA fuzzer rule family detection"""
        assert zap_rule_family("10104", "User Agent Fuzzer") == "ua_fuzzer"
        assert zap_rule_family(None, "User Agent Fuzzer") == "ua_fuzzer"
    
    def test_zap_rule_family_csp(self):
        """Test CSP rule family detection"""
        assert zap_rule_family("10038", "Content Security Policy") == "csp"
        assert zap_rule_family(None, "CSP: unsafe-inline") == "csp"
        assert zap_rule_family(None, "Wildcard Directive") == "csp"
    
    def test_zap_rule_family_default(self):
        """Test default rule family"""
        assert zap_rule_family(None, "Unknown Rule") == "info"


class TestFindingKeyComputation:
    """Test finding key computation for deduplication"""
    
    def test_compute_finding_key_same_issue_different_urls(self):
        """Test that same issue across different URLs produces same key"""
        key1 = compute_finding_key(
            tool="zap",
            rule_id=None,
            plugin_id="10020",
            normalized_host="example.com",
            evidence_signature="title:Cross-Domain Misconfiguration|riskcode:2|confidence:2",
            normalized_param=None,
            path_bucket="host-level",
        )
        key2 = compute_finding_key(
            tool="zap",
            rule_id=None,
            plugin_id="10020",
            normalized_host="example.com",
            evidence_signature="title:Cross-Domain Misconfiguration|riskcode:2|confidence:2",
            normalized_param=None,
            path_bucket="host-level",
        )
        assert key1 == key2
    
    def test_compute_finding_key_different_issues(self):
        """Test that different issues produce different keys"""
        key1 = compute_finding_key(
            tool="zap",
            rule_id=None,
            plugin_id="10020",
            normalized_host="example.com",
            evidence_signature="title:Cross-Domain Misconfiguration|riskcode:2|confidence:2",
            normalized_param=None,
            path_bucket="host-level",
        )
        key2 = compute_finding_key(
            tool="zap",
            rule_id=None,
            plugin_id="10021",
            normalized_host="example.com",
            evidence_signature="title:Different Issue|riskcode:2|confidence:2",
            normalized_param=None,
            path_bucket="host-level",
        )
        assert key1 != key2


class TestSeverityNormalization:
    """Test severity normalization (de-noising)"""
    
    def test_normalize_severity_cors_static_asset(self):
        """Test CORS on static asset -> INFO"""
        finding_data = {
            "title": "Cross-Domain Misconfiguration",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/_next/static/app.js",
            "path": "/_next/static/app.js",
            "evidence": "",
            "description": "",
        }
        raw_data = {"riskcode": 2, "confidence": 2}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "cors",
            True,  # is_static_asset
        )
        assert severity == Severity.INFO
    
    def test_normalize_severity_cors_api_endpoint(self):
        """Test CORS on API endpoint -> MEDIUM"""
        finding_data = {
            "title": "Cross-Domain Misconfiguration",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/api/user",
            "path": "/api/user",
            "evidence": "",
            "description": "",
        }
        raw_data = {"riskcode": 2, "confidence": 2}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "cors",
            False,  # is_static_asset
        )
        assert severity == Severity.MEDIUM
    
    def test_normalize_severity_cors_high_risk(self):
        """Test CORS with ACAO=* + ACAC=true -> HIGH"""
        finding_data = {
            "title": "Cross-Domain Misconfiguration",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/api/user",
            "path": "/api/user",
            "evidence": "Access-Control-Allow-Origin: * Access-Control-Allow-Credentials: true",
            "description": "CORS allows all origins with credentials",
        }
        raw_data = {"riskcode": 2, "confidence": 2}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "cors",
            False,
        )
        assert severity == Severity.HIGH
    
    def test_normalize_severity_cache_static_asset(self):
        """Test cache on static asset -> INFO"""
        finding_data = {
            "title": "Retrieved from Cache",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/app.js",
            "path": "/app.js",
            "evidence": "",
            "description": "",
        }
        raw_data = {"riskcode": 2, "confidence": 2}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "cache",
            True,  # is_static_asset
        )
        assert severity == Severity.INFO
    
    def test_normalize_severity_cache_authenticated(self):
        """Test cache on authenticated path -> MEDIUM"""
        finding_data = {
            "title": "Retrieved from Cache",
            "severity": Severity.MEDIUM,
            "url": "https://example.com/dashboard",
            "path": "/dashboard",
            "evidence": "",
            "description": "",
        }
        raw_data = {"riskcode": 2, "confidence": 2}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "cache",
            False,
        )
        assert severity == Severity.MEDIUM
    
    def test_normalize_severity_ua_fuzzer(self):
        """Test UA fuzzer -> INFO always"""
        finding_data = {
            "title": "User Agent Fuzzer",
            "severity": Severity.LOW,
            "url": "https://example.com/",
            "path": "/",
            "evidence": "",
            "description": "",
        }
        raw_data = {"riskcode": 1, "confidence": 1}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "ua_fuzzer",
            False,
        )
        assert severity == Severity.INFO
    
    def test_normalize_severity_csp_unsafe_eval(self):
        """Test CSP unsafe-eval -> MEDIUM (at least)"""
        finding_data = {
            "title": "CSP: unsafe-eval",
            "severity": Severity.LOW,
            "url": "https://example.com/",
            "path": "/",
            "evidence": "unsafe-eval",
            "description": "CSP allows unsafe-eval",
        }
        raw_data = {"riskcode": 1, "confidence": 1}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "csp",
            False,
        )
        assert severity == Severity.MEDIUM
    
    def test_normalize_severity_csp_unsafe_inline(self):
        """Test CSP unsafe-inline -> MEDIUM (at least)"""
        finding_data = {
            "title": "CSP: unsafe-inline",
            "severity": Severity.LOW,
            "url": "https://example.com/",
            "path": "/",
            "evidence": "unsafe-inline",
            "description": "CSP allows unsafe-inline",
        }
        raw_data = {"riskcode": 1, "confidence": 1}
        
        severity = normalize_severity_for_finding(
            finding_data,
            raw_data,
            "csp",
            False,
        )
        assert severity == Severity.MEDIUM


class TestNormalizeAndGroupFinding:
    """Test full normalization and grouping"""
    
    def test_normalize_and_group_cors_findings(self):
        """Test that multiple CORS findings across URLs produce same key"""
        finding1 = {
            "tool": "zap",
            "title": "Cross-Domain Misconfiguration",
            "url": "https://example.com/_next/static/app.js",
            "path": "/_next/static/app.js",
            "plugin_id": "10020",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2, "pluginId": "10020"}',
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Cross-Domain Misconfiguration",
            "url": "https://example.com/_next/static/chunks/main.js",
            "path": "/_next/static/chunks/main.js",
            "plugin_id": "10020",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2, "pluginId": "10020"}',
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        
        # Same finding key (should dedupe)
        assert canonical1["finding_key"] == canonical2["finding_key"]
        
        # Severity normalized to INFO for static assets
        assert canonical1["severity"] == Severity.INFO
        
        # Different instance URLs
        assert instance1["url"] != instance2["url"]
        assert instance1["is_static_asset"] is True
        assert instance2["is_static_asset"] is True
    
    def test_normalize_and_group_csp_findings(self):
        """Test that CSP findings remain MEDIUM"""
        finding = {
            "tool": "zap",
            "title": "CSP: unsafe-inline",
            "url": "https://example.com/",
            "path": "/",
            "plugin_id": "10038",
            "severity": Severity.LOW,
            "raw_data": '{"riskcode": 1, "confidence": 1, "pluginId": "10038"}',
            "evidence": "unsafe-inline",
        }
        
        canonical, instance = normalize_and_group_finding(finding, "scan1", "project1")
        
        # CSP should be at least MEDIUM
        assert canonical["severity"] == Severity.MEDIUM
        assert canonical["rule_family"] == "csp"
    
    def test_normalize_and_group_csp_header_not_set(self):
        """Test that CSP Header Not Set findings group across all URLs"""
        finding1 = {
            "tool": "zap",
            "title": "Content Security Policy (CSP) Header Not Set",
            "url": "https://example.com/page1",
            "path": "/page1",
            "plugin_id": "10038",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2, "pluginId": "10038"}',
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Content Security Policy (CSP) Header Not Set",
            "url": "https://example.com/page2",
            "path": "/page2",
            "plugin_id": "10038",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2, "pluginId": "10038"}',
        }
        
        finding3 = {
            "tool": "zap",
            "title": "Content Security Policy (CSP) Header Not Set",
            "url": "https://example.com/api/endpoint",
            "path": "/api/endpoint",
            "plugin_id": "10038",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2, "pluginId": "10038"}',
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        canonical3, instance3 = normalize_and_group_finding(finding3, "scan1", "project1")
        
        # All should have the same finding_key (host-level grouping)
        assert canonical1["finding_key"] == canonical2["finding_key"]
        assert canonical2["finding_key"] == canonical3["finding_key"]
        assert canonical1["rule_family"] == "csp"
    
    def test_normalize_and_group_modern_web_application(self):
        """Test that Modern Web Application findings group across all URLs"""
        finding1 = {
            "tool": "zap",
            "title": "Modern Web Application",
            "url": "https://example.com/page1",
            "path": "/page1",
            "severity": Severity.INFO,
            "raw_data": '{"riskcode": 0, "confidence": 1}',
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Modern Web Application",
            "url": "https://example.com/page2",
            "path": "/page2",
            "severity": Severity.INFO,
            "raw_data": '{"riskcode": 0, "confidence": 1}',
        }
        
        finding3 = {
            "tool": "zap",
            "title": "Modern Web Application",
            "url": "https://example.com/api/data",
            "path": "/api/data",
            "severity": Severity.INFO,
            "raw_data": '{"riskcode": 0, "confidence": 1}',
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        canonical3, instance3 = normalize_and_group_finding(finding3, "scan1", "project1")
        
        # All should have the same finding_key (host-level grouping)
        assert canonical1["finding_key"] == canonical2["finding_key"]
        assert canonical2["finding_key"] == canonical3["finding_key"]
        assert canonical1["rule_family"] == "headers"  # Modern Web Application is categorized as headers
    
    def test_normalize_and_group_cookie_findings(self):
        """Test that cookie findings group by cookie name across URLs"""
        finding1 = {
            "tool": "zap",
            "title": "Cookie No HttpOnly Flag",
            "url": "https://example.com/page1",
            "path": "/page1",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
            "evidence": "Set-Cookie: GRUYERE=value; Path=/",
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Cookie No HttpOnly Flag",
            "url": "https://example.com/page2",
            "path": "/page2",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
            "evidence": "Set-Cookie: GRUYERE=value2; Path=/",
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        
        # Should have the same finding_key (same cookie name "GRUYERE")
        assert canonical1["finding_key"] == canonical2["finding_key"]
        assert canonical1["rule_family"] == "cookies"
    
    def test_normalize_and_group_csrf_findings(self):
        """Test that CSRF findings group by form action path"""
        finding1 = {
            "tool": "zap",
            "title": "Absence of Anti-CSRF Tokens",
            "url": "https://example.com/upload.gtl?param1=value1",
            "path": "/upload.gtl",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Absence of Anti-CSRF Tokens",
            "url": "https://example.com/upload.gtl?param2=value2",
            "path": "/upload.gtl",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        
        # Should have the same finding_key (same form action "/upload.gtl")
        assert canonical1["finding_key"] == canonical2["finding_key"]
        assert canonical1["rule_family"] == "csrf"
    
    def test_normalize_and_group_big_redirect(self):
        """Test that Big Redirect findings group by redirecting path"""
        finding1 = {
            "tool": "zap",
            "title": "Big Redirect Detected (Potential Sensitive Information Leak)",
            "url": "https://example.com/redirect?url=http://evil.com",
            "path": "/redirect",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
        }
        
        finding2 = {
            "tool": "zap",
            "title": "Big Redirect Detected (Potential Sensitive Information Leak)",
            "url": "https://example.com/redirect?url=http://other.com",
            "path": "/redirect",
            "severity": Severity.MEDIUM,
            "raw_data": '{"riskcode": 2, "confidence": 2}',
        }
        
        canonical1, instance1 = normalize_and_group_finding(finding1, "scan1", "project1")
        canonical2, instance2 = normalize_and_group_finding(finding2, "scan1", "project1")
        
        # Should have the same finding_key (same redirecting path "/redirect")
        assert canonical1["finding_key"] == canonical2["finding_key"]
    
    def test_group_scope_for_zap_host_level(self):
        """Test that CSP and header findings use host-level grouping"""
        assert group_scope_for_zap("10038", "Content Security Policy (CSP) Header Not Set", "csp") == "host"
        assert group_scope_for_zap(None, "X-Content-Type-Options Header Missing", "headers") == "host"
        assert group_scope_for_zap(None, "Missing Anti-clickjacking Header", "headers") == "host"
        assert group_scope_for_zap(None, "Modern Web Application", "headers") == "host"
        assert group_scope_for_zap("10020", "Cross-Domain Misconfiguration", "cors") == "host"
    
    def test_group_scope_for_zap_path_level(self):
        """Test that path-specific vulnerabilities use path-level grouping"""
        assert group_scope_for_zap(None, "SQL Injection", "info") == "path"
        assert group_scope_for_zap(None, "XSS Vulnerability", "info") == "path"
        assert group_scope_for_zap(None, "Big Redirect Detected", "info") == "path"
    
    def test_group_scope_for_zap_cookies(self):
        """Test that cookie findings use host-level grouping"""
        assert group_scope_for_zap(None, "Cookie No HttpOnly Flag", "cookies") == "host"
        assert group_scope_for_zap(None, "Cookie without SameSite Attribute", "cookies") == "host"
        assert group_scope_for_zap(None, "Cookie Without Secure Flag", "cookies") == "host"
    
    def test_group_scope_for_zap_csrf(self):
        """Test that CSRF findings use form_action grouping"""
        assert group_scope_for_zap(None, "Absence of Anti-CSRF Tokens", "csrf") == "form_action"
    
    def test_zap_rule_family_modern_web_application(self):
        """Test that Modern Web Application is detected"""
        assert zap_rule_family(None, "Modern Web Application") == "headers"
        assert zap_rule_family(None, "modern web application") == "headers"
    
    def test_zap_rule_family_cookies(self):
        """Test that cookie-related findings are detected"""
        assert zap_rule_family(None, "Cookie No HttpOnly Flag") == "cookies"
        assert zap_rule_family(None, "Cookie without SameSite Attribute") == "cookies"
        assert zap_rule_family(None, "Cookie Without Secure Flag") == "cookies"
    
    def test_zap_rule_family_csrf(self):
        """Test that CSRF findings are detected"""
        assert zap_rule_family(None, "Absence of Anti-CSRF Tokens") == "csrf"
        assert zap_rule_family(None, "CSRF Token Missing") == "csrf"


class TestDalfoxSinkIdentity:
    def _base(self, **overrides):
        finding = {
            "tool": "dalfox",
            "title": "Found XSS",
            "severity": "medium",
            "url": "https://example.com/search?uid=%3Csvg%2Fonload%3Dalert(1)%3E",
            "raw_data": "{}",
            "message": "Reflected XSS",
            "payload": "<svg/onload=alert(1)>",
        }
        finding.update(overrides)
        return finding

    def test_dalfox_fingerprint_invariant_to_payload_title_message(self):
        f1 = self._base(
            title="payload <svg/onload=alert(1)>",
            message="Reflected XSS",
            raw_data='{"payload":"<svg/onload=alert(1)>","param":"uid"}',
        )
        f2 = self._base(
            title="totally different title with payload <img src=x onerror=alert(2)>",
            message="Triggered XSS in another payload",
            raw_data='{"payload":"<img src=x onerror=alert(2)>","param":"uid"}',
            payload="<img src=x onerror=alert(2)>",
        )

        c1, _ = normalize_and_group_finding(f1, "scan-1", "proj-1")
        c2, _ = normalize_and_group_finding(f2, "scan-1", "proj-1")
        assert c1["finding_key"] == c2["finding_key"]

    def test_dalfox_fingerprint_changes_with_identity_components(self):
        base, _ = normalize_and_group_finding(
            self._base(raw_data='{"param":"uid"}'),
            "scan-1",
            "proj-1",
        )
        changed_path, _ = normalize_and_group_finding(
            self._base(url="https://example.com/profile?uid=%3Cscript%3E1%3C/script%3E", raw_data='{"param":"uid"}'),
            "scan-1",
            "proj-1",
        )
        changed_param, _ = normalize_and_group_finding(
            self._base(url="https://example.com/search?q=%3Cscript%3E1%3C/script%3E", raw_data='{"param":"q"}'),
            "scan-1",
            "proj-1",
        )
        changed_kind, _ = normalize_and_group_finding(
            self._base(message="Found DOM Object", raw_data='{"param":"uid","message":"Found DOM Object"}'),
            "scan-1",
            "proj-1",
        )
        changed_vuln, _ = normalize_and_group_finding(
            self._base(message="Found Open Redirect", raw_data='{"param":"next","message":"Found Open Redirect","cwe":"CWE-601"}'),
            "scan-1",
            "proj-1",
        )
        changed_host_port, _ = normalize_and_group_finding(
            self._base(url="https://example.com:8080/search?uid=%3Cscript%3E1%3C/script%3E", raw_data='{"param":"uid"}'),
            "scan-1",
            "proj-1",
        )

        assert base["finding_key"] != changed_path["finding_key"]
        assert base["finding_key"] != changed_param["finding_key"]
        assert base["finding_key"] != changed_kind["finding_key"]
        assert base["finding_key"] != changed_vuln["finding_key"]
        assert base["finding_key"] != changed_host_port["finding_key"]

    def test_dalfox_title_payload_free_and_param_inferred(self):
        payload = "<svg/onload=alert(1)>"
        canonical, _ = normalize_and_group_finding(
            self._base(
                title=f"Reflected XSS with payload {payload}",
                url="https://example.com/search?=&uid=%3Csvg%2Fonload%3Dalert(1)%3E",
                raw_data='{"payload":"<svg/onload=alert(1)>"}',
                parameter=None,
            ),
            "scan-1",
            "proj-1",
        )
        assert payload not in canonical["title"]
        assert "uid" in canonical["title"]

    def test_dalfox_instance_severity_mapping(self):
        triggered_canonical, triggered_instance = normalize_and_group_finding(
            self._base(
                message="Triggered XSS in response",
                raw_data='{"param":"uid","message":"Triggered XSS in response","type":"V"}',
            ),
            "scan-1",
            "proj-1",
        )
        dom_canonical, dom_instance = normalize_and_group_finding(
            self._base(
                message="Found DOM Object",
                raw_data='{"param":"uid","message":"Found DOM Object"}',
            ),
            "scan-1",
            "proj-1",
        )

        triggered_meta = parse_dalfox_evidence_snippet(triggered_instance["evidence_snippet"])
        dom_meta = parse_dalfox_evidence_snippet(dom_instance["evidence_snippet"])
        assert triggered_meta["instance_severity"] == "high"
        assert dom_meta["instance_severity"] == "medium"
        assert triggered_canonical["severity"] == Severity.HIGH
        assert dom_canonical["severity"] == Severity.MEDIUM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
