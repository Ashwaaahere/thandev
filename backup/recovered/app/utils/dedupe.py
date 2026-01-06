# backend/app/utils/dedupe.py  (or inline in your exploits route file)
import re
from typing import Any, Dict, Iterable, List

_normalize_re_non_alnum = re.compile(r"[^a-z0-9\s]")
_normalize_re_spaces = re.compile(r"\s+")

def normalize_title_key(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    t = _normalize_re_non_alnum.sub(" ", t)
    t = _normalize_re_spaces.sub(" ", t)
    return t.strip()

def canonical_key_for_item(item: Dict[str, Any]) -> str:
    """
    item is expected to be a dict-like object (the serialized row)
    Keys checked (in order): cve_id, provenance.external_id (or provenance['external_id']),
    normalized title, id.
    """
    # prefer CVE
    cve = item.get("cve_id")
    if cve:
        return f"cve:{str(cve).strip().lower()}"

    prov = item.get("provenance")
    if prov:
        # provenance might be a dict or JSON string; handle dicts primarily
        if isinstance(prov, dict):
            ext = prov.get("external_id") or prov.get("externalId") or prov.get("id")
            if ext:
                return f"ext:{str(ext).strip().lower()}"
    # fallback to normalized title
    title = item.get("title") or ""
    nt = normalize_title_key(title)
    if nt:
        return f"title:{nt}"
    # last fallback: id
    return f"id:{str(item.get('id'))}"

def dedupe_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Returns a deduped-list preserving the first-seen unique key by default.
    If you prefer the newest item (by published_at/created_at) for each key,
    pass items sorted by newest first or change insertion logic below.
    """
    seen = {}
    deduped = []
    for it in items:
        key = canonical_key_for_item(it)
        if key in seen:
            # already have an item for this canonical content key -> skip
            continue
        seen[key] = True
        deduped.append(it)
    return deduped
