# improved normalize_and_upsert for ingest_nvd.py
import hashlib
from datetime import datetime

def _find_cvss_recursive(obj):
    """Recursively search for a numeric 'baseScore' or 'baseScore' keys anywhere."""
    if isinstance(obj, dict):
        if "baseScore" in obj and obj["baseScore"] is not None:
            try:
                return float(obj["baseScore"])
            except Exception:
                pass
        for v in obj.values():
            res = _find_cvss_recursive(v)
            if res is not None:
                return res
    elif isinstance(obj, list):
        for el in obj:
            res = _find_cvss_recursive(el)
            if res is not None:
                return res
    return None

def _make_external_id(cve_id, title, pub_date):
    if cve_id:
        return cve_id
    s = (title or "") + "|" + (pub_date.isoformat() if getattr(pub_date, "isoformat", None) else str(pub_date))
    return "EXT-" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def normalize_and_upsert(cve_item, session):
    cve = cve_item.get("cve") or {}
    cve_id = cve.get("id") or cve.get("CVE_data_meta", {}).get("ID") or None

    # title / description
    title = cve.get("title") or None
    if not title:
        descs = cve.get("descriptions") or []
        if isinstance(descs, list) and descs:
            for d in descs:
                if d.get("lang", "en").lower().startswith("en") and d.get("value"):
                    title = d.get("value")
                    break

    description = None
    descs = cve.get("descriptions") or []
    if isinstance(descs, list):
        for d in descs:
            if d.get("lang", "en") and d.get("value"):
                description = d.get("value")
                break

    # published date - try several fields
    pub_date = None
    for key in ("published", "publishedDate", "publishedUtc", "publishedTimestamp"):
        try:
            val = cve_item.get(key) or cve_item.get("published")
            if val:
                pub_date = datetime.fromisoformat(val.replace("Z", "+00:00"))
                break
        except Exception:
            pub_date = None

    # fallback: look under 'vulnPublished' etc.
    if pub_date is None:
        try:
            candidate = cve_item.get("vulnerabilities", [{}])[0].get("published") if cve_item.get("vulnerabilities") else None
            if candidate:
                pub_date = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except Exception:
            pub_date = None

    # find cvss
    cvss_v3 = None
    try:
        cvss_v3 = _find_cvss_recursive(cve_item.get("metrics") or cve_item)
        if cvss_v3 is None:
            # some structures use cvssV3 key
            cvss_v3 = cve_item.get("cvssV3", {}).get("baseScore") or cve_item.get("cvssV3")
    except Exception:
        cvss_v3 = None

    def severity_from_score(score):
        try:
            s = float(score)
        except Exception:
            return "none"
        if s >= 9.0: return "critical"
        if s >= 7.0: return "high"
        if s >= 4.0: return "medium"
        if s > 0: return "low"
        return "none"
    severity = severity_from_score(cvss_v3)

    # references dedupe
    references = []
    seen = set()
    refs = cve.get("references") or []
    if isinstance(refs, list):
        for r in refs:
            url = r.get("url") if isinstance(r, dict) else (r if isinstance(r, str) else None)
            if not url:
                continue
            # normalize trivial trailing fragments
            norm = url.strip()
            if norm not in seen:
                seen.add(norm)
                references.append({"url": norm, "source": r.get("source") if isinstance(r, dict) else "reference"})

    # external id for non-cve dedupe
    external_id = _make_external_id(cve_id, title or "", pub_date)

    # provenance
    prov = {
        "source": "nvd",
        "raw_id": cve_item.get("id") or cve_id,
        "fetched_at": datetime.utcnow().isoformat(),
        "external_id": external_id
    }

    # upsert by cve_id
    existing = None
    if cve_id:
        existing = session.query(Exploit).filter(Exploit.cve_id == cve_id).one_or_none()

    if existing:
        existing.title = (title or existing.title)[:512]
        existing.description = (description or existing.description or "")[:2000]
        existing.cvss_v3 = float(cvss_v3) if cvss_v3 is not None else existing.cvss_v3
        existing.severity = severity
        existing.published_at = pub_date or existing.published_at
        existing.references = references or existing.references
        existing.source_tags = list(dict.fromkeys((existing.source_tags or []) + ["nvd"]))
        existing.provenance = (existing.provenance or {})
        existing.provenance.update(prov)
        existing.updated_at = datetime.utcnow()
        LOG.info("Updated %s", cve_id)
    else:
        obj = Exploit(
            cve_id=cve_id,
            title=(title or cve_id or external_id)[:512],
            description=(description or "")[:2000],
            cvss_v3=float(cvss_v3) if cvss_v3 is not None else None,
            severity=severity,
            published_at=pub_date,
            references=references,
            source_tags=["nvd"],
            provenance=prov
        )
        session.add(obj)
        LOG.info("Inserted %s", cve_id or external_id)
