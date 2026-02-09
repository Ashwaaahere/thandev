"""
Tests for Nuclei finding deduplication, grouping, and severity mapping.

Verifies:
- nuclei_to_severity() uses info.severity as source of truth
- nuclei_to_severity() falls back to CVSS, then tags, then INFO
- Finding normalizer groups nuclei findings by template_id + host
- MongoBleed spam scenario: multiple identical host events collapse into one finding
- Severity is never incorrectly defaulted to INFO when template provides a valid value
"""
import pytest
import hashlib
from app.core.severity import nuclei_to_severity, normalize_severity
from app.models.finding import Severity
from app.utils.finding_normalizer import (
    normalize_and_group_finding,
    nuclei_rule_family,
    group_scope_for_nuclei,
    compute_finding_key,
    compute_evidence_signature,
)


class TestNucleiSeverityMapping:
    """Test that nuclei_to_severity() correctly maps severity from nuclei JSONL data."""
    
    def test_info_severity_is_respected(self):
        """When template says severity=info, return INFO (not fall through to tags)."""
        meta = {
            "info": {
                "severity": "info",
                "tags": ["creds", "exposed-panel"],  # These should NOT override info
            }
        }
        assert nuclei_to_severity(meta) == Severity.INFO
    
    def test_high_severity(self):
        """When template says severity=high, return HIGH."""
        meta = {"info": {"severity": "high", "name": "Test Vuln"}}
        assert nuclei_to_severity(meta) == Severity.HIGH
    
    def test_medium_severity(self):
        """When template says severity=medium, return MEDIUM."""
        meta = {"info": {"severity": "medium", "name": "Test Vuln"}}
        assert nuclei_to_severity(meta) == Severity.MEDIUM
    
    def test_critical_severity(self):
        """When template says severity=critical, return CRITICAL."""
        meta = {"info": {"severity": "critical", "name": "Test Vuln"}}
        assert nuclei_to_severity(meta) == Severity.CRITICAL
    
    def test_low_severity(self):
        """When template says severity=low, return LOW."""
        meta = {"info": {"severity": "low", "name": "Test Vuln"}}
        assert nuclei_to_severity(meta) == Severity.LOW
    
    def test_case_insensitive(self):
        """Severity mapping should be case-insensitive."""
        assert nuclei_to_severity({"info": {"severity": "HIGH"}}) == Severity.HIGH
        assert nuclei_to_severity({"info": {"severity": "Medium"}}) == Severity.MEDIUM
        assert nuclei_to_severity({"info": {"severity": "CRITICAL"}}) == Severity.CRITICAL
    
    def test_fallback_to_cvss(self):
        """When severity is missing, fall back to CVSS score."""
        meta = {
            "info": {
                "name": "Test Vuln",
                "classification": {"cvss-score": 9.8}
            }
        }
        assert nuclei_to_severity(meta) == Severity.CRITICAL
    
    def test_fallback_cvss_high(self):
        """CVSS 7.0-8.9 maps to HIGH."""
        meta = {"info": {"classification": {"cvss-score": 7.5}}}
        assert nuclei_to_severity(meta) == Severity.HIGH
    
    def test_fallback_cvss_medium(self):
        """CVSS 4.0-6.9 maps to MEDIUM."""
        meta = {"info": {"classification": {"cvss-score": 5.0}}}
        assert nuclei_to_severity(meta) == Severity.MEDIUM
    
    def test_fallback_cvss_low(self):
        """CVSS 0.1-3.9 maps to LOW."""
        meta = {"info": {"classification": {"cvss-score": 2.0}}}
        assert nuclei_to_severity(meta) == Severity.LOW
    
    def test_fallback_to_tags_critical(self):
        """When severity and CVSS are missing, infer from tags."""
        meta = {"info": {"tags": ["rce", "network"]}}
        assert nuclei_to_severity(meta) == Severity.CRITICAL
    
    def test_fallback_to_tags_high(self):
        """Tags like 'exposed-panel' infer HIGH severity."""
        meta = {"info": {"tags": ["exposed-panel", "network"]}}
        assert nuclei_to_severity(meta) == Severity.HIGH
    
    def test_fallback_default_info(self):
        """When nothing is available, default to INFO."""
        meta = {"info": {"name": "Unknown Finding"}}
        assert nuclei_to_severity(meta) == Severity.INFO
    
    def test_empty_dict(self):
        """Empty dict returns INFO."""
        assert nuclei_to_severity({}) == Severity.INFO
    
    def test_non_dict(self):
        """Non-dict input returns INFO."""
        assert nuclei_to_severity("not a dict") == Severity.INFO
    
    def test_top_level_severity_fallback(self):
        """When info.severity is missing but top-level severity exists, use it."""
        meta = {"severity": "high", "info": {"name": "Test Vuln"}}
        assert nuclei_to_severity(meta) == Severity.HIGH
    
    def test_mongobleed_severity_preserved(self):
        """MongoBleed template has severity=high and should be mapped correctly."""
        meta = {
            "template-id": "mongodb-detect-mongobleed",
            "info": {
                "name": "MongoDB Server - Information Disclosure (MongoBleed)",
                "severity": "high",
                "tags": ["network", "mongodb", "mongobleed"],
                "classification": {
                    "cve-id": ["CVE-2024-XXXX"],
                    "cvss-score": 7.5,
                }
            },
            "matched-at": "pentest-ground.com:4280"
        }
        assert nuclei_to_severity(meta) == Severity.HIGH


