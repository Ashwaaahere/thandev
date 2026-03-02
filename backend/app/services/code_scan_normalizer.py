"""
Normalize raw code scan artifacts (Semgrep, Gitleaks, OSV, Trivy, SBOM) into a unified
finding dict shape. Used on read; raw artifacts are stored as-is.
Never log or expose secret values; gitleaks evidence is always redacted.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _fingerprint(parts: List[Any]) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _norm_severity(s: Any) -> str:
    if not s:
        return "medium"
    lower = str(s).lower()
    if lower in ("critical", "error"):
        return "critical"
    if lower == "high":
        return "high"
    if lower in ("medium", "warning"):
        return "medium"
    if lower in ("low", "note"):
        return "low"
    if lower == "info":
        return "info"
    return "medium"


def _loc(file_path: Optional[str] = None, start_line: Optional[int] = None, end_line: Optional[int] = None,
         start_col: Optional[int] = None, end_col: Optional[int] = None, manifest_path: Optional[str] = None) -> Dict[str, Any]:
    return {"file_path": file_path, "start_line": start_line, "end_line": end_line, "start_col": start_col, "end_col": end_col, "manifest_path": manifest_path}


def _ev(snippet: Any = None, snippet_start_line: Optional[int] = None, raw: Any = None) -> Dict[str, Any]:
    return {"snippet": snippet, "snippet_start_line": snippet_start_line, "raw": raw}


def _ident(cve: Optional[List[str]] = None, ghsa: Optional[List[str]] = None, osv: Optional[List[str]] = None, rule_id: Optional[str] = None) -> Dict[str, Any]:
    return {"cve": cve or [], "ghsa": ghsa or [], "osv": osv or [], "rule_id": rule_id}


def _dep(package: Optional[str] = None, ecosystem: Optional[str] = None, installed_version: Optional[str] = None,
         fixed_version: Optional[str] = None, dependency_chain: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"package": package, "ecosystem": ecosystem, "installed_version": installed_version, "fixed_version": fixed_version, "dependency_chain": dependency_chain}


def _rem(recommendation: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
    return {"recommendation": recommendation, "command": command}


def normalize_semgrep(semgrep_json: Any, scan_id: str) -> List[Dict[str, Any]]:
    """Convert Semgrep JSON to list of normalized finding dicts."""
    findings: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    if isinstance(semgrep_json, list):
        results = semgrep_json
    elif isinstance(semgrep_json, dict):
        results = semgrep_json.get("results") or semgrep_json.get("matches") or []
    for r in results:
        if not isinstance(r, dict):
            continue
        path = r.get("path") or r.get("file") or ""
        start = r.get("start") or {}
        end = r.get("end") or {}
        start_line = start.get("line") if isinstance(start, dict) else r.get("line")
        end_line = end.get("line") if isinstance(end, dict) else start_line
        start_col = start.get("col") if isinstance(start, dict) else None
        end_col = end.get("col") if isinstance(end, dict) else None
        rule_id = str(r.get("check_id") or r.get("rule_id") or "")
        extra = r.get("extra") or {}
        if isinstance(extra, dict):
            message = extra.get("message") or r.get("message") or rule_id or "Finding"
            severity = _norm_severity(extra.get("severity") or (extra.get("metadata") or {}).get("severity"))
        else:
            message = str(rule_id or "Finding")
            severity = "medium"
        snippet = None
        if isinstance(extra, dict) and "lines" in extra:
            snippet = extra.get("lines")
        refs: List[str] = []
        if isinstance(extra, dict):
            meta = extra.get("metadata") or {}
            if isinstance(meta, dict) and meta.get("url"):
                refs.append(str(meta["url"]))
        fid = _fingerprint(["semgrep", rule_id, path, start_line, end_line])
        findings.append({
            "id": fid,
            "scan_id": scan_id,
            "source_tool": "semgrep",
            "category": "sast",
            "severity": severity,
            "confidence": "high",
            "title": str(message)[:500],
            "summary": str(message)[:2000] if message else None,
            "identifiers": _ident(rule_id=rule_id or None),
            "location": _loc(path or None, int(start_line) if start_line is not None else None, int(end_line) if end_line is not None else None, int(start_col) if start_col is not None else None, int(end_col) if end_col is not None else None, None),
            "dependency": _dep(),
            "remediation": _rem(),
            "references": refs,
            "evidence": _ev(snippet, int(start_line) if start_line is not None else None, {"check_id": rule_id, "path": path, "start": r.get("start"), "end": r.get("end")} if r else None),
        })
    return findings


def _redact_secret(value: Any) -> str:
    """Never expose secret content. Return redacted preview only."""
    if value is None:
        return "redacted"
    s = str(value).strip()
    if not s:
        return "redacted"
    if len(s) <= 4:
        return "****"
    return f"****{s[-4:]}"  # last 4 chars only, e.g. last4 of token


def normalize_gitleaks(gitleaks_json: Any, scan_id: str) -> List[Dict[str, Any]]:
    """Convert Gitleaks JSON (or SARIF) to normalized findings. Evidence is always redacted."""
    findings: List[Dict[str, Any]] = []
    if isinstance(gitleaks_json, list):
        for item in gitleaks_json:
            if not isinstance(item, dict):
                continue
            rule_id = str(item.get("RuleID") or item.get("ruleID") or item.get("SecretType") or "secret")
            file_path = str(item.get("File") or item.get("file") or item.get("Match") or "")
            line = item.get("Line") or item.get("line") or 0
            desc = str(item.get("Description") or item.get("description") or item.get("Message") or "Secret detected")
            # Never use item.get("Secret") or raw value in evidence
            snippet_redacted = _redact_secret(item.get("Match") or item.get("Secret") or item.get("Value"))
            fid = _fingerprint(["gitleaks", rule_id, file_path, line])
            findings.append({
                "id": fid,
                "scan_id": scan_id,
                "source_tool": "gitleaks",
                "category": "secret",
                "severity": "high",
                "confidence": "high",
                "title": f"Secret detected: {rule_id}",
                "summary": desc[:2000] if desc else None,
                "identifiers": _ident(rule_id=rule_id),
                "location": _loc(file_path or None, int(line) if line else None, None, None, None, None),
                "dependency": _dep(),
                "remediation": _rem(recommendation="Rotate the exposed secret and remove it from history."),
                "references": [],
                "evidence": _ev(snippet_redacted, int(line) if line else None, None),
            })
        return findings
    # SARIF-style
    runs = (gitleaks_json or {}).get("runs") or []
    for run in runs:
        results = run.get("results") or []
        for res in results:
            if not isinstance(res, dict):
                continue
            rule_id = str(res.get("ruleId") or "secret")
            locs = res.get("locations") or []
            file_path = ""
            line = None
            if locs and isinstance(locs[0], dict):
                pl = locs[0].get("physicalLocation") or {}
                art = pl.get("artifactLocation") or {}
                file_path = str(art.get("uri") or "")
                reg = pl.get("region") or {}
                line = reg.get("startLine")
            msg = res.get("message") or {}
            desc = (msg.get("text") if isinstance(msg, dict) else str(msg)) or "Secret detected"
            fid = _fingerprint(["gitleaks", rule_id, file_path, line])
            findings.append({
                "id": fid,
                "scan_id": scan_id,
                "source_tool": "gitleaks",
                "category": "secret",
                "severity": "high",
                "confidence": "high",
                "title": f"Secret detected: {rule_id}",
                "summary": str(desc)[:2000],
                "identifiers": _ident(rule_id=rule_id),
                "location": _loc(file_path or None, int(line) if line is not None else None, None, None, None, None),
                "dependency": _dep(),
                "remediation": _rem(recommendation="Rotate the exposed secret and remove it from history."),
                "references": [],
                "evidence": _ev("redacted", int(line) if line is not None else None, None),
            })
    return findings


def normalize_osv(osv_json: Any, scan_id: str) -> List[Dict[str, Any]]:
    """Convert OSV scanner output to normalized dependency findings."""
    findings: List[Dict[str, Any]] = []
    pkg_name = str((osv_json or {}).get("name") or (osv_json or {}).get("package") or "")
    vulns: List[Dict] = []
    if isinstance(osv_json, dict):
        vulns = osv_json.get("vulns") or osv_json.get("vulnerabilities") or []
        if not vulns and isinstance(osv_json.get("results"), list):
            for r in osv_json["results"]:
                vulns.extend((r or {}).get("vulns") or [])
    for v in vulns:
        if not isinstance(v, dict):
            continue
        vuln_id = str(v.get("id") or (v.get("aliases") or [None])[0] or "")
        severity = _norm_severity(v.get("severity") or (v.get("database_specific") or {}).get("severity"))
        refs = list(v.get("references") or [])
        ref_urls = [r.get("url") for r in refs if isinstance(r, dict) and r.get("url")]
        cve = [a for a in (v.get("aliases") or []) if isinstance(a, str) and a.startswith("CVE-")]
        ghsa = [a for a in (v.get("aliases") or []) if isinstance(a, str) and "GHSA-" in a]
        osv_ids = [vuln_id] if vuln_id.startswith("GHSA-") or vuln_id.startswith("OSV-") or "CVE-" in vuln_id else [vuln_id]
        fixed_ver = (v.get("database_specific") or {}).get("fixed_version")
        if not fixed_ver and isinstance(v.get("affected"), list) and v["affected"]:
            aff = v["affected"][0] or {}
            for r in (aff.get("ranges") or [])[:1]:
                for e in (r.get("events") or [])[:1]:
                    if e.get("fixed"):
                        fixed_ver = e["fixed"]
                        break
        fid = _fingerprint(["osv", pkg_name, vuln_id])
        findings.append({
            "id": fid,
            "scan_id": scan_id,
            "source_tool": "osv",
            "category": "dependency",
            "severity": severity,
            "confidence": "medium",
            "title": f"{pkg_name}: {vuln_id}" if pkg_name else vuln_id,
            "summary": (v.get("summary") or v.get("details")) and str((v.get("summary") or v.get("details")))[:2000] or None,
            "identifiers": _ident(cve=cve[:20], ghsa=ghsa[:20], osv=osv_ids[:20]),
            "location": _loc(),
            "dependency": _dep(package=pkg_name or None, fixed_version=str(fixed_ver) if fixed_ver else None),
            "remediation": _rem(recommendation=f"Upgrade to fixed version: {fixed_ver}" if fixed_ver else "Check advisory for remediation.", command=f"npm update {pkg_name}" if pkg_name else None),
            "references": ref_urls[:20],
            "evidence": _ev(raw={"id": vuln_id, "package": pkg_name}),
        })
    return findings


def normalize_trivy(trivy_json: Any, scan_id: str) -> List[Dict[str, Any]]:
    """Convert Trivy JSON (Results[].Vulnerabilities / Misconfigurations) to normalized findings."""
    findings: List[Dict[str, Any]] = []
    results: List[Dict] = []
    if isinstance(trivy_json, list):
        results = trivy_json
    elif isinstance(trivy_json, dict):
        results = trivy_json.get("Results") or []
    for res in results:
        if not isinstance(res, dict):
            continue
        target = str(res.get("Target") or "")
        vulns = res.get("Vulnerabilities") or res.get("vulnerabilities") or []
        for v in vulns:
            if not isinstance(v, dict):
                continue
            cve_id = str(v.get("VulnerabilityID") or v.get("vulnerabilityID") or v.get("CVE") or "")
            pkg = str(v.get("PkgName") or v.get("pkgName") or "")
            inst = str(v.get("InstalledVersion") or v.get("installedVersion") or "")
            fixed = str(v.get("FixedVersion") or v.get("fixedVersion") or "") or None
            severity = _norm_severity(v.get("Severity") or v.get("severity"))
            refs = list(v.get("References") or v.get("references") or [])
            ref_urls = [r if isinstance(r, str) else r.get("url") for r in refs if r and (isinstance(r, str) or r.get("url"))]
            fid = _fingerprint(["trivy", pkg, inst, cve_id, target])
            findings.append({
                "id": fid,
                "scan_id": scan_id,
                "source_tool": "trivy",
                "category": "dependency",
                "severity": severity,
                "confidence": "high",
                "title": f"{pkg}: {cve_id}" if pkg else cve_id,
                "summary": (v.get("Title") or v.get("Description")) and str((v.get("Title") or v.get("Description")))[:2000] or None,
                "identifiers": _ident(cve=[cve_id] if cve_id.startswith("CVE-") else [], ghsa=[cve_id] if "GHSA-" in cve_id else [], rule_id=cve_id or None),
                "location": _loc(manifest_path=target or None),
                "dependency": _dep(package=pkg or None, installed_version=inst or None, fixed_version=fixed),
                "remediation": _rem(recommendation=f"Upgrade {pkg} to {fixed}" if fixed else "Check advisory for fix.", command=f"npm update {pkg}" if pkg else None),
                "references": ref_urls[:20],
                "evidence": _ev(raw={"VulnerabilityID": cve_id, "PkgName": pkg, "InstalledVersion": inst, "FixedVersion": v.get("FixedVersion")}),
            })
        misconfigs = res.get("Misconfigurations") or res.get("misconfigurations") or []
        for m in misconfigs:
            if not isinstance(m, dict):
                continue
            mid = str(m.get("ID") or m.get("AVDID") or "")
            title = str(m.get("Title") or m.get("Message") or mid)
            severity = _norm_severity(m.get("Severity") or m.get("severity"))
            resolution = (m.get("Resolution") or m.get("resolution")) or None
            fid = _fingerprint(["trivy-misconf", mid, target, m.get("StartLine"), m.get("EndLine")])
            sl = int(m["StartLine"]) if m.get("StartLine") is not None else None
            el = int(m["EndLine"]) if m.get("EndLine") is not None else None
            findings.append({
                "id": fid,
                "scan_id": scan_id,
                "source_tool": "trivy",
                "category": "misconfig",
                "severity": severity,
                "confidence": "medium",
                "title": title[:500],
                "summary": (m.get("Description") or resolution) and str(m.get("Description") or resolution)[:2000] or None,
                "identifiers": _ident(rule_id=mid or None),
                "location": _loc(file_path=target or None, start_line=sl, end_line=el),
                "dependency": _dep(),
                "remediation": _rem(recommendation=resolution),
                "references": [],
                "evidence": _ev(snippet_start_line=sl, raw={"ID": mid, "Title": title}),
            })
    return findings


def get_sbom_components(sbom_json: Any) -> List[Dict[str, Any]]:
    """Extract flat list of components from SBOM (CycloneDX or SPDX-style). For GET /sbom."""
    components: List[Dict[str, Any]] = []
    if not sbom_json:
        return components
    if isinstance(sbom_json, dict):
        arr = sbom_json.get("components") or sbom_json.get("Components") or sbom_json.get("packages") or []
    elif isinstance(sbom_json, list):
        arr = sbom_json
    else:
        return components
    for c in arr:
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("Name") or ""
        version = c.get("version") or c.get("Version") or ""
        purl = c.get("purl") or c.get("purl") or ""
        license_val = c.get("license") or c.get("License") or ""
        if isinstance(license_val, dict):
            license_val = license_val.get("id") or license_val.get("name") or ""
        components.append({
            "name": str(name),
            "version": str(version),
            "purl": str(purl),
            "license": str(license_val),
        })
    return components


def normalize_all_findings(artifacts: Dict[str, Any], scan_id: str) -> List[Dict[str, Any]]:
    """Run all normalizers on artifacts and return combined list. Counts derived from this."""
    out: List[Dict[str, Any]] = []
    if not artifacts:
        return out
    if artifacts.get("semgrep"):
        out.extend(normalize_semgrep(artifacts["semgrep"], scan_id))
    if artifacts.get("gitleaks"):
        out.extend(normalize_gitleaks(artifacts["gitleaks"], scan_id))
    if artifacts.get("osv"):
        out.extend(normalize_osv(artifacts["osv"], scan_id))
    if artifacts.get("trivy"):
        out.extend(normalize_trivy(artifacts["trivy"], scan_id))
    return out


def get_counts(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compute counts from normalized findings for API response."""
    counts = {"total": len(findings), "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "secrets": 0}
    for f in findings:
        cat = (f.get("category") or "").lower()
        sev = (f.get("severity") or "medium").lower()
        if cat == "secret":
            counts["secrets"] += 1
        if sev == "critical":
            counts["critical"] += 1
        elif sev == "high":
            counts["high"] += 1
        elif sev == "medium":
            counts["medium"] += 1
        elif sev == "low":
            counts["low"] += 1
        elif sev == "info":
            counts["info"] += 1
    return counts
