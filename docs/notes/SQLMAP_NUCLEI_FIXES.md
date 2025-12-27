# SQLMap and Nuclei Fixes

## Summary
Fixed SQLMap SQL injection detection and Nuclei duplicate findings issues.

## Changes Made

### 1. Enhanced SQLMap Detection Parameters
**File**: `backend/app/services/tools.py`

**Changes**:
- Increased `--level` from 3 to 5 (maximum comprehensive tests)
- Increased `--timeout` from 30 to 60 seconds
- Increased `--time-sec` from 5 to 10 seconds (better time-based detection)
- Increased `--crawl` from 1 to 2 levels
- Increased verbosity from `-v 2` to `-v 3` (maximum detail)
- Added `--tamper=space2comment,charencode` for better evasion
- Added `--dbms=all` to test all database types
- Added `--no-cast` and `--no-escape` for better detection

**Result**: SQLMap will now be much more thorough in detecting SQL injection, especially on login forms.

### 2. Fixed SQLMap Parsing in Runner
**File**: `services/thandev-runner/app/tasks.py`

**Changes**:
- Now parses both stdout AND output directory
- Deduplicates findings from both sources
- Better logging for debugging

**Result**: SQLMap findings are now properly extracted from both stdout and log files.

### 3. Enhanced SQLMap Output Parsing
**File**: `backend/app/services/findings_ingestor.py`

**Changes**:
- `parse_sqlmap_output` now also parses log files in subdirectories
- Checks target-specific directories (sqlmap creates `<target_domain>/log`)

**Result**: More comprehensive parsing of SQLMap results.

### 4. Added Nuclei Deduplication
**File**: `backend/app/services/findings_ingestor.py`

**Changes**:
- Added deduplication based on `template-id + URL` combination
- Normalizes URLs (removes query params, trailing slashes) to avoid false duplicates
- Skips duplicate findings with debug logging

**Result**: No more duplicate Nuclei findings for the same template on the same URL.

## Testing

### Test SQLMap Detection
1. Run an Advanced-level scan on `http://testphp.vulnweb.com/login.php`
2. SQLMap should detect SQL injection in the login form
3. Findings should appear in the frontend with CRITICAL severity

### Test Nuclei Deduplication
1. Run any scan with Nuclei
2. Check that duplicate findings (same template, same URL) are not shown
3. Different URLs or different templates should still show separate findings

## Expected Results

### SQLMap
- Should detect SQL injection on `http://testphp.vulnweb.com/login.php`
- Finding title: "SQL Injection (technique) on parameter 'uname'"
- Severity: CRITICAL
- Should show in frontend under findings list

### Nuclei
- No duplicate findings for same template + URL
- Each unique finding shown once
- Better user experience with cleaner results

## Files Modified
1. `backend/app/services/tools.py` - Enhanced SQLMap parameters
2. `services/thandev-runner/app/tasks.py` - Fixed SQLMap parsing
3. `backend/app/services/findings_ingestor.py` - Enhanced parsing and deduplication