class TestNucleiRuleFamily:
    """Test nuclei rule family categorization."""
    
    def test_cve_family(self):
        assert nuclei_rule_family("CVE-2024-1234", "Some CVE Vuln", ["cve"]) == "cve"
    
    def test_vuln_family(self):
        assert nuclei_rule_family("sqli-test", "SQL Injection", []) == "vuln"
    
    def test_misconfig_family(self):
        assert nuclei_rule_family("default-login-admin", "Default Login", []) == "misconfig"
    
    def test_exposure_family(self):
        assert nuclei_rule_family("admin-panel-exposed", "Admin Panel Exposed", []) == "exposure"
    
    def test_detect_family(self):
        assert nuclei_rule_family("tech-detect-php", "PHP Detection", []) == "detect"
    
    def test_info_default(self):
        assert nuclei_rule_family("some-unknown", "Unknown Finding", []) == "info"


class TestNucleiGroupingScope:
    """Test nuclei grouping scope."""
    
    def test_default_host_level(self):
        """Most nuclei findings should group at host level."""
        assert group_scope_for_nuclei("mongodb-detect-mongobleed", "MongoBleed", "vuln") == "host"
    
    def test_param_level_for_sqli(self):
        """SQL injection findings should group at param level."""
        assert group_scope_for_nuclei("sqli-test", "SQL Injection in parameter", "vuln") == "param"


