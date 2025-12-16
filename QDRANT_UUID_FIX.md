# Qdrant UUID Fix

## Issue
Qdrant was rejecting point IDs with error:
```
value finding_8c9f3275-cda3-4996-b04a-6e947bc83271 is not a valid point ID, 
valid values are either an unsigned integer or a UUID
```

## Root Cause
The code was generating IDs with prefixes like `finding_8c9f3275-cda3-4996-b04a-6e947bc83271`, but Qdrant requires:
- Pure UUID objects (not strings with prefixes)
- Or unsigned integers

## Fix Applied

### 1. `app/rag/ingestion.py`
- **Finding documents**: Parse `finding_id` as UUID directly (it's already a UUID string)
- **Artifact documents**: Generate UUID5 from `artifact_{artifact_id}`
- **Tech fingerprint documents**: Generate UUID5 from `tech_{target}`
- **CVE template documents**: Generate UUID5 from `cve_{cve_id}`
- All document IDs are now stored as UUID objects (not strings)

### 2. `app/rag/store.py`
- Enhanced UUID handling in `upsert_documents()`:
  - Accepts UUID objects directly
  - Parses UUID strings
  - Generates UUID5 for invalid strings
  - Supports integer IDs
  - Handles None values by generating UUID4

## Testing

Run the indexing script:
```bash
cd services/thandev-brain
source venv/bin/activate
python scripts/index_findings.py --limit 1000
```

The script should now successfully index findings into Qdrant without UUID format errors.




