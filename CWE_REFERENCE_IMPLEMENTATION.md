# CWE Reference Implementation

## Summary

Implemented clickable CWE references for findings with a details drawer and external links.

## Backend Implementation

### 1. CWE Dataset (`backend/app/data/cwe_min.json`)
- Contains 18 common CWEs with:
  - Title
  - Summary
  - Why it matters
  - Common impacts
  - Basic mitigations
- Covers top CWEs: 79 (XSS), 89 (SQL Injection), 1021 (Clickjacking), 319 (Cleartext Transmission), etc.

### 2. Reference API (`backend/app/api/reference.py`)
- **Endpoint**: `GET /api/v1/reference/cwe/{cwe_id}`
- **Features**:
  - Validates CWE ID (1-9999 range)
  - Handles "CWE-1021" or "1021" formats
  - Returns local dataset if available
  - Falls back gracefully with external links only
  - In-memory caching (loads once at startup)
- **Response**:
  ```json
  {
    "id": 1021,
    "title": "Improper Restriction of Rendered UI Layers or Frames",
    "summary": "...",
    "why_it_matters": "...",
    "common_impacts": [...],
    "basic_mitigations": [...],
    "links": {
      "mitre": "https://cwe.mitre.org/data/definitions/1021.html",
      "nvd_search": "https://nvd.nist.gov/vuln/search/results?query=CWE-1021"
    }
  }
  ```

### 3. Security
- ✅ Validates CWE ID is numeric and in range (1-9999)
- ✅ No SSRF (no external fetching)
- ✅ No dynamic scraping (uses local dataset)

## Frontend Implementation

### 1. CWE Badge (`frontend/components/Dashboard/FindingDetailsDrawer.tsx`)
- CWE badge is clickable in References section
- Styled as pill badge with brand color border
- Opens CWE drawer on click

### 2. CWE Drawer (`frontend/components/Dashboard/CWEDrawer.tsx`)
- Right-side drawer (consistent with finding details drawer)
- Fetches CWE data from API on open
- Displays:
  - CWE ID and title
  - About this weakness (summary)
  - Why it matters
  - Common impacts (bullets)
  - Basic mitigations (bullets)
  - External links (MITRE CWE, NVD Search)
- Handles missing data gracefully
- Dark UI consistent with dashboard

### 3. CVE Links
- CVE badges are clickable and link directly to NVD CVE page
- Opens in new tab with `noopener noreferrer`

## Files Created/Modified

### Backend
- ✅ `backend/app/data/cwe_min.json` - CWE dataset (18 entries)
- ✅ `backend/app/api/reference.py` - Reference API endpoint
- ✅ `backend/app/main.py` - Added reference router
- ✅ `backend/tests/test_cwe_reference.py` - Tests

### Frontend
- ✅ `frontend/components/Dashboard/CWEDrawer.tsx` - CWE drawer component
- ✅ `frontend/components/Dashboard/FindingDetailsDrawer.tsx` - Updated References section

## Testing

### Backend Tests
```bash
pytest backend/tests/test_cwe_reference.py -v
```

### Manual Testing
1. Open a finding with `cwe_id` (e.g., from ZAP scan)
2. Click the CWE badge in References section
3. Verify drawer opens with CWE information
4. Test external links (MITRE, NVD)
5. Test with CWE not in dataset (should show links only)

## Acceptance Criteria

✅ **CWE badge shows in References section**
- Badge displays as "CWE-XXXX" with clickable styling

✅ **Drawer opens on click**
- Right-side drawer opens
- Fetches CWE data from API
- Displays information sections

✅ **External links work**
- MITRE CWE link opens correct page
- NVD search link opens with CWE query

✅ **Unknown CWE handled gracefully**
- Shows "No local details yet" message
- Still provides external links

✅ **CVE badges are clickable**
- Link directly to NVD CVE page
- Opens in new tab

## Next Steps

1. **Expand CWE dataset**: Add more CWEs as needed (currently 18)
2. **Add WASC support**: Similar drawer for WASC IDs
3. **Add caching**: Consider client-side caching of CWE data
4. **Add analytics**: Track which CWEs are viewed most