class TestNucleiFindingGrouping:
    """Test that nuclei findings with same template_id collapse into one finding."""
    
    def _make_nuclei_finding(self, template_id: str, name: str, severity: str, 
                              matched_at: str, tags: list = None):
        """Create a normalized nuclei finding dict."""
        return {
            "tool": "nuclei",
            "title": name,
            "severity": severity,
            "description": f"Detected by template {template_id}",
            "template_id": template_id,
            "url": matched_at,
            "categories": tags or [],
            "evidence": f"Matched at: {matched_at}",
            "http_method": None,
            "parameter": None,
            "cve_id": None,
            "cwe_id": None,
            "cvss_score": None,
            "raw_data": "{}",
        }
    
    def test_same_template_same_host_produces_same_key(self):
        """
        5 nuclei JSONL lines with same template_id and same host
        should produce the same finding_key => 1 canonical finding.
        """
        findings = [
            self._make_nuclei_finding(
                "mongodb-detect-mongobleed",
                "MongoDB Server - Information Disclosure (MongoBleed)",
                "high",
                f"pentest-ground.com:4280/path{i}"
            )
            for i in range(5)
        ]
        
        keys = set()
        for f in findings:
            canonical, instance = normalize_and_group_finding(f, "scan-1", "proj-1")
            keys.add(canonical["finding_key"])
        
        assert len(keys) == 1, f"Expected 1 unique key, got {len(keys)}: {keys}"
    
    def test_different_templates_produce_different_keys(self):
        """Different template_ids should produce different finding_keys."""
        f1 = self._make_nuclei_finding(
            "mongodb-detect-mongobleed", "MongoBleed", "high",
            "pentest-ground.com:4280"
        )
        f2 = self._make_nuclei_finding(
            "magmi-csrf", "MAGMI CSRF", "medium",
            "pentest-ground.com:4280/magmi"
        )
        
        canonical1, _ = normalize_and_group_finding(f1, "scan-1", "proj-1")
        canonical2, _ = normalize_and_group_finding(f2, "scan-1", "proj-1")
        
        assert canonical1["finding_key"] != canonical2["finding_key"]
    
    def test_instance_contains_url(self):
        """Each instance should contain the specific matched-at URL."""
        f = self._make_nuclei_finding(
            "mongodb-detect-mongobleed", "MongoBleed", "high",
            "pentest-ground.com:4280"
        )
        
        canonical, instance = normalize_and_group_finding(f, "scan-1", "proj-1")
        
        assert instance["url"] == "pentest-ground.com:4280"
        assert canonical["tool"] == "nuclei"
        assert canonical["template_id"] == "mongodb-detect-mongobleed"
    
    def test_severity_preserved_in_canonical(self):
        """Severity should be preserved (not downgraded to INFO) in canonical finding."""
        f = self._make_nuclei_finding(
            "mongodb-detect-mongobleed", "MongoBleed", "high",
            "pentest-ground.com:4280"
        )
        
        canonical, _ = normalize_and_group_finding(f, "scan-1", "proj-1")
        
        assert canonical["severity"] == Severity.HIGH
    
    def test_mongobleed_spam_regression(self):
        """
        Regression test: MongoBleed appearing 10 times with same location 
        should produce 1 canonical finding with 10 instances.
        """
        findings = [
            self._make_nuclei_finding(
                "mongodb-detect-mongobleed",
                "MongoDB Server - Information Disclosure (MongoBleed)",
                "high",
                "pentest-ground.com:4280",
            )
            for _ in range(10)
        ]
        
        # All should produce the same finding_key
        keys = set()
        instances = []
        for f in findings:
            canonical, instance = normalize_and_group_finding(f, "scan-1", "proj-1")
            keys.add(canonical["finding_key"])
            instances.append(instance)
        
        # 1 canonical finding
        assert len(keys) == 1
        # 10 instances
        assert len(instances) == 10
        # All instances have the same URL
        assert all(i["url"] == "pentest-ground.com:4280" for i in instances)
    
    def test_different_hosts_produce_different_keys(self):
        """Same template on different hosts should produce different findings."""
        f1 = self._make_nuclei_finding(
            "mongodb-detect-mongobleed", "MongoBleed", "high",
            "http://host1.com:4280"
        )
        f2 = self._make_nuclei_finding(
            "mongodb-detect-mongobleed", "MongoBleed", "high",
            "http://host2.com:4280"
        )
        
        canonical1, _ = normalize_and_group_finding(f1, "scan-1", "proj-1")
        canonical2, _ = normalize_and_group_finding(f2, "scan-1", "proj-1")
        
        assert canonical1["finding_key"] != canonical2["finding_key"]


class TestDalfoxGrouping:
    """Test that Dalfox findings also group correctly."""
    
    def test_same_xss_type_groups(self):
        """Same XSS finding at different URLs should group."""
        f1 = {
            "tool": "dalfox",
            "title": "Reflected XSS",
            "severity": "high",
            "url": "http://target.com/page1?q=test",
            "parameter": "q",
            "raw_data": "{}",
        }
        f2 = {
            "tool": "dalfox",
            "title": "Reflected XSS",
            "severity": "high",
            "url": "http://target.com/page2?q=test",
            "parameter": "q",
            "raw_data": "{}",
        }
        
        canonical1, _ = normalize_and_group_finding(f1, "scan-1", "proj-1")
        canonical2, _ = normalize_and_group_finding(f2, "scan-1", "proj-1")
        
        # Same XSS type with same param on same host should group
        assert canonical1["finding_key"] == canonical2["finding_key"]

