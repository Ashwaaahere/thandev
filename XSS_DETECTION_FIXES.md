# XSS Detection Fixes - Nuclei & Dalfox

## Summary
Fixed critical configuration issues preventing Nuclei and Dalfox from detecting XSS vulnerabilities.

## Issues Found and Fixed

### 1. Nuclei Configuration Issues

#### Problem 1: Incorrect Tag Names
- **Issue**: `NUCLEI_PROFILE_TAGS` used `"cves"` (plural) but Nuclei templates use `"cve"` (singular)
- **Impact**: Templates with `cve` tag wouldn't match, reducing detection coverage
- **Fix**: Changed `"cves"` to `"cve"` in all profile definitions

#### Problem 2: Missing XSS Tag in Basic Level
- **Issue**: `basic_web` profile didn't include `"xss"` tag
- **Impact**: Basic scans wouldn't detect XSS vulnerabilities
- **Fix**: Added `"xss"` tag to `basic_web` profile

#### Problem 3: Missing Headless Tag
- **Issue**: `pro_web` and `advanced_web` profiles didn't include `"headless"` tag
- **Impact**: DOM-based XSS vulnerabilities wouldn't be detected
- **Fix**: Added `"headless"` tag to `pro_web` and `advanced_web` profiles

#### Problem 4: Fallback Tags Map Missing XSS
- **Issue**: Fallback `tags_map` didn't include `"xss"` tag for any level
- **Impact**: If profile lookup failed, XSS detection would be completely disabled
- **Fix**: Added `"xss"` tag to all levels in fallback `tags_map`:
  - Basic: `"cve,vulnerability,exposure,xss"`
  - Pro: `"cve,vulnerability,exposure,misconfig,xss,sqli,ssrf,ssti,xxe,lfi,rfi,path-traversal,cmdi,headless"`
  - Advanced: `"cve,vulnerability,exposure,misconfig,xss,sqli,ssrf,ssti,xxe,lfi,rfi,path-traversal,cmdi,idor,csrf,cors,headless,tech,ssl"`

### 2. Dalfox Configuration Enhancements

#### Problem 1: Missing Parameter Mining Options
- **Issue**: Only used `--mining-dict` and `--mining-dom`, missing `--mining-all`
- **Impact**: Some parameter discovery techniques weren't being used
- **Fix**: Added `--mining-all` flag to use all parameter mining techniques

#### Problem 2: Incomplete User-Agent
- **Issue**: User-Agent was truncated, might be flagged as bot
- **Impact**: Some applications might block or limit requests
- **Fix**: Updated to full realistic User-Agent string

#### Problem 3: Missing Context-Aware Analysis
- **Issue**: Advanced and Pro levels didn't use `--context-aware` flag
- **Impact**: Less intelligent payload selection
- **Fix**: Added `--context-aware` to Pro and Advanced levels (already present in backend version)

## Files Modified

1. **`services/thandev-runner/app/services/tools.py`**
   - Fixed `NUCLEI_PROFILE_TAGS` dictionary
   - Fixed fallback `tags_map` in `_run_nuclei()`
   - Enhanced Dalfox command in `_run_dalfox()`

2. **`backend/app/services/tools.py`**
   - Fixed `NUCLEI_PROFILE_TAGS` dictionary
   - Fixed fallback `tags_map` in `_run_nuclei()`
   - Enhanced Dalfox command in `_run_dalfox()`

## Verification

To verify the fixes work:

1. **Test Nuclei XSS Detection:**
   ```bash
   echo "http://localhost:5000/search?q=test" | nuclei -severity low,medium,high,critical -tags xss -jsonl -silent
   ```

2. **Test Dalfox XSS Detection:**
   ```bash
   echo "http://localhost:5000/search?q=test" | dalfox pipe --silence --format json --mining-dict --mining-dom --mining-all --only-poc g,v
   ```

3. **Test with Vulnerable App:**
   - Start the vulnerable app: `cd services/vulnerable-app && python app.py`
   - Run a scan on `http://localhost:5000`
   - Both tools should now detect XSS vulnerabilities

## Key Changes Summary

### Nuclei Tags (Before → After)

**basic_web:**
- Before: `["cves", "misconfig", "exposed-panels", "exposures"]`
- After: `["cve", "vulnerability", "exposure", "misconfig", "xss"]`

**pro_web:**
- Before: `["cves", "misconfig", "exposed-panels", "exposures", "xss", ...]`
- After: `["cve", "vulnerability", "exposure", "misconfig", "exposed-panels", "xss", ..., "headless"]`

**advanced_web:**
- Before: `["cves", "misconfig", "exposed-panels", "exposures", "xss", ...]`
- After: `["cve", "vulnerability", "exposure", "misconfig", "exposed-panels", "xss", ..., "headless", "tech", "ssl"]`

### Dalfox Flags (Enhanced)

**Added/Improved:**
- `--mining-all` - Use all parameter mining techniques
- Full User-Agent string for better stealth
- `--context-aware` for Pro/Advanced levels (runner version)
- Better logging for debugging

## Expected Results

After these fixes:
- ✅ Nuclei will detect XSS vulnerabilities at all scan levels (Basic, Pro, Advanced)
- ✅ Nuclei will detect DOM-based XSS using headless templates (Pro, Advanced)
- ✅ Dalfox will use all available parameter mining techniques
- ✅ Dalfox will have better payload selection with context-aware analysis
- ✅ Both tools will work even if profile lookup fails (fallback includes XSS)

## Next Steps

1. Restart the thandev-runner service to apply changes
2. Run a test scan on the vulnerable app
3. Verify XSS findings are detected and reported correctly
4. Monitor logs to ensure tools are using correct tags/flags

